"""Text boxes and shapes in a file, shared by every app that writes them (D465, D1479).

Which objects a converter writes as boxes (:func:`is_written`: a text box, and a shape that is a circle, a rectangle or
a triangle, the outlines an office file draws by name), what such a box looks like in values a file holds
(:class:`BoxLook`, from the styles of the model: :func:`look_of`), and the OpenDocument elements of a box: a
``draw:frame`` with a ``draw:text-box`` for a text box, a ``draw:ellipse``, ``draw:rect`` or ``draw:custom-shape`` (the
triangle) for a shape, and the graphic style that gives it its look. A text and a spreadsheet differ only in where the
box stands (in a paragraph, on a sheet) and in how its words are styled; the caller places it.

A box of a file comes in when the model can show it as it is (:func:`held_box`, see :mod:`claudia_core.file_boxes`):
one paragraph of plain words, one of the three outlines, turned by nothing but a rotation. Its colours and line are
read (:func:`box_look`) only to be compared with the look the model gives it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol

from lxml import etree

from claudia_core import (
    ASPECT_TOLERANCE,
    PRIMITIVES,
    SHAPE_LABEL_STYLE,
    ObjectBody,
    Palette,
    StyleBook,
    VisualObject,
    box_body,
    colour_of,
)
from claudia_opc_io import EMU_PER_POINT, UNKNOWN

from .names import NS
from .paragraph import read_text, xml_safe
from .pictures import description_of, size_and_turn
from .transform import inches

#: A pixel (the model's unit, 96 to the inch) is this many points.
POINTS_PER_PIXEL = 0.75
_DEFAULT_LINE_PX = 1.0
_NUMBER = re.compile(r"[\d.]+")
_POINTS_PER_INCH = 72


class Styled(Protocol):
    """A model with styles and a palette: what gives a box its look."""

    styles: StyleBook
    palette: Palette


def is_written(obj: VisualObject) -> bool:
    """Does a converter write ``obj``: a text box, or a shape that is one of the outlines every office format knows?"""
    body = obj.body
    return body.kind == "text" or (body.kind == "shape" and body.shape in PRIMITIVES)


def authored(boxes: Iterable[VisualObject]) -> int:
    """How many of ``boxes`` say who wrote which of their words: what no file keeps (``authorship``)."""
    return sum(
        1
        for obj in boxes
        if obj.body.paragraph is not None and any(run.author is not None for run in obj.body.paragraph.runs)
    )


@dataclass(frozen=True)
class BoxLook:
    """What a box looks like in a file: the colour that fills it and the colour and width (in EMU) of its line; ``None``
    for none, :data:`claudia_opc_io.UNKNOWN` for a colour that is no plain colour."""

    fill: tuple[int, int, int] | None
    line: tuple[int, int, int] | None
    width: int

    def matches(self, other: BoxLook) -> bool:
        """Are the two looks the same to the eye (the widths within a hundredth of a point, which a file rounds)?"""
        return (self.fill, self.line) == (other.fill, other.line) and abs(
            self.width - other.width
        ) <= EMU_PER_POINT // 50


def line_points(value: str | None) -> float:
    """The width a style gives a line (CSS pixels, the first number of ``value``; one pixel when it says none) as
    points."""
    found = _NUMBER.search(value) if value else None
    return (float(found.group()) if found else _DEFAULT_LINE_PX) * POINTS_PER_PIXEL


def look_of(model: Styled, body: ObjectBody) -> BoxLook:
    """The look the styles of ``model`` give the box ``body``: a shape's ``fill``, ``stroke`` and ``stroke-width``, a
    text box's ``background-color`` and ``border`` (a translucent colour flattened over the page, which a solid fill
    cannot hold)."""
    colours = model.palette.colours()
    css = model.styles.resolved(body.style, colours)
    page = colours.get("page")
    if body.kind == "shape":
        fill, line = colour_of(css, "fill", page), colour_of(css, "stroke", page)
        width = line_points(css.get("stroke-width"))
    else:
        fill = colour_of(css, "background-color", page)
        border = css.get("border")
        line = colour_of({"border": border}, "border", page) if border else None
        width = line_points(border)
    return BoxLook(fill, line, round(width * EMU_PER_POINT) if line else 0)


# ------------------------------------------------------------------------------------------------------ OpenDocument
#: The name an OpenDocument file gives the outline of each shape of the model (an ellipse and a rectangle are elements
#: of their own).
_TRIANGLE = "isosceles-triangle"
_GEOMETRY = {"rectangle": "rectangle", "ellipse": "ellipse", _TRIANGLE: "triangle"}
_BASIC = {"rect": "rectangle", "ellipse": "circle", "circle": "circle"}
_TRIANGLE_GEOMETRY = (
    '<draw:enhanced-geometry xmlns:draw="{draw}" xmlns:svg="{svg}" svg:viewBox="0 0 21600 21600" '
    'draw:type="isosceles-triangle" draw:text-areas="5400 10800 16200 21600" '
    'draw:enhanced-path="M 10800 0 L 21600 21600 0 21600 10800 0 Z N"/>'
)
_WORDS = ("p", "h")
_ALLOWED = {
    ("svg", "desc"),
    ("svg", "title"),
    ("draw", "text-box"),
    ("draw", "enhanced-geometry"),
    ("text", "p"),
    ("text", "h"),
}


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def odf_properties(element: etree._Element, graphics: Mapping[str, etree._Element]) -> dict[str, str]:
    """What the graphic style of ``element`` (and the styles it is based on) says, by ``prefix:name``; what the
    element's own style says wins over what its parents say."""
    found: dict[str, str] = {}
    name: str | None = element.get(_q("draw", "style-name"))
    seen: set[str] = set()
    while name and name in graphics and name not in seen:
        seen.add(name)
        style = graphics[name]
        for properties in style.findall("style:graphic-properties", NS):
            for key, value in properties.attrib.items():
                uri, local = etree.QName(key).namespace, etree.QName(key).localname
                short = next((each for each, known in NS.items() if known == uri), "")
                found.setdefault(f"{short}:{local}", str(value))
        name = style.get(_q("style", "parent-style-name"))
    return found


def _hex(value: str | None) -> tuple[int, int, int] | None:
    """``#rrggbb`` as red, green and blue; ``None`` when it is not."""
    if value and len(value) == 7 and value.startswith("#"):
        try:
            return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)
        except ValueError:
            return None
    return None


def _emu(length: str | None) -> int:
    found = inches(length)
    return 0 if found is None else round(found * _POINTS_PER_INCH * EMU_PER_POINT)


def box_look(element: etree._Element, graphics: Mapping[str, etree._Element]) -> BoxLook:
    """The fill and the line a box says it has: ``draw:fill`` and ``draw:stroke`` (or, of a frame,
    ``fo:background-color`` and ``fo:border``); what it does not say is no colour anyone knows."""
    found = odf_properties(element, graphics)
    fill: tuple[int, int, int] | None = UNKNOWN
    if "draw:fill" in found:
        fill = None if found["draw:fill"] == "none" else _hex(found.get("draw:fill-color")) or UNKNOWN
    elif "fo:background-color" in found:
        fill = None if found["fo:background-color"] == "transparent" else _hex(found["fo:background-color"]) or UNKNOWN
    line: tuple[int, int, int] | None = UNKNOWN
    width = 0
    if "draw:stroke" in found:
        line = None if found["draw:stroke"] == "none" else _hex(found.get("svg:stroke-color")) or UNKNOWN
        width = _emu(found.get("svg:stroke-width"))
    elif "fo:border" in found:
        parts = found["fo:border"].split()
        line = None if parts[0] == "none" else (_hex(parts[-1]) or UNKNOWN)
        width = _emu(parts[0])
    return BoxLook(fill, line, width if line is not None else 0)


def _words_in(holder: etree._Element) -> tuple[str, etree._Element | None] | None:
    """``(the words, the paragraph)`` of ``holder`` (a ``draw:text-box`` or a shape) that has none or one paragraph of
    words; ``None`` when it has more or its paragraph holds anything shown but text."""
    paragraphs = [
        child
        for child in holder
        if isinstance(child.tag, str)
        and etree.QName(child).localname in _WORDS
        and etree.QName(child).namespace == NS["text"]
    ]
    if len(paragraphs) > 1:
        return None
    if not paragraphs:
        return "", None
    paragraph = paragraphs[0]
    if any(isinstance(child.tag, str) and etree.QName(child).namespace == NS["draw"] for child in paragraph.iter()):
        return None
    return read_text(paragraph), paragraph


def _only_known(element: etree._Element) -> bool:
    """Has ``element`` nothing in it the model has no place for (another shape, a glue point, a chart)?"""
    for child in element:
        if not isinstance(child.tag, str):
            continue
        name = etree.QName(child)
        key = next((each for each, uri in NS.items() if uri == name.namespace), ""), name.localname
        if key not in _ALLOWED:
            return False
    return True


def _shape_of(element: etree._Element) -> tuple[str | None, bool] | None:
    """``(the shape of the model, whether it is a text box)`` of ``element`` -- a ``draw:frame`` with a text box, a
    ``draw:rect``, ``draw:ellipse`` or ``draw:custom-shape`` of one of the three outlines -- or ``None``."""
    tag = etree.QName(element).localname
    if tag == "frame":
        return (None, True) if element.find("draw:text-box", NS) is not None and _only_known(element) else None
    if not _only_known(element) or element.find("draw:enhanced-geometry", NS) is not None and tag != "custom-shape":
        return None
    if tag in _BASIC:
        flat = (
            _q("draw", "corner-radius"),
            _q("svg", "rx"),
            _q("svg", "ry"),
            _q("draw", "start-angle"),
            _q("draw", "end-angle"),
        )
        return None if any(key in element.attrib for key in flat) else (_BASIC[tag], False)
    geometry = element.find("draw:enhanced-geometry", NS)
    kind = _GEOMETRY.get(geometry.get(_q("draw", "type"), "")) if geometry is not None else None
    return None if kind is None else ("circle" if kind == "ellipse" else kind, False)


def held_box(
    element: etree._Element,
    graphics: Mapping[str, etree._Element],
    words_style: Callable[[etree._Element, str | None], str],
    *,
    plain_words: str,
) -> tuple[ObjectBody, BoxLook] | None:
    """The box the model holds for ``element`` (with its id left ``""``), and what the file says it looks like; ``None``
    when it is not one the model shows as it is. ``words_style(paragraph, shape)`` is the style of its words; a text
    box without a paragraph has ``plain_words``, a shape the shape label's."""
    found = _shape_of(element)
    if found is None:
        return None
    shape, is_box = found
    holder = element.find("draw:text-box", NS) if is_box else element
    assert holder is not None
    words = _words_in(holder)
    placed = size_and_turn(element)
    if words is None or placed is None:
        return None
    size, rotation = placed
    if shape == "circle" and abs(size[0] - size[1]) > ASPECT_TOLERANCE:
        return None
    text, paragraph = words
    style = words_style(paragraph, shape) if paragraph is not None else (SHAPE_LABEL_STYLE if shape else plain_words)
    body = box_body(
        "", size, text, style, shape=None if is_box else shape, description=description_of(element), rotation=rotation
    )
    return body, box_look(element, graphics)


def _colour(rgb: tuple[int, int, int] | None) -> str:
    assert rgb is not None
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def graphic_properties(kind: str, look: BoxLook) -> str:
    """The attributes of the ``style:graphic-properties`` that give a box of ``kind`` (``"text"`` or ``"shape"``)
    ``look``: its fill, its line, and its words inside it (a text box's at its top left, a shape's in its middle), at
    the size the box has (a program would else fit the box to its words)."""
    fill = f'draw:fill="solid" draw:fill-color="{_colour(look.fill)}"' if look.fill else 'draw:fill="none"'
    if look.line:
        width = f"{look.width / EMU_PER_POINT:.4g}pt"
        line = f'draw:stroke="solid" svg:stroke-color="{_colour(look.line)}" svg:stroke-width="{width}"'
    else:
        line = 'draw:stroke="none"'
    fixed = 'draw:auto-grow-height="false" draw:auto-grow-width="false"'
    inside = (
        f'fo:padding="0cm" {fixed}'
        if kind == "text"
        else f'{fixed} draw:textarea-vertical-align="middle" draw:textarea-horizontal-align="center"'
    )
    return f"{fill} {line} {inside}"


def default_name(body: ObjectBody, number: int) -> str:
    """What a file calls the ``number``-th box that has no name of its own: "Text box n" or "Shape n"."""
    return f"{'Text box' if body.kind == 'text' else 'Shape'} {number}"


def box_element(body: ObjectBody, style: str, name: str, words: etree._Element | None) -> etree._Element:
    """The ``draw:frame`` (a text box) or the shape element of ``body``, drawn with the graphic style ``style``, called
    ``name``, with ``words`` (its paragraph, written by the caller) in it; the caller places it."""
    is_box = body.kind == "text"
    tag = "frame" if is_box else {"circle": "ellipse", "rectangle": "rect"}.get(body.shape or "", "custom-shape")
    element = etree.Element(_q("draw", tag), nsmap={prefix: NS[prefix] for prefix in ("draw", "svg", "xlink", "text")})
    element.set(_q("draw", "style-name"), style)
    element.set(_q("draw", "name"), xml_safe(name))
    if is_box:
        text_box = etree.SubElement(element, _q("draw", "text-box"))
        if words is not None:
            text_box.append(words)
    else:
        if words is not None and body.paragraph is not None and body.paragraph.text:
            element.append(words)
        if tag == "custom-shape":
            element.append(etree.fromstring(_TRIANGLE_GEOMETRY.format(draw=NS["draw"], svg=NS["svg"])))
    if body.description and not body.decorative:  # (ODF 1.3 has no mark for decoration: see the losses)
        etree.SubElement(element, _q("svg", "desc")).text = xml_safe(body.description)
    return element
