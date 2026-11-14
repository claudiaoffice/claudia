"""The looks of an ods file's cells, read from its cell styles and number styles (E6.14, D379).

An ods file names a cell's look by a *cell style* (``table:style-name``). The named ones (``office:styles`` in
``styles.xml``, "Default", "Heading", "Result"...) are what a person chose; the automatic ones (``ce1``, ``ce2``... in
``content.xml``) are what LibreOffice made from direct formats, each based on a named style. A style's properties are
its own on top of its parent's, and all of them on top of the file's default cell style. A cell without a style of its
own takes its row's or its column's default cell style (``table:default-cell-style-name``).

This module turns each style into a :class:`~claudia_computes_io.cell_looks.Look` -- the same thing
:mod:`.xlsx_looks` makes from an xlsx file, so both become the same styles (the parity rule).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from lxml import etree

from claudia_computes.numformats import check_code
from claudia_odf_io import NS

from .cell_looks import GENERAL, Look, checked, font_family, size_text
from .odf_numbers import NUMBER_STYLES, code_of

#: A style's property: the element of the style it is on (``table-cell-properties``...) and its attribute.
Property = tuple[str, str]
_POINTS = {"pt": 1.0, "px": 0.75, "pc": 12.0, "in": 72.0, "cm": 72 / 2.54, "mm": 72 / 25.4}
_LENGTH = re.compile(r"(-?\d+(?:\.\d+)?)(pt|px|pc|in|cm|mm)")
_ALIGN = {"start": "left", "left": "left", "center": "center", "end": "right", "right": "right", "justify": "justify"}
_VALIGN = {"top": "top", "middle": "middle", "bottom": "bottom", "automatic": "bottom"}
_LINES = {"solid": "solid", "double": "double", "dotted": "dotted", "dashed": "dashed", "dash": "dashed",
          "fine-dashed": "dashed", "dot-dash": "dashed", "dot-dot-dash": "dotted"}  # fmt: skip
_DATA_STYLE: Property = ("", "data-style-name")


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


@dataclass
class OdsLooks:
    """The looks of a file: ``normal`` (the default cell style, every cell's look unless it has another), the
    ``named`` styles (by their name: the name a person reads, and the look) and every cell style by its name (the
    named style it starts from, and the look)."""

    normal: Look = field(default_factory=Look)
    named: dict[str, tuple[str, Look]] = field(default_factory=dict)
    styles: dict[str, tuple[str | None, Look]] = field(default_factory=dict)

    def look(self, name: str) -> tuple[str | None, Look]:
        """The named style a cell style starts from and its look; the default look for a name the file lacks."""
        return self.styles.get(name, (None, self.normal))


def read_looks(parts: Mapping[str, bytes], content: etree._Element) -> OdsLooks:
    """Every cell style of the file, from ``styles.xml`` and ``content.xml``, as looks."""
    roots = [content]
    if "styles.xml" in parts:
        roots.insert(0, etree.fromstring(parts["styles.xml"], etree.XMLParser(resolve_entities=False, no_network=True)))
    return _Reader(roots).looks()


class _Reader:
    def __init__(self, roots: list[etree._Element]) -> None:
        self.fonts: dict[str, str] = {}
        self.numbers: dict[str, etree._Element] = {}
        self.raw: dict[str, tuple[str | None, dict[Property, str], bool]] = {}  # name -> parent, own, named?
        self.default: dict[Property, str] = {}
        self.display: dict[str, str] = {}
        for root in roots:
            self._collect(root)

    def _collect(self, root: etree._Element) -> None:
        for face in root.iter(_q("style", "font-face")):
            family = face.get(_q("svg", "font-family"), "").strip("'\"")
            self.fonts[face.get(_q("style", "name"), "")] = family
        for kind in NUMBER_STYLES:
            for element in root.iter(_q("number", kind)):
                self.numbers[element.get(_q("style", "name"), "")] = element
        for default in root.iter(_q("style", "default-style")):
            if default.get(_q("style", "family")) == "table-cell":
                self.default = _properties(default)
        for element in root.iter(_q("style", "style")):
            if element.get(_q("style", "family")) != "table-cell":
                continue
            name = element.get(_q("style", "name"), "")
            parent = element.getparent()
            named = parent is not None and etree.QName(parent).localname == "styles"
            self.raw[name] = (element.get(_q("style", "parent-style-name")), _properties(element), named)
            self.display[name] = element.get(_q("style", "display-name")) or name

    def resolved(self, name: str | None, seen: tuple[str, ...] = ()) -> dict[Property, str]:
        if name is None or name not in self.raw or name in seen:
            return dict(self.default)
        parent, own, _ = self.raw[name]
        merged = self.resolved(parent, (*seen, name))
        merged.update(own)
        return merged

    def looks(self) -> OdsLooks:
        default = "Default" if "Default" in self.raw else None
        result = OdsLooks(self.look(self.resolved(default)))
        for name, (_, _, named) in self.raw.items():
            if named and name != default:
                result.named[name] = (self.display[name], self.look(self.resolved(name)))
        for name, (parent, _, named) in self.raw.items():
            start = name if named else self._named_parent(parent)
            result.styles[name] = (None if start == default else start, self.look(self.resolved(name)))
        return result

    def _named_parent(self, name: str | None) -> str | None:
        seen = set()
        while name is not None and name in self.raw and name not in seen:
            seen.add(name)
            parent, _, named = self.raw[name]
            if named:
                return name
            name = parent
        return None

    def look(self, props: Mapping[Property, str]) -> Look:
        css: dict[str, str] = {"vertical-align": "bottom"}
        unmapped: list[str] = []
        self._text(props, css, unmapped)
        _cell(props, css, unmapped)
        if props.get(("table-cell-properties", _attr("style", "text-align-source"))) != "value-type":
            align = props.get(("paragraph-properties", _attr("fo", "text-align")))
            if align in _ALIGN:
                css["text-align"] = _ALIGN[align]
        indent = _points(props.get(("paragraph-properties", _attr("fo", "margin-left")), ""))
        if indent:
            css["padding-left"] = size_text(round(indent, 1))
        return Look.of(css, self._code(props.get(_DATA_STYLE), unmapped), unmapped)

    def _text(self, props: Mapping[Property, str], css: dict[str, str], unmapped: list[str]) -> None:
        def text(prefix: str, local: str) -> str | None:
            return props.get(("text-properties", _attr(prefix, local)))

        face = text("style", "font-name")
        name = self.fonts.get(face, face) if face else text("fo", "font-family")
        family = font_family(name.strip("'\"")) if name else None
        if family:
            css["font-family"] = family
        size = _points(text("fo", "font-size") or "")
        if size:
            css["font-size"] = size_text(round(size, 1))
        weight = text("fo", "font-weight")
        if weight == "bold" or (weight or "").isdigit() and int(weight or 0) >= 600:  # noqa: PLR2004
            css["font-weight"] = "bold"
        if text("fo", "font-style") in ("italic", "oblique"):
            css["font-style"] = "italic"
        decoration = []
        if text("style", "text-underline-style") not in (None, "none"):
            decoration.append("underline")
            if text("style", "text-underline-type") == "double":
                unmapped.append("double-underline")
        if text("style", "text-line-through-style") not in (None, "none"):
            decoration.append("line-through")
        if decoration:
            css["text-decoration"] = " ".join(decoration)
        colour = text("fo", "color")
        if colour and text("style", "use-window-font-color") != "true" and (found := checked("color", colour)):
            css["color"] = found
        if (text("style", "text-position") or "0").split()[0] not in ("0", "0%"):
            unmapped.append("superscript")

    def _code(self, name: str | None, unmapped: list[str]) -> str:
        style = self.numbers.get(name or "")
        if style is None:
            return GENERAL
        code = code_of(style, self.numbers)
        if code.casefold() == "general":
            return GENERAL
        try:
            check_code(code)
        except ValueError:
            unmapped.append("number-format")
            return GENERAL
        return code


def _cell(props: Mapping[Property, str], css: dict[str, str], unmapped: list[str]) -> None:
    def cell(prefix: str, local: str) -> str | None:
        return props.get(("table-cell-properties", _attr(prefix, local)))

    background = cell("fo", "background-color")
    if background and background != "transparent" and (found := checked("background-color", background)):
        css["background-color"] = found
    for side in ("top", "right", "bottom", "left"):
        line = cell("fo", f"border-{side}") or cell("fo", "border")
        border = _border(line) if line else None
        if border:
            css[f"border-{side}"] = border
    if cell("fo", "diagonal-tl-br") not in (None, "none") or cell("fo", "diagonal-bl-tr") not in (None, "none"):
        unmapped.append("diagonal")
    vertical = cell("style", "vertical-align")
    if vertical:
        css["vertical-align"] = _VALIGN.get(vertical, "bottom")
    if cell("fo", "wrap-option") == "wrap":
        css["white-space"] = "pre-wrap"
    if (cell("style", "rotation-angle") or "0").rstrip("deg") not in ("0", "0.0", ""):
        unmapped.append("rotation")
    if cell("style", "shrink-to-fit") == "true":
        unmapped.append("shrink")
    if cell("style", "repeat-content") == "true":
        unmapped.append("fill")


def _border(text: str) -> str | None:
    """``0.74pt solid #000000`` as a CSS border of whole pixels; ``None`` for no line."""
    words = text.split()
    if not words or words[0] == "none":
        return None
    width = next((_points(w) for w in words if _LENGTH.fullmatch(w)), 0.75)
    line = next((_LINES[w] for w in words if w in _LINES), "solid")
    colour = next((w for w in words if w.startswith("#")), "@text")
    pixels = 1 if width <= 1.0 else 2 if width <= 2.0 else 3  # noqa: PLR2004 (thin, medium, thick)
    return checked("border-top", f"{pixels}px {line} {colour}")


def _points(text: str) -> float:
    match = _LENGTH.fullmatch(text.strip())
    return 0.0 if match is None else float(match.group(1)) * _POINTS[match.group(2)]


def _attr(prefix: str, local: str) -> str:
    return f"{prefix}:{local}"


def _properties(style: etree._Element) -> dict[Property, str]:
    props: dict[Property, str] = {}
    for child in style:
        if not isinstance(child.tag, str) or etree.QName(child).namespace != NS["style"]:
            continue
        element = etree.QName(child).localname
        for name, value in child.attrib.items():
            qname = etree.QName(name)
            prefix = next((p for p, uri in NS.items() if uri == qname.namespace), "")
            props[(element, _attr(prefix, qname.localname))] = str(value)
    data = style.get(_q("style", "data-style-name"))
    if data:
        props[_DATA_STYLE] = data
    return props


def column_styles(table: etree._Element) -> Iterable[tuple[int, int, str]]:
    """The default cell style of each run of columns of a table: (first, last, style name)."""
    column = 0
    for declared in table.iter(_q("table", "table-column")):
        width = max(1, int(declared.get(_q("table", "number-columns-repeated"), "1") or 1))
        name = declared.get(_q("table", "default-cell-style-name"))
        if name:
            yield column, column + width - 1, name
        column += width
