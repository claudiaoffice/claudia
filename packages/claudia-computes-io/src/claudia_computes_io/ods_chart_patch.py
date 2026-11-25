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
from collections.abc import Callable, Iterable, Mapping, Sequence

from lxml import etree

from claudia_computes import ChartSpec, SheetId, VisualObject, WorkbookModel
from claudia_odf_io import NS, XmlPart, local_name, qname, update_manifest, xml_safe

from ._charts import chart_change, definition_of
from ._placed import placed_on_its_sheet
from .ods_chart_files import FileChart
from .ods_charts import Parts, a_chart, chart_document, new_shapes, place_of

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


class SheetShapes:
    """Where the frames a patch puts on the sheets of a kept file go: the ``table:shapes`` of a sheet of the file, one
    made for a sheet that has none, or the table of a sheet the patch adds (charts and pictures share them)."""

    def __init__(
        self,
        part: XmlPart,
        tables: Mapping[SheetId, etree._Element],
        new_tables: Mapping[SheetId, etree._Element],
    ) -> None:
        self.part, self.tables, self.new_tables = part, tables, new_tables
        self.made: dict[SheetId, etree._Element] = {}  # the ``table:shapes`` made for sheets that had none

    def holds(self, frame: etree._Element, sheet: SheetId) -> bool:
        """Whether ``frame`` is among the drawings of ``sheet`` in the file (and not, say, in one of its cells)."""
        shapes = frame.getparent()
        table = self.tables.get(sheet)
        return shapes is not None and local_name(shapes.tag) == "shapes" and table is not None and shapes in table

    def put(self, sheet: SheetId, frame: etree._Element) -> None:
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
        elif sheet in self.made:
            self.made[sheet].append(frame)
        else:
            made = self.made[sheet] = new_shapes()
            made.append(frame)
            first = next(
                (child for child in table if isinstance(child.tag, str) and local_name(child.tag) in _AFTER_SHAPES),
                None,
            )
            if first is None:
                self.part.insert_into(table, made)
            else:
                self.part.insert_before(first, made)

    def move(
        self, frame: etree._Element, sheet: SheetId, attributes: Mapping[str, str], remove: Iterable[str] = ()
    ) -> etree._Element:
        """``frame`` among the drawings of ``sheet`` with ``attributes`` (where it is: :func:`.ods_charts.place_of`)
        and without those named in ``remove``, and returned: a frame in a cell of the file is taken out of it and a
        copy is put there, at the corner of the cell. A place it no longer has (``svg:x`` and ``svg:y``, or
        ``draw:transform``) is taken off."""
        gone = [*(key for key in ("svg:x", "svg:y", "draw:transform") if key not in attributes), *remove]
        if self.holds(frame, sheet):
            self.part.set_attributes(frame, attributes, remove=gone)
            return frame
        moved = copy.deepcopy(frame)
        for key, value in attributes.items():
            moved.set(qname(key), value)
        for key in gone:
            if qname(key) in moved.attrib:
                del moved.attrib[qname(key)]
        self.part.remove(frame)
        self.put(sheet, moved)
        return moved


def describe(part: XmlPart, frame: etree._Element, text: str) -> None:
    """What a frame of the file (in ``part``) says to someone who cannot see it: ``svg:desc``. A description that came
    from the title of the frame is taken from there."""
    desc, title = frame.find("svg:desc", NS), frame.find("svg:title", NS)
    if desc is None and title is not None:
        part.remove(title)
    if desc is not None and text:
        part.replace(desc, part.make("svg:desc", text=xml_safe(text)))
    elif desc is not None:
        part.remove(desc)
    elif text:
        part.insert_into(frame, part.make("svg:desc", text=xml_safe(text)))


class ChartPatch:
    """The charts of one run of :func:`~claudia_computes_io.apply_edits_to_ods`."""

    def __init__(  # noqa: PLR0913 (the file's parts and sheets, the two models, and where to say what was lost)
        self,
        part: XmlPart,
        parts: dict[str, bytes],
        baseline: WorkbookModel,
        current: WorkbookModel,
        charts: Sequence[FileChart],
        shapes: SheetShapes,
        lose: Callable[[str, str], None],
    ) -> None:
        self.part, self.parts, self.baseline, self.current = part, parts, baseline, current
        self.charts, self.shapes, self.lose = charts, shapes, lose
        self.tables = shapes.tables
        self.by_object = {chart.object_id: chart for chart in charts if chart.held is not None}
        self.listed: dict[str, str] = {}  # the parts to list in the manifest
        self.unlisted: list[str] = []  # the folders to take off it
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
        old = {obj.id: obj for obj in self.baseline.objects.values() if obj.body.chart is not None}
        new = {obj.id: obj for obj in self.current.objects.values() if obj.body.chart is not None}
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

    # -- changes -----------------------------------------------------------------------------------------------
    def _remove(self, file: FileChart) -> None:
        self.part.remove(file.frame)
        self._forget(file)

    def _change(self, file: FileChart, was: VisualObject, now: VisualObject) -> None:
        change = chart_change(self.baseline, self.current, was, now)
        before, after = (change.before, was), (change.after, now)
        if change.redraw and not self._redraw(file, before, after, drawn_differently=change.redefined):
            return
        place = place_of(placed_on_its_sheet(self.current, now))
        if was.anchor != now.anchor:
            self._relocate(file, now, place)
        elif (was.body.w, was.body.h) != (now.body.w, now.body.h):
            self.part.set_attributes(file.frame, {key: place[key] for key in ("svg:width", "svg:height")})
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

    def _relocate(self, file: FileChart, now: VisualObject, place: Mapping[str, str]) -> None:
        """The frame at another cell, or on another sheet (:meth:`SheetShapes.move`)."""
        self.shapes.move(file.frame, now.anchor.sheet, place)
        self.changed = True

    def _describe(self, frame: etree._Element, text: str) -> None:
        describe(self.part, frame, text)
        self.changed = True

    # -- additions ---------------------------------------------------------------------------------------------
    def _add(self, now: VisualObject) -> None:
        spec = definition_of(self.current, now)
        made = a_chart(self.current, spec, self.number, placed_on_its_sheet(self.current, now))
        if made is None:
            return  # (it shows nothing: counted among what could not be written)
        self.number += 1
        self._keep_parts(made.parts)
        self.shapes.put(now.anchor.sheet, made.frame)
