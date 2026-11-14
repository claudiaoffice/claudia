"""The looks of an xlsx file's cells, read from ``xl/styles.xml`` and the theme (E6.14, D379).

An xlsx file keeps every look of a cell once, in ``cellXfs``: a font, a fill, a border, an alignment and a number
format, each by its number in a list of its own, and the named style (``cellStyleXfs``, named in ``cellStyles``) the
look starts from. A cell says which look it has by its place in ``cellXfs`` (``s="3"``). This module turns each of
those into a :class:`~claudia_computes_io.cell_looks.Look`; :mod:`.cell_looks` makes them styles.

Colours come as ``rgb`` (ARGB), as an entry of the theme with a ``tint`` that lightens or darkens it, or as an entry
of the old 64-colour palette. The theme's first dark colour without a tint is the palette's text colour
(``@text``), so a sheet in Excel's default black reads well in a dark appearance too.
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass, field

from lxml import etree

from claudia_computes.numformats import BUILTIN, check_code

from .cell_looks import GENERAL, Look, checked, font_family, size_text
from .xlsx_read import NS, parse_xml

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
#: The theme's colours in the order a ``theme="n"`` counts them (light and dark swapped against the theme part's
#: own order, as Excel does), with Office's own theme for a file that has none.
_THEME_ORDER = ("lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink",
                "folHlink")  # fmt: skip
_OFFICE_THEME = {
    "dk1": "000000",
    "lt1": "FFFFFF",
    "dk2": "44546A",
    "lt2": "E7E6E6",
    "accent1": "4472C4",
    "accent2": "ED7D31",
    "accent3": "A5A5A5",
    "accent4": "FFC000",
    "accent5": "5B9BD5",
    "accent6": "70AD47",
    "hlink": "0563C1",
    "folHlink": "954F72",
}
#: The old palette a colour can name by ``indexed="n"`` (64 and above: the system's own, read as "automatic").
_INDEXED_COLOURS = (
    "000000 FFFFFF FF0000 00FF00 0000FF FFFF00 FF00FF 00FFFF 000000 FFFFFF FF0000 00FF00 0000FF FFFF00 FF00FF 00FFFF "
    "800000 008000 000080 808000 800080 008080 C0C0C0 808080 9999FF 993366 FFFFCC CCFFFF 660066 FF8080 0066CC CCCCFF "
    "000080 FF00FF FFFF00 00FFFF 800080 800000 008080 0000FF 00CCFF CCFFFF CCFFCC FFFF99 99CCFF FF99CC CC99FF FFCC99 "
    "3366FF 33CCCC 99CC00 FFCC00 FF9900 FF6600 666699 969696 003366 339966 003300 333300 993300 993366 333399 333333"
)
#: Excel's accounting formats, which a file may name by number alone.
_ACCOUNTING = {
    41: '_(* #,##0_);_(* \\(#,##0\\);_(* "-"_);_(@_)',
    42: '_("$"* #,##0_);_("$"* \\(#,##0\\);_("$"* "-"_);_(@_)',
    43: '_(* #,##0.00_);_(* \\(#,##0.00\\);_(* "-"??_);_(@_)',
    44: '_("$"* #,##0.00_);_("$"* \\(#,##0.00\\);_("$"* "-"??_);_(@_)',
}
#: An xlsx line as a CSS border: its width, and the line CSS draws closest to it.
_LINES = {
    "thin": "1px solid",
    "hair": "1px dotted",
    "dotted": "1px dotted",
    "dashed": "1px dashed",
    "dashDot": "1px dashed",
    "dashDotDot": "1px dotted",
    "medium": "2px solid",
    "mediumDashed": "2px dashed",
    "mediumDashDot": "2px dashed",
    "mediumDashDotDot": "2px dashed",
    "slantDashDot": "2px dashed",
    "thick": "3px solid",
    "double": "3px double",
}
_ALIGN = {"left": "left", "center": "center", "right": "right", "justify": "justify", "distributed": "justify"}
_VALIGN = {"top": "top", "center": "middle", "bottom": "bottom"}
#: How far one step of indent moves a cell's words in, as Excel draws it (about three spaces).
_INDENT_POINTS = 9


@dataclass
class XlsxLooks:
    """The looks of a file: ``normal`` (Excel's *Normal*, every cell's look unless it has another), the ``named``
    styles (by their place in ``cellStyleXfs``: a name and a look) and each look of ``cells`` (by its place in
    ``cellXfs``: the named style it starts from and the look)."""

    normal: Look = field(default_factory=Look)
    named: dict[int, tuple[str, Look]] = field(default_factory=dict)
    cells: list[tuple[int, Look]] = field(default_factory=list)

    def look(self, index: int) -> Look:
        """The look a cell with ``s=index`` has (the default look for a number the file does not list)."""
        return self.cells[index][1] if 0 <= index < len(self.cells) else self.normal


def read_looks(parts: dict[str, bytes]) -> XlsxLooks:
    """Every look of the file's cells; a file without ``xl/styles.xml`` has Excel's default look only."""
    data = parts.get("xl/styles.xml")
    if data is None:
        return XlsxLooks(Look.of(_DEFAULT_CSS))
    return _Reader(parse_xml(data), _theme(parts)).looks()


_DEFAULT_CSS = {"font-family": "Calibri, Carlito, sans-serif", "font-size": "11pt", "vertical-align": "bottom"}


def _theme(parts: dict[str, bytes]) -> list[str]:
    colours = dict(_OFFICE_THEME)
    data = parts.get("xl/theme/theme1.xml")
    scheme = None if data is None else parse_xml(data).find(f".//{{{_A}}}clrScheme")
    if scheme is not None:
        for entry in scheme:
            name = etree.QName(entry).localname
            for value in entry:
                rgb = value.get("val") if etree.QName(value).localname == "srgbClr" else value.get("lastClr")
                if rgb and len(rgb) == 6:  # noqa: PLR2004 (rrggbb)
                    colours[name] = rgb
    return [colours[name] for name in _THEME_ORDER]


def tinted(rgb: str, tint: float) -> str:
    """``rgb`` lightened (``tint`` above 0) or darkened (below 0) as Excel does it, on the lightness of the colour."""
    red, green, blue = (int(rgb[i : i + 2], 16) / 255 for i in (0, 2, 4))
    hue, light, saturation = colorsys.rgb_to_hls(red, green, blue)
    light = light * (1 + tint) if tint < 0 else light * (1 - tint) + tint
    red, green, blue = colorsys.hls_to_rgb(hue, min(max(light, 0.0), 1.0), saturation)
    return "".join(f"{round(part * 255):02X}" for part in (red, green, blue))


@dataclass
class _Reader:
    styles: etree._Element
    theme: list[str]

    def __post_init__(self) -> None:
        self.fonts = self.styles.findall("x:fonts/x:font", NS)
        self.fills = self.styles.findall("x:fills/x:fill", NS)
        self.borders = self.styles.findall("x:borders/x:border", NS)
        self.codes = {
            int(f.get("numFmtId", "0")): f.get("formatCode", "") for f in self.styles.iterfind("x:numFmts/x:numFmt", NS)
        }
        custom = [c.get("rgb", "")[-6:] for c in self.styles.iterfind("x:colors/x:indexedColors/x:rgbColor", NS)]
        self.indexed = custom if custom else _INDEXED_COLOURS.split()

    def looks(self) -> XlsxLooks:
        named_xfs = [self.look(xf) for xf in self.styles.iterfind("x:cellStyleXfs/x:xf", NS)]
        result = XlsxLooks(named_xfs[0] if named_xfs else Look.of(_DEFAULT_CSS))
        for element in self.styles.iterfind("x:cellStyles/x:cellStyle", NS):
            index = int(element.get("xfId", "0"))
            if element.get("builtinId") == "0" or index == 0:
                continue  # Normal, whatever the file calls it ("Standard" in a German Excel): Body text
            if 0 < index < len(named_xfs):
                result.named[index] = (element.get("name", "") or f"Style {index}", named_xfs[index])
        for xf in self.styles.iterfind("x:cellXfs/x:xf", NS):
            result.cells.append((int(xf.get("xfId", "0")), self.look(xf)))
        return result

    def look(self, xf: etree._Element) -> Look:
        css: dict[str, str] = {"vertical-align": "bottom"}
        unmapped: list[str] = []
        self._font(_at(self.fonts, xf.get("fontId")), css, unmapped)
        self._fill(_at(self.fills, xf.get("fillId")), css, unmapped)
        self._border(_at(self.borders, xf.get("borderId")), css, unmapped)
        self._alignment(xf.find("x:alignment", NS), css, unmapped)
        code = self._code(int(xf.get("numFmtId", "0")), unmapped)
        return Look.of(css, code, unmapped)

    def colour(self, element: etree._Element | None) -> str | None:
        """A colour element as CSS; ``None`` for "automatic" or nothing."""
        if element is None or element.get("auto") in ("1", "true"):
            return None
        rgb = None
        if element.get("rgb"):
            rgb = element.get("rgb", "")[-6:]
        elif element.get("theme") is not None:
            index = int(element.get("theme", "0"))
            if element.get("tint") is None and index == 1:
                return "@text"
            rgb = self.theme[index] if 0 <= index < len(self.theme) else None
        elif element.get("indexed") is not None:
            index = int(element.get("indexed", "0"))
            rgb = self.indexed[index] if 0 <= index < len(self.indexed) else None
        if rgb is None or len(rgb) != 6:  # noqa: PLR2004
            return None
        tint = float(element.get("tint", "0") or 0)
        return "#" + (tinted(rgb, tint) if tint else rgb.upper())

    def _font(self, font: etree._Element | None, css: dict[str, str], unmapped: list[str]) -> None:
        if font is None:
            return
        name = _val(font, "name")
        family = font_family(name) if name else None
        if family:
            css["font-family"] = family
        size = _val(font, "sz")
        if size and (text := checked("font-size", size_text(float(size)))):
            css["font-size"] = text
        if _on(font, "b"):
            css["font-weight"] = "bold"
        if _on(font, "i"):
            css["font-style"] = "italic"
        decoration = []
        underline = font.find("x:u", NS)
        if underline is not None and underline.get("val", "single") != "none":
            decoration.append("underline")
            if underline.get("val", "single") not in ("single", "singleAccounting"):
                unmapped.append("double-underline")
        if _on(font, "strike"):
            decoration.append("line-through")
        if decoration:
            css["text-decoration"] = " ".join(decoration)
        colour = self.colour(font.find("x:color", NS))
        if colour is not None:
            css["color"] = colour
        if _val(font, "vertAlign") in ("superscript", "subscript"):
            unmapped.append("superscript")

    def _fill(self, fill: etree._Element | None, css: dict[str, str], unmapped: list[str]) -> None:
        if fill is None:
            return
        if fill.find("x:gradientFill", NS) is not None:
            unmapped.append("gradient")
            return
        pattern = fill.find("x:patternFill", NS)
        kind = "none" if pattern is None else pattern.get("patternType", "solid" if len(pattern) else "none")
        if kind == "none" or pattern is None:
            return
        if kind != "solid":
            unmapped.append("pattern")
            return
        colour = self.colour(pattern.find("x:fgColor", NS))
        if colour is not None and colour != "@text":
            css["background-color"] = colour

    def _border(self, border: etree._Element | None, css: dict[str, str], unmapped: list[str]) -> None:
        if border is None:
            return
        for side, names in (("top", ("top",)), ("right", ("right", "end")), ("bottom", ("bottom",)),
                            ("left", ("left", "start"))):  # fmt: skip
            line = next((found for n in names if (found := border.find(f"x:{n}", NS)) is not None), None)
            style = None if line is None else line.get("style")
            if not style or style == "none":
                continue
            colour = self.colour(line.find("x:color", NS)) if line is not None else None
            css[f"border-{side}"] = f"{_LINES.get(style, '1px solid')} {colour or '@text'}"
        diagonal = border.find("x:diagonal", NS)
        if diagonal is not None and diagonal.get("style") not in (None, "none"):
            unmapped.append("diagonal")

    @staticmethod
    def _alignment(alignment: etree._Element | None, css: dict[str, str], unmapped: list[str]) -> None:
        if alignment is None:
            return
        horizontal = alignment.get("horizontal", "general")
        if horizontal in _ALIGN:
            css["text-align"] = _ALIGN[horizontal]
        elif horizontal == "centerContinuous":
            unmapped.append("center-across")
        elif horizontal == "fill":
            unmapped.append("fill")
        vertical = alignment.get("vertical", "bottom")
        if vertical in _VALIGN:
            css["vertical-align"] = _VALIGN[vertical]
        else:
            unmapped.append("vertical-spread")
        if alignment.get("wrapText") in ("1", "true"):
            css["white-space"] = "pre-wrap"
        indent = int(alignment.get("indent", "0") or 0)
        if indent:
            css["padding-left"] = size_text(indent * _INDENT_POINTS)
        if int(alignment.get("textRotation", "0") or 0):
            unmapped.append("rotation")
        if alignment.get("shrinkToFit") in ("1", "true"):
            unmapped.append("shrink")

    def _code(self, number: int, unmapped: list[str]) -> str:
        code = self.codes.get(number) or BUILTIN.get(number) or _ACCOUNTING.get(number)
        if code is None or code.casefold() == "general":
            if code is None and number:
                unmapped.append("number-format")
            return GENERAL
        try:
            check_code(code)
        except ValueError:
            unmapped.append("number-format")
            return GENERAL
        return code


def _at(items: list[etree._Element], index: str | None) -> etree._Element | None:
    number = int(index or 0)
    return items[number] if 0 <= number < len(items) else None


def _val(element: etree._Element, name: str) -> str | None:
    found = element.find(f"x:{name}", NS)
    return None if found is None else found.get("val")


def _on(element: etree._Element, name: str) -> bool:
    found = element.find(f"x:{name}", NS)
    return found is not None and found.get("val", "1") not in ("0", "false")
