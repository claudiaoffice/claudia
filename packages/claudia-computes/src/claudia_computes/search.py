"""Search and replace in a workbook (E6.20, D285, D286): what is looked at, where, and what a replacement changes.

``claudia_core.search`` finds spans in plain texts and knows no app. This module is computes' part of it: which texts
a workbook offers and how a replacement is stored.

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

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field

from claudia_core import Batch, Command, CompiledSearch, Match, SearchError

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

MAX_LISTED = 2_000  # matches a search lists; the counts are of all of them
CONTEXT = 60  # characters of a cell shown on each side of a match
MAX_SHOWN = 120  # characters of a match itself that are shown

_KIND_OF = {"text": "text", "formulas": "formula", "values": "value"}
_KIND_ORDER = {"text": 0, "formula": 1, "value": 2}
_COUNT_OF = {"text": "text", "formula": "formulas", "value": "values"}

Area = tuple[int, int, int, int]  # first row, first column, last row, last column, all 0-based and included
Leave = Mapping[tuple[str, int, int], "set[int] | None"]  # cell -> the matches in it to leave (None: all of them)
Held = Callable[[str, int, int], "str | None"]  # who holds this cell, if somebody else does


@dataclass(frozen=True)
class Hit:
    """One match: the cell, the kind of text it is in, its number among the cell's matches and where it is."""

    sheet: str
    row: int
    col: int
    kind: str  # "text", "formula" or "value"
    number: int
    start: int
    end: int
    kept: tuple[str, ...]
    after: str | None  # what the match would become; ``None`` for a value (never replaced) or without replacement
    text: str  # an excerpt of the cell around the match
    excerpt_start: int  # the match inside ``text``
    excerpt_end: int
    clipped_before: bool  # the cell goes on before ``text``
    clipped_after: bool  # and after it


@dataclass(frozen=True)
class LeftOut:
    """A cell that looks like a match but was left out, and why (a condition's data, or ``{"kind": "filter"}``)."""

    sheet: str
    row: int
    col: int
    kind: str
    why: dict


@dataclass
class Scan:
    """What a search found: the matches (at most :data:`MAX_LISTED`), the cells left out, and how much there is."""

    matches: list[Hit] = field(default_factory=list)
    left_out: list[LeftOut] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(KINDS, 0))  # cells holding a match, by kind
    total: int = 0  # all matches, also those not listed
    truncated: bool = False  # more matches than are listed
    timed_out: bool = False  # the search was stopped before it had looked at everything


@dataclass(frozen=True)
class Change:
    """A cell a replacement changes, from ``before`` to ``after`` (text, or a formula with its ``=``)."""

    sheet: str
    row: int
    col: int
    kind: str  # "text" or "formula"
    before: str
    after: str
    content: Content  # what is stored then


@dataclass(frozen=True)
class Skip:
    """A cell a replacement leaves alone, ``reason`` being ``locked`` (``by`` holds it), ``formula`` (it would no
    longer be a formula that reads) or ``too_long``."""

    sheet: str
    row: int
    col: int
    kind: str
    reason: str
    by: str | None = None


@dataclass
class Plan:
    """What a replacement would do."""

    changes: list[Change] = field(default_factory=list)
    skipped: list[Skip] = field(default_factory=list)


# --------------------------------------------------------------------------------------------------------- looking
def _sheets_in(model: WorkbookModel, sheets: Sequence[str] | None) -> list[Sheet]:
    if sheets is None:
        return list(model.sheets.values())
    for sheet_id in sheets:
        model.sheet(SheetId(sheet_id))  # (ValueError for a sheet this workbook does not have)
    wanted = set(sheets)
    return [sheet for sheet in model.sheets.values() if sheet.id in wanted]


def _texts(sheet: Sheet, kinds: Sequence[str], area: Area | None) -> Iterator[tuple[int, int, str, str]]:
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


def _check_kinds(kinds: Sequence[str]) -> None:
    unknown = [kind for kind in kinds if kind not in KINDS]
    if unknown:
        raise ValueError(f"cannot look in {unknown[0]!r}: choose from {', '.join(KINDS)}")


def _excerpt(text: str, start: int, end: int) -> tuple[str, int, int, bool, bool]:
    shown_end = min(end, start + MAX_SHOWN)
    first, last = max(0, start - CONTEXT), min(len(text), shown_end + CONTEXT)
    return text[first:last], start - first, shown_end - first, first > 0, last < len(text)


def scan(
    model: WorkbookModel,
    search: CompiledSearch,
    *,
    kinds: Sequence[str] = ("text",),
    sheets: Sequence[str] | None = None,
    area: Area | None = None,
    time_up: Callable[[], bool] | None = None,
) -> Scan:
    """Where ``search`` finds something: in the ``kinds`` of text, on ``sheets`` (``None``: all of them) and inside
    ``area`` (on the one sheet). ``time_up`` is asked before every text; once it says yes the search stops and the
    answer says so. ``ValueError`` for a sheet that does not exist."""
    _check_kinds(kinds)
    result = Scan()
    for sheet in _sheets_in(model, sheets):
        for row, col, kind, text in _texts(sheet, kinds, area):
            if time_up is not None and time_up():
                result.timed_out = True
                return result
            found = search.matches(text)
            if not found:
                why = search.left_out(text)
                if why is not None:
                    result.left_out.append(LeftOut(sheet.id, row, col, kind, why))
                continue
            result.counts[_COUNT_OF[kind]] += 1
            result.total += len(found)
            for number, match in enumerate(found):
                if len(result.matches) >= MAX_LISTED:
                    result.truncated = True
                    break
                result.matches.append(_hit(sheet.id, row, col, kind, number, text, match))
    return result


def _hit(sheet: str, row: int, col: int, kind: str, number: int, text: str, match: Match) -> Hit:
    shown, first, last, before_cut, after_cut = _excerpt(text, match.start, match.end)
    after = match.after if kind != "value" else None
    return Hit(
        sheet,
        row,
        col,
        kind,
        number,
        match.start,
        match.end,
        match.kept,
        after,
        shown,
        first,
        last,
        before_cut,
        after_cut,
    )


# ------------------------------------------------------------------------------------------------------- replacing
def plan_replacement(
    model: WorkbookModel,
    search: CompiledSearch,
    *,
    kinds: Sequence[str] = ("text",),
    sheets: Sequence[str] | None = None,
    area: Area | None = None,
    leave: Leave | None = None,
    held: Held | None = None,
    max_length: int | None = None,
) -> Plan:
    """What replacing would do, without doing it. Only text and formulas are replaced, whatever ``kinds`` says;
    ``leave`` names matches (or whole cells, with ``None``) a person wants to keep; ``held`` says who holds a cell
    (a cell held by somebody else is skipped, and named); ``max_length`` is the longest text a cell may get.

    ``SearchError`` when the search has no replacement."""
    _check_kinds(kinds)
    wanted = tuple(kind for kind in kinds if kind in REPLACEABLE)
    plan = Plan()
    for sheet in _sheets_in(model, sheets):
        for row, col, kind, text in _texts(sheet, wanted, area):
            skip = (leave or {}).get((sheet.id, row, col), ())
            if skip is None:
                continue
            after = search.replaced(text, set(skip))
            if after == text:
                continue
            reason = _refusal(model, kind, text, after, max_length)
            owner = held(sheet.id, row, col) if held is not None else None
            if owner is not None:
                plan.skipped.append(Skip(sheet.id, row, col, kind, "locked", owner))
            elif reason is not None:
                plan.skipped.append(Skip(sheet.id, row, col, kind, reason))
            else:
                plan.changes.append(Change(sheet.id, row, col, kind, text, after, _content(kind, after)))
    return plan


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


def replace_command(plan: Plan) -> Command | None:
    """The one command that makes ``plan``: the cells as they will be, stored by row and run of columns so that it
    holds exactly the cells it changes (and only those can be locked against it). ``None`` when nothing changes."""
    if not plan.changes:
        return None
    steps: list[Command] = []
    ordered = sorted(plan.changes, key=lambda c: (c.sheet, c.row, c.col))
    run: list[Change] = []
    for change in ordered:
        if run and (change.sheet, change.row, change.col - 1) != (run[-1].sheet, run[-1].row, run[-1].col):
            steps.append(_set(run))
            run = []
        run.append(change)
    steps.append(_set(run))
    count = len(ordered)
    return Batch(tuple(steps), f"Replace in {count} cell{'' if count == 1 else 's'}")


def _set(run: list[Change]) -> SetCells:
    return SetCells(SheetId(run[0].sheet), tuple((c.row, c.col, c.content) for c in run))


__all__ = [
    "EXTRA_PARTS",
    "KINDS",
    "MAX_LISTED",
    "REPLACEABLE",
    "Change",
    "Hit",
    "LeftOut",
    "Plan",
    "Scan",
    "SearchError",
    "Skip",
    "plan_replacement",
    "replace_command",
    "scan",
]
