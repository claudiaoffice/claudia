"""The page and the language of a docx: written into the first section and the document defaults, read back, and
changed in a file that has them (D454).

The page of a text is the first section: its paper (``w:pgSz``), how it lies, its margins (``w:pgMar``); whether pages
carry their number is a ``PAGE`` field in the footer of that section. The language is what the document defaults say
in ``w:lang``; a text with no language is one with ``zxx``, Word's "no proofing". A file measures in twentieths of a
point, so a size that is not a whole number of them (50 mpt) is written to the nearest one."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Twips
from lxml import etree

from claudia_core import LanguageError, PageSetup, normalize_language
from claudia_odf_io import NO_LANGUAGE

from ._layout import page_from_sizes, sides_of

_MPT_PER_TWIP = 50
_PAGE = " PAGE "


def _twips(mpt: int) -> Any:
    return Twips(round(mpt / _MPT_PER_TWIP))


def _mpt(length: Any) -> int | None:
    return None if length is None else int(length.twips) * _MPT_PER_TWIP


@dataclass
class Setup:
    """What a docx says of the page and the language; ``None`` for what it does not say (or says in a way the model
    cannot hold)."""

    page: PageSetup | None = None
    language: str | None = None
    #: A page the model cannot hold (a side that is no length, margins that leave no room).
    odd_page: bool = False


# -- the footer ------------------------------------------------------------------------------------------------------
def _page_fields(footer: Any) -> list[etree._Element]:
    """The elements of a footer that show the page number: simple fields, and the runs of complex ones."""
    found: list[etree._Element] = []
    for paragraph in footer.iter(qn("w:p")):
        group: list[etree._Element] = []
        inside = shows_page = False
        for child in paragraph:
            if child.tag == qn("w:fldSimple"):
                if "PAGE" in (child.get(qn("w:instr")) or "").upper():
                    found.append(child)
                continue
            if child.tag != qn("w:r"):
                continue
            kinds = [c.get(qn("w:fldCharType")) for c in child.findall(qn("w:fldChar"))]
            if "begin" in kinds:
                inside, shows_page, group = True, False, []
            if inside:
                group.append(child)
                shows_page = shows_page or any("PAGE" in (t.text or "").upper() for t in child.iter(qn("w:instrText")))
            if "end" in kinds and inside:
                inside = False
                if shows_page:
                    found.extend(group)
    return found


def _has_footer(section: Any) -> bool:
    return not section.footer.is_linked_to_previous


def _number_the_pages(section: Any) -> None:
    footer = section.footer
    footer.is_linked_to_previous = False
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), _PAGE)
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "1"
    run.append(text)
    field.append(run)
    paragraph._p.append(field)


# -- reading ---------------------------------------------------------------------------------------------------------
def _language_element(document: Any) -> etree._Element | None:
    return document.styles.element.find(
        qn("w:docDefaults") + "/" + qn("w:rPrDefault") + "/" + qn("w:rPr") + "/" + qn("w:lang")
    )


def read_setup(document: Any) -> Setup:
    """The page (of the first section) and the language of ``document``."""
    found = Setup()
    if (lang := _language_element(document)) is not None:
        found.language = _tag(lang.get(qn("w:val")))
    sections = document.sections
    if len(sections) == 0:
        return found
    section = sections[0]
    numbers = _has_footer(section) and bool(_page_fields(section.footer._element))
    page = page_from_sizes(
        _mpt(section.page_width),
        _mpt(section.page_height),
        (
            _mpt(section.top_margin),
            _mpt(section.right_margin),
            _mpt(section.bottom_margin),
            _mpt(section.left_margin),
        ),
        landscape=section.orientation == WD_ORIENT.LANDSCAPE,
        page_numbers=numbers,
    )
    found.page, found.odd_page = page, page is None
    return found


def _tag(tag: str | None) -> str | None:
    if not tag or tag.lower() in NO_LANGUAGE:
        return None
    try:
        return normalize_language(tag)
    except LanguageError:
        return None


# -- writing ---------------------------------------------------------------------------------------------------------
def write_page(document: Any, before: PageSetup | None, page: PageSetup) -> set[str]:
    """Make the first section of ``document`` have ``page`` where it differs from ``before`` (``None``: everywhere); the
    parts of the package that the writing made new or changed, besides the text."""
    section = document.sections[0]
    owned: set[str] = set()
    width, height = sides_of(page)
    if before is None or sides_of(before) != (width, height) or before.orientation != page.orientation:
        section.page_width, section.page_height = _twips(width), _twips(height)
        section.orientation = WD_ORIENT.LANDSCAPE if page.orientation == "landscape" else WD_ORIENT.PORTRAIT
    edges = (page.margin_top, page.margin_right, page.margin_bottom, page.margin_left)
    if before is None or edges != (before.margin_top, before.margin_right, before.margin_bottom, before.margin_left):
        section.top_margin, section.right_margin = _twips(edges[0]), _twips(edges[1])
        section.bottom_margin, section.left_margin = _twips(edges[2]), _twips(edges[3])
    if (before is None and page.page_numbers) or (before is not None and before.page_numbers != page.page_numbers):
        if page.page_numbers:
            new_footer = not _has_footer(section)
            _number_the_pages(section)
            owned |= {str(section.footer.part.partname).lstrip("/")}
            if new_footer:
                owned |= {"[Content_Types].xml", "word/_rels/document.xml.rels"}
        elif _has_footer(section):
            footer = section.footer._element
            for element in _page_fields(footer):
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)
            owned.add(str(section.footer.part.partname).lstrip("/"))
    return owned


def write_language(document: Any, language: str | None) -> None:
    """Make the document defaults of ``document`` say ``language`` (``zxx`` for none)."""
    lang = _language_element(document)
    if lang is None:
        lang = _make_language_element(document)
    lang.set(qn("w:val"), language if language is not None else NO_LANGUAGE[0])


def _make_language_element(document: Any) -> etree._Element:
    styles = document.styles.element
    defaults = styles.find(qn("w:docDefaults"))
    if defaults is None:
        defaults = OxmlElement("w:docDefaults")
        styles.insert(0, defaults)
    run_defaults = defaults.find(qn("w:rPrDefault"))
    if run_defaults is None:
        run_defaults = OxmlElement("w:rPrDefault")
        defaults.insert(0, run_defaults)
    properties = run_defaults.find(qn("w:rPr"))
    if properties is None:
        properties = OxmlElement("w:rPr")
        run_defaults.append(properties)
    lang = OxmlElement("w:lang")
    properties.append(lang)
    return lang
