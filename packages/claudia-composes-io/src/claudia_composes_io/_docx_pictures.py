"""The pictures floating over a text, in a docx (D464): written as a drawing in a run of the paragraph they hang from,
read back as image objects, and changed in a kept file.

A picture of the model is written as an *anchored* drawing that does not wrap the text (the words do not flow around it,
as the model has it): its place is the character of the paragraph the run stands at. A picture of a file comes in when
the model can show it as it is (see :mod:`claudia_core.file_pictures`): an image the app decodes, not cropped, not
flipped, in the proportions of the picture itself; an inline picture comes in too (it floats in the model). What the
file says of it -- its alt text, whether Word's mark says it is decorative, the size and the turn -- becomes the
object's. Everything else stays in the file and is reported as ``picture``.
"""

from __future__ import annotations

from collections.abc import Callable, Container, Mapping
from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.part import Part
from docx.oxml import parse_xml
from docx.oxml.ns import qn
from lxml import etree

from claudia_composes import TextModel
from claudia_core import (
    MIN_OBJECT_SIZE,
    ImageAsset,
    ObjectBody,
    Rasterise,
    VisualObject,
    asset_of,
    blank_png,
    keeps_proportions,
    picture_body,
)
from claudia_odf_io import LossLog

from ._pictures import all_pictures

#: English Metric Units in a pixel (the model's units are pixels at 96 to the inch).
EMU = 9525
#: A turn in the file is in sixtieths of a degree.
_ANGLE = 60000
_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "asvg": "http://schemas.microsoft.com/office/drawing/2016/SVG/main",
    "adec": "http://schemas.microsoft.com/office/drawing/2017/decorative",
}
_PICTURE_URI = "http://schemas.openxmlformats.org/drawingml/2006/picture"
#: How a picture is drawn in Word 2016 and later: the SVG itself, next to an ordinary picture as its fallback.
_SVG_BLIP_URI = "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"
#: The mark that says a picture is decorative (Word 2019 and later).
_DECORATIVE_URI = "{C183D7F6-B498-43B3-948B-1728B52AA6E4}"


def _xpath(expression: str) -> Callable[[Any], list[Any]]:
    """An XPath over the namespaces of a docx, typed as what it gives for the paths used here: a list."""
    return etree.XPath(expression, namespaces=_NS)  # type: ignore[return-value]


_DRAWINGS = _xpath(".//w:drawing")
_GRAPHIC = _xpath("(./wp:inline | ./wp:anchor)/a:graphic/a:graphicData[@uri='" + _PICTURE_URI + "']/pic:pic")
_FRAME = _xpath("./wp:inline | ./wp:anchor")
_BLIP = _xpath("./pic:blipFill/a:blip")
_SVG = _xpath("./a:extLst/a:ext/asvg:svgBlip/@r:embed")
_CROP = _xpath("./pic:blipFill/a:srcRect")
_TRANSFORM = _xpath("./pic:spPr/a:xfrm")
_DOC_PR = _xpath("./wp:docPr")
_DECORATIVE = _xpath("./a:extLst/a:ext/adec:decorative/@val")
_ALL_DOC_PR = _xpath("//wp:docPr/@id")
_SMALL_FRAME_ENTRIES = ("l", "t", "r", "b")


@dataclass(frozen=True)
class FilePicture:
    """A picture of a file the model holds: where it is, the run that carries it, what the file says of it."""

    object_id: str
    block: int  # the index of the paragraph among the paragraphs of the document
    offset: int  # the characters of the paragraph before the run
    run: Any  # the ``w:r`` that holds the drawing
    drawing: Any  # the ``w:drawing``
    asset: ImageAsset
    size: tuple[int, int]
    rotation: int
    description: str
    decorative: bool
    name: str

    @property
    def body(self) -> ObjectBody:
        """The image object the file's picture is."""
        return picture_body(
            self.object_id,
            self.asset,
            self.size,
            name=self.name,
            description=self.description,
            decorative=self.decorative,
            rotation=self.rotation,
        )


def pixels(emu: str | None) -> int:
    """A length in EMU as pixels (``0`` when the file gives none)."""
    try:
        return round(int(emu or 0) / EMU)
    except ValueError:
        return 0


def _first(found: list[Any]) -> Any:  # noqa: ANN401 (lxml's own element types)
    return found[0] if found else None


def _graphic_of(drawing: Any) -> Any:  # noqa: ANN401
    """The ``pic:pic`` of a ``w:drawing`` that holds exactly one picture, else ``None``."""
    frames = _FRAME(drawing)
    pictures = _GRAPHIC(drawing)
    return pictures[0] if len(frames) == 1 and len(pictures) == 1 else None


def _blob_of(part: Any, blip: Any) -> bytes | None:  # noqa: ANN401
    """What the picture draws: its SVG when it has one next to the ordinary picture, else the picture itself."""
    related = _first(_SVG(blip)) or blip.get(qn("r:embed"))
    try:
        return part.related_parts[related].blob
    except KeyError:
        return None


def _turn_of(transform: Any) -> int | None:  # noqa: ANN401
    """The whole degrees (clockwise, 0 to 359) a ``a:xfrm`` turns by; ``None`` when it flips the picture."""
    if transform is None:
        return 0
    if transform.get("flipH") in ("1", "true") or transform.get("flipV") in ("1", "true"):
        return None
    try:
        return round(int(transform.get("rot", "0")) / _ANGLE) % 360
    except ValueError:
        return 0


def held_picture(part: Any, drawing: Any) -> tuple[ImageAsset, tuple[int, int], int, str, bool, str] | None:  # noqa: ANN401
    """What the model holds of a ``w:drawing`` of ``part`` (the document part): ``(asset, size, rotation, description,
    decorative, name)``; ``None`` when it is not a picture the model shows as it is."""
    picture = _graphic_of(drawing)
    if picture is None:
        return None
    frame = _FRAME(drawing)[0]
    blip = _first(_BLIP(picture))
    extent = frame.find(qn("wp:extent"))
    crop = _first(_CROP(picture))
    if blip is None or extent is None:
        return None
    if crop is not None and any(int(crop.get(side, "0") or 0) for side in _SMALL_FRAME_ENTRIES):
        return None
    rotation = _turn_of(_first(_TRANSFORM(picture)))
    asset = asset_of(_blob_of(part, blip))
    size = (pixels(extent.get("cx")), pixels(extent.get("cy")))
    if rotation is None or asset is None or min(size) < MIN_OBJECT_SIZE or not keeps_proportions(asset, *size):
        return None
    properties = _first(_DOC_PR(frame))
    description = properties.get("descr", "") if properties is not None else ""
    decorative = properties is not None and "1" in _DECORATIVE(properties)
    name = properties.get("name", "") if properties is not None else ""
    return asset, size, rotation, description, decorative, name


def text_length(child: Any) -> int:  # noqa: ANN401
    """How many characters of the paragraph's text a child of a ``w:p`` stands for (what python-docx's own
    ``paragraph.text`` counts: the runs and the hyperlinks, nothing in a tracked change)."""
    return len(child.text) if child.tag in (qn("w:r"), qn("w:hyperlink")) else 0


def offset_of(paragraph: Any, run: Any) -> int:  # noqa: ANN401
    """The characters of ``paragraph`` (a ``w:p``) before ``run``, one of its own runs."""
    position = 0
    for child in paragraph:
        if child is run:
            break
        position += text_length(child)
    return position


def file_pictures(document: Any) -> list[FilePicture]:  # noqa: ANN401
    """The pictures of the paragraphs of ``document`` that the model holds, in the order of the file; the ``n``-th is
    the object ``o{n}``. A picture in a table, a header or a text box is not among them."""
    found: list[FilePicture] = []
    part = document.part
    for index, paragraph in enumerate(document.paragraphs):
        for run in paragraph._p.findall(qn("w:r")):
            drawings = run.findall(qn("w:drawing"))
            if len(drawings) != 1:
                continue
            held = held_picture(part, drawings[0])
            if held is None:
                continue
            asset, size, rotation, description, decorative, name = held
            found.append(
                FilePicture(
                    f"o{len(found) + 1}",
                    index,
                    offset_of(paragraph._p, run),
                    run,
                    drawings[0],
                    asset,
                    size,
                    rotation,
                    description,
                    decorative,
                    name,
                )
            )
    return found


def unheld_pictures(document: Any, held: list[FilePicture]) -> int:  # noqa: ANN401
    """How many pictures of the file the model does not show as they are (cropped, flipped, stretched, in a table)."""
    kept = {id(each.drawing) for each in held}
    return sum(
        1
        for drawing in _DRAWINGS(document.element.body)
        if id(drawing) not in kept and _graphic_of(drawing) is not None
    )


# ------------------------------------------------------------------------------------------------------ writing
class PictureWriter:
    """Writes the pictures of image objects into a document: the drawing of each, with the picture in a part of its
    own (once for the same bytes)."""

    def __init__(self, document: Any, rasterise: Rasterise | None = None) -> None:  # noqa: ANN401
        self.document, self.rasterise = document, rasterise
        taken = [int(value) for value in _ALL_DOC_PR(document.element) if value.isdigit()]
        self.next_id = max(taken, default=0) + 1
        self.svg_parts: dict[str, str] = {}

    def run(self, obj: VisualObject, asset: ImageAsset) -> Any:  # noqa: ANN401
        """The ``w:r`` that carries the drawing of ``obj`` showing ``asset``."""
        body = obj.body
        width, height = body.w * EMU, body.h * EMU
        picture_id, svg_id = self._relations(asset, body)
        number, self.next_id = self.next_id, self.next_id + 1
        name = _escape(body.imported.source_name if body.imported is not None and body.imported.source_name else "")
        title = name or f"Picture {number}"
        alt = "" if body.decorative else _escape(body.description)
        extensions = (
            f'<a:extLst><a:ext uri="{_SVG_BLIP_URI}"><asvg:svgBlip xmlns:asvg="{_NS["asvg"]}" r:embed="{svg_id}"/>'
            "</a:ext></a:extLst>"
            if svg_id
            else ""
        )
        decorative = (
            f'<a:extLst><a:ext uri="{_DECORATIVE_URI}"><adec:decorative xmlns:adec="{_NS["adec"]}" val="1"/></a:ext>'
            "</a:extLst>"
            if body.decorative
            else ""
        )
        turn = f' rot="{body.rotation * _ANGLE}"' if body.rotation else ""
        xml = (
            f'<w:r xmlns:w="{_NS["w"]}" xmlns:wp="{_NS["wp"]}" xmlns:a="{_NS["a"]}" xmlns:pic="{_NS["pic"]}" '
            f'xmlns:r="{_NS["r"]}"><w:drawing>'
            f'<wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="{number}" '
            'behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">'
            '<wp:simplePos x="0" y="0"/>'
            '<wp:positionH relativeFrom="column"><wp:posOffset>0</wp:posOffset></wp:positionH>'
            '<wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset></wp:positionV>'
            f'<wp:extent cx="{width}" cy="{height}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
            f'<wp:docPr id="{number}" name="{title}" descr="{alt}">{decorative}</wp:docPr>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            f'<a:graphic><a:graphicData uri="{_PICTURE_URI}"><pic:pic>'
            f'<pic:nvPicPr><pic:cNvPr id="{number}" name="{title}" descr="{alt}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{picture_id}">{extensions}</a:blip>'
            "<a:stretch><a:fillRect/></a:stretch></pic:blipFill>"
            f'<pic:spPr><a:xfrm{turn}><a:off x="0" y="0"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            "</pic:pic></a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>"
        )
        return parse_xml(xml)

    def _relations(self, asset: ImageAsset, body: ObjectBody) -> tuple[str, str | None]:
        """The relationship ids of the picture the drawing shows and of its SVG (``None`` when it is not one). An SVG is
        shown by a picture that every program draws, ``rasterise`` made of it or else an empty one."""
        part = self.document.part
        if asset.format != "svg":
            return part.get_or_add_image(BytesIO(asset.data))[0], None
        shown = self.rasterise(asset.data, body.w, body.h) if self.rasterise is not None else blank_png(body.w, body.h)
        if asset.id not in self.svg_parts:
            name = part.package.next_partname("/word/media/svg%d.svg")
            self.svg_parts[asset.id] = part.relate_to(Part(name, "image/svg+xml", asset.data, part.package), RT.IMAGE)
        return part.get_or_add_image(BytesIO(shown))[0], self.svg_parts[asset.id]


def _escape(text: str) -> str:
    """``text`` as the value of an XML attribute."""
    return escape(text, {'"': "&quot;", "\n": "&#10;"})


# ------------------------------------------------------------------------------------------------------ placing
def _plain_text_run(child: Any) -> bool:  # noqa: ANN401
    """Is ``child`` a run of nothing but one piece of text (which can be cut in two)?"""
    if child.tag != qn("w:r"):
        return False
    content = [each for each in child if each.tag != qn("w:rPr")]
    return len(content) == 1 and content[0].tag == qn("w:t")


def place(paragraph: Any, offset: int, run: Any) -> None:  # noqa: ANN401
    """Put ``run`` into ``paragraph`` (a ``w:p``) after ``offset`` characters of its text: between the runs, or in the
    middle of one run of text, which is cut in two (both halves keep its formatting). A place inside anything that
    cannot be cut (a hyperlink, a run with a tab) is the place after it. What stands at the place already stays before
    ``run``."""
    after: Any = None  # the child ``run`` goes behind: the properties of the paragraph, or what is before the place
    position = 0
    for child in paragraph:
        if child.tag == qn("w:pPr"):
            after = child
            continue
        length = text_length(child)
        if position + length <= offset:
            after, position = child, position + length
            continue
        if offset > position:
            after = _cut(child, offset - position) if _plain_text_run(child) else child
        break
    if after is None:
        paragraph.insert(0, run)
    else:
        after.addnext(run)


def _cut(child: Any, at: int) -> Any:  # noqa: ANN401
    """Cut the text run ``child`` after ``at`` characters; the first half."""
    text = child.find(qn("w:t"))
    whole = text.text or ""
    second = deepcopy(child)
    text.text, second.find(qn("w:t")).text = whole[:at], whole[at:]
    for piece in (text, second.find(qn("w:t"))):
        piece.set(qn("xml:space"), "preserve")
    child.addnext(second)
    return child


def interleave(paragraph: Any, marks: list[tuple[int, Any]]) -> None:  # noqa: ANN401
    """Put the runs of ``marks`` (``(offset, run)``) into ``paragraph``, each after its characters; those at the same
    place keep their order."""
    for offset, run in sorted(marks, key=lambda mark: mark[0]):
        place(paragraph, offset, run)


# ------------------------------------------------------------------------------------------------------ changing
def restyle(picture: FilePicture, before: ObjectBody, after: ObjectBody) -> None:
    """Give the drawing of ``picture`` the description, the decorative mark, the size and the turn of ``after`` (what
    changed from ``before``; what did not stays as the file has it)."""
    frame = _FRAME(picture.drawing)[0]
    properties = _first(_DOC_PR(frame))
    shown = _graphic_of(picture.drawing)
    names = [properties, _first(_xpath("./pic:nvPicPr/pic:cNvPr")(shown))]
    if (before.description, before.decorative) != (after.description, after.decorative):
        for each in names:
            if each is not None:
                each.set("descr", "" if after.decorative else after.description)
        if properties is not None:
            _mark_decorative(properties, after.decorative)
    if (before.w, before.h) != (after.w, after.h):
        cx, cy = str(after.w * EMU), str(after.h * EMU)
        frame.find(qn("wp:extent")).set("cx", cx)
        frame.find(qn("wp:extent")).set("cy", cy)
        transform = _first(_TRANSFORM(shown))
        if transform is not None and (extent := transform.find(qn("a:ext"))) is not None:
            extent.set("cx", cx)
            extent.set("cy", cy)
    if before.rotation != after.rotation:
        transform = _first(_TRANSFORM(shown))
        if transform is not None:
            if after.rotation:
                transform.set("rot", str(after.rotation * _ANGLE))
            elif "rot" in transform.attrib:
                del transform.attrib["rot"]


def _mark_decorative(properties: Any, decorative: bool) -> None:  # noqa: ANN401
    """Say in the ``wp:docPr`` that its picture is decorative, or take the mark off."""
    for each in properties.findall(qn("a:extLst")):
        for ext in each.findall(qn("a:ext")):
            if ext.get("uri") == _DECORATIVE_URI:
                each.remove(ext)
        if not len(each):
            properties.remove(each)
    if decorative:
        properties.append(
            parse_xml(
                f'<a:extLst xmlns:a="{_NS["a"]}"><a:ext uri="{_DECORATIVE_URI}">'
                f'<adec:decorative xmlns:adec="{_NS["adec"]}" val="1"/></a:ext></a:extLst>'
            )
        )


def take_out(picture: FilePicture, document: Any) -> None:  # noqa: ANN401
    """Take the drawing of ``picture`` out of the file; its run too when nothing else is in it, and the relationship of
    its picture when nothing else shows it."""
    relationships = {value for value in _xpath(".//@r:embed")(picture.drawing) if isinstance(value, str)}
    run = picture.run
    run.remove(picture.drawing)
    if not [each for each in run if each.tag != qn("w:rPr")]:
        run.getparent().remove(run)
    for relationship in relationships:
        document.part.drop_rel(relationship)


class PictureEdits:
    """What the pictures of a kept file need for the edits from ``baseline`` to ``current``: the drawings of pictures
    that went are taken out, those that changed get their alt text, size and turn, those that moved or hang from a
    paragraph whose words are written again are lifted out to be put back where the text says, and new ones are drawn.

    ``rewritten`` says which paragraphs (by block id) get their words written again: the pictures of those are handed
    over as ``marks`` for the writer of the paragraph; those of the others are put in place afterwards (:meth:`settle`).
    ``changed`` says whether the package's relationships and content types changed too."""

    def __init__(
        self,
        document: Any,  # noqa: ANN401
        baseline: TextModel,
        current: TextModel,
        rewritten: Container[str],
        rasterise: Rasterise | None,
        losses: LossLog | None = None,
    ) -> None:
        self.document, self.rewritten = document, rewritten
        self.losses, self.rasterised = losses, rasterise is not None
        self.marks: dict[str, list[tuple[int, Any]]] = {}
        self.loose: dict[str, list[tuple[int, Any]]] = {}
        self.changed = False
        self.writer = PictureWriter(document, rasterise)
        wanted = all_pictures(current)
        in_file = file_pictures(document)
        new = dict(wanted)
        for picture in in_file:
            new.pop(picture.object_id, None)
            self._edit(picture, wanted.get(picture.object_id), baseline, new)
        for obj, asset in new.values():
            self._route(obj, self.writer.run(obj, asset))
            if self.losses is not None and asset.format == "svg" and not self.rasterised:
                self.losses.add("svg-fallback")  # (the picture every program draws is an empty one)
            self.changed = True

    def _edit(
        self,
        picture: FilePicture,
        now: tuple[VisualObject, ImageAsset] | None,
        baseline: TextModel,
        new: dict[str, tuple[VisualObject, ImageAsset]],
    ) -> None:
        if now is None:
            take_out(picture, self.document)
            self.changed = True
            return
        obj, asset = now
        before = baseline.get_object(picture.object_id)
        if asset.id != before.body.image:  # another picture: the old one goes, the new one is drawn
            take_out(picture, self.document)
            new[obj.id] = now
            self.changed = True
            return
        restyle(picture, before.body, obj.body)
        if obj.anchor.block in self.rewritten or obj.anchor != before.anchor:
            picture.run.getparent().remove(picture.run)
            self._route(obj, picture.run)

    def _route(self, obj: VisualObject, run: Any) -> None:  # noqa: ANN401
        where = self.marks if obj.anchor.block in self.rewritten else self.loose
        where.setdefault(obj.anchor.block, []).append((obj.anchor.offset, run))

    def settle(self, paragraph_of: Mapping[str, Any]) -> None:
        """Put the pictures of the paragraphs that were not written again into them (``paragraph_of``: the ``w:p`` of
        each block id)."""
        for block_id, marks in self.loose.items():
            interleave(paragraph_of[block_id], marks)
