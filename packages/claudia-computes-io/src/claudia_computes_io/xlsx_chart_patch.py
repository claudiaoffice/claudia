"""Charts put into an xlsx file, new or kept (D463).

:class:`Drawings` is the one place that knows how a chart gets into a package: a new drawing for the sheet if it has
none (a part, its media type, the relationship from the sheet and the ``drawing`` element in the sheet's XML, put where
the standard has it), a part for the chart, its relationship from the drawing and an anchor in it. A fresh export uses
it to add the charts to the file openpyxl wrote; :class:`ChartPatch` uses it to change a kept file the way
:class:`~claudia_computes_io.ods_chart_patch.ChartPatch` changes an ods: a chart that was added is a new anchor with a
new part, one that was removed is taken out with its part, one that was moved or made another size has its anchor
changed, and one whose definition changed -- or whose numbers did, for a chart that carries a copy of them -- has its
part drawn again. A chart the model does not hold, and every chart nobody touched, stays byte for byte as it was. A
chart another program drew that is drawn again is drawn the way this program draws a bar chart, and says so (``chart``,
``look``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace

from lxml import etree

from claudia_computes import ChartSpec, VisualObject, WorkbookModel

from ._pictures import MEDIA_TYPES, WrittenPicture
from .chart_plan import chart_losses
from .xlsx_charts import (
    CHART_TYPE,
    DRAWING_TYPE,
    NS,
    FileChart,
    anchor_element,
    chart_xml,
    file_charts,
    new_drawing,
)
from .xlsx_patch import PackagePatch, UnsupportedEdit, serialized
from .xlsx_pictures import picture_anchor
from .xlsx_read import Package, parse_xml, q, relationships, rels_part

#: What may follow ``drawing`` in a worksheet (ECMA-376 part 1, 18.3.1.99): a new one goes before the first.
_AFTER_DRAWING = (
    "legacyDrawing",
    "legacyDrawingHF",
    "drawingHF",
    "picture",
    "oleObjects",
    "controls",
    "webPublishItems",
    "tableParts",
    "extLst",
)
_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


class Drawings:
    """The drawings of the sheets of a package, changed for charts: only what is changed is written back."""

    def __init__(
        self,
        patch: PackagePatch,
        roots: dict[str, etree._Element] | None = None,
        charts: Sequence[FileChart] = (),
    ) -> None:
        self.patch = patch
        self.roots = roots if roots is not None else {}
        self.charts = list(charts)
        self.changed: set[str] = set()
        self.sheets: dict[str, etree._Element] = {}  # the worksheets that got a ``drawing``, parsed
        self.gone: list[FileChart] = []
        self.media: dict[tuple[str, str], str] = {}  # (what is shown, as what) -> the part that holds it

    # -- the drawing of a sheet ----------------------------------------------------------------------------------
    def _sheet_root(self, sheet_part: str) -> etree._Element:
        if sheet_part not in self.sheets:
            self.sheets[sheet_part] = parse_xml(self.patch.parts[sheet_part])
        return self.sheets[sheet_part]

    def _drawing_of(self, sheet_part: str) -> str:
        """The part of the drawing of a sheet, made if the sheet has none."""
        for _, kind, target in relationships(self.patch.parts, sheet_part):
            if kind.endswith("/drawing") and target in self.patch.parts:
                if target not in self.roots:
                    self.roots[target] = parse_xml(self.patch.parts[target])
                return target
        name = self.patch.free_name("xl/drawings/drawing{}.xml")
        root = new_drawing()
        self.roots[name] = root
        self.patch.parts[name] = serialized(root)
        self.patch.declare(name, DRAWING_TYPE)
        rid = self.patch.add_relationship(sheet_part, "drawing", name)
        element = etree.fromstring(f'<drawing xmlns="{_MAIN}" xmlns:r="{NS["r"]}" r:id="{rid}"/>')
        sheet = self._sheet_root(sheet_part)
        later = next((e for e in sheet if isinstance(e.tag, str) and etree.QName(e).localname in _AFTER_DRAWING), None)
        if later is None:
            sheet.append(element)
        else:
            later.addprevious(element)
        return name

    # -- adding and taking away ----------------------------------------------------------------------------------
    def add(  # noqa: PLR0913 (a chart is: where it goes, what it is, where it is pinned, how big and what it says)
        self, sheet_part: str, xml: bytes, row: int, col: int, width: int, height: int, description: str = ""
    ) -> None:
        """A chart on the sheet in ``sheet_part``, pinned to the corner of cell ``row``, ``col``."""
        drawing = self._drawing_of(sheet_part)
        part = self.patch.free_name("xl/charts/chart{}.xml")
        self.patch.parts[part] = xml
        self.patch.declare(part, CHART_TYPE)
        rid = self.patch.add_relationship(drawing, "chart", part)
        root = self.roots[drawing]
        used = [int(p.get("id", "0")) for p in root.iter(f"{{{NS['xdr']}}}cNvPr") if (p.get("id") or "").isdigit()]
        number = max(used, default=0) + 1
        root.append(anchor_element(rid, number, f"Chart {number - 1}", row, col, width, height, description))
        self.changed.add(drawing)

    def _media_part(self, key: tuple[str, str], extension: str, data: bytes, media_type: str) -> str:
        """The part that holds a picture's bytes: made once for what is shown however many pictures show it."""
        if key not in self.media:
            part = self.patch.free_name(f"xl/media/image{{}}.{extension}")
            self.patch.parts[part] = data
            self.patch.declare_extension(extension, media_type)
            self.media[key] = part
        return self.media[key]

    def add_picture(self, sheet_part: str, picture: WrittenPicture) -> None:
        """A picture on the sheet in ``sheet_part``, pinned to the corner of its cell (D1233)."""
        drawing = self._drawing_of(sheet_part)
        part = self._media_part((picture.asset, "picture"), picture.format, picture.data, MEDIA_TYPES[picture.format])
        rid = self.patch.add_relationship(drawing, "image", part)
        svg_rid = None
        if picture.svg is not None:
            svg_part = self._media_part((picture.asset, "svg"), "svg", picture.svg, MEDIA_TYPES["svg"])
            svg_rid = self.patch.add_relationship(drawing, "image", svg_part)
        root = self.roots[drawing]
        used = [int(p.get("id", "0")) for p in root.iter(f"{{{NS['xdr']}}}cNvPr") if (p.get("id") or "").isdigit()]
        root.append(picture_anchor(picture, max(used, default=0) + 1, rid, svg_rid))
        self.changed.add(drawing)

    def remove(self, chart: FileChart) -> None:
        """A chart's anchor taken out of its drawing, and its part (with what only it uses) out of the package."""
        parent = chart.anchor.getparent()
        if parent is not None:
            parent.remove(chart.anchor)
        self.changed.add(chart.drawing)
        self.gone.append(chart)
        reference = chart.frame.find(".//c:chart", NS)
        if reference is not None and reference.get(q("r", "id")):
            self.patch.remove_relationship(chart.drawing, reference.get(q("r", "id"), ""))
        if any(other.part == chart.part and other not in self.gone for other in self.charts):
            return  # (another anchor shows the same chart)
        for _, _, target in relationships(self.patch.parts, chart.part):
            self.patch.forget(target)
        self.patch.parts.pop(rels_part(chart.part), None)
        self.patch.forget(chart.part)

    def finish(self) -> None:
        """The parts that were changed, written back."""
        for part in self.changed:
            self.patch.parts[part] = serialized(self.roots[part])
        for part, root in self.sheets.items():
            self.patch.parts[part] = serialized(root)


# ------------------------------------------------------------------------------------------------ a kept file
def _definition(model: WorkbookModel, obj: VisualObject) -> ChartSpec:
    assert obj.body.chart is not None  # (the caller picks chart objects)
    spec = model.charts[obj.body.chart]
    assert isinstance(spec, ChartSpec)
    return spec


def _without_id(spec: ChartSpec) -> ChartSpec:
    return replace(spec, id="")


def _size(obj: VisualObject) -> tuple[int, int]:
    return obj.body.w, obj.body.h


class ChartPatch:
    """The charts of one run of :func:`~claudia_computes_io.apply_edits_to_xlsx`."""

    def __init__(  # noqa: PLR0913 (the file's parts and sheets, the two models, and where to say what was lost)
        self,
        patch: PackagePatch,
        package: Package,
        baseline: WorkbookModel,
        current: WorkbookModel,
        found: tuple[Sequence[FileChart], dict[str, etree._Element]],
        lose: Callable[[str, str], None],
    ) -> None:
        self.patch, self.baseline, self.current, self.lose = patch, baseline, current, lose
        self.charts, roots = found
        self.drawings = Drawings(patch, roots, self.charts)
        self.by_object = {chart.object_id: chart for chart in self.charts if chart.held is not None}
        self.sheet_parts = {sheet.sheet_id: sheet.part for sheet in package.sheets}
        self.changed = False

    def run(self) -> bool:
        """Put the changes of the charts into the file; whether there were any."""
        old = {obj.id: obj for obj in self.baseline.objects.values() if obj.body.chart is not None}
        new = {obj.id: obj for obj in self.current.objects.values() if obj.body.chart is not None}
        if sorted(old) != sorted(self.by_object):
            raise UnsupportedEdit("the baseline does not know the charts of the file")
        for object_id, was in old.items():
            file = self.by_object[object_id]
            now = new.get(object_id)
            if now is None:
                self.drawings.remove(file)
                self.changed = True
            else:
                self._change(file, was, now)
        for object_id, now in new.items():
            if object_id not in old:
                self._add(now)
        if self.changed:
            self.drawings.finish()
        return self.changed

    # -- changes -----------------------------------------------------------------------------------------------
    def _change(self, file: FileChart, was: VisualObject, now: VisualObject) -> None:
        spec_was, spec_now = _definition(self.baseline, was), _definition(self.current, now)
        redefined = _without_id(spec_was) != _without_id(spec_now)
        needs_redraw = (
            redefined
            or _size(was) != _size(now)
            or self.baseline.chart_figure(spec_was.id) != self.current.chart_figure(spec_now.id)
        )
        if needs_redraw and not self._redraw(file, (spec_was, spec_now), redefined=redefined):
            return
        if was.anchor != now.anchor or _size(was) != _size(now):
            self._place(file, now)
        if was.body.description != now.body.description:
            self._describe(file, now.body.description)

    def _redraw(self, file: FileChart, specs: tuple[ChartSpec, ChartSpec], *, redefined: bool) -> bool:
        """The chart's part drawn again for what it shows now; ``False`` when it shows nothing and is taken out. A
        chart this program drew is drawn the same way again. One that another program drew keeps its own drawing when
        only its numbers or its size changed and is drawn the way this program draws a bar chart when its definition
        did (and that is said)."""
        spec_was, spec_now = specs
        document = chart_xml(self.current, spec_now)
        if document is None:
            self.drawings.remove(file)
            self.changed = True
            return False
        if chart_xml(self.baseline, spec_was) != self.patch.parts.get(file.part):  # (not one of ours)
            if not redefined:
                return True
            self.lose("chart", "look")
        if document != self.patch.parts.get(file.part):
            self.patch.parts[file.part] = document
            self.changed = True
        return True

    def _place(self, file: FileChart, now: VisualObject) -> None:
        """The chart pinned to the cell it is at now and as big as it is now: its frame in an anchor of the one-cell
        kind (a file's two-cell anchor says its size by the cells it reaches, which a move would change)."""
        anchor = now.anchor
        moved = anchor_element("", 1, "", anchor.row, anchor.col, now.body.w, now.body.h)
        placeholder = moved.find("xdr:graphicFrame", NS)
        assert placeholder is not None
        moved.replace(placeholder, file.frame)
        parent = file.anchor.getparent()
        assert parent is not None
        parent.replace(file.anchor, moved)
        file.anchor = moved
        self.drawings.changed.add(file.drawing)
        self.changed = True

    def _describe(self, file: FileChart, text: str) -> None:
        """What the frame says to someone who cannot see it: ``descr``. A description that came from the title of the
        frame is taken from there."""
        properties = file.frame.find("xdr:nvGraphicFramePr/xdr:cNvPr", NS)
        if properties is None:
            return
        if text:
            properties.set("descr", text)
        else:
            for name in ("descr", "title"):
                if name in properties.attrib:
                    del properties.attrib[name]
        self.drawings.changed.add(file.drawing)
        self.changed = True

    # -- additions ---------------------------------------------------------------------------------------------
    def _add(self, now: VisualObject) -> None:
        document = chart_xml(self.current, _definition(self.current, now))
        if document is None:
            return  # (it shows nothing: counted among what could not be written)
        body = now.body
        self.drawings.add(
            self.sheet_parts[now.anchor.sheet],
            document,
            now.anchor.row,
            now.anchor.col,
            body.w,
            body.h,
            body.description,
        )
        self.changed = True


def patch_charts(
    patch: PackagePatch,
    package: Package,
    baseline: WorkbookModel,
    current: WorkbookModel,
    lose: Callable[[str, str], None],
) -> bool:
    """The charts of a kept file brought up to date with ``current``; whether anything in the file changed. What a file
    cannot keep of the charts is said through ``lose`` (``chart``, with the detail). Raises
    :class:`~claudia_computes_io.UnsupportedEdit` for a baseline that does not know the charts of the file."""
    for detail in chart_losses(current):
        lose("chart", detail)
    return ChartPatch(patch, package, baseline, current, file_charts(package), lose).run()
