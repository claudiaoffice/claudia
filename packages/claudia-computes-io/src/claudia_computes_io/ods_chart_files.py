"""The charts a file holds, and which of them the model holds too (D462).

:func:`file_charts` goes through the sheets of a file in order and lists every frame that embeds a chart, each with the
cell it is pinned to and, when the model can hold it (:func:`~claudia_computes_io.ods_charts.read_chart`), what the
model makes of it. The ``n``-th chart the model holds is the object ``o{n}`` showing the definition ``c{n}``: the import
and the patch both read the file this way, so the model that was read and the file it came from match again.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from lxml import etree

from claudia_computes import MAX_OBJECTS_PER_SHEET, SheetId
from claudia_core.assets import MAX_ALT_CHARS
from claudia_odf_io import CM_PER_INCH, CM_PER_PIXEL, NS, description_of, inches, local_name, pixels, qname, turned_box

from ._charts import FileChart as SharedFileChart
from ._placed import cell_at
from .ods_charts import holds_a_chart, read_chart, sizes_of

if TYPE_CHECKING:
    from .ods import _Table

_DRAWN = ("frame", "custom-shape", "g", "line", "rect", "ellipse", "circle", "path", "polygon", "polyline", "connector")
_DRAWN_TAGS = tuple(f"{{{NS['draw']}}}{name}" for name in _DRAWN)
_CELLS = ("table-cell", "covered-table-cell")
_FRAMES = tuple(f"{{{NS['draw']}}}{name}" for name in ("frame", "rect", "ellipse", "custom-shape"))


@dataclass(kw_only=True)
class FileChart(SharedFileChart):
    """One chart frame of a file: the frame, and the folder of its part. It is pinned to the cell it is in, or the one
    at its position when it is on the sheet itself."""

    frame: etree._Element
    folder: str


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


def frame_corner(frame: etree._Element) -> tuple[float, float]:
    """Where the corner of a frame is, in pixels from the corner of its sheet: its ``svg:x`` and ``svg:y``, or for a
    turned one the corner of its box before the turn, to a hundredth of a pixel."""
    transform = frame.get(qname("draw:transform"))
    if transform:
        width, height = (inches(frame.get(qname(f"svg:{side}"))) or 0.0 for side in ("width", "height"))
        turned = turned_box(transform, width * CM_PER_INCH, height * CM_PER_INCH)
        if turned is not None:
            return round(turned[1] / CM_PER_PIXEL, 2), round(turned[2] / CM_PER_PIXEL, 2)
    return round(pixels(frame.get(qname("svg:x"))) or 0.0, 2), round(pixels(frame.get(qname("svg:y"))) or 0.0, 2)


@dataclass(frozen=True)
class DrawnFrame:
    """A frame (or a shape) alone on a sheet of a file (not in a group or a text box): the sheet, the element, the cell
    it is pinned to (the cell it is in, or the one at its corner when it is on the sheet itself) and where its corner
    is."""

    sheet: SheetId
    frame: etree._Element
    row: int
    col: int
    corner: Callable[[], tuple[float, float]]
    #: Its place among the drawings of the file (on a sheet, the later is in front).
    order: int


def drawn_frames(tables: Sequence[_Table]) -> Iterator[DrawnFrame]:
    """Every frame alone on a sheet of a file, and every rectangle, ellipse and custom shape (what may be a box of the
    model, D1479), sheet by sheet, in the order of the file."""
    order = 0
    for table in tables:
        cells = _cells_of(table)
        for frame in table.element.iter(*_FRAMES):
            if not _is_alone(frame, table.element):
                continue
            order += 1
            parent = frame.getparent()
            corner = partial(frame_corner, frame)
            if parent is not None and isinstance(parent.tag, str) and local_name(parent.tag) in _CELLS:
                row, col = cells.get(parent, (0, 0))
            else:
                # (in whole pixels, as the model counts: what a file's units leave over does not put a frame a cell off)
                x, y = corner()
                pin = cell_at(table.col_widths, table.row_heights, round(x), round(y))
                row, col = pin.row, pin.col
            yield DrawnFrame(SheetId(table.id), frame, row, col, corner, order)


def drawing_name(element: etree._Element) -> str:
    """What a frame or a shape of a file is called (``draw:name``)."""
    return (element.get(qname("draw:name")) or "").strip()


def file_charts(tables: Sequence[_Table], parts: Mapping[str, bytes], drawn: Sequence[DrawnFrame]) -> list[FileChart]:
    """Every chart frame of the sheets of a file (``drawn``: what :func:`drawn_frames` found on them), with the ones the
    model holds numbered in the order of the file."""
    sheet_ids = {table.name: SheetId(table.id) for table in tables}
    by_folded = {name.casefold(): sheet for name, sheet in sheet_ids.items()}

    def resolve(name: str) -> SheetId | None:
        return sheet_ids.get(name) or by_folded.get(name.casefold())

    found: list[FileChart] = []
    held = 0
    counted: Counter[SheetId] = Counter()
    for one in drawn:
        folder = holds_a_chart(one.frame)
        if folder is None:
            continue
        frame = one.frame
        chart = FileChart(
            sheet=one.sheet,
            row=one.row,
            col=one.col,
            corner=one.corner,
            order=one.order,
            name=drawing_name(frame),
            frame=frame,
            folder=folder,
        )
        part = parts.get(f"{folder}/content.xml")
        read = None if part is None else read_chart(part, resolve)
        size = None if read is None else sizes_of(frame, read)
        description = description_of(frame)
        if (
            read is not None
            and size is not None
            and len(description) <= MAX_ALT_CHARS
            and counted[one.sheet] < MAX_OBJECTS_PER_SHEET
        ):
            held += 1
            counted[one.sheet] += 1
            chart.held, (chart.width, chart.height), chart.description = read, size, description
            chart.object_id, chart.spec_id = f"o{held}", f"c{held}"
        found.append(chart)
    return found
