"""The pictures floating over a text, in an odt (D464): a ``draw:frame`` with a ``draw:image`` in it, standing in the
paragraph at the character the picture hangs from, wrapping nothing (the words do not flow around it, as the model has
it). Written, read back as image objects and changed in a kept file.

A picture of a file comes in when the model can show it as it is (see :mod:`claudia_core.file_pictures` and
:func:`claudia_odf_io.picture_of`): an image the app decodes whose bytes are in the package, not cropped, in the
proportions of the picture itself, turned by nothing but a rotation. What the file says of it (``svg:desc``, or else
``svg:title``) is its description. Everything else stays in the file and is reported as ``picture``.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from itertools import count

from lxml import etree

from claudia_composes import TextModel
from claudia_core import (
    MIN_OBJECT_SIZE,
    ImageAsset,
    ObjectBody,
    Rasterise,
    VisualObject,
    keeps_proportions,
    picture_body,
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
    name_of,
    offset_of,
    picture_of,
    transform_of,
    turned_box,
    xml_safe,
)

from ._pictures import all_pictures, pictures_of

_PX_PER_INCH = 96
_CM_PER_INCH = 2.54
#: The name of the style of the frame of a picture: no wrapping, in front of the text, at the top left of its paragraph.
PICTURE_STYLE = "Claudia_20_picture"
PICTURE_STYLE_XML = (
    f'<style:style xmlns:style="{NS["style"]}" xmlns:text="{NS["text"]}" style:name="{PICTURE_STYLE}" '
    'style:family="graphic"><style:graphic-properties style:wrap="none" style:run-through="foreground" '
    'style:horizontal-pos="from-left" style:horizontal-rel="paragraph" '
    'style:vertical-pos="from-top" style:vertical-rel="paragraph"/></style:style>'
)
_EXTENSION = {"jpeg": "jpg"}
_MEDIA_TYPE = {"svg": "image/svg+xml", "png": "image/png", "jpeg": "image/jpeg", "gif": "image/gif", "bmp": "image/bmp"}


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def graphic_styles(*roots: etree._Element | None) -> dict[str, etree._Element]:
    """Every style of graphics of the parts ``roots`` (content and styles), by name."""
    found: dict[str, etree._Element] = {}
    for root in roots:
        if root is None:
            continue
        for style in root.iter(_q("style", "style")):
            name = style.get(_q("style", "name"))
            if name and style.get(_q("style", "family")) == "graphic":
                found[name] = style
    return found


@dataclass(frozen=True)
class FilePicture:
    """A picture of a file the model holds: where it is and what the file says of it."""

    object_id: str
    block: int  # the index of the paragraph among the paragraphs of the text
    offset: int  # the characters of the paragraph before the frame
    frame: etree._Element
    asset: ImageAsset
    size: tuple[int, int]
    rotation: int
    description: str
    name: str
    href: str

    @property
    def body(self) -> ObjectBody:
        """The image object the file's picture is."""
        return picture_body(
            self.object_id,
            self.asset,
            self.size,
            name=self.name,
            description=self.description,
            rotation=self.rotation,
        )


def _pixels(length: str | None) -> float | None:
    found = inches(length)
    return None if found is None else found * _PX_PER_INCH


def held_frame(
    frame: etree._Element, graphics: Mapping[str, etree._Element], parts: Mapping[str, bytes]
) -> tuple[ImageAsset, tuple[int, int], int] | None:
    """``(asset, size in pixels, rotation)`` of a ``draw:frame`` that is a picture the model shows as it is, else
    ``None``."""
    asset = picture_of(frame, graphics, parts)
    width, height = _pixels(frame.get(_q("svg", "width"))), _pixels(frame.get(_q("svg", "height")))
    if asset is None or width is None or height is None:
        return None
    size = (round(width), round(height))
    rotation = 0
    if transform := frame.get(_q("draw", "transform")):
        turned = turned_box(transform, width, height)
        if turned is None:
            return None
        rotation = round(turned[0]) % 360
    if min(size) < MIN_OBJECT_SIZE or not keeps_proportions(asset, *size):
        return None
    return asset, size, rotation


def file_pictures(
    paragraphs: list[etree._Element], graphics: Mapping[str, etree._Element], parts: Mapping[str, bytes]
) -> list[FilePicture]:
    """The pictures of ``paragraphs`` (the paragraphs of the text, in order) that the model holds, in the order of the
    file; the ``n``-th is the object ``o{n}``."""
    found: list[FilePicture] = []
    for index, paragraph in enumerate(paragraphs):
        for frame in frames_of(paragraph):
            held = held_frame(frame, graphics, parts)
            offset = offset_of(paragraph, frame)
            if held is None or offset is None:
                continue
            asset, size, rotation = held
            href = (frame.find("draw:image", NS).get(_q("xlink", "href")) or "").removeprefix("./")  # type: ignore[union-attr]
            found.append(
                FilePicture(
                    f"o{len(found) + 1}",
                    index,
                    offset,
                    frame,
                    asset,
                    size,
                    rotation,
                    description_of(frame),
                    name_of(frame),
                    href,
                )
            )
    return found


def unheld_pictures(
    paragraphs: list[etree._Element], held: list[FilePicture], graphics: Mapping[str, etree._Element]
) -> int:
    """How many frames of ``paragraphs`` hold a picture (one image in them) the model does not show as it is."""
    kept = {id(each.frame) for each in held}
    return sum(
        1
        for paragraph in paragraphs
        for frame in frames_of(paragraph)
        if id(frame) not in kept and frame.find("draw:image", NS) is not None
    )


def frames_not_pictures(paragraph: etree._Element) -> int:
    """How many frames of ``paragraph`` hold no image (a text box, a chart, a formula)."""
    return sum(1 for frame in frames_of(paragraph) if frame.find("draw:image", NS) is None)


# ------------------------------------------------------------------------------------------------------ writing
def _cm(pixels: float) -> str:
    """A length in pixels as centimetres, to four places."""
    text = f"{pixels / _PX_PER_INCH * _CM_PER_INCH:.4f}".rstrip("0").rstrip(".")
    return f"{text or '0'}cm"


class PictureWriter:
    """Writes the frames of image objects; collects the pictures' own bytes for the package."""

    def __init__(self, rasterise: Rasterise | None = None, taken: set[str] | None = None) -> None:
        self.rasterise = rasterise
        self.parts: dict[str, bytes] = {}  # what to add to the package, by name
        self.media_types: dict[str, str] = {}
        self._hrefs: dict[str, str] = {}
        self._taken = taken if taken is not None else set()
        self._numbers = count(1)

    def frame(self, obj: VisualObject, asset: ImageAsset) -> etree._Element:
        """The ``draw:frame`` that shows ``asset`` for ``obj``."""
        body = obj.body
        number = next(self._numbers)
        frame = etree.Element(
            _q("draw", "frame"), nsmap={prefix: NS[prefix] for prefix in ("draw", "svg", "xlink", "text")}
        )
        frame.set(_q("draw", "style-name"), PICTURE_STYLE)
        frame.set(_q("draw", "name"), f"Picture {number}")
        frame.set(_q("text", "anchor-type"), "char")
        frame.set(_q("draw", "z-index"), str(number))
        frame.set(_q("svg", "width"), _cm(body.w))
        frame.set(_q("svg", "height"), _cm(body.h))
        turn = transform_of(
            body.rotation, (0.0, 0.0, body.w / _PX_PER_INCH * _CM_PER_INCH, body.h / _PX_PER_INCH * _CM_PER_INCH)
        )
        if turn is None:
            frame.set(_q("svg", "x"), "0cm")
            frame.set(_q("svg", "y"), "0cm")
        else:
            frame.set(_q("draw", "transform"), turn)
        image = etree.SubElement(frame, _q("draw", "image"))
        for name, value in (
            ("href", self._href(asset, body)),
            ("type", "simple"),
            ("show", "embed"),
            ("actuate", "onLoad"),
        ):
            image.set(_q("xlink", name), value)
        if body.description and not body.decorative:  # (ODF 1.3 has no mark for decoration: see the losses)
            etree.SubElement(frame, _q("svg", "desc")).text = xml_safe(body.description)
        return frame

    def _href(self, asset: ImageAsset, body: ObjectBody) -> str:
        """The name in the package of the picture ``asset`` shows as: itself, or for a rendered text container the
        picture ``rasterise`` draws of its SVG when there is one."""
        if asset.format == "svg" and self.rasterise is not None and body.kind == "rendered":
            href = f"Pictures/{asset.id}-{body.w}x{body.h}.png"
            if href not in self.parts:
                self.parts[href] = self.rasterise(asset.data, body.w, body.h)
                self.media_types[href] = "image/png"
            return href
        if asset.id not in self._hrefs:
            href = f"Pictures/{re.sub(r'[^A-Za-z0-9_-]', '_', asset.id)}.{_EXTENSION.get(asset.format, asset.format)}"
            while href in self._taken:
                href = href.replace("Pictures/", "Pictures/c")
            self._hrefs[asset.id] = href
            self.parts[href] = asset.data
            self.media_types[href] = _MEDIA_TYPE.get(asset.format, "application/octet-stream")
        return self._hrefs[asset.id]


# ------------------------------------------------------------------------------------------------------ changing
def restyle(picture: FilePicture, before: ObjectBody, after: ObjectBody) -> None:
    """Give the frame of ``picture`` (a copy) the description, the size and the turn of ``after``; what did not change
    from ``before`` stays as the file has it."""
    frame = picture.frame
    if (before.description, before.decorative) != (after.description, after.decorative):
        found = description_element(frame)
        wanted = "" if after.decorative else after.description
        if wanted:
            if found is None:
                found = etree.SubElement(frame, _q("svg", "desc"))
            found.text = xml_safe(wanted)
        elif found is not None:
            frame.remove(found)
    if (before.w, before.h) != (after.w, after.h) or before.rotation != after.rotation:
        frame.set(_q("svg", "width"), _cm(after.w))
        frame.set(_q("svg", "height"), _cm(after.h))
        turn = transform_of(
            after.rotation, (0.0, 0.0, after.w / _PX_PER_INCH * _CM_PER_INCH, after.h / _PX_PER_INCH * _CM_PER_INCH)
        )
        x = frame.get(_q("svg", "x"))
        if turn is None:
            _drop(frame, _q("draw", "transform"))
            if x is None:
                frame.set(_q("svg", "x"), "0cm")
                frame.set(_q("svg", "y"), "0cm")
        else:
            frame.set(_q("draw", "transform"), turn)
            _drop(frame, _q("svg", "x"))
            _drop(frame, _q("svg", "y"))


def _drop(element: etree._Element, name: str) -> None:
    """Take the attribute ``name`` off ``element`` when it has it."""
    if name in element.attrib:
        del element.attrib[name]


def _look(body: ObjectBody) -> tuple[str, bool, int, int, int]:
    """What of a picture :func:`restyle` can change."""
    return body.description, body.decorative, body.w, body.h, body.rotation


class PicturePlan:
    """What the pictures of a kept file need for the edits from ``baseline`` to ``current``: the frames of pictures that
    went are taken out (and their image, when nothing else shows it), those that changed get their description, size and
    turn, those whose paragraph is written again are put back where the text says, and new ones are drawn.

    ``block_ids`` are the ids of the blocks of the paragraphs of the file, in order; ``taken`` the names of the parts
    the package has. :attr:`touched` are the blocks whose paragraph has to be written again for the pictures' sake."""

    def __init__(
        self,
        in_file: list[FilePicture],
        block_ids: list[str],
        baseline: TextModel,
        current: TextModel,
        rasterise: Rasterise | None,
        taken: set[str],
        losses: LossLog | None = None,
    ) -> None:
        self.baseline, self.current, self.losses, self.rasterised = baseline, current, losses, rasterise is not None
        self.writer = PictureWriter(rasterise, taken)
        self.written = 0  # how many frames were drawn anew
        self.in_file: dict[str, list[FilePicture]] = {}
        self.kept: dict[str, FilePicture] = {}
        self.touched: set[str] = set()
        self.removed: set[str] = set()  # the names in the package of the pictures that went
        wanted = all_pictures(current)
        for picture in in_file:
            block = block_ids[picture.block]
            self.in_file.setdefault(block, []).append(picture)
            now = wanted.get(picture.object_id)
            before = baseline.get_object(picture.object_id)
            if now is None or now[1].id != before.body.image:  # gone, or another picture: the old one goes
                self.touched.add(block)
                self.removed.add(picture.href)
                continue
            self.kept[picture.object_id] = picture
            if now[0].anchor != before.anchor or _look(now[0].body) != _look(before.body):
                self.touched |= {block, now[0].anchor.block}
        self.touched |= {obj.anchor.block for obj_id, (obj, _) in wanted.items() if obj_id not in self.kept}

    def has_any(self, block_id: str) -> bool:
        """Does the paragraph of ``block_id`` have frames of pictures, or is it to get some?"""
        return block_id in self.in_file or bool(pictures_of(self.current, block_id))

    def take_out(self, paragraph: etree._Element, original: etree._Element, block_id: str) -> None:
        """Take the frames of the pictures the file had out of ``paragraph`` (a copy of ``original``), to be put back
        by :meth:`hang` once its words are written (in the paragraph they hang from now, which can be another)."""
        mine, theirs = frames_of(original), frames_of(paragraph)
        for picture in self.in_file.get(block_id, []):
            detach(theirs[mine.index(picture.frame)])

    def hang(self, paragraph: etree._Element, block_id: str, at: Callable[[int], int]) -> None:
        """Put the frames of the pictures of ``block_id`` into ``paragraph`` at ``at(offset)`` -- where the text says
        each hangs, in the words as written: those the file had (a copy of the frame, taken out of its paragraph
        before) changed as they changed, the new ones drawn."""
        marks: list[tuple[int, etree._Element]] = []
        for obj, asset in pictures_of(self.current, block_id):
            picture = self.kept.get(obj.id)
            if picture is not None:
                frame = copy.deepcopy(picture.frame)
                frame.tail = None
                restyle(replace(picture, frame=frame), self.baseline.get_object(obj.id).body, obj.body)
            else:
                frame = self.writer.frame(obj, asset)
                self.written += 1
                if (
                    self.losses is not None
                    and obj.body.kind == "rendered"
                    and asset.format == "svg"
                    and not self.rasterised
                ):
                    self.losses.add("svg-picture")
            if self.losses is not None and obj.body.decorative:  # (ODF 1.3 has no mark for it)
                self.losses.add("decorative")
            marks.append((at(obj.anchor.offset), frame))
        insert_elements(paragraph, marks)
