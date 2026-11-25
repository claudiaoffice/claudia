"""Pictures patched into a kept ods file (CODE-66, D1233).

What the person did to the pictures since the file was read is put into the file's own XML, the way the charts are
(:mod:`.ods_chart_patch`, with the same :class:`~.ods_chart_patch.SheetShapes`): a picture that was added is a new
frame in the ``table:shapes`` of its sheet with its bytes under ``Pictures/``, as a fresh export writes it
(:func:`~.ods_pictures.picture_frame`); one that was removed is taken out with the bytes nothing else shows; one that
was moved, made another size or turned gets its place (``svg:x`` and ``svg:y``, or the ``draw:transform`` of a turned
one); one that was renamed or described its ``draw:name`` and ``svg:desc``. A picture a file has in a cell that is
moved or turned is taken out of the cell onto the sheet, as a chart is. ODF 1.3 has no way to say a picture is
decorative: that is reported (``decorative``). The rest of a picture of the file and every picture nobody touched stay
byte for byte as they were.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from lxml import etree

from claudia_computes import VisualObject, WorkbookModel
from claudia_odf_io import NS, XmlPart, qname, update_manifest, xml_safe

from ._pictures import MEDIA_TYPES, PICTURE_KINDS, picture_losses, written_pictures
from ._placed import placed_on_its_sheet, placed_on_their_sheets
from .ods_chart_files import DrawnFrame
from .ods_chart_patch import SheetShapes, describe
from .ods_charts import place_of
from .ods_pictures import part_name, picture_frame
from .xlsx_patch import UnsupportedEdit

_HREF = qname("xlink:href")


def _pictures(model: WorkbookModel) -> dict[str, VisualObject]:
    return {obj.id: obj for obj in model.objects.values() if obj.body.kind in PICTURE_KINDS}


def _href(frame: etree._Element) -> str:
    """The part of the package a frame's picture is (``Pictures/…``), or ``""``."""
    image = frame.find("draw:image", NS)
    return "" if image is None else (image.get(_HREF) or "").removeprefix("./")


class PicturePatch:
    """The pictures of one run of :func:`~claudia_computes_io.apply_edits_to_ods`."""

    def __init__(  # noqa: PLR0913 (the file's parts and sheets, the two models, its pictures, where to say losses)
        self,
        parts: dict[str, bytes],
        shapes: SheetShapes,
        models: tuple[WorkbookModel, WorkbookModel],
        found: Mapping[str, DrawnFrame],
        lose: Callable[[str, str, int], None],
    ) -> None:
        self.parts, self.shapes, self.found, self.lose = parts, shapes, found, lose
        self.part: XmlPart = shapes.part
        self.baseline, self.current = models
        self.gone: set[etree._Element] = set()  # the frames taken out, with those of sheets taken out
        self.listed: dict[str, str] = {}
        self.changed = False

    def run(self) -> bool:
        """Put the changes of the pictures into the file; whether there were any. Raises
        :class:`~claudia_computes_io.UnsupportedEdit` for a baseline that does not know the pictures of the file."""
        old, new = _pictures(self.baseline), _pictures(self.current)
        if sorted(old) != sorted(self.found):
            raise UnsupportedEdit("the baseline is not the workbook this file holds")
        for object_id, was in old.items():
            drawn, now = self.found[object_id], new.get(object_id)
            if drawn.sheet not in self.current.sheets:
                self.gone.add(drawn.frame)  # (the sheet is taken out of the file with its frames)
            elif now is None:
                self.part.remove(drawn.frame)
                self.gone.add(drawn.frame)
            else:
                self._change(drawn, was, now)
        self._forget_unshown({_href(each) for each in self.gone} - {""})
        self._add({object_id for object_id in new if object_id not in old})
        if decorative := sum(1 for obj in new.values() if obj.body.decorative):
            self.lose("decorative", "", decorative)
        if self.listed:
            update_manifest(self.parts, add=self.listed)
        return self.changed or bool(self.gone)

    # -- what is taken out -------------------------------------------------------------------------------------
    def _forget_unshown(self, hrefs: set[str]) -> None:
        """The parts among ``hrefs`` no frame shows any more, out of the package and its manifest."""
        shown = {
            (image.get(_HREF) or "").removeprefix("./")
            for image in self.part.root.iter(qname("draw:image"))
            if not any(ancestor in self.gone for ancestor in image.iterancestors())
        }
        elsewhere = [
            data
            for name, data in self.parts.items()
            if name.endswith(".xml") and name != "content.xml" and not name.startswith("META-INF/")
        ]
        unshown = [
            href
            for href in sorted(hrefs)
            if href not in shown and href in self.parts and not any(href.encode() in data for data in elsewhere)
        ]
        for href in unshown:
            del self.parts[href]
        if unshown:
            update_manifest(self.parts, remove=tuple(unshown))
            self.changed = True

    # -- what is added -----------------------------------------------------------------------------------------
    def _add(self, added: set[str]) -> None:
        """The pictures ``added`` among the drawings of their sheets, in the order they are stacked; what cannot be
        written of them is said (``rendering-pending``, ``svg-fallback``)."""
        placed = placed_on_their_sheets(self.current, added)
        for loss in picture_losses(self.current, placed, rasterised=False):
            self.lose(loss.kind, loss.detail, loss.count)
        pictures = written_pictures(self.current, placed, svg_beside_png=False)
        for number, picture in enumerate(pictures, start=len(self.found) + 1):
            name = part_name(picture)
            if name not in self.parts:
                self.parts[name] = picture.data
                self.listed[name] = MEDIA_TYPES[picture.format]
            self.shapes.put(picture.placed.tab.id, picture_frame(picture, number))
            self.changed = True

    # -- what is changed ---------------------------------------------------------------------------------------
    def _change(self, drawn: DrawnFrame, was: VisualObject, now: VisualObject) -> None:
        before, after = was.body, now.body
        placed = (was.anchor, before.w, before.h, before.rotation) != (now.anchor, after.w, after.h, after.rotation)
        named = before.name != after.name
        said = "" if after.decorative else after.description
        described = ("" if before.decorative else before.description) != said
        attributes = place_of(placed_on_its_sheet(self.current, now), after.rotation) if placed else {}
        if named and after.name:
            attributes["draw:name"] = xml_safe(after.name)
        remove = ["draw:name"] if named and not after.name else []
        frame = drawn.frame
        if placed:
            frame = self.shapes.move(frame, now.anchor.sheet, attributes, remove)
        elif attributes or remove:
            self.part.set_attributes(frame, attributes, remove=remove)
        if described and frame is drawn.frame:
            describe(self.part, frame, said)
        elif described:
            _say(frame, said)
        self.changed |= placed or named or described


def _say(frame: etree._Element, text: str) -> None:
    """What a frame that is not yet in the file says to someone who cannot see it (:func:`.ods_chart_patch.describe`
    for one that is)."""
    for old in [*frame.findall("svg:title", NS), *frame.findall("svg:desc", NS)]:
        frame.remove(old)
    if text:
        etree.SubElement(frame, qname("svg:desc")).text = xml_safe(text)
