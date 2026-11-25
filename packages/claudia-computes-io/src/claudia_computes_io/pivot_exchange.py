"""A pivot table as a file holds it, the same for every format (E6.30, D625, D628).

Every format says a pivot in its own words -- ods as ``table:data-pilot-table``, xlsx as a cache and a
``pivotTableDefinition`` -- but it says the same things: which cells it summarises, which cells it fills, which fields
go where and how they are added up. :class:`FilePivot` is that, and nothing else; the format modules
(:mod:`.ods_pivots`, :mod:`.xlsx_pivots`) turn it into their XML and back, so the rules below are written once.

*Writing* (:func:`written_pivots`, :func:`sheet_cells`): a pivot of the model is a ``PIVOT("name")`` formula that
fills cells; no file knows that formula, so the cells it fills are written as plain values, which is what a pivot's
cells are in every file, and the pivot itself next to them. A pivot that cannot be written as one (its source is no
range with a header row) is written as the values alone, and the loss is said.

*Reading* (:func:`adopt_pivots`): a file's pivot is taken into the model as a live pivot only when the engine, given
the same source and fields, makes the very cells the file shows (the rule of D370: a cell is never wrong). The words
the file puts in its cells -- "Total Result", "Sum - Amount" -- are read off those cells, not guessed. What does not
match stays what it was: plain cells, with the loss said.
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace

from claudia_computes import (
    CellRef,
    NamedRange,
    PivotDefinition,
    PivotEntry,
    PivotError,
    PivotFilter,
    PivotLabels,
    PivotResult,
    PivotRole,
    RangeRef,
    Sheet,
    SheetId,
    ValueField,
    WorkbookModel,
    compute_pivot,
    content_of,
    parse_input,
)
from claudia_computes import sql as engine
from claudia_computes.model import Content
from claudia_computes.names import key_of, name_problem
from claudia_computes.values import Value, format_value
from claudia_odf_io import Loss, LossLog

#: The loss code of every problem with a pivot, and the details it comes with (``losses.add(PIVOT_LOSS, detail)``).
PIVOT_LOSS = "pivot-table"
#: Written as values: ``source`` (the pivot's source is no range with a header row), ``empty`` (no value field yet,
#: so it fills nothing). Not read as a pivot: ``fields`` (more of them than this version has, or none to add up),
#: ``source`` (the source is not a range of this file), ``different`` (the engine's cells are not the file's) and
#: ``layout`` (read, but the headers show the field names, not "Row Labels").
DETAILS = ("source", "empty", "fields", "different", "layout")

Position = tuple[int, int]


@dataclass(frozen=True, slots=True)
class FilePivot:
    """What a file says of one pivot table. ``source`` is the range it summarises (the header row first) and ``target``
    the cells it fills (a file may count some more above: the buttons of its filters). ``result`` is the grid the model
    gave, set when the pivot is written and used for the order of its members; a pivot read from a file has none."""

    name: str
    source: RangeRef
    target: RangeRef
    rows: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    values: tuple[ValueField, ...] = ()
    filters: tuple[PivotFilter, ...] = ()
    total_row: bool = True
    total_column: bool = True
    labels: PivotLabels = PivotLabels()
    result: PivotResult | None = None

    def definition(self, source: str) -> PivotDefinition:
        """The model's definition of it, over the name ``source``; :class:`~claudia_computes.PivotError` when the
        engine cannot hold it."""
        return PivotDefinition(
            source, self.rows, self.columns, self.values, self.filters, self.total_row, self.total_column
        )


@dataclass(frozen=True, slots=True)
class WrittenPivots:
    """The pivots of a model a file can hold as pivots, and what it cannot (each said as a loss)."""

    pivots: tuple[FilePivot, ...]
    losses: tuple[Loss, ...]


@dataclass(frozen=True, slots=True)
class Adoption:
    """What reading the pivots of a file came to: how many are live pivots of the model now, and the loss of each
    that is not."""

    adopted: int
    losses: tuple[Loss, ...]


# ------------------------------------------------------------------------------------------------ the source
def source_table(model: WorkbookModel, source: RangeRef) -> tuple[list[str], tuple[tuple[Value, ...], ...]]:
    """The header texts and the rows of ``source`` (a range whose first row is its header), as the engine reads a
    table: the texts are made into column names (:func:`claudia_computes.sql.column_names`)."""
    assert source.sheet is not None  # (a source is on a sheet)
    grid = model.sheet(source.sheet).grid
    first, last = source.first, source.last
    headers = [format_value(grid.get((first.row, col))) for col in range(first.col, last.col + 1)]
    rows = tuple(
        tuple(grid.get((row, col)) for col in range(first.col, last.col + 1))
        for row in range(first.row + 1, last.row + 1)
    )
    return engine.column_names(headers), rows


# ------------------------------------------------------------------------------------------------ writing
@dataclass(frozen=True, slots=True)
class _Placed:
    """A pivot that shows cells: where, and what it shows."""

    entry: PivotEntry
    anchor: tuple[SheetId, int, int]
    result: PivotResult

    @property
    def target(self) -> RangeRef:
        sheet, row, col = self.anchor
        last = CellRef(row + self.result.height - 1, col + self.result.width - 1, sheet)
        return RangeRef.between(CellRef(row, col, sheet), last)


def _placed(model: WorkbookModel) -> list[_Placed]:
    found = []
    for entry in model.pivots.sorted():
        named = model.names.get(key_of(None, entry.name))
        result = model.pivots.result(entry.name)
        if named is not None and named.anchor is not None and result is not None and result.rows:
            found.append(_Placed(entry, named.anchor, result))
    return found


def written_pivots(model: WorkbookModel, among: Collection[str] | None = None) -> WrittenPivots:
    """The pivots of ``model`` as a file says them, and what a file cannot hold of the others: a pivot that shows
    nothing (``empty``) is not written, one over cells that are no range with a header row (``source``: a query's
    result, a range with no header) is written as the values it shows. With ``among``, only the pivots of those names
    (what a kept file adds)."""
    found: list[FilePivot] = []
    losses = LossLog()
    placed_ones = [placed for placed in _placed(model) if among is None or placed.entry.name in among]
    shown = {placed.entry.name for placed in placed_ones}
    for entry in model.pivots.sorted():
        if entry.name not in shown and (among is None or entry.name in among):
            losses.add(PIVOT_LOSS, "empty")
    for placed in placed_ones:
        pivot = _file_pivot(model, placed)
        if pivot is None:
            losses.add(PIVOT_LOSS, "source")
        else:
            found.append(pivot)
    return WrittenPivots(tuple(found), losses.result())


def _file_pivot(model: WorkbookModel, placed: _Placed) -> FilePivot | None:
    definition = placed.entry.definition
    named = model.names.resolve(placed.anchor[0], definition.source)
    if named is None or named.range is None or not named.header or named.range.first.row == named.range.last.row:
        return None
    fields = {field.casefold(): field for field in source_table(model, named.range)[0]}

    def find(field: str) -> str:
        return fields.get(field.casefold(), field)

    return FilePivot(
        placed.entry.name,
        named.range,
        placed.target,
        tuple(find(field) for field in definition.rows),
        tuple(find(field) for field in definition.columns),
        tuple(replace(value, field=find(value.field)) for value in definition.values),
        tuple(replace(each, field=find(each.field)) for each in definition.filters),
        definition.total_row,
        definition.total_column,
        placed.entry.labels,
        placed.result,
    )


def sheet_cells(model: WorkbookModel, sheet: Sheet) -> dict[Position, tuple[Content, Value]]:
    """Every cell a file has on ``sheet`` with the value it shows: the sheet's own cells, and the cells its pivots
    fill, which are values (the formula that fills them is the model's, not the file's)."""
    cells: dict[Position, tuple[Content, Value]] = {
        position: (content, sheet.grid.get(position)) for position, content in sheet.cells.items()
    }
    for placed in _placed(model):
        if placed.anchor[0] != sheet.id:
            continue
        _, row, col = placed.anchor
        for r, line in enumerate(placed.result.rows):
            for c, value in enumerate(line):
                content = content_of(value)
                if content is None:
                    cells.pop((row + r, col + c), None)
                else:
                    cells[(row + r, col + c)] = (content, value)
    return cells


def pivot_positions(model: WorkbookModel, sheet: SheetId) -> set[Position]:
    """The positions on ``sheet`` that a pivot of ``model`` fills."""
    inside: set[Position] = set()
    for placed in _placed(model):
        if placed.anchor[0] == sheet:
            _, row, col = placed.anchor
            inside |= {(row + r, col + c) for r in range(placed.result.height) for c in range(placed.result.width)}
    return inside


def outside_pivots(model: WorkbookModel, sheet: SheetId, cells: Mapping[Position, Content]) -> dict[Position, Content]:
    """``cells`` of ``sheet`` without those a pivot of ``model`` fills: what a kept file's cells must be to be the ones
    the model was read from (a pivot's cells are the file's, and need not be the engine's to the letter)."""
    inside = pivot_positions(model, sheet)
    return {position: content for position, content in cells.items() if position not in inside}


# ------------------------------------------------------------------------------------------------ reading
class _Refused(Exception):  # noqa: N818 (not an error: the answer "this pivot stays cells")
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True, slots=True)
class _Plan:
    """A pivot of a file that the engine makes the same cells of: what to put in the model for it."""

    entry: PivotEntry
    anchor: tuple[SheetId, int, int]
    result: PivotResult
    source: NamedRange | None
    layout: bool

    def apply(self, model: WorkbookModel) -> None:
        sheet = model.sheet(self.anchor[0])
        _, row, col = self.anchor
        for r in range(self.result.height):
            for c in range(self.result.width):
                sheet.cells.pop((row + r, col + c), None)
        formula = parse_input(f'=PIVOT("{self.entry.name}")')
        assert formula is not None
        sheet.cells[(row, col)] = formula
        if self.source is not None:
            model.names.put(self.source)
        model.pivots.put(self.entry.name, self.entry)
        model.names.put(NamedRange(self.entry.name, None, None, True, False, "result", (), self.anchor))


def adopt_pivots(model: WorkbookModel, found: Sequence[FilePivot]) -> Adoption:
    """Take the pivots ``found`` in a file into ``model`` -- whose cells are the file's, already calculated -- as live
    pivots, each only if the engine makes the cells the file has. The cells a pivot fills are then its own (the model
    holds the formula in the first one); the others stay the file's cells and the loss of each is in the result."""
    losses = LossLog()
    plans: list[_Plan] = []
    for pivot in found:
        try:
            plan = _plan(model, pivot, plans)
        except _Refused as refusal:
            losses.add(PIVOT_LOSS, refusal.detail)
            continue
        plans.append(plan)
        if plan.layout:
            losses.add(PIVOT_LOSS, "layout")
    for plan in plans:
        plan.apply(model)
    if plans:
        model._calculate_loaded()  # noqa: SLF001 (the restore()-mirroring construction idiom, as the importers do)
    return Adoption(len(plans), losses.result())


def _plan(model: WorkbookModel, pivot: FilePivot, earlier: Sequence[_Plan]) -> _Plan:
    if pivot.source.sheet not in model.sheets or pivot.target.sheet not in model.sheets:
        raise _Refused("source")
    taken = {plan.entry.name.casefold() for plan in earlier} | {
        plan.source.name.casefold() for plan in earlier if plan.source is not None
    }
    name = _free_name(model, pivot.name, taken)
    source = _source_name(model, pivot, name, taken | {name.casefold()}, earlier)
    table = source_table(model, pivot.source)
    pivot = replace(pivot, filters=tuple(_restored(each, table) for each in pivot.filters))

    def tables(text: str):  # noqa: ANN202 (the engine's TableSource)
        return table if text.casefold() == source.name.casefold() else None

    try:
        definition = pivot.definition(source.name)
    except PivotError:
        raise _Refused("fields") from None
    if not definition.values:
        raise _Refused("fields")
    entry, result, layout = _prove(model, pivot, name, definition, tables)
    assert pivot.target.sheet is not None  # (a pivot's ranges are on sheets)
    anchor = (
        pivot.target.sheet,
        pivot.target.last.row - result.height + 1,
        pivot.target.first.col,
    )
    return _Plan(entry, anchor, result, None if source.existing else source.named, layout)


def _restored(each: PivotFilter, table: tuple[list[str], tuple[tuple[Value, ...], ...]]) -> PivotFilter:
    """A filter whose members a file wrote as text, with each as the value the source has (``1`` for ``"1"``)."""
    names = [name.casefold() for name in table[0]]
    if each.keep is None or each.field.casefold() not in names:
        return each
    column = names.index(each.field.casefold())
    shown = {format_value(line[column]): line[column] for line in table[1] if line[column] is not None}
    return PivotFilter(each.field, tuple(shown.get(format_value(member), member) for member in each.keep))


@dataclass(frozen=True, slots=True)
class _Source:
    name: str
    named: NamedRange
    existing: bool


def _source_name(
    model: WorkbookModel, pivot: FilePivot, pivot_name: str, taken: set[str], earlier: Sequence[_Plan]
) -> _Source:
    """The name the pivot's source goes by: a table or range of the workbook that is exactly its cells (or one an
    earlier pivot of the file made for them), else a new one (``<pivot>_Source``)."""
    made = [plan.source for plan in earlier if plan.source is not None]
    for named in (*model.names, *made):
        if named.scope is None and named.range == pivot.source and named.header and not named.is_result:
            return _Source(named.name, named, existing=True)
    name = _free_name(model, f"{pivot_name}_Source", taken)
    return _Source(name, NamedRange(name, None, pivot.source, True), existing=False)


def _free_name(model: WorkbookModel, wanted: str, taken: set[str]) -> str:
    text = re.sub(r"[^\w.]", "_", wanted.strip()) or "Pivot"
    if name_problem(text) is not None:
        text = f"Pivot_{text}"
    if name_problem(text) is not None:
        text = "Pivot"

    def free(candidate: str) -> bool:
        return (
            candidate.casefold() not in taken
            and model.names.get(key_of(None, candidate)) is None
            and model.pivots.get(candidate) is None
        )

    candidate, number = text, 1
    while not free(candidate):
        number += 1
        candidate = f"{text}_{number}"
    return candidate


def _prove(
    model: WorkbookModel, pivot: FilePivot, name: str, definition: PivotDefinition, tables
) -> tuple[PivotEntry, PivotResult, bool]:  # noqa: ANN001
    """The pivot as the model will hold it, the grid it makes and whether the headers differ (the file shows
    "Row Labels" where the engine writes the field's name), or :class:`_Refused` when the engine's cells are not the
    file's. The words of the file -- its total, its blank, its value titles -- are read off the cells first."""
    labels = pivot.labels
    first = _run(definition, tables, labels)
    found = _file_grid(model, pivot, first)
    words = _words(first, found, definition, labels)
    values = tuple(
        replace(value, name=words.titles.get(_title(value, labels), value.name)) for value in definition.values
    )
    labels = replace(labels, total=words.total or labels.total, blank=words.blank or labels.blank)
    definition = replace(definition, values=values)
    result = _run(definition, tables, labels)
    layout = False
    for r, line in enumerate(result.rows):
        for c, value in enumerate(line):
            if _same(value, found[r][c]):
                continue
            if result.roles[r][c] is PivotRole.FIELD and isinstance(found[r][c], str):
                layout = True
                continue
            raise _Refused("different")
    return PivotEntry(name, definition, labels), result, layout


def _run(definition: PivotDefinition, tables, labels: PivotLabels) -> PivotResult:  # noqa: ANN001
    try:
        result = compute_pivot(definition, tables, labels)
    except PivotError:
        raise _Refused("source") from None
    if not result.rows:
        raise _Refused("fields")
    return result


def _file_grid(model: WorkbookModel, pivot: FilePivot, result: PivotResult) -> list[list[Value]]:
    """The cells of the file where the engine's grid would go: the bottom of the target (a file may put the buttons of
    its filters above)."""
    target = pivot.target
    if result.width != target.last.col - target.first.col + 1 or result.height > target.last.row - target.first.row + 1:
        raise _Refused("different")
    top = target.last.row - result.height + 1
    sheet = model.sheet(target.sheet)  # type: ignore[arg-type]
    return [
        [sheet.grid.get((top + r, target.first.col + c)) for c in range(result.width)] for r in range(result.height)
    ]


@dataclass(frozen=True, slots=True)
class _Words:
    total: str | None
    blank: str | None
    titles: dict[str, str]


def _title(value: ValueField, labels: PivotLabels) -> str:
    return value.name or labels.title(value.aggregation, value.field)


def _words(result: PivotResult, found: list[list[Value]], definition: PivotDefinition, labels: PivotLabels) -> _Words:
    """The words the file puts where the engine puts its own: ``Total``, ``(blank)`` and the title of each value."""
    titles = {_title(value, labels) for value in definition.values}
    total: set[str] = set()
    blank: set[str] = set()
    named: dict[str, str] = {}
    for r, line in enumerate(result.rows):
        for c, ours in enumerate(line):
            theirs = found[r][c]
            if _same(ours, theirs) or not isinstance(theirs, str):
                continue
            role = result.roles[r][c]
            if ours == labels.total and role in (PivotRole.TOTAL, PivotRole.HEADER):
                total.add(theirs)
            elif ours == labels.blank and role in (PivotRole.LABEL, PivotRole.HEADER):
                blank.add(theirs)
            elif ours in titles and role in (PivotRole.CORNER, PivotRole.HEADER):
                named.setdefault(str(ours), theirs)
    return _Words(
        next(iter(total)) if len(total) == 1 else None,
        next(iter(blank)) if len(blank) == 1 else None,
        named,
    )


def _same(ours: Value, theirs: Value) -> bool:
    """Whether a cell the engine made is the cell the file shows: numbers to the digits a file keeps, an empty cell
    and an empty text as one."""
    if ours in (None, "") and theirs in (None, ""):
        return True
    numbers = (int, float)
    if isinstance(ours, numbers) and isinstance(theirs, numbers) and not isinstance(ours, bool):
        return not isinstance(theirs, bool) and math.isclose(ours, theirs, rel_tol=1e-9, abs_tol=1e-9)
    return ours == theirs and type(ours) is type(theirs)


__all__ = [
    "DETAILS",
    "PIVOT_LOSS",
    "Adoption",
    "FilePivot",
    "WrittenPivots",
    "adopt_pivots",
    "outside_pivots",
    "sheet_cells",
    "source_table",
    "written_pivots",
]
