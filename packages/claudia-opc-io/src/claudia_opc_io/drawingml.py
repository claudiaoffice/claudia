"""What a DrawingML drawing says of itself, the same in a docx, an xlsx and a pptx (D464, D1478): how it is turned,
whether it is cropped, which part a picture draws and whether it is decorative. Each format finds these elements where
it keeps them (``wp:docPr`` or ``xdr:cNvPr``, ``pic:spPr`` or ``xdr:spPr``) and asks here what they say."""

from __future__ import annotations

from lxml import etree

#: The namespaces of the parts of a drawing every format shares.
DRAWINGML = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "asvg": "http://schemas.microsoft.com/office/drawing/2016/SVG/main",
    "adec": "http://schemas.microsoft.com/office/drawing/2017/decorative",
}
#: English Metric Units in a pixel (at 96 to the inch).
EMU_PER_PIXEL = 9525
#: A turn is said in sixty thousandths of a degree.
ANGLE = 60000
#: How Office 2016 and later draw an SVG: the SVG itself, beside an ordinary picture as its fallback.
SVG_URI = "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"
#: The mark that says a drawing is decorative (Office 2019 and later).
DECORATIVE_URI = "{C183D7F6-B498-43B3-948B-1728B52AA6E4}"
_SIDES = ("l", "t", "r", "b")
# (compiled: an element of python-docx has an ``xpath`` of its own, which takes no namespaces)
_SVG = etree.XPath("./a:extLst/a:ext/asvg:svgBlip/@r:embed", namespaces=DRAWINGML)
_DECORATIVE = etree.XPath("./a:extLst/a:ext/adec:decorative/@val", namespaces=DRAWINGML)


def turn_of(transform: etree._Element | None) -> int | None:
    """The whole degrees (clockwise, 0 to 359) an ``a:xfrm`` turns by; ``None`` when it flips the drawing."""
    if transform is None:
        return 0
    if transform.get("flipH") in ("1", "true") or transform.get("flipV") in ("1", "true"):
        return None
    try:
        return round(int(transform.get("rot", "0")) / ANGLE) % 360
    except ValueError:
        return 0


def cropped(source: etree._Element | None) -> bool:
    """Does the ``a:srcRect`` of a picture cut something off it?"""
    return source is not None and any(int(source.get(side, "0") or 0) for side in _SIDES)


def shown_part(blip: etree._Element) -> str:
    """The relationship of the part a picture draws (its ``a:blip``): its SVG when it has one beside the ordinary
    picture, else the picture itself."""
    found = _SVG(blip)
    return str(found[0]) if found else blip.get(f"{{{DRAWINGML['r']}}}embed", "")


def is_decorative(properties: etree._Element | None) -> bool:
    """Does the drawing's ``docPr`` or ``cNvPr`` carry Office's mark of a decorative one?"""
    if properties is None:
        return False
    return "1" in _DECORATIVE(properties)  # type: ignore[operator]


# -- the look of a shape (D465, D1479) ---------------------------------------------------------------------------------
#: The colour a file gives a fill or a line that is not a plain colour (a theme's, a gradient): it is not any colour.
UNKNOWN: tuple[int, int, int] = (-1, -1, -1)
#: A line is this many EMU wide to the point.
EMU_PER_POINT = 12700
#: The name DrawingML gives the outline of each shape of the model, and back.
PRESET = {"circle": "ellipse", "rectangle": "rect", "triangle": "triangle"}
SHAPE_OF = {preset: shape for shape, preset in PRESET.items()}
_A = f"{{{DRAWINGML['a']}}}"

Colour = tuple[int, int, int] | None


def solid(colour: Colour) -> str:
    """The fill of a shape for ``colour`` (``None``: none)."""
    if colour is None:
        return "<a:noFill/>"
    return f'<a:solidFill><a:srgbClr val="{colour[0]:02X}{colour[1]:02X}{colour[2]:02X}"/></a:solidFill>'


def outline(colour: Colour, width: int) -> str:
    """The line round a shape: ``colour`` (``None``: none), ``width`` EMU wide."""
    return f'<a:ln w="{width}">{solid(colour)}</a:ln>' if colour else "<a:ln><a:noFill/></a:ln>"


def _colour_in(properties: etree._Element | None) -> Colour:
    """The colour of the ``a:solidFill`` of ``properties``: ``None`` for none or ``a:noFill``, :data:`UNKNOWN` for one
    that is not plain."""
    if properties is None or properties.find(f"{_A}noFill") is not None:
        return None
    fill = properties.find(f"{_A}solidFill")
    if fill is None:
        return None
    plain = fill.find(f"{_A}srgbClr")
    value = "" if plain is None else plain.get("val", "")
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except ValueError:
        return UNKNOWN


def look_in(properties: etree._Element | None, *, styled: bool) -> tuple[Colour, Colour, int]:
    """``(fill, line, line width in EMU)`` a shape's properties (its ``spPr``) say it has. A shape ``styled`` (it has a
    style of the theme) whose properties do not say is given what the style says: :data:`UNKNOWN`."""
    fill = _colour_in(properties)
    if styled and (properties is None or all(properties.find(f"{_A}{tag}") is None for tag in ("solidFill", "noFill"))):
        fill = UNKNOWN
    line_element = None if properties is None else properties.find(f"{_A}ln")
    line = _colour_in(line_element)
    if styled and line_element is None:
        line = UNKNOWN
    width = 0
    if line is not None and line_element is not None:
        try:
            width = int(line_element.get("w", "0"))
        except ValueError:
            width = 0
    return fill, line, width
