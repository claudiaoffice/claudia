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

from claudia_composes import DEFAULT_STYLE, DEFAULT_WRAP_GAP, ParagraphAnchor, TextModel
from claudia_core import (
    ObjectBody,
    VisualObject,
)
from claudia_odf_io import (
    NS,
    BoxLook,
    LossLog,
    box_element,
    default_name,
    description_element,
    detach,
    frames_of,
    graphic_properties,
    held_box,
    insert_elements,
    look_of,
    odf_properties,
    offset_of,
    shapes_of,
    xml_safe,
)

from ._boxes import all_boxes, boxes_of, shown_words
from ._odt_pictures import _q
from ._wrap import ODF_POSITION, WrapStyles, odf_attributes, odf_offset_of, odf_place, odf_wrap_of

_NAME = "Claudia_box_"
#: Where every box (as every picture) stands: its place is measured from its character and line. How the text flows
#: round it is not here but the box's own (:func:`claudia_composes_io._wrap.odf_attributes`).
_PLACE = ODF_POSITION


@dataclass(frozen=True)
class FileBox:
    """A text box or a shape of a file the model holds: where it is and what the file says of it."""

    object_id: str
    paragraph: int  # the index of the paragraph among the paragraphs of the text
    offset: int  # the characters of the paragraph before the element
    element: etree._Element
    body: ObjectBody
    look: BoxLook
    wrap: str = "over"  # how the text flows round it (D1061) ...
    gap: int = DEFAULT_WRAP_GAP  # ... and how far the words keep from it
    dx: int = 0  # how far off its character it sits, to the right ...
    dy: int = 0  # ... and down (D1067)


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
            held = held_box(element, graphics, words_style, plain_words=DEFAULT_STYLE)
            offset = offset_of(paragraph, element)
            if held is None or offset is None:
                continue
            object_id = f"x{len(found) + 1}"
            properties = odf_properties(element, graphics)
            wrap = (*odf_wrap_of(properties), *odf_offset_of(element, properties))
            found.append(FileBox(object_id, index, offset, element, replace(held[0], id=object_id), held[1], *wrap))
    return found


# ------------------------------------------------------------------------------------------------------ writing
class BoxStyles:
    """The graphic styles of the boxes a file gets: one for each look, named after the ones the file has."""

    def __init__(self, taken: set[str] | None = None) -> None:
        self._taken = taken if taken is not None else set()
        self._by_look: dict[tuple[str, BoxLook, str, int], str] = {}
        self.new: list[bytes] = []  # the styles to add to the file, as XML

    def name_of(self, kind: str, look: BoxLook, anchor: ParagraphAnchor | None = None) -> str:
        """The name of the style of a box of ``kind`` (``"text"`` or ``"shape"``) that looks like ``look`` and has
        the text flow round it as ``anchor`` says (over it, when there is none)."""
        anchor = anchor if anchor is not None else ParagraphAnchor("", 0)
        key = (kind, look, anchor.wrap, anchor.gap)
        if key not in self._by_look:
            number = len(self._by_look) + 1
            while f"{_NAME}{number}" in self._taken:
                number += 1
            name = f"{_NAME}{number}"
            self._taken.add(name)
            self._by_look[key] = name
            self.new.append(self._xml(name, kind, look, anchor).encode())
        return self._by_look[key]

    @staticmethod
    def _xml(name: str, kind: str, look: BoxLook, anchor: ParagraphAnchor) -> str:
        return (
            f'<style:style xmlns:style="{NS["style"]}" xmlns:draw="{NS["draw"]}" xmlns:svg="{NS["svg"]}" '
            f'xmlns:fo="{NS["fo"]}" style:name="{name}" style:family="graphic"><style:graphic-properties '
            f"{graphic_properties(kind, look)} {_PLACE} {odf_attributes(anchor)}/></style:style>"
        )


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
        style = self.styles.name_of(body.kind, look_of(self.model, body), obj.anchor)
        words = body.paragraph
        inner = self.paragraph_of(words.style, xml_safe(shown_words(self.model, words))) if words is not None else None
        name = default_name(body, self._number)
        element = box_element(body, style, name, inner)
        element.set(_q("text", "anchor-type"), "char")
        element.set(_q("draw", "z-index"), str(self._number))
        odf_place(element, body.w, body.h, body.rotation, dx=obj.anchor.dx, dy=obj.anchor.dy)
        return element


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
        odf_place(element, after.w, after.h, after.rotation, dx=box.dx, dy=box.dy)
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

    ``paragraph_ids`` are the ids of the text's paragraphs for the paragraphs of the file, in order. :attr:`touched` are
    the paragraphs whose element in the file has to be written again for the boxes' sake."""

    def __init__(
        self,
        in_file: list[FileBox],
        paragraph_ids: list[str],
        baseline: TextModel,
        current: TextModel,
        writer: BoxWriter,
        losses: LossLog | None = None,
        wraps: WrapStyles | None = None,
    ) -> None:
        self.baseline, self.current, self.losses, self.writer = baseline, current, losses, writer
        self.wraps = wraps if wraps is not None else WrapStyles()  # (the styles for boxes whose wrapping changed)
        self.written = 0  # how many elements were drawn anew
        self.in_file: dict[str, list[FileBox]] = {}
        self.kept: dict[str, FileBox] = {}
        self.touched: set[str] = set()
        wanted = all_boxes(current)
        for box in in_file:
            paragraph = paragraph_ids[box.paragraph]
            self.in_file.setdefault(paragraph, []).append(box)
            now = wanted.get(box.object_id)
            before = baseline.get_object(box.object_id)
            if now is None or not _same_but(before.body, now.body):  # gone, or drawn anew where it hangs now
                self.touched.add(paragraph)
                if now is not None:
                    self.touched.add(now.anchor.paragraph)
                    if self.losses is not None and not box.look.matches(look_of(baseline, before.body)):
                        self.losses.add("look")
                continue
            self.kept[box.object_id] = box
            if now.anchor != before.anchor or _look(now.body) != _look(before.body):
                self.touched |= {paragraph, now.anchor.paragraph}
        self.touched |= {obj.anchor.paragraph for obj_id, obj in wanted.items() if obj_id not in self.kept}

    def has_any(self, paragraph_id: str) -> bool:
        """Does the paragraph of ``paragraph_id`` have boxes, or is it to get some?"""
        return paragraph_id in self.in_file or bool(boxes_of(self.current, paragraph_id))

    def take_out(self, paragraph: etree._Element, original: etree._Element, paragraph_id: str) -> None:
        """Take the elements of the boxes the file had out of ``paragraph`` (a copy of ``original``), to be put back by
        :meth:`hang` once its words are written."""
        mine, theirs = _drawn(original), _drawn(paragraph)
        for box in self.in_file.get(paragraph_id, []):
            detach(theirs[mine.index(box.element)])

    def hang(self, paragraph: etree._Element, paragraph_id: str, at: Callable[[int], int]) -> None:
        """Put the elements of the boxes of ``paragraph_id`` into ``paragraph`` at ``at(offset)``: those the file had (a
        copy of the element, changed as the box changed), the new ones drawn."""
        marks: list[tuple[int, etree._Element]] = []
        for obj in boxes_of(self.current, paragraph_id):
            box = self.kept.get(obj.id)
            if box is not None:
                element = copy.deepcopy(box.element)
                element.tail = None
                restyle(box, element, self.baseline.get_object(obj.id).body, obj.body, self.writer.paragraph_of)
                before = self.baseline.get_object(obj.id).anchor
                wrapped = (obj.anchor.wrap, obj.anchor.gap) != (before.wrap, before.gap)
                moved = (obj.anchor.dx, obj.anchor.dy) != (before.dx, before.dy)
                if wrapped or moved:
                    self.wraps.give(element, obj.anchor, wrap=wrapped, position=moved)
                if moved:
                    body = obj.body
                    odf_place(element, body.w, body.h, body.rotation, dx=obj.anchor.dx, dy=obj.anchor.dy)
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
