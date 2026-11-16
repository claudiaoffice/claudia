"""The styles of a text as Word paragraph styles: the look of every paragraph style of the model, written with the
palette's colours (D455).

The built-in styles of the model are written into the styles Word has for them (``Normal``, ``Title``, ``Heading 1``,
``Heading 2``, ``Quote``); the others are added as styles of their own name. A style that a file already has is
written anew: what it set before is replaced by the look of the model, its place in Word (outline level, whether it
keeps with the next paragraph) stays. What Word cannot say of a style is returned with it, so that it can be
reported."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from docx.document import Document as DocxDocument
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from lxml import etree

from claudia_core import StyleBook, StyleDef

from ._style_look import Look, look_for

#: The built-in styles of the model by the name that Word has for them.
WORD_NAMES = {
    "body": "Normal",
    "title": "Title",
    "heading-1": "Heading 1",
    "heading-2": "Heading 2",
    "heading-3": "Heading 3",
    "heading-4": "Heading 4",
    "heading-5": "Heading 5",
    "heading-6": "Heading 6",
    "quote": "Quote",
}
#: What Word keeps of a style that it replaces: where the style stands in the document, not how it looks.
_KEPT = ("w:keepNext", "w:keepLines", "w:outlineLvl", "w:numPr")
_ALIGN = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}
_LINES = {"solid": "single", "dashed": "dashed", "dotted": "dotted", "double": "double"}
#: The order in which a paragraph's properties follow each other in a file (the part of it that is written here).
_PARAGRAPH_ORDER = ("w:pBdr", "w:shd", "w:suppressAutoHyphens", "w:spacing", "w:ind", "w:jc", "w:outlineLvl")
_PARAGRAPH_LATER = {
    "w:pBdr": _PARAGRAPH_ORDER[1:],
    "w:shd": _PARAGRAPH_ORDER[2:],
    "w:suppressAutoHyphens": _PARAGRAPH_ORDER[3:],
    "w:outlineLvl": ("w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange"),
}
_TEXT_LATER = ("w:w", "w:kern", "w:position", "w:sz", "w:szCs", "w:highlight", "w:u", "w:effect", "w:bdr", "w:shd")
_SIDES = ("top", "left", "bottom", "right")
_MAX_SPACE = 31  # points: the most that Word puts between a border and its text


class WordNames:
    """The Word name of each paragraph style of a book: the built-in ones by the name Word knows them by, the others
    by their own name, and never two the same (nor one of ``taken``, the styles a file already has)."""

    def __init__(self, book: StyleBook, taken: Collection[str] = ()) -> None:
        self.book = book
        self._names: dict[str, str] = {}
        taken = {*WORD_NAMES.values(), *taken}
        for style in book:
            if style.kind != "paragraph":
                continue
            if style.id in WORD_NAMES:
                self._names[style.id] = WORD_NAMES[style.id]
                continue
            candidate, number = style.name or style.id, 1
            while candidate in taken:
                number += 1
                candidate = f"{style.name or style.id} {number}"
            taken.add(candidate)
            self._names[style.id] = candidate

    def __contains__(self, style_id: object) -> bool:
        return style_id in self._names

    def of(self, style_id: str) -> str:
        """The name of the style, or ``Normal`` for one the book does not have."""
        return self._names.get(style_id, WORD_NAMES["body"])


def _body_hyphenates(book: StyleBook, colours: dict[str, str]) -> bool:
    """Whether the body text of ``book`` is hyphenated: Word has that for the whole document, and a paragraph style
    that says otherwise switches it off for itself."""
    return "body" in book.ids() and look_for(book, "body", colours).hyphenate is True


def unsaid_of(book: StyleBook, style: StyleDef, colours: dict[str, str]) -> list[str]:
    """What the style sets that a Word style cannot say."""
    return _unsaid(look_for(book, style.id, colours), body_hyphenates=_body_hyphenates(book, colours))


def write_styles(
    document: DocxDocument,
    book: StyleBook,
    names: WordNames,
    colours: dict[str, str],
    only: Collection[str] | None = None,
) -> list[tuple[str, str]]:
    """Write the paragraph styles of ``book`` into ``document`` -- every one, or those whose ids are in ``only`` -- and
    return what of them Word cannot say, as ``(style id, property)``."""
    unsaid: list[tuple[str, str]] = []
    styles = document.styles
    hyphenates = _body_hyphenates(book, colours)
    if only is None or "body" in only:
        _set_auto_hyphenation(document, hyphenates)
    for style in book:
        if style.kind != "paragraph" or (only is not None and style.id not in only):
            continue
        name = names.of(style.id)
        found = next((s for s in styles if s.type == WD_STYLE_TYPE.PARAGRAPH and s.name == name), None)
        word = found if found is not None else styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        _clear(word.element)
        if style.based_on:
            word.base_style = styles[names.of(style.based_on)]
        elif found is None:
            word.base_style = None
        look = look_for(book, style.id, colours)
        level = book.heading_level(style.id)
        _write_look(word, look, keep_with_next=level is not None)
        _write_outline_level(word.element, level)
        unsaid += [(style.id, prop) for prop in _unsaid(look, body_hyphenates=hyphenates)]
    return unsaid


def _unsaid(look: Look, *, body_hyphenates: bool) -> list[str]:
    said = list(look.unsaid)
    if look.hyphenate and not body_hyphenates:
        said.append("hyphens")
    if look.padding and not look.borders:
        said.append("padding")
    return said


def _set_auto_hyphenation(document: DocxDocument, on: bool) -> None:
    """Switch the hyphenation of the whole document on or off (its settings)."""
    settings = document.settings.element
    for found in settings.findall(qn("w:autoHyphenation")):
        settings.remove(found)
    if not on:
        return
    part = OxmlElement("w:autoHyphenation")
    anchor = settings.find(qn("w:defaultTabStop"))
    if anchor is not None:
        anchor.addnext(part)
        return
    _insert(settings, part, ("w:characterSpacingControl", "w:compat", "w:rsids"))


def _clear(element: Any) -> None:
    """Remove the look a style has, keeping what it is in a document (its outline level...)."""
    for tag in ("w:pPr", "w:rPr"):
        child = element.find(qn(tag))
        if child is None:
            continue
        if tag == "w:rPr":
            element.remove(child)
            continue
        for part in list(child):
            if part.tag not in {qn(kept) for kept in _KEPT}:
                child.remove(part)


def _write_look(word: Any, look: Look, *, keep_with_next: bool) -> None:
    _write_text(word, look)
    paragraph = word.paragraph_format
    if look.align in _ALIGN:
        paragraph.alignment = _ALIGN[look.align]
    _write_spacing(paragraph, look)
    if keep_with_next:
        paragraph.keep_with_next = True
    if look.hyphenate is False:
        _paragraph_property(word.element, "w:suppressAutoHyphens", {})
    if look.background is not None:
        _paragraph_property(word.element, "w:shd", {"w:val": "clear", "w:color": "auto", "w:fill": look.background[1:]})
    if look.borders:
        _write_borders(word.element, look)


def _write_outline_level(element: Any, level: int | None) -> None:
    """Give a Word style the outline level of a section heading (Word counts from 0: Heading 1 is 0), or take away the
    one Word's own style had when the style is no section heading (the title, body text) (E9.22)."""
    properties = element.find(qn("w:pPr"))
    if properties is not None and (old := properties.find(qn("w:outlineLvl"))) is not None:
        properties.remove(old)
    if level:
        _paragraph_property(element, "w:outlineLvl", {"w:val": str(level - 1)})


def _write_text(word: Any, look: Look) -> None:
    font = word.font
    if look.family is not None:
        font.name = look.family
    if look.size is not None:
        font.size = Pt(look.size)
    if look.weight is not None:
        font.bold = look.weight >= 600  # noqa: PLR2004 - the weight from which a font is bold
    if look.italic is not None:
        font.italic = look.italic
    if look.underline is not None:
        font.underline = look.underline
    if look.strike is not None:
        font.strike = look.strike
    if look.colour is not None:
        font.color.rgb = RGBColor.from_string(look.colour[1:])
    if look.spacing is not None:
        _text_property(word.element, "w:spacing", {"w:val": str(round(look.spacing * 20))})


def _write_spacing(paragraph: Any, look: Look) -> None:
    if "top" in look.margins:
        paragraph.space_before = Pt(look.margins["top"])
    if "bottom" in look.margins:
        paragraph.space_after = Pt(look.margins["bottom"])
    if "left" in look.margins:
        paragraph.left_indent = Pt(look.margins["left"])
    if "right" in look.margins:
        paragraph.right_indent = Pt(look.margins["right"])
    if look.line is None:
        return
    if look.line_fixed:
        paragraph.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        paragraph.line_spacing = Pt(look.line)
    else:
        paragraph.line_spacing = look.line


def _write_borders(element: Any, look: Look) -> None:
    borders = OxmlElement("w:pBdr")
    for side in _SIDES:
        if side not in look.borders:
            continue
        border = look.borders[side]
        part = OxmlElement(f"w:{side}")
        if border is None:
            part.set(qn("w:val"), "nil")
        else:
            part.set(qn("w:val"), _LINES.get(border.line, "single"))
            part.set(qn("w:sz"), str(max(2, min(96, round(border.width * 8)))))
            part.set(qn("w:space"), str(min(_MAX_SPACE, round(look.padding.get(side, 0)))))
            part.set(qn("w:color"), border.colour[1:])
        borders.append(part)
    _insert(_properties(element, "w:pPr"), borders, _PARAGRAPH_LATER["w:pBdr"])


def _properties(element: Any, tag: str) -> Any:
    found = element.find(qn(tag))
    if found is None:
        found = OxmlElement(tag)
        # a style has its name and where it comes from first, then the properties of its paragraph, then its text's
        after = element.find(qn("w:rPr")) if tag == "w:pPr" else None
        if after is not None:
            after.addprevious(found)
        else:
            element.append(found)
    return found


def _paragraph_property(element: Any, tag: str, attributes: dict[str, str]) -> None:
    part = OxmlElement(tag)
    for key, value in attributes.items():
        part.set(qn(key), value)
    _insert(_properties(element, "w:pPr"), part, _PARAGRAPH_LATER[tag])


def _text_property(element: Any, tag: str, attributes: dict[str, str]) -> None:
    part = OxmlElement(tag)
    for key, value in attributes.items():
        part.set(qn(key), value)
    _insert(_properties(element, "w:rPr"), part, _TEXT_LATER)


def _insert(parent: Any, part: etree._Element, later: tuple[str, ...]) -> None:
    """Put ``part`` into ``parent`` before the first child that has to follow it."""
    follow = {qn(tag) for tag in later}
    for child in parent:
        if child.tag in follow:
            child.addprevious(part)
            return
    parent.append(part)
