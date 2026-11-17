"""A table of contents in an odt, both ways (E9.31, step E).

**Writing.** A ``text:table-of-content`` whose source lists the outline levels up to the last the model's table lists
(``text:outline-level``; OpenDocument always starts at level 1) and whose ``text:index-body`` holds the entries, one
paragraph each in the styles ``Contents 1`` … ``Contents 9``, **without page numbers**: pages are the layout's, and an
odt is laid out by its program. OpenDocument has no "update when opened", so the loss ``toc-pages`` is reported.

**Reading.** A ``text:table-of-content`` becomes one generated paragraph listing levels 1 to its source's outline
level; the entries the program wrote are not read (they are derived again from the headings).
"""

from __future__ import annotations

from collections.abc import Callable

from lxml import etree

from claudia_core import ContentsEntry, Toc
from claudia_odf_io import NS

TABLE_OF_CONTENT = f"{{{NS['text']}}}table-of-content"
_SOURCE = f"{{{NS['text']}}}table-of-content-source"
_LEVEL = f"{{{NS['text']}}}outline-level"


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def _element(prefix: str, local: str, **attributes: str) -> etree._Element:
    element = etree.Element(_q(prefix, local))
    for name, value in attributes.items():
        element.set(_q(prefix, name.replace("_", "-")), value)
    return element


def contents_element(
    toc: Toc, entries: tuple[ContentsEntry, ...], name: str, style_of: Callable[[str], str]
) -> etree._Element:
    """The ``text:table-of-content`` called ``name`` that lists what ``toc`` lists, with ``entries`` as its body
    (each in the odt style ``style_of(entry.style)``), without page numbers."""
    table = _element("text", "table-of-content", name=name, protected="true")
    source = etree.SubElement(table, _SOURCE)
    source.set(_LEVEL, str(toc.last))
    source.set(_q("text", "use-outline-level"), "true")
    for level in range(1, toc.last + 1):
        template = etree.SubElement(source, _q("text", "table-of-content-entry-template"))
        template.set(_q("text", "outline-level"), str(level))
        template.set(_q("text", "style-name"), style_of(f"contents-{level}"))
        if toc.numbers:
            etree.SubElement(template, _q("text", "index-entry-chapter"))
        etree.SubElement(template, _q("text", "index-entry-text"))
    body = etree.SubElement(table, _q("text", "index-body"))
    for entry in entries:
        line = etree.SubElement(body, _q("text", "p"))
        line.set(_q("text", "style-name"), style_of(entry.style))
        line.text = f"{entry.number} {entry.text}" if toc.numbers and entry.number else entry.text
    return table


def read_contents(table: etree._Element) -> Toc:
    """The options of a ``text:table-of-content``: levels 1 to its source's outline level (10 and more: 9)."""
    source = table.find(_SOURCE)
    try:
        last = int(source.get(_LEVEL) or 10) if source is not None else 10
    except ValueError:
        last = 10
    return Toc(1, max(1, min(last, 9)))
