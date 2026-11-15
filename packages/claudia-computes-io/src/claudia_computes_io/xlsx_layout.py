"""Row heights and column widths of a worksheet, in the units Excel keeps them in (D458).

The model counts both in pixels (``Sheet.row_heights``, ``Sheet.col_widths``; a line that is not listed shows at
``DEFAULT_ROW_HEIGHT`` or ``DEFAULT_COL_WIDTH``). Excel counts a column in characters of its default font -- seven
pixels each -- and a row in points, three quarters of a pixel each. Both are rounded to whole pixels on the way in:
Excel itself shows nothing finer.

Excel holds a column up to 255 characters and a row up to 409.5 points; a size beyond them is written at the limit and
reported (``layout``: ``beyond-excel-limits``).
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence

from claudia_computes import Sheet, WorkbookModel
from claudia_computes.model import DEFAULT_COL_WIDTH, DEFAULT_ROW_HEIGHT
from claudia_odf_io import LossLog

from .layout_sizes import fit_height, fit_width

PIXELS_PER_CHARACTER = 7
POINTS_PER_PIXEL = 0.75
MAX_EXCEL_WIDTH = 255.0
MAX_EXCEL_HEIGHT = 409.5
#: What the file says of a size beyond Excel's limits.
BEYOND_EXCEL = "beyond-excel-limits"


def width_of(pixels: float) -> float:
    """A column of ``pixels`` as Excel's width in characters."""
    return round(pixels / PIXELS_PER_CHARACTER, 6)


def height_of(pixels: float) -> float:
    """A row of ``pixels`` as Excel's height in points."""
    return round(pixels * POINTS_PER_PIXEL, 2)


def size_of_width(characters: float) -> int:
    """The pixels of a column that Excel gives ``characters``, kept within what the model allows."""
    return fit_width(characters * PIXELS_PER_CHARACTER)


def size_of_height(points: float) -> int:
    """The pixels of a row that Excel gives ``points``, kept within what the model allows."""
    return fit_height(points / POINTS_PER_PIXEL)


def written_width(pixels: float | None) -> float:
    """The width to write for a column of ``pixels`` (``None``: the model's default, which a column that was given
    up must say outright: the file's own default may be another), at most what Excel holds."""
    return min(MAX_EXCEL_WIDTH, width_of(DEFAULT_COL_WIDTH if pixels is None else pixels))


def written_height(pixels: float | None) -> float:
    """The height to write for a row of ``pixels`` (``None``: the model's default), at most what Excel holds."""
    return min(MAX_EXCEL_HEIGHT, height_of(DEFAULT_ROW_HEIGHT if pixels is None else pixels))


def column_runs[Look: Hashable](
    looks: Sequence[tuple[int, int, Look]], widths: Mapping[int, float]
) -> list[tuple[int, int, Look | None, float | None]]:
    """The ``col`` elements of a sheet: its runs of columns with a look (first, last, look) cut where a width starts or
    ends, joined where neighbours say the same, and a run of columns with a width but no look of their own. Each is
    ``(first, last, look, width)`` with ``None`` for what the run does not set; columns are counted from 0."""
    edges = {0}
    for first, last, _ in looks:
        edges.update((first, last + 1))
    for column in widths:
        edges.update((column, column + 1))
    runs: list[tuple[int, int, Look | None, float | None]] = []
    ordered = sorted(edges)
    for start, stop in zip(ordered, ordered[1:], strict=False):
        look = next((each for first, last, each in looks if first <= start <= last), None)
        width = widths.get(start)
        if look is None and width is None:
            continue
        if runs and runs[-1][1] == start - 1 and runs[-1][2:] == (look, width):
            runs[-1] = (runs[-1][0], stop - 1, look, width)
        else:
            runs.append((start, stop - 1, look, width))
    return runs


def beyond_excel(sheet: Sheet, before: Sheet | None) -> int:
    """How many rows and columns of ``sheet`` that are not as they were in ``before`` (``None``: a new sheet) have a
    size Excel cannot hold."""
    count = 0
    for index, size in sheet.col_widths.items():
        count += width_of(size) > MAX_EXCEL_WIDTH and (before is None or before.col_widths.get(index) != size)
    for index, size in sheet.row_heights.items():
        count += height_of(size) > MAX_EXCEL_HEIGHT and (before is None or before.row_heights.get(index) != size)
    return count


def layout_losses(model: WorkbookModel, baseline: WorkbookModel | None) -> LossLog:
    """What the sizes of ``model`` that differ from ``baseline`` (``None``: an empty workbook) cannot say in Excel."""
    losses = LossLog()
    total = sum(
        beyond_excel(sheet, None if baseline is None else baseline.sheets.get(sheet.id))
        for sheet in model.sheets.values()
    )
    if total:
        losses.add("layout", BEYOND_EXCEL, total)
    return losses
