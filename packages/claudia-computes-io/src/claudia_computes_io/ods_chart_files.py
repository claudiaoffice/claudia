"""The charts a file holds, and which of them the model holds too (D462).

:func:`file_charts` goes through the sheets of a file in order and lists every frame that embeds a chart, each with the
cell it is pinned to and, when the model can hold it (:func:`~claudia_computes_io.ods_charts.read_chart`), what the
model makes of it. The ``n``-th chart the model holds is the object ``o{n}`` showing the definition ``c{n}``: the import
and the patch both read the file this way, so the model that was read and the file it came from match again.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lxml import etree

from claudia_computes import MAX_OBJECTS_PER_SHEET, ChartSpec, SheetId
from claudia_computes.limits import MAX_COLS, MAX_ROWS
from claudia_computes.model import DEFAULT_COL_WIDTH, DEFAULT_ROW_HEIGHT
from claudia_core.assets import MAX_ALT_CHARS
from claudia_odf_io import NS, local_name

from .ods_charts import ReadChart, describe, holds_a_chart, read_chart, sizes_of, with_id
from .ods_layout import pixels_of

if TYPE_CHECKING:
    from .ods import _Table

_DRAWN = ("frame", "custom-shape", "g", "line", "rect", "ellipse", "circle", "path", "polygon", "polyline", "connector")
_DRAWN_TAGS = tuple(f"{{{NS['draw']}}}{name}" for name in _DRAWN)
_CELLS = ("table-cell", "covered-table-cell")


@dataclass
class FileChart:
    """One chart frame of a file."""

    sheet: SheetId
    frame: etree._Element
    folder: str
    #: Where its frame is pinned: the cell it is in, or the one at its position when it is on the sheet itself.
    row: int
    col: int
    #: What the model makes of it, and the ids it has there; ``None`` for a chart the model does not hold.
    held: ReadChart | None = None
    width: int = 0
    height: int = 0
    description: str = ""
    object_id: str = ""
    spec_id: str = ""

    @property
    def spec(self) -> ChartSpec:
        """The definition the model has of this chart (only for one the model holds)."""
        assert self.held is not None
        return with_id(self.held.spec, self.spec_id)


def cell_at(table: _Table, x: float, y: float) -> tuple[int, int]:
    """The cell at ``x`` and ``y`` pixels from the corner of the sheet, by the widths and heights the sheet has."""
    widths, heights = table.col_widths, table.row_heights
    column = row = 0
    left = top = 0.0
    while column < MAX_COLS - 1 and left + widths.get(column, DEFAULT_COL_WIDTH) <= x:
        left += widths.get(column, DEFAULT_COL_WIDTH)
        column += 1
    while row < MAX_ROWS - 1 and top + heights.get(row, DEFAULT_ROW_HEIGHT) <= y:
        top += heights.get(row, DEFAULT_ROW_HEIGHT)
        row += 1
    return row, column


def _cells_of(table: _Table) -> dict[etree._Element, tuple[int, int]]:
    return {cell.element: (run.first, cell.first) for run in table.rows for cell in run.cells}


def _is_alone(frame: etree._Element, table: etree._Element) -> bool:
    """Whether no other drawing holds the frame (a chart in a group or a text box is not one the sheet shows)."""
    parent = frame.getparent()
    while parent is not None and parent is not table:
        if parent.tag in _DRAWN_TAGS:
            return False
        parent = parent.getparent()
    return True


def _position(table: _Table, frame: etree._Element, cells: Mapping[etree._Element, tuple[int, int]]) -> tuple[int, int]:
    parent = frame.getparent()
    if parent is not None and isinstance(parent.tag, str) and local_name(parent.tag) in _CELLS:
        return cells.get(parent, (0, 0))
    x = pixels_of(frame.get(f"{{{NS['svg']}}}x")) or 0
    y = pixels_of(frame.get(f"{{{NS['svg']}}}y")) or 0
    return cell_at(table, x, y)


def file_charts(tables: Sequence[_Table], parts: Mapping[str, bytes]) -> list[FileChart]:
    """Every chart frame of the sheets of a file, with the ones the model holds numbered in the order of the file."""
    sheet_ids = {table.name: SheetId(table.id) for table in tables}
    by_folded = {name.casefold(): sheet for name, sheet in sheet_ids.items()}

    def resolve(name: str) -> SheetId | None:
        return sheet_ids.get(name) or by_folded.get(name.casefold())

    found: list[FileChart] = []
    held = 0
    for table in tables:
        cells = _cells_of(table)
        counted = 0
        for frame in table.element.iter(f"{{{NS['draw']}}}frame"):
            folder = holds_a_chart(frame)
            if folder is None or not _is_alone(frame, table.element):
                continue
            row, col = _position(table, frame, cells)
            chart = FileChart(SheetId(table.id), frame, folder, row, col)
            part = parts.get(f"{folder}/content.xml")
            read = None if part is None else read_chart(part, resolve)
            size = None if read is None else sizes_of(frame, read)
            description = describe(frame)
            if (
                read is not None
                and size is not None
                and len(description) <= MAX_ALT_CHARS
                and counted < MAX_OBJECTS_PER_SHEET
            ):
                held += 1
                counted += 1
                chart.held, (chart.width, chart.height), chart.description = read, size, description
                chart.object_id, chart.spec_id = f"o{held}", f"c{held}"
            found.append(chart)
    return found
