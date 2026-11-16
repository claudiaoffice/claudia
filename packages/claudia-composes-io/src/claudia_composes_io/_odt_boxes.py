"""The text boxes and shapes floating over a text, in an odt (D465): a ``draw:frame`` with a ``draw:text-box`` in it for
a text box, a ``draw:ellipse``, ``draw:rect`` or ``draw:custom-shape`` (the triangle) for a shape, standing in the
paragraph at the character the box hangs from and wrapping nothing (the words do not flow around it, as the model has
it). Written, read back as objects and changed in a kept file.

A box of a file comes in when the model can show it as it is (see :mod:`claudia_core.file_boxes`): one paragraph of
plain words, a circle, a rectangle or a triangle, turned by nothing but a rotation. Its colours and line are not read:
the model gives it the look of its styles, and a file whose box looks otherwise says ``look``. Everything else stays in
the file and is reported as a ``frame``.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import cast

from lxml import etree

from claudia_composes import TextModel
from claudia_core import (
    ASPECT_TOLERANCE,
    MIN_OBJECT_SIZE,
    SHAPE_LABEL_STYLE,
    ObjectBody,
    VisualObject,
    box_body,
)
from claudia_odf_io import (
    NS,
    LossLog,
    description_element,
    description_of,
    detach,
    frames_of,
    inches,
    insert_elements,
    offset_of,
    read_text,
    shapes_of,
    transform_of,
    turned_box,
    xml_safe,
)

from ._boxes import EMU_PER_POINT, UNKNOWN, BoxLook, all_boxes, boxes_of, look_of
from ._odt_pictures import _cm, _drop, _pixels, _q

#: The name an odt gives the outline of each shape of the model (an ellipse and a rectangle are elements of their own).
_TRIANGLE = "isosceles-triangle"
_GEOMETRY = {"rectangle": "rectangle", "ellipse": "ellipse", _TRIANGLE: "triangle"}
_BASIC = {"rect": "rectangle", "ellipse": "circle", "circle": "circle"}
_TRIANGLE_GEOMETRY = (
    '<draw:enhanced-geometry xmlns:draw="{draw}" xmlns:svg="{svg}" svg:viewBox="0 0 21600 21600" '
    'draw:type="isosceles-triangle" draw:text-areas="5400 10800 16200 21600" '
    'draw:enhanced-path="M 10800 0 L 21600 21600 0 21600 10800 0 Z N"/>'
)
_NAME = "Claudia_box_"
_POINTS_PER_INCH = 72
_WORDS = ("p", "h")
#: The graphic style properties of every box (as of every picture): nothing wraps round it, it stands in front of the
#: text at the top left of its paragraph.
_PLACE = (
    'style:wrap="none" style:run-through="foreground" style:horizontal-pos="from-left" '
    'style:horizontal-rel="paragraph" style:vertical-pos="from-top" style:vertical-rel="paragraph"'
)


@dataclass(frozen=True)
class FileBox:
    """A text box or a shape of a file the model holds: where it is and what the file says of it."""

    object_id: str
    block: int  # the index of the paragraph among the paragraphs of the text
    offset: int  # the characters of the paragraph before the element
    element: etree._Element
    body: ObjectBody
    look: BoxLook


def _hex(value: str | None) -> tuple[int, int, int] | None:
    """``#rrggbb`` as red, green and blue; ``None`` when it is not."""
    if value and len(value) == 7 and value.startswith("#"):
        try:
            return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)
        except ValueError:
            return None
    return None


def _properties(element: etree._Element, graphics: Mapping[str, etree._Element]) -> dict[str, str]:
    """What the graphic style of ``element`` (and the styles it is based on) says, by ``prefix:name``."""
    found: dict[str, str] = {}
    name: str | None = element.get(_q("draw", "style-name"))
    seen: set[str] = set()
    while name and name in graphics and name not in seen:
        seen.add(name)
        style = graphics[name]
        for properties in style.findall("style:graphic-properties", NS):
            for key, value in properties.attrib.items():
                prefix, local = etree.QName(key).namespace, etree.QName(key).localname
                short = next((each for each, uri in NS.items() if uri == prefix), "")
                found.setdefault(f"{short}:{local}", str(value))
        name = style.get(_q("style", "parent-style-name"))
    return found


def _looks(element: etree._Element, graphics: Mapping[str, etree._Element]) -> BoxLook:
    """The fill and the line a box says it has: ``draw:fill`` and ``draw:stroke`` (or, of a frame,
    ``fo:background-color`` and ``fo:border``); what it does not say is no colour anyone knows."""
    found = _properties(element, graphics)
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


def _emu(length: str | None) -> int:
    found = inches(length)
    return 0 if found is None else round(found * _POINTS_PER_INCH * EMU_PER_POINT)


def _words_in(holder: etree._Element) -> tuple[str, etree._Element | None] | None:
    """``(the words, the paragraph)`` of ``holder`` (a ``draw:text-box`` or a shape) that has none or one paragraph of
    words; ``None`` when it has more or its paragraph holds anything shown but text."""
    paragraphs = [
        child
        for child in holder
        if etree.QName(child).localname in _WORDS and etree.QName(child).namespace == NS["text"]
    ]
    if len(paragraphs) > 1:
        return None
    if not paragraphs:
        return "", None
    paragraph = paragraphs[0]
    if any(isinstance(child.tag, str) and etree.QName(child).namespace == NS["draw"] for child in paragraph.iter()):
        return None
    return read_text(paragraph), paragraph


_ALLOWED = {
    ("svg", "desc"),
    ("svg", "title"),
    ("draw", "text-box"),
    ("draw", "enhanced-geometry"),
    ("text", "p"),
    ("text", "h"),
}


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
) -> tuple[ObjectBody, BoxLook] | None:
    """The box the model holds for ``element`` (with its id left ``""``), and what the file says it looks like; ``None``
    when it is not one the model shows as it is."""
    found = _shape_of(element)
    if found is None:
        return None
    shape, is_box = found
    holder = element.find("draw:text-box", NS) if is_box else element
    assert holder is not None
    words = _words_in(holder)
    width, height = _pixels(element.get(_q("svg", "width"))), _pixels(element.get(_q("svg", "height")))
    if words is None or width is None or height is None:
        return None
    size = (round(width), round(height))
    rotation = 0
    if transform := element.get(_q("draw", "transform")):
        turned = turned_box(transform, width, height)
        if turned is None:
            return None
        rotation = round(turned[0]) % 360
    if min(size) < MIN_OBJECT_SIZE or (shape == "circle" and abs(size[0] - size[1]) > ASPECT_TOLERANCE):
        return None
    text, paragraph = words
    style = words_style(paragraph, shape) if paragraph is not None else (SHAPE_LABEL_STYLE if shape else "body")
    body = box_body(
        "", size, text, style, shape=None if is_box else shape, description=description_of(element), rotation=rotation
    )
    return body, _looks(element, graphics)


def file_boxes(
    paragraphs: list[etree._Element],
    graphics: Mapping[str, etree._Element],
    words_style: Callable[[etree._Element, str | None], str],
) -> list[FileBox]:
    """The text boxes and shapes of ``paragraphs`` (the paragraphs of the text, in order) that the model holds, in the
    order of the file; the ``n``-th is the object ``x{n}``."""
    found: list[FileBox] = []
    for index, paragraph in enumerate(paragraphs):
        elements = sorted(
            [*frames_of(paragraph), *shapes_of(paragraph)], key=lambda each: offset_of(paragraph, each) or 0
        )
        for element in elements:
            held = held_box(element, graphics, words_style)
            offset = offset_of(paragraph, element)
            if held is None or offset is None:
                continue
            object_id = f"x{len(found) + 1}"
            found.append(FileBox(object_id, index, offset, element, replace(held[0], id=object_id), held[1]))
    return found


# ------------------------------------------------------------------------------------------------------ writing
class BoxStyles:
    """The graphic styles of the boxes a file gets: one for each look, named after the ones the file has."""

    def __init__(self, taken: set[str] | None = None) -> None:
        self._taken = taken if taken is not None else set()
        self._by_look: dict[tuple[str, BoxLook], str] = {}
        self.new: list[bytes] = []  # the styles to add to the file, as XML

    def name_of(self, kind: str, look: BoxLook) -> str:
        """The name of the style of a box of ``kind`` (``"text"`` or ``"shape"``) that looks like ``look``."""
        key = (kind, look)
        if key not in self._by_look:
            number = len(self._by_look) + 1
            while f"{_NAME}{number}" in self._taken:
                number += 1
            name = f"{_NAME}{number}"
            self._taken.add(name)
            self._by_look[key] = name
            self.new.append(self._xml(name, kind, look).encode())
        return self._by_look[key]

    @staticmethod
    def _xml(name: str, kind: str, look: BoxLook) -> str:
        fill = f'draw:fill="solid" draw:fill-color="{_colour(look.fill)}"' if look.fill else 'draw:fill="none"'
        if look.line:
            width = f"{look.width / EMU_PER_POINT:.4g}pt"
            line = f'draw:stroke="solid" svg:stroke-color="{_colour(look.line)}" svg:stroke-width="{width}"'
        else:
            line = 'draw:stroke="none"'
        fixed = 'draw:auto-grow-height="false" draw:auto-grow-width="false"'  # (else a program fits it to its words)
        inside = (
            f'fo:padding="0cm" {fixed}'
            if kind == "text"
            else f'{fixed} draw:textarea-vertical-align="middle" draw:textarea-horizontal-align="center"'
        )
        return (
            f'<style:style xmlns:style="{NS["style"]}" xmlns:draw="{NS["draw"]}" xmlns:svg="{NS["svg"]}" '
            f'xmlns:fo="{NS["fo"]}" style:name="{name}" style:family="graphic">'
            f"<style:graphic-properties {fill} {line} {inside} {_PLACE}/></style:style>"
        )


def _colour(rgb: tuple[int, int, int] | None) -> str:
    assert rgb is not None
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


class BoxWriter:
    """Writes the elements of text box and shape objects: the frame or the shape with its words in a paragraph of the
    style the model gives them. ``paragraph_of(style id, text)`` makes that paragraph."""

    def __init__(self, model: TextModel, styles: BoxStyles, paragraph_of: Callable[[str, str], etree._Element]) -> None:
        self.model, self.styles, self.paragraph_of = model, styles, paragraph_of
        self._number = 0

    def element(self, obj: VisualObject) -> etree._Element:
        """The ``draw:frame`` (a text box) or the shape element that is ``obj``."""
        body = obj.body
        self._number += 1
        is_box = body.kind == "text"
        tag = "frame" if is_box else {"circle": "ellipse", "rectangle": "rect"}.get(body.shape or "", "custom-shape")
        element = etree.Element(
            _q("draw", tag), nsmap={prefix: NS[prefix] for prefix in ("draw", "svg", "xlink", "text")}
        )
        element.set(_q("draw", "style-name"), self.styles.name_of(body.kind, look_of(self.model, body)))
        element.set(_q("draw", "name"), f"{'Text box' if is_box else 'Shape'} {self._number}")
        element.set(_q("text", "anchor-type"), "char")
        element.set(_q("draw", "z-index"), str(self._number))
        _place(element, body.w, body.h, body.rotation)
        words = body.paragraph
        inner = self.paragraph_of(words.style, xml_safe(words.text)) if words is not None else None
        if is_box:
            text_box = etree.SubElement(element, _q("draw", "text-box"))
            if inner is not None:
                text_box.append(inner)
        else:
            if inner is not None and words is not None and words.text:
                element.append(inner)
            if tag == "custom-shape":
                geometry = etree.fromstring(_TRIANGLE_GEOMETRY.format(draw=NS["draw"], svg=NS["svg"]))
                element.append(geometry)
        if body.description and not body.decorative:  # (ODF 1.3 has no mark for decoration: see the losses)
            etree.SubElement(element, _q("svg", "desc")).text = xml_safe(body.description)
        return element


def _place(element: etree._Element, w: int, h: int, rotation: int) -> None:
    """Give ``element`` its size and turn (and the place at the top left of its paragraph that an unturned one has)."""
    element.set(_q("svg", "width"), _cm(w))
    element.set(_q("svg", "height"), _cm(h))
    turn = transform_of(rotation, (0.0, 0.0, w / 96 * 2.54, h / 96 * 2.54))
    if turn is None:
        element.set(_q("svg", "x"), "0cm")
        element.set(_q("svg", "y"), "0cm")
        _drop(element, _q("draw", "transform"))
    else:
        element.set(_q("draw", "transform"), turn)
        _drop(element, _q("svg", "x"))
        _drop(element, _q("svg", "y"))


# ------------------------------------------------------------------------------------------------------ changing
def _same_but(before: ObjectBody, after: ObjectBody) -> bool:
    """Do ``before`` and ``after`` differ in nothing but what :func:`restyle` can change in place?"""
    return (before.kind, before.shape, before.style) == (after.kind, after.shape, after.style)


def restyle(
    box: FileBox,
    element: etree._Element,
    before: ObjectBody,
    after: ObjectBody,
    paragraph_of: Callable[[str, str], etree._Element],
) -> None:
    """Give ``element`` (a copy of the box's) the description, the size, the turn and the words of ``after``; what did
    not change from ``before`` stays as the file has it."""
    if (before.description, before.decorative) != (after.description, after.decorative):
        found = description_element(element)
        wanted = "" if after.decorative else after.description
        if wanted:
            if found is None:
                found = etree.SubElement(element, _q("svg", "desc"))
            found.text = xml_safe(wanted)
        elif found is not None:
            element.remove(found)
    if (before.w, before.h, before.rotation) != (after.w, after.h, after.rotation):
        _place(element, after.w, after.h, after.rotation)
    if before.paragraph != after.paragraph and after.paragraph is not None:
        holder = element.find("draw:text-box", NS) if after.kind == "text" else element
        assert holder is not None
        for old in [each for each in holder if each.tag in (_q("text", "p"), _q("text", "h"))]:
            holder.remove(old)
        inner = paragraph_of(after.paragraph.style, xml_safe(after.paragraph.text))
        if after.kind == "text" or after.paragraph.text:
            holder.insert(0, inner)


def _look(body: ObjectBody) -> tuple[object, ...]:
    """What of a box :func:`restyle` can change."""
    return body.description, body.decorative, body.w, body.h, body.rotation, body.paragraph


class BoxPlan:
    """What the boxes of a kept file need for the edits from ``baseline`` to ``current``: the elements of boxes that
    went are taken out, those that changed get their description, size, turn and words, those whose paragraph is written
    again are put back where the text says, one whose outline or style changed is drawn anew (with the look of its
    style) and new ones are drawn.

    ``block_ids`` are the ids of the blocks of the paragraphs of the file, in order. :attr:`touched` are the blocks
    whose paragraph has to be written again for the boxes' sake."""

    def __init__(
        self,
        in_file: list[FileBox],
        block_ids: list[str],
        baseline: TextModel,
        current: TextModel,
        writer: BoxWriter,
        losses: LossLog | None = None,
    ) -> None:
        self.baseline, self.current, self.losses, self.writer = baseline, current, losses, writer
        self.written = 0  # how many elements were drawn anew
        self.in_file: dict[str, list[FileBox]] = {}
        self.kept: dict[str, FileBox] = {}
        self.touched: set[str] = set()
        wanted = all_boxes(current)
        for box in in_file:
            block = block_ids[box.block]
            self.in_file.setdefault(block, []).append(box)
            now = wanted.get(box.object_id)
            before = baseline.get_object(box.object_id)
            if now is None or not _same_but(before.body, now.body):  # gone, or drawn anew where it hangs now
                self.touched.add(block)
                if now is not None:
                    self.touched.add(now.anchor.block)
                    if self.losses is not None and not box.look.matches(look_of(baseline, before.body)):
                        self.losses.add("look")
                continue
            self.kept[box.object_id] = box
            if now.anchor != before.anchor or _look(now.body) != _look(before.body):
                self.touched |= {block, now.anchor.block}
        self.touched |= {obj.anchor.block for obj_id, obj in wanted.items() if obj_id not in self.kept}

    def has_any(self, block_id: str) -> bool:
        """Does the paragraph of ``block_id`` have boxes, or is it to get some?"""
        return block_id in self.in_file or bool(boxes_of(self.current, block_id))

    def take_out(self, paragraph: etree._Element, original: etree._Element, block_id: str) -> None:
        """Take the elements of the boxes the file had out of ``paragraph`` (a copy of ``original``), to be put back by
        :meth:`hang` once its words are written."""
        mine, theirs = _drawn(original), _drawn(paragraph)
        for box in self.in_file.get(block_id, []):
            detach(theirs[mine.index(box.element)])

    def hang(self, paragraph: etree._Element, block_id: str, at: Callable[[int], int]) -> None:
        """Put the elements of the boxes of ``block_id`` into ``paragraph`` at ``at(offset)``: those the file had (a
        copy of the element, changed as the box changed), the new ones drawn."""
        marks: list[tuple[int, etree._Element]] = []
        for obj in boxes_of(self.current, block_id):
            box = self.kept.get(obj.id)
            if box is not None:
                element = copy.deepcopy(box.element)
                element.tail = None
                restyle(box, element, self.baseline.get_object(obj.id).body, obj.body, self.writer.paragraph_of)
            else:
                element = self.writer.element(obj)
                self.written += 1
            if self.losses is not None and obj.body.decorative:  # (ODF 1.3 has no mark for it)
                self.losses.add("decorative")
            marks.append((at(obj.anchor.offset), element))
        insert_elements(paragraph, marks)


def _drawn(paragraph: etree._Element) -> list[etree._Element]:
    """The frames and the shapes of ``paragraph``, in order."""
    return sorted([*frames_of(paragraph), *shapes_of(paragraph)], key=lambda each: offset_of(paragraph, each) or 0)


def graphic_style_names(*roots: etree._Element | None) -> set[str]:
    """The names of the graphic styles of the parts ``roots``."""
    return {
        cast(str, style.get(_q("style", "name")))
        for root in roots
        if root is not None
        for style in root.iter(_q("style", "style"))
        if style.get(_q("style", "family")) == "graphic" and style.get(_q("style", "name"))
    }
