"""What a chart of the model is, as the cells a file's chart names (D462, D463).

A bar chart of the model is one range with a header row and column the way
:meth:`~claudia_computes.WorkbookModel.chart_figure` reads it: one series per column (or row) of the range, named by its
header, over categories from its first column (row). Every file format says the same thing in its own words (an ods
chart part, an xlsx ``c:chart``), so what they share is here: :func:`plan_of`, the cells the model reads for a range;
:func:`plan_from`, the other way round (the range, if the cells a chart names are exactly what the model would read of
it); :func:`spec_of`, the definition the model holds of such a chart; and :func:`chart_losses`, what no file keeps of
the charts of a workbook.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import NamedTuple

from claudia_computes import CellRef, ChartError, ChartSpec, RangeRef, SheetId, WorkbookModel
from claudia_computes.limits import MAX_COLS, MAX_ROWS
from claudia_computes.model import DEFAULT_COL_WIDTH, DEFAULT_ROW_HEIGHT


class Series(NamedTuple):
    """One series as the model reads a range: the cells of its values and the cell of its name (``None``: it has
    none). A cell is ``(row, col)``; a run of cells is its first and last."""

    values: tuple[tuple[int, int], tuple[int, int]]
    label: tuple[int, int] | None


class Plan(NamedTuple):
    """What :meth:`~claudia_computes.WorkbookModel.chart_figure` makes of a range, as the cells it reads."""

    categories: tuple[tuple[int, int], tuple[int, int]] | None
    series: tuple[Series, ...]
    first_row_is_header: bool
    first_column_is_header: bool


def plan_of(first: CellRef, last: CellRef, *, series_in: str, header_row: bool) -> Plan:
    """The series and the categories ``chart_figure`` draws of the range ``first``..``last``: the first column (row)
    names the categories as soon as there is more than one column (row to read them in), and the first row (column)
    the series if the definition says it has a header."""
    has_row = header_row and last.row > first.row
    has_col = last.col > first.col
    row0, col0 = first.row + has_row, first.col + has_col
    if series_in == "columns":
        categories = ((row0, first.col), (last.row, first.col)) if has_col else None
        series = tuple(
            Series(((row0, col), (last.row, col)), (first.row, col) if has_row else None)
            for col in range(col0, last.col + 1)
        )
    else:
        categories = ((first.row, col0), (first.row, last.col)) if has_row else None
        series = tuple(
            Series(((row, col0), (row, last.col)), (row, first.col) if has_col else None)
            for row in range(row0, last.row + 1)
        )
    return Plan(categories, series, has_row, has_col)


Area = tuple[tuple[int, int], tuple[int, int]]


def plan_from(
    sheet: SheetId, categories: Area | None, series: list[tuple[Area, Area | None]], rows: bool
) -> tuple[CellRef, CellRef, bool, Plan] | None:
    """The range the cells a chart names make, the way the model reads it, and what the model would draw of that
    range, when that is exactly the series and the categories the chart names; else ``None``."""
    areas = [area for values, label in series for area in (values, label) if area is not None]
    if categories is not None:
        areas.append(categories)
    first = CellRef(min(a[0][0] for a in areas), min(a[0][1] for a in areas), sheet)
    last = CellRef(max(a[1][0] for a in areas), max(a[1][1] for a in areas), sheet)
    if not (last.row < MAX_ROWS and last.col < MAX_COLS):
        return None
    want = tuple(Series(values, None if label is None else label[0]) for values, label in series)
    for header_row in (True, False):
        plan = plan_of(first, last, series_in="rows" if rows else "columns", header_row=header_row)
        if plan.categories == categories and plan.series == want and header_row == plan.first_row_is_header:
            return first, last, header_row, plan
    return None


def spec_of(  # noqa: PLR0913 (a chart's definition: its cells, its direction and everything it says)
    first: CellRef,
    last: CellRef,
    *,
    rows: bool,
    header_row: bool,
    title: str,
    x_title: str,
    y_title: str,
    legend: bool,
    gridlines: bool,
) -> ChartSpec | None:
    """The definition the model holds of a bar chart over ``first``..``last``, or ``None`` when the titles are more
    than a title of the model may be (the model checks what a file says before it takes it)."""
    try:
        spec = ChartSpec(
            id="c0",
            kind="bar",
            range=RangeRef(first, last),
            series_in="rows" if rows else "columns",
            header_row=header_row,
            title=title,
            x_title=x_title,
            y_title=y_title,
            legend=legend,
            gridlines=gridlines,
        )
        ChartSpec.from_data(spec.to_data())
    except ChartError:
        return None
    return spec


@dataclass(frozen=True)
class ReadChart:
    """A chart of a file that the model can hold: its definition (``id`` is left for the caller to give), its size
    in pixels and what it says to someone who cannot see it."""

    spec: ChartSpec
    width: int
    height: int
    description: str


def with_id(spec: ChartSpec, spec_id: str) -> ChartSpec:
    """``spec`` called ``spec_id``."""
    return replace(spec, id=spec_id)


def chart_losses(model: WorkbookModel) -> list[str]:
    """What a file cannot keep of the charts of ``model``, one detail for each: ``source`` (a chart that follows a name
    has the cells the name is now), ``rotation`` (a chart in a file stands upright) and ``empty`` (a chart that reads
    nothing is not written)."""
    lost: list[str] = []
    shown = [obj.body.chart for obj in model.objects.values() if obj.body.chart is not None]
    lost.extend("rotation" for obj in model.objects.values() if obj.body.chart is not None and obj.body.rotation)
    for spec_id in shown:
        spec = model.charts.get(spec_id)
        if not isinstance(spec, ChartSpec) or model.chart_cells(spec_id) is None:
            lost.append("empty")
            continue
        lost.extend(["source"] if spec.source else [])
    return lost


def number_text(value: float) -> str:
    return repr(int(value)) if float(value).is_integer() else repr(float(value))


def offset_of(widths: Mapping[int, float], heights: Mapping[int, float], row: int, col: int) -> tuple[float, float]:
    """Where the corner of a cell is, in pixels from the corner of the sheet (the inverse of ``cell_at``)."""
    left = sum(widths.get(column, DEFAULT_COL_WIDTH) for column in range(col))
    top = sum(heights.get(line, DEFAULT_ROW_HEIGHT) for line in range(row))
    return left, top
