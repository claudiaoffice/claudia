"""The charts of a workbook as both formats need them (D462, D463, D1477): which are written and where, what changed
of one since a file was read, and what a file's chart is in the model (:meth:`FileChart.file_object`). Only how a
file says it differs (:mod:`.xlsx_charts`, :mod:`.ods_charts`)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace

from claudia_computes import ChartSpec, ObjectBody, SheetId, VisualObject, WorkbookModel

from ._placed import Placed
from ._read_back import FileObject
from .chart_plan import ReadChart, with_id


def definition_of(model: WorkbookModel, obj: VisualObject) -> ChartSpec:
    """The definition a chart object of ``model`` shows."""
    assert obj.body.chart is not None  # (the caller picks chart objects)
    spec = model.charts[obj.body.chart]
    assert isinstance(spec, ChartSpec)
    return spec


@dataclass(frozen=True)
class WrittenChart:
    """A chart for a file: where it is, and what it shows."""

    placed: Placed
    spec: ChartSpec


def written_charts(model: WorkbookModel, placed: Iterable[Placed]) -> tuple[WrittenChart, ...]:
    """The charts among ``placed``, in their order."""
    return tuple(WrittenChart(one, definition_of(model, one.obj)) for one in placed if one.obj.body.chart is not None)


@dataclass(frozen=True)
class ChartChange:
    """What became of a chart of a kept file: what it showed and shows, whether it shows something else now
    (``redefined``) and whether its part is to be drawn again (``redraw``: also when its size or numbers changed)."""

    before: ChartSpec
    after: ChartSpec
    redefined: bool
    redraw: bool


def chart_change(baseline: WorkbookModel, current: WorkbookModel, was: VisualObject, now: VisualObject) -> ChartChange:
    """What became of the chart ``was`` of ``baseline``, which is ``now`` in ``current``."""
    before, after = definition_of(baseline, was), definition_of(current, now)
    redefined = replace(before, id="") != replace(after, id="")
    redraw = (
        redefined
        or (was.body.w, was.body.h) != (now.body.w, now.body.h)
        or baseline.chart_figure(before.id) != current.chart_figure(after.id)
    )
    return ChartChange(before, after, redefined, redraw)


@dataclass(kw_only=True)
class FileChart:
    """One chart of a file, pinned to the cell ``row``, ``col`` of ``sheet`` (``corner``: how far from the corner of
    the sheet, in pixels); what the model makes of it (``None``: one the model does not hold) and the ids it has
    there. Each format adds where its chart is in the file."""

    sheet: SheetId
    row: int
    col: int
    corner: Callable[[], tuple[float, float]] = lambda: (0.0, 0.0)
    order: int = 0
    name: str = ""
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

    def file_object(self) -> FileObject | None:
        """The chart as the model holds it (``None``: it does not)."""
        if self.held is None:
            return None
        body = ObjectBody(
            self.object_id,
            "chart",
            self.width,
            self.height,
            "plain-image",
            ref=self.spec_id,
            name=self.name,
            description=self.description,
        )
        return FileObject(self.sheet, self.row, self.col, self.corner, body, "chart", self.order, chart=self.spec)
