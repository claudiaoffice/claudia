"""Search and replace in a workbook (E6.20, D285, D286): what is looked at, where, and what a replacement changes.

``claudia_search`` runs a search over texts that come with their place and knows no app. This module is computes'
part of it: which texts a workbook offers, where they are (``at`` = ``{"sheet", "row", "col"}``, CODE-18) and how a
replacement is stored.

A search looks in one or more *kinds* of text:

``text``      a cell holding text, as typed
``formulas``  a formula as typed, with its ``=``
``values``    what a cell *shows* that is not text typed into it: a number, TRUE or FALSE, and what a formula gives
              (an error shows its code)

Text and formulas are stored contents and may be replaced. Values are only ever found: the value of a formula follows
from its text, and a number's shown text is not what is stored. A cell that shows a part of a query result is a
value too (it is not stored). The part ``cellref`` (``B4``, ``$A$2``) is computes' own.

A replacement is planned first (:func:`plan_replacement`: which cells change, to what, which are skipped and why),
so that a person can see the effect before it is made; :func:`replace_command` turns the plan into one command that
stores the cells as they will be, never the pattern: replaying a log does not need the engine.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence

from claudia_core import Batch, Command
from claudia_search import CompiledSearch, Location, Plan, Scan, SearchError, Text, plan, scan

from .commands import SetCells
from .formula import parse_formula
from .model import Content, Sheet, WorkbookModel, content_of
from .refs import SheetId
from .values import format_value

KINDS = ("text", "formulas", "values")
REPLACEABLE = ("text", "formulas")
EXTRA_PARTS: Mapping[str, str] = {
    # A cell reference as a formula writes it: not part of a longer word or number, not a function name
    "cellref": r"(?<![\w.])\$?[A-Za-z]{1,3}\$?\d+(?![\w(])",
}

_KIND_OF = {"text": "text", "formulas": "formula", "values": "value"}
_REPLACEABLE_TEXTS = frozenset(_KIND_OF[k] for k in REPLACEABLE)
_COUNT_OF = {"text": "text", "formula": "formulas", "value": "values"}

Area = tuple[int, int, int, int]  # first row, first column, last row, last column, all 0-based and included
Held = Callable[[str, int, int], "str | None"]  # who holds this cell, if somebody else does


def cell_at(sheet: str, row: int, col: int) -> Location:
    """Where a cell is, as every answer of a search names it: ``{"sheet", "row", "col"}``."""
    return {"sheet": sheet, "row": row, "col": col}


def cell_of(at: Location) -> tuple[str, int, int]:
    """``(sheet, row, col)`` of a place a client sent back; ``ValueError`` if it is not a cell's."""
    ok = isinstance(at, Mapping) and set(at) == {"sheet", "row", "col"} and isinstance(at["sheet"], str)
    numbers = ok and all(isinstance(at[k], int) and not isinstance(at[k], bool) and at[k] >= 0 for k in ("row", "col"))
    if not numbers:
        raise ValueError("a place in a workbook is {sheet, row, col}")
    return at["sheet"], at["row"], at["col"]


# --------------------------------------------------------------------------------------------------------- looking
def _sheets_in(model: WorkbookModel, sheets: Sequence[str] | None) -> list[Sheet]:
    if sheets is None:
        return list(model.sheets.values())
    for sheet_id in sheets:
        model.sheet(SheetId(sheet_id))  # (ValueError for a sheet this workbook does not have)
    wanted = set(sheets)
    return [sheet for sheet in model.sheets.values() if sheet.id in wanted]


def _cells(sheet: Sheet, kinds: Sequence[str], area: Area | None) -> Iterator[tuple[int, int, str, str]]:
    """``(row, col, kind, text)`` for what the sheet offers to a search, by row, column and kind."""
    positions = set(sheet.cells)
    if "values" in kinds:
        positions.update(sheet.spilled)
    for row, col in sorted(positions):
        if area is not None and not (area[0] <= row <= area[2] and area[1] <= col <= area[3]):
            continue
        content = sheet.cells.get((row, col))
        if content is None:  # a part of a query result: shown, not stored
            if "values" in kinds:
                yield row, col, "value", format_value(sheet.grid.get((row, col)))
        elif content["t"] == "text":
            if "text" in kinds:
                yield row, col, "text", content["v"]
        elif content["t"] == "formula":
            if "formulas" in kinds:
                yield row, col, "formula", content["v"]
            if "values" in kinds:
                yield row, col, "value", format_value(sheet.grid.get((row, col)))
        elif "values" in kinds:  # a number or TRUE/FALSE, as it shows
            yield row, col, "value", format_value(content["v"])


def workbook_texts(
    model: WorkbookModel,
    kinds: Sequence[str] = ("text",),
    sheets: Sequence[str] | None = None,
    area: Area | None = None,
) -> Iterator[Text]:
    """What a workbook offers a search: the ``kinds`` of text, on ``sheets`` (``None``: all of them) and inside ``area``
    (on the one sheet), each with its cell as ``at``. ``ValueError`` for a kind or a sheet that does not exist."""
    _check_kinds(kinds)
    for sheet in _sheets_in(model, sheets):
        for row, col, kind, text in _cells(sheet, kinds, area):
            yield Text(cell_at(sheet.id, row, col), kind, text)


def _check_kinds(kinds: Sequence[str]) -> None:
    unknown = [kind for kind in kinds if kind not in KINDS]
    if unknown:
        raise ValueError(f"cannot look in {unknown[0]!r}: choose from {', '.join(KINDS)}")


def scan_workbook(
    model: WorkbookModel,
    search: CompiledSearch,
    *,
    kinds: Sequence[str] = ("text",),
    sheets: Sequence[str] | None = None,
    area: Area | None = None,
    deadline: float | None = None,
) -> Scan:
    """Where ``search`` finds something in the workbook (see :func:`workbook_texts`), until ``deadline`` (a
    :func:`time.monotonic` time; then the answer says ``timed_out``). ``counts`` is by the kinds asked for
    (``text``, ``formulas``, ``values``), each counting cells."""
    found = scan(workbook_texts(model, kinds, sheets, area), search, deadline=deadline, replaceable=_REPLACEABLE_TEXTS)
    counts = dict.fromkeys(KINDS, 0)
    for kind, cells in found.counts.items():
        counts[_COUNT_OF[kind]] = cells
    found.counts = counts
    return found


# ------------------------------------------------------------------------------------------------------- replacing
def plan_replacement(
    model: WorkbookModel,
    search: CompiledSearch,
    *,
    kinds: Sequence[str] = ("text",),
    sheets: Sequence[str] | None = None,
    area: Area | None = None,
    leave: Iterable[tuple[Location, int | None]] = (),
    held: Held | None = None,
    max_length: int | None = None,
    deadline: float | None = None,
) -> Plan:
    """What replacing would do, without doing it. Only text and formulas are replaced, whatever ``kinds`` says;
    ``leave`` names matches as ``(cell, number)`` (``number`` ``None``: the whole cell) a person wants to keep; ``held``
    says who holds a cell (a cell held by somebody else is skipped, and named); ``max_length`` is the longest text a
    cell may get. A plan that ran out of time before ``deadline`` says ``timed_out``.

    ``SearchError`` when the search has no replacement."""
    _check_kinds(kinds)
    wanted = tuple(kind for kind in kinds if kind in REPLACEABLE)

    def refuse(item: Text, after: str) -> tuple[str, str | None] | None:
        sheet, row, col = cell_of(item.at)
        owner = held(sheet, row, col) if held is not None else None
        if owner is not None:
            return "locked", owner
        reason = _refusal(model, item.kind, item.text, after, max_length)
        return None if reason is None else (reason, None)

    return plan(workbook_texts(model, wanted, sheets, area), search, leave=leave, refuse=refuse, deadline=deadline)


def _refusal(model: WorkbookModel, kind: str, before: str, after: str, max_length: int | None) -> str | None:
    if max_length is not None and len(after) > max_length:
        return "too_long"
    if kind == "formula" and _reads(model, before) and not (after.startswith("=") and _reads(model, after)):
        return "formula"
    return None


def _reads(model: WorkbookModel, formula: str) -> bool:
    return len(formula.strip()) > 1 and parse_formula(formula, model.sheet_id_of).ast is not None


def _content(kind: str, text: str) -> Content:
    if kind == "formula":
        return {"t": "formula", "v": text}
    return content_of(text) if text else None  # (nothing left of a text: the cell is empty)


def replace_command(made: Plan) -> Command | None:
    """The one command that makes the plan: the cells as they will be, stored by row and run of columns so that it
    holds exactly the cells it changes (and only those can be locked against it). ``None`` when nothing changes."""
    if not made.changes:
        return None
    cells = sorted(((cell_of(c.at), _content(c.kind, c.after)) for c in made.changes), key=lambda cell: cell[0])
    steps: list[Command] = []
    run: list[tuple[tuple[str, int, int], Content]] = []
    for (sheet, row, col), content in cells:
        if run and (sheet, row, col - 1) != run[-1][0]:
            steps.append(_set(run))
            run = []
        run.append(((sheet, row, col), content))
    steps.append(_set(run))
    count = len(cells)
    return Batch(tuple(steps), f"Replace in {count} cell{'' if count == 1 else 's'}")


def _set(run: list[tuple[tuple[str, int, int], Content]]) -> SetCells:
    return SetCells(SheetId(run[0][0][0]), tuple((row, col, content) for (_, row, col), content in run))


__all__ = [
    "EXTRA_PARTS",
    "KINDS",
    "REPLACEABLE",
    "SearchError",
    "cell_at",
    "cell_of",
    "plan_replacement",
    "replace_command",
    "scan_workbook",
    "workbook_texts",
]
