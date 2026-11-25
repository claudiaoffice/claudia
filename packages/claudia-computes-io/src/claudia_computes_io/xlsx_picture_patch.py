"""Pictures patched into a kept xlsx file (CODE-66, D1233).

What the person did to the pictures since the file was read is put into the drawings of its sheets, the way the charts
are (:mod:`.xlsx_chart_patch`, with the same :class:`~.xlsx_chart_patch.Drawings`): a picture that was added is a new
anchor with its bytes, as a fresh export writes it (:func:`~.xlsx_pictures.picture_anchor`); one that was removed is
taken out with the bytes nothing else shows; one that was moved or made another size is pinned to its cell again, one
that was turned has the turn of its ``a:xfrm``, and one that was renamed or described has its ``cNvPr`` changed. The
rest of a picture of the file -- a border, an effect, a link -- and every picture nobody touched stay as they were.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from lxml import etree

from claudia_computes import ObjectBody, SheetId, VisualObject, WorkbookModel
from claudia_odf_io import xml_safe
from claudia_opc_io import ANGLE, DECORATIVE_URI, mark_decorative

from ._pictures import PICTURE_KINDS, picture_losses, written_pictures
from ._placed import placed_on_its_sheet, placed_on_their_sheets
from .xlsx_chart_patch import Drawings
from .xlsx_charts import NS, DrawnAnchor, emu
from .xlsx_patch import UnsupportedEdit
from .xlsx_read import q


def _pictures(model: WorkbookModel) -> dict[str, VisualObject]:
    return {obj.id: obj for obj in model.objects.values() if obj.body.kind in PICTURE_KINDS}


class PicturePatch:
    """The pictures of one run of :func:`~claudia_computes_io.apply_edits_to_xlsx`."""

    def __init__(  # noqa: PLR0913 (the drawings and sheets of the file, the two models, the file's pictures, the losses)
        self,
        drawings: Drawings,
        sheet_parts: Mapping[SheetId, str],
        models: tuple[WorkbookModel, WorkbookModel],
        found: Mapping[str, DrawnAnchor],
        lose: Callable[[str, str, int], None],
    ) -> None:
        self.drawings, self.sheet_parts, self.found, self.lose = drawings, sheet_parts, found, lose
        self.baseline, self.current = models
        self.changed = False

    def run(self) -> bool:
        """Put the changes of the pictures into the file; whether there were any."""
        old, new = _pictures(self.baseline), _pictures(self.current)
        if sorted(old) != sorted(self.found):
            raise UnsupportedEdit("the baseline does not know the pictures of the file")
        for object_id, was in old.items():
            now = new.get(object_id)
            if now is None:
                drawn = self.found[object_id]
                self.drawings.take_out(drawn.drawing, drawn.anchor)
                self.changed = True
            else:
                self._change(self.found[object_id], was, now)
        self._add({object_id for object_id in new if object_id not in old})
        return self.changed

    def _add(self, added: set[str]) -> None:
        """The pictures ``added`` in the drawings of their sheets, in the order they are stacked; what cannot be
        written of them is said (``rendering-pending``, ``svg-fallback``)."""
        placed = placed_on_their_sheets(self.current, added)
        for loss in picture_losses(self.current, placed, rasterised=False):
            self.lose(loss.kind, loss.detail, loss.count)
        for picture in written_pictures(self.current, placed, svg_beside_png=True):
            self.drawings.add_picture(self.sheet_parts[picture.placed.tab.id], picture)
            self.changed = True

    def _change(self, drawn: DrawnAnchor, was: VisualObject, now: VisualObject) -> None:
        picture = drawn.anchor.find("xdr:pic", NS)
        assert picture is not None  # (the import held it as a picture)
        before, after = was.body, now.body
        moved = (was.anchor, before.w, before.h) != (now.anchor, after.w, after.h)
        turned = before.rotation != after.rotation
        described = (before.name, before.description, before.decorative) != (
            after.name,
            after.description,
            after.decorative,
        )
        if moved:
            self.drawings.pin(drawn.drawing, drawn.anchor, picture, placed_on_its_sheet(self.current, now))
            extent = _transform(picture).find("a:ext", NS)
            if extent is not None:
                extent.set("cx", str(emu(after.w)))
                extent.set("cy", str(emu(after.h)))
        if turned:
            _turn(_transform(picture), after.rotation)
        if described:
            _describe(picture.find("xdr:nvPicPr/xdr:cNvPr", NS), after)
        if moved or turned or described:
            self.drawings.changed.add(drawn.drawing)
            self.changed = True


def _transform(picture: etree._Element) -> etree._Element:
    """The ``a:xfrm`` of a picture, made when it has none."""
    shape = picture.find("xdr:spPr", NS)
    if shape is None:
        raise UnsupportedEdit("a picture of the file has no shape properties")
    transform = shape.find("a:xfrm", NS)
    if transform is None:
        transform = etree.Element(q("a", "xfrm"))
        etree.SubElement(transform, q("a", "off"), x="0", y="0")
        etree.SubElement(transform, q("a", "ext"), cx="0", cy="0")
        shape.insert(0, transform)
    return transform


def _turn(transform: etree._Element, rotation: int) -> None:
    """The turn of an ``a:xfrm``: sixty thousandths of a degree, clockwise; none for an upright picture."""
    if rotation % 360:
        transform.set("rot", str(rotation % 360 * ANGLE))
    elif "rot" in transform.attrib:
        del transform.attrib["rot"]


def _describe(properties: etree._Element | None, body: ObjectBody) -> None:
    """The name of a picture and what it says on its ``cNvPr``: a description, or Office's mark of a decorative one
    beside the file's own extensions of it."""
    if properties is None:
        raise UnsupportedEdit("a picture of the file has no name")
    properties.set("name", xml_safe(body.name) or "Picture")
    for key in ("descr", "title"):
        if key in properties.attrib:
            del properties.attrib[key]
    extensions = properties.find("a:extLst", NS)
    if extensions is not None:
        properties.remove(extensions)
        for mark in extensions.findall(f"a:ext[@uri='{DECORATIVE_URI}']", NS):
            extensions.remove(mark)
    if body.decorative:
        mark_decorative(properties)
        if extensions is not None:
            properties.find("a:extLst", NS)[:0] = list(extensions)  # type: ignore[index]
    else:
        if body.description:
            properties.set("descr", xml_safe(body.description))
        if extensions is not None and len(extensions):
            properties.append(extensions)
