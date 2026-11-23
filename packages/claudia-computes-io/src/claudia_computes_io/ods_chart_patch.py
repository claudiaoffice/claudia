"""Charts patched into a kept ods file (D462).

What the person did to the charts since the file was read is put into the file's own XML: a chart that was added is a
new frame (in the ``table:shapes`` of its sheet) with a new part, one that was removed is taken out with its part, one
that was moved or made another size has its frame changed, and one whose definition changed -- or whose numbers did,
for a chart that carries a copy of them -- has its part drawn again. A chart the model does not hold, and every chart
that was not touched, stays byte for byte as it was. A chart somebody else's program drew that is drawn again is drawn
the way this program draws a bar chart, and says so (``chart``, ``look``); a chart this program wrote is not changed by
being drawn again.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace

from lxml import etree

from claudia_computes import ChartSpec, SheetId, VisualObject, WorkbookModel
from claudia_odf_io import NS, XmlPart, local_name, qname, update_manifest, xml_safe

from .chart_plan import offset_of
from .ods_chart_files import FileChart
from .ods_charts import Parts, a_chart, chart_document, new_shapes
from .ods_layout import text_of

#: What a table of a file holds that comes after its drawings.
_AFTER_SHAPES = (
    "table-column",
    "table-columns",
    "table-column-group",
    "table-header-columns",
    "table-row",
    "table-rows",
    "table-row-group",
    "table-header-rows",
)
_FOLDER = re.compile(r"Object (\d+)/")


def _definition(model: WorkbookModel, obj: VisualObject) -> ChartSpec:
    assert obj.body.diagram is not None  # (the caller picks diagram objects)
    spec = model.diagrams[obj.body.diagram]
    assert isinstance(spec, ChartSpec)
    return spec


def _without_id(spec: ChartSpec) -> ChartSpec:
    return replace(spec, id="")


def _size(obj: VisualObject) -> tuple[int, int]:
    return obj.body.w, obj.body.h


class ChartPatch:
    """The charts of one run of :func:`~claudia_computes_io.apply_edits_to_ods`."""

    def __init__(  # noqa: PLR0913 (the file's parts and sheets, the two models, and where to say what was lost)
        self,
        part: XmlPart,
        parts: dict[str, bytes],
        baseline: WorkbookModel,
        current: WorkbookModel,
        charts: Sequence[FileChart],
        tables: Mapping[SheetId, etree._Element],
        new_tables: Mapping[SheetId, etree._Element],
        lose: Callable[[str, str], None],
    ) -> None:
        self.part, self.parts, self.baseline, self.current = part, parts, baseline, current
        self.charts, self.tables, self.new_tables, self.lose = charts, tables, new_tables, lose
        self.by_object = {chart.object_id: chart for chart in charts if chart.held is not None}
        self.listed: dict[str, str] = {}  # the parts to list in the manifest
        self.unlisted: list[str] = []  # the folders to take off it
        self.shapes: dict[SheetId, etree._Element] = {}  # the ``table:shapes`` made for sheets that had none
        names = [int(found.group(1)) for name in parts if (found := _FOLDER.match(name))]
        self.number = max(names, default=0) + 1
        self.changed = False

    # -- the run -----------------------------------------------------------------------------------------------
    def run(self) -> bool:
        """Put the changes of the charts into the file; whether there were any."""
        gone = {sheet for sheet in self.tables if sheet not in self.current.sheets}
        for chart in self.charts:
            if chart.sheet in gone:  # (the sheet is taken out of the file with its frames)
                self._forget(chart)
        old = {obj.id: obj for obj in self.baseline.objects.values() if obj.body.diagram is not None}
        new = {obj.id: obj for obj in self.current.objects.values() if obj.body.diagram is not None}
        for object_id, was in old.items():
            file = self.by_object[object_id]
            if file.sheet in gone:
                continue
            now = new.get(object_id)
            if now is None:
                self._remove(file)
            else:
                self._change(file, was, now)
        for object_id, now in new.items():
            if object_id not in old:
                self._add(now)
        if self.changed:
            update_manifest(self.parts, add=self.listed, remove=tuple(self.unlisted))
        return self.changed

    # -- parts -------------------------------------------------------------------------------------------------
    def _forget(self, chart: FileChart) -> None:
        """Take the part of a chart out of the package (its frame goes with the sheet or is taken out by the caller)."""
        folder = (f"{chart.folder}/", f"ObjectReplacements/{chart.folder}")
        for name in [name for name in self.parts if name.startswith(folder)]:
            del self.parts[name]
        self.unlisted.extend([f"{chart.folder}/", f"ObjectReplacements/{chart.folder}"])
        self.changed = True

    def _keep_parts(self, made: Parts) -> None:
        for name, (data, media) in made.items():
            if data is not None:
                self.parts[name] = data
            self.listed[name] = media
        self.changed = True

    # -- where a frame goes ------------------------------------------------------------------------------------
    def _put(self, sheet: SheetId, frame: etree._Element) -> None:
        """Put ``frame`` among the drawings of ``sheet``, which may be a sheet this run adds."""
        new = self.new_tables.get(sheet)
        if new is not None:
            shapes = new.find("table:shapes", NS)
            if shapes is None:
                shapes = new_shapes()
                new.insert(0, shapes)
            shapes.append(frame)
            return
        table = self.tables[sheet]
        shapes = table.find("table:shapes", NS)
        if shapes is not None:
            self.part.insert_into(shapes, frame)
        elif sheet in self.shapes:
            self.shapes[sheet].append(frame)
        else:
            made = self.shapes[sheet] = new_shapes()
            made.append(frame)
            first = next(
                (child for child in table if isinstance(child.tag, str) and local_name(child.tag) in _AFTER_SHAPES),
                None,
            )
            if first is None:
                self.part.insert_into(table, made)
            else:
                self.part.insert_before(first, made)

    def _corner(self, sheet: SheetId, row: int, col: int) -> tuple[float, float]:
        found = self.current.sheets[sheet]
        return offset_of(found.col_widths, found.row_heights, row, col)

    # -- changes -----------------------------------------------------------------------------------------------
    def _remove(self, file: FileChart) -> None:
        self.part.remove(file.frame)
        self._forget(file)

    def _change(self, file: FileChart, was: VisualObject, now: VisualObject) -> None:
        spec_was, spec_now = _definition(self.baseline, was), _definition(self.current, now)
        redefined = _without_id(spec_was) != _without_id(spec_now)
        needs_redraw = (
            redefined
            or _size(was) != _size(now)
            or self.baseline.chart_figure(spec_was.id) != self.current.chart_figure(spec_now.id)
        )
        if needs_redraw and not self._redraw(file, (spec_was, was), (spec_now, now), drawn_differently=redefined):
            return
        size = {"svg:width": text_of(now.body.w), "svg:height": text_of(now.body.h)}
        if was.anchor != now.anchor:
            self._relocate(file, now, size)
        elif _size(was) != _size(now):
            self.part.set_attributes(file.frame, size)
            self.changed = True
        if was.body.description != now.body.description:
            self._describe(file.frame, now.body.description)

    def _redraw(
        self,
        file: FileChart,
        before: tuple[ChartSpec, VisualObject],
        after: tuple[ChartSpec, VisualObject],
        *,
        drawn_differently: bool,
    ) -> bool:
        """The chart's part drawn again for what it shows now; ``False`` when it shows nothing and is taken out. A
        chart this program drew is drawn the same way again. One that another program drew keeps its own drawing when
        only its numbers or its size changed (the sheet is where it reads the numbers, the frame is where the size is)
        and is drawn the way this program draws a bar chart when its definition did (and that is said)."""
        (spec_was, was), (spec_now, now) = before, after
        document = chart_document(self.current, spec_now, now.body.w, now.body.h)
        if document is None:
            self._remove(file)
            return False
        key = f"{file.folder}/content.xml"
        ours = chart_document(self.baseline, spec_was, was.body.w, was.body.h) == self.parts.get(key)
        if not ours:
            if not drawn_differently:
                return True
            self.lose("chart", "look")
        self.parts[key] = document
        self.changed = True
        return True

    def _relocate(self, file: FileChart, now: VisualObject, size: Mapping[str, str]) -> None:
        """The frame at another cell, or on another sheet: a frame in a cell of the file is taken out of it and a
        copy is put among the drawings of the sheet, at the corner of the cell."""
        sheet = now.anchor.sheet
        x, y = self._corner(sheet, now.anchor.row, now.anchor.col)
        where = {"svg:x": text_of(x), "svg:y": text_of(y)}
        shapes = file.frame.getparent()
        if file.sheet == sheet and shapes is not None and local_name(shapes.tag) == "shapes":
            self.part.set_attributes(file.frame, {**where, **size})
        else:
            frame = copy.deepcopy(file.frame)
            for key, value in {**where, **size}.items():
                frame.set(qname(key), value)
            self.part.remove(file.frame)
            self._put(sheet, frame)
        self.changed = True

    def _describe(self, frame: etree._Element, text: str) -> None:
        """What the frame says to someone who cannot see it: ``svg:desc``. A description that came from the title of
        the frame is taken from there."""
        desc, title = frame.find("svg:desc", NS), frame.find("svg:title", NS)
        if desc is None and title is not None:
            self.part.remove(title)
        if desc is not None and text:
            self.part.replace(desc, self.part.make("svg:desc", text=xml_safe(text)))
        elif desc is not None:
            self.part.remove(desc)
        elif text:
            self.part.insert_into(frame, self.part.make("svg:desc", text=xml_safe(text)))
        self.changed = True

    # -- additions ---------------------------------------------------------------------------------------------
    def _add(self, now: VisualObject) -> None:
        spec = _definition(self.current, now)
        corner = self._corner(now.anchor.sheet, now.anchor.row, now.anchor.col)
        made = a_chart(self.current, spec, self.number, (now.body.w, now.body.h), corner, now.body.description)
        if made is None:
            return  # (it shows nothing: counted among what could not be written)
        self.number += 1
        self._keep_parts(made.parts)
        self._put(now.anchor.sheet, made.frame)
