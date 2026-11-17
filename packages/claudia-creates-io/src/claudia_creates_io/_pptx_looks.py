"""What a pptx says about how its objects and its slides look, as CSS of the model's styles (IEW-20, D467).

A shape says its fill and outline in its own ``spPr`` (or, as PowerPoint's own shapes do, through the ``p:style`` that
points into the theme), its words in the properties of their runs and paragraphs. :class:`Theme` turns a colour a file
names (``accent1``) into the one the theme has for it; :func:`read_look` turns what a shape says into the properties a
:class:`~claudia_creates_io._file_looks.LookBook` makes a style of. What a placeholder takes from its layout is not
followed, and what the model has no property for (a gradient, a dash, a shadow, a colour made lighter) is not read:
it is said so, in ``Look.unread``."""

from __future__ import annotations

import re

from lxml import etree

from ._file_looks import Look

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_EMU_PER_POINT = 12_700
_HEX = re.compile(r"[0-9a-fA-F]{6}")
#: Which theme colour a ``schemeClr`` stands for (the master's own mapping is the identity for all but every deck).
_SCHEME = {"bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2"}
_ALIGN = {"l": "left", "ctr": "center", "r": "right", "just": "justify"}
#: What a colour element can say that moves the colour away from the one named, which the model cannot hold.
_MODIFIERS = {"lumMod", "lumOff", "tint", "shade", "satMod", "alpha", "hueMod"}


def _a(local: str) -> str:
    return f"{{{_A}}}{local}"


def _p(local: str) -> str:
    return f"{{{_P}}}{local}"


class Theme:
    """The colours of a deck's theme, by the names a file uses for them."""

    def __init__(self, theme_xml: bytes | None = None) -> None:
        self._colours: dict[str, str] = {}
        if theme_xml:
            for scheme in etree.fromstring(theme_xml).iter(_a("clrScheme")):
                for entry in scheme:
                    inner = entry[0] if len(entry) else None
                    value = None if inner is None else inner.get("lastClr") or inner.get("val")
                    if value and _HEX.fullmatch(value):
                        self._colours[etree.QName(entry).localname] = f"#{value.lower()}"

    def colour(self, element: etree._Element) -> tuple[str | None, bool]:
        """The colour a ``solidFill``-like ``element`` names, as ``#rrggbb`` or ``None``, and whether it says more than
        that (a lighter or translucent variant: the named colour is what is read, and that is said to be not all)."""
        inner = element[0] if len(element) else None
        if inner is None:
            return None, False
        more = any(etree.QName(child).localname in _MODIFIERS for child in inner)
        name = etree.QName(inner).localname
        if name == "srgbClr" and _HEX.fullmatch(inner.get("val", "")):
            return f"#{inner.get('val', '').lower()}", more
        if name == "schemeClr":
            value = inner.get("val", "")
            return self._colours.get(_SCHEME.get(value, value)), more
        return None, True


def read_look(shape_element: etree._Element, theme: Theme, units_per_emu: float, *, outline: bool) -> Look:
    """The look of the shape ``shape_element`` (a ``p:sp``). ``outline`` says whether the model gives the object a fill
    and a line (an autoshape does; a text box does not, and what the file draws around one is not shown)."""
    look = Look()
    properties = shape_element.find(_p("spPr"))
    style = shape_element.find(_p("style"))
    _read_fill(look, theme, properties, style)
    _read_line(look, theme, properties, style, units_per_emu)
    effects = None if properties is None else properties.find(_a("effectLst"))
    look.unread |= effects is not None and len(effects) > 0  # a shadow, a glow
    if not outline:
        look.unread |= any(look.outline.get(prop, "none") != "none" for prop in ("fill", "stroke"))
        look.outline.clear()
    _read_words(look, shape_element, theme, style, units_per_emu * _EMU_PER_POINT)
    return look


def _read_fill(look: Look, theme: Theme, properties: etree._Element | None, style: etree._Element | None) -> None:
    drawn = (
        None if properties is None else _first(properties, ("solidFill", "noFill", "gradFill", "pattFill", "blipFill"))
    )
    if drawn is None:
        reference = None if style is None else style.find(_a("fillRef"))
        if reference is not None and reference.get("idx", "0") != "0":
            colour, more = theme.colour(reference)
            if colour:
                look.outline["fill"] = colour
            look.unread |= more
        return
    kind = etree.QName(drawn).localname
    if kind == "noFill":
        look.outline["fill"] = "none"
    elif kind == "solidFill":
        colour, more = theme.colour(drawn)
        if colour:
            look.outline["fill"] = colour
        look.unread |= more or colour is None
    else:
        look.unread = True  # a gradient, a pattern, a picture


def _read_line(
    look: Look, theme: Theme, properties: etree._Element | None, style: etree._Element | None, units_per_emu: float
) -> None:
    line = None if properties is None else properties.find(_a("ln"))
    if line is None:
        reference = None if style is None else style.find(_a("lnRef"))
        if reference is not None and reference.get("idx", "0") != "0":
            colour, more = theme.colour(reference)
            if colour:
                look.outline["stroke"] = colour
            look.unread |= more
        return
    drawn = _first(line, ("solidFill", "noFill", "gradFill", "pattFill"))
    if drawn is not None and etree.QName(drawn).localname == "noFill":
        look.outline["stroke"] = "none"
        return
    if drawn is not None and etree.QName(drawn).localname == "solidFill":
        colour, more = theme.colour(drawn)
        if colour:
            look.outline["stroke"] = colour
        look.unread |= more or colour is None
    elif drawn is not None:
        look.unread = True
    if line.get("w", "").isdigit() and "stroke" in look.outline:
        look.outline["stroke-width"] = f"{max(int(line.get('w', '0')) * units_per_emu, 0.5):.1f}px"
    dash = line.find(_a("prstDash"))
    look.unread |= dash is not None and dash.get("val") != "solid"


def _read_words(
    look: Look, shape_element: etree._Element, theme: Theme, style: etree._Element | None, units_per_point: float
) -> None:
    body = shape_element.find(_p("txBody"))
    if body is None:
        return
    first = next((p for p in body.findall(_a("p")) if any(str(text).strip() for text in p.itertext())), None)
    if first is None:
        return
    said: list[etree._Element | None] = []
    reference = None if style is None else style.find(_a("fontRef"))
    if reference is not None:
        colour, more = theme.colour(reference)
        if colour:
            look.words["color"] = colour
        look.unread |= more
    said.append(body.find(f"{_a('lstStyle')}/{_a('lvl1pPr')}/{_a('defRPr')}"))
    said.append(first.find(f"{_a('r')}/{_a('rPr')}"))
    for properties in said:  # the later one is nearer the words
        if properties is not None:
            _read_run(look, properties, theme, units_per_point)
    paragraph = first.find(_a("pPr"))
    if paragraph is not None and paragraph.get("algn") in _ALIGN:
        look.words["text-align"] = _ALIGN[paragraph.get("algn", "")]


def _read_run(look: Look, properties: etree._Element, theme: Theme, units_per_point: float) -> None:
    if properties.get("sz", "").isdigit():
        look.words["font-size"] = f"{int(properties.get('sz', '0')) / 100 * units_per_point:.1f}px"
    if properties.get("b") in ("1", "true"):
        look.words["font-weight"] = "bold"
    if properties.get("i") in ("1", "true"):
        look.words["font-style"] = "italic"
    fill = properties.find(_a("solidFill"))
    if fill is not None:
        colour, more = theme.colour(fill)
        if colour:
            look.words["color"] = colour
        look.unread |= more or colour is None
    elif properties.find(_a("gradFill")) is not None:
        look.unread = True
    typeface = properties.find(_a("latin"))
    if typeface is not None and (name := typeface.get("typeface", "")) and not name.startswith("+"):
        look.words["font-family"] = f"'{name}'" if " " in name else name


def _first(parent: etree._Element, names: tuple[str, ...]) -> etree._Element | None:
    return next((child for child in parent if etree.QName(child).localname in names), None)
