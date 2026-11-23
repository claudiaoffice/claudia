"""Commands for pivot tables (E6.30, D620): the one that sets a pivot's definition, and the three things a person does
with a pivot — make one, change one, delete one — each as the single step of the history it is.

A pivot is three things that belong together: its definition (:class:`~claudia_computes.PivotEntry`), the
``PIVOT("name")`` formula in the cell where it starts, and the name its cells have (D607). :func:`create_pivot`,
:func:`update_pivot` and :func:`delete_pivot` build the commands that keep the three in step, out of ``SetPivot`` and
the commands of cells and names; so an undo is always an exact inverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from claudia_core import Batch, Command, Context, Refusal

from .commands import AddSheet, SetCells, register
from .entry import parse_input
from .events import PivotsChanged
from .formula.syntax import MAX_LENGTH
from .model import WorkbookModel
from .name_commands import DefineName, RemoveName
from .names import NamedRange, key_of, name_problem
from .pivot import PivotDefinition, PivotLabels
from .pivots import PivotEntry
from .refs import SheetId


@register
@dataclass(frozen=True)
class SetPivot(Command):
    """Set the definition of the pivot called ``name``, or with ``entry`` ``None`` take the pivot's definition away.
    The cells that show the pivot are calculated again. On its own it does not touch the cells or the name: see
    :func:`create_pivot`, :func:`update_pivot` and :func:`delete_pivot`."""

    kind: ClassVar[str] = "computes.SetPivot"
    name: str
    entry: PivotEntry | None

    @property
    def label(self) -> str:
        return "Delete pivot table" if self.entry is None else "Pivot table"

    @property
    def summary(self) -> str:
        return f"delete {self.name}" if self.entry is None else f"pivot {self.name}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        before = ctx.model.put_pivot(self.name, self.entry)
        ctx.emit(PivotsChanged())
        return SetPivot(self.name, before)

    def to_data(self) -> dict:
        return {"name": self.name, "entry": None if self.entry is None else self.entry.to_data()}

    @classmethod
    def from_data(cls, data, registry) -> SetPivot:
        return cls(data["name"], None if data["entry"] is None else PivotEntry.from_data(data["entry"]))

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, SetPivot) and other.name.casefold() == self.name.casefold() else self


def create_pivot(
    model: WorkbookModel,
    name: str,
    anchor: tuple[SheetId, int, int],
    definition: PivotDefinition,
    labels: PivotLabels | None = None,
    new_sheet: str | None = None,
) -> Command:
    """Make the pivot ``name`` that starts in the cell ``anchor`` (sheet, row, column): its definition, the formula in
    the cell and the name of what it fills, as one change. With ``new_sheet`` the sheet is made too, called that,
    with the id ``anchor`` names (Excel's "On a new sheet"). ``ValueError`` when ``name`` is no good or is taken, or
    the sheet is not there (or is, for a new one)."""
    problem = name_problem(name)
    if problem is not None:
        raise problem
    if model.names.get(key_of(None, name)) is not None or model.pivots.get(name) is not None:
        raise Refusal("{name} is already a name", name=name)
    steps: list[Command] = []
    if new_sheet is None:
        if anchor[0] not in model.sheets:
            raise ValueError(f"this document does not know the sheet {anchor[0]!r}")
    else:
        if anchor[0] in model.sheets:
            raise ValueError(f"sheet id {anchor[0]!r} exists")
        steps.append(AddSheet(anchor[0], new_sheet))
    entry = PivotEntry(name, definition, labels if labels is not None else PivotLabels())
    cell = parse_input(f'=PIVOT("{name}")')
    result = NamedRange(name, None, None, True, False, "result", (), anchor)
    steps += [SetPivot(name, entry), SetCells(anchor[0], ((anchor[1], anchor[2], cell),)), DefineName(result)]
    return Batch(tuple(steps))


def update_pivot(
    model: WorkbookModel, name: str, definition: PivotDefinition, labels: PivotLabels | None = None
) -> Command:
    """Change what the pivot ``name`` is made from (and, with ``labels``, its words); its cells follow. ``ValueError``
    when there is no such pivot."""
    entry = _entry(model, name)
    return SetPivot(entry.name, PivotEntry(entry.name, definition, entry.labels if labels is None else labels))


def delete_pivot(model: WorkbookModel, name: str) -> Command:
    """Take the pivot ``name`` away: its cells are empty, its name and its definition gone, as one change.
    ``ValueError`` when there is no such pivot."""
    entry = _entry(model, name)
    named = model.names.get(key_of(None, entry.name))
    steps: list[Command] = [SetPivot(entry.name, None)]
    if named is not None and named.anchor is not None:
        steps.append(SetCells(named.anchor[0], ((named.anchor[1], named.anchor[2], None),)))
    if named is not None:
        steps.append(RemoveName(None, entry.name))
    return steps[0] if len(steps) == 1 else Batch(tuple(steps))


def pivot_to_sql(model: WorkbookModel, name: str) -> Command:
    """Turn the pivot ``name`` into the ``SQL()`` query it is (D624): the cell that starts it holds the query, the
    name is the query's result now, and the pivot is gone, as one change. The cells are what the query gives, which
    is one header row (the column names) and the rows below it; a pivot with a column field had more header rows.
    ``ValueError`` when there is no such pivot, it gave nothing (it has no SQL to turn), or its query is too long for a
    formula."""
    entry = _entry(model, name)
    result = model.pivots.result(entry.name)
    named = model.names.get(key_of(None, entry.name))
    if result is None or not result.sql or named is None or named.anchor is None:
        raise Refusal("the pivot table {name} gave nothing: there is no SQL to turn it into", name=entry.name)
    formula = '=SQL("' + result.sql.replace('"', '""') + '")'
    if len(formula) > MAX_LENGTH:
        raise Refusal(
            "the query of {name} is too long for a formula: {count_formula:,} of {max_length:,} characters",
            name=entry.name,
            count_formula=len(formula),
            max_length=MAX_LENGTH,
        )
    sheet, row, col = named.anchor
    return Batch(
        (
            SetPivot(entry.name, None),
            SetCells(sheet, ((row, col, parse_input(formula)),)),
            DefineName(NamedRange(entry.name, None, None, True, False, "result", (), named.anchor)),
        )
    )


def _entry(model: WorkbookModel, name: str) -> PivotEntry:
    entry = model.pivots.get(name)
    if entry is None:
        raise Refusal("there is no pivot table called {name!r}", name=name)
    return entry


__all__ = ["SetPivot", "create_pivot", "delete_pivot", "pivot_to_sql", "update_pivot"]
