"""Row heights and column widths of a table in an ods file (D458).

An ods file gives a column or a row a *style* (``table:style-name``) that holds its size: ``style:column-width`` in a
``table-column`` style, ``style:row-height`` in a ``table-row`` style, both lengths with a unit. The model counts in
pixels (:mod:`.layout_sizes`), and a length is turned into pixels by the unit it names (a pixel is 1/96 inch, as in
CSS). A row or column the application sizes by its content (``style:use-optimal-row-height``,
``style:use-optimal-column-width``) has no size of its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree

from claudia_odf_io import NS

from .layout_sizes import fit_height, fit_width

_PIXELS = {"px": 1.0, "pt": 96 / 72, "pc": 16.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4}
_LENGTH = re.compile(r"(\d+(?:\.\d+)?)(px|pt|pc|in|cm|mm)")
_CM_PER_PIXEL = 2.54 / 96


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def pixels_of(length: str | None) -> int | None:
    """A length of a file (``2.258cm``, ``0.5in``, ``12pt``...) in whole pixels; ``None`` for what is not one."""
    found = _LENGTH.fullmatch((length or "").strip())
    return None if found is None else round(float(found.group(1)) * _PIXELS[found.group(2)])


def text_of(pixels: float) -> str:
    """``pixels`` as the length a file writes (centimetres, to four places: finer than a pixel)."""
    return f"{pixels * _CM_PER_PIXEL:.4f}cm"


@dataclass
class OdsSizes:
    """The sizes the automatic styles of a file give, by style name: ``columns`` (a width) and ``rows`` (a height)."""

    columns: dict[str, int] = field(default_factory=dict)
    rows: dict[str, int] = field(default_factory=dict)


def read_sizes(content: etree._Element) -> OdsSizes:
    """The sizes of the column and row styles in the automatic styles of ``content.xml`` (the ones somebody set)."""
    sizes = OdsSizes()
    for style in content.iterfind("office:automatic-styles/style:style", NS):
        name = style.get(_q("style", "name"))
        family = style.get(_q("style", "family"))
        if name is None:
            continue
        if family == "table-column":
            properties = style.find("style:table-column-properties", NS)
            if properties is None or properties.get(_q("style", "use-optimal-column-width")) == "true":
                continue
            width = pixels_of(properties.get(_q("style", "column-width")))
            if width:
                sizes.columns[name] = fit_width(width)
        elif family == "table-row":
            properties = style.find("style:table-row-properties", NS)
            if properties is None or properties.get(_q("style", "use-optimal-row-height")) == "true":
                continue
            height = pixels_of(properties.get(_q("style", "row-height")))
            if height:
                sizes.rows[name] = fit_height(height)
    return sizes


def column_style(name: str, pixels: float) -> etree._Element:
    """The automatic style ``name`` of a column ``pixels`` wide."""
    element = etree.Element(_q("style", "style"), nsmap={p: u for p, u in NS.items() if p != "xml"})
    element.set(_q("style", "name"), name)
    element.set(_q("style", "family"), "table-column")
    properties = etree.SubElement(element, _q("style", "table-column-properties"))
    properties.set(_q("fo", "break-before"), "auto")
    properties.set(_q("style", "column-width"), text_of(pixels))
    return element


def row_style(name: str, pixels: float) -> etree._Element:
    """The automatic style ``name`` of a row ``pixels`` high: one somebody set, not sized by its content."""
    element = etree.Element(_q("style", "style"), nsmap={p: u for p, u in NS.items() if p != "xml"})
    element.set(_q("style", "name"), name)
    element.set(_q("style", "family"), "table-row")
    properties = etree.SubElement(element, _q("style", "table-row-properties"))
    properties.set(_q("fo", "break-before"), "auto")
    properties.set(_q("style", "row-height"), text_of(pixels))
    properties.set(_q("style", "use-optimal-row-height"), "false")
    return element
