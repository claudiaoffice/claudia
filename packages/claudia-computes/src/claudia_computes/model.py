"""The computes document model: sheets of cells that hold values or formulas.

A cell *holds* ``Content`` (what was typed: a constant, or a formula as text) and *shows* a value. The first is the
document: it is what commands write, what is serialized and what history keeps. The second is derived from it by
the calculator (``calc``) after every command, so it is never stored and always follows from the contents.

    sheet.cells   stored contents, sparse            {"t": "int"|"float"|"text"|"bool"|"formula", "v": ...}
    sheet.grid    the values the cells show, sparse  int, float, str, bool or ErrorValue (never None)
    sheet.view()  the content a client displays      a constant as stored; a formula as its value plus "f", the formula

Everything that changes a cell goes through ``WorkbookModel`` (``store``, ``restructure``, ``drop_sheet``), which
tells the calculator what happened; commands never touch ``cells`` themselves.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right, insort
from collections import defaultdict
from heapq import heappop, heappush
from typing import ClassVar, Self

from claudia_core import CommandRegistry, DocumentModel, Region, new_registry

from .calc import Calculator
from .formula.rewrite import adjusted, without_sheet
from .functions.registry import FunctionRegistry
from .limits import MAX_COLS, MAX_ROWS  # noqa: F401  (the names have lived here: other packages import them from here)
from .refs import Position, SheetId, StructuralEdit
from .values import ErrorValue, Value

Content = dict | None  # None (empty) or {"t": "int"|"float"|"text"|"bool"|"formula", "v": ...}
Cells = list[tuple[int, int, Content]]

_default_functions: FunctionRegistry | None = None


def default_functions() -> FunctionRegistry:
    """The built-in functions, one registry for all workbooks of the process."""
    global _default_functions  # noqa: PLW0603
    if _default_functions is None:
        from .functions.builtin import builtin_registry

        _default_functions = builtin_registry()
    return _default_functions


def content_of(value) -> Content:
    """Typed content for a Python value (``None`` is an empty cell). An ``ErrorValue`` becomes an ``error`` content,
    which is how a client is told about a formula that ended in an error."""
    if value is None:
        return None
    if isinstance(value, bool):
        return {"t": "bool", "v": value}
    if isinstance(value, int):
        return {"t": "int", "v": value}
    if isinstance(value, float):
        return {"t": "float", "v": value}
    if isinstance(value, ErrorValue):
        return {"t": "error", "v": value.code, **({"d": value.detail} if value.detail else {})}
    return {"t": "text", "v": str(value)}


def value_of(content: Content) -> Value:
    """The value a constant content shows (formulas show what they calculate: this gives ``None`` for them)."""
    if content is not None and content["t"] in ("int", "float", "text", "bool"):
        return content["v"]
    return None


class _LiveMax:
    """The largest of a set of non-negative ints that gains and loses members, without rescanning on removal.

    A max-heap of values that have ever been live, lazily cleaned: a value no longer live is dropped only once it
    would be the answer, not when it stops being live. Cost is amortized over how often a value newly becomes live,
    never over how many values are currently live — the same trade a hash index makes against a sorted one."""

    __slots__ = ("_heap", "_live")

    def __init__(self) -> None:
        self._heap: list[int] = []
        self._live: dict[int, int] = {}  # value -> how many times it is currently live

    def add(self, value: int) -> None:
        count = self._live.get(value, 0)
        self._live[value] = count + 1
        if count == 0:
            heappush(self._heap, -value)

    def discard(self, value: int) -> None:
        count = self._live.get(value, 0)
        if count <= 1:
            self._live.pop(value, None)
        else:
            self._live[value] = count - 1

    def max(self) -> int:
        """The largest live value, or -1 if nothing is live."""
        while self._heap and self._live.get(-self._heap[0], 0) == 0:
            heappop(self._heap)
        return -self._heap[0] if self._heap else -1


class Sheet:
    def __init__(self, sheet_id: SheetId, name: str):
        self.id = sheet_id
        self.name = name
        self.cells: dict[Position, dict] = {}  # sparse: only cells that hold something
        self.grid: dict[Position, Value] = {}  # sparse: the values they show
        self.rows_used = 0  # rows and columns beyond these hold nothing
        self.cols_used = 0
        self._tick = 0
        self._epoch = 0  # the tick of the last change to every column at once (rows moved)
        self._columns: dict[int, int] = {}  # column -> tick of its last change
        # The row/column index behind `cells_in` and `extent` (QA review 2026-11-06, PERF-01, PERF-05): kept
        # incrementally on every single-cell set/clear (`_note_filled`/`_note_emptied`, called from
        # `WorkbookModel.store`), so a window query or the extent cost what they return, not the size of the sheet.
        # A structural edit moves or destroys cells wholesale, so `refit` rebuilds this the same way it already
        # rebuilds `rows_used`/`cols_used` — that path was already O(sheet size) and stays so.
        self._row_cols: dict[int, list[int]] = {}  # row -> sorted columns that hold something, for `cells_in`
        self._rows_live = _LiveMax()  # rows that hold something, for `extent`
        self._cols_live = _LiveMax()  # columns that hold something, for `extent`

    def to_data(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "cells": [[r, c, content] for (r, c), content in sorted(self.cells.items())],
        }

    # -- values
    def set_value(self, position: Position, value: Value) -> bool:
        """Show ``value`` at ``position`` (``None``: nothing). Returns whether that was a change."""
        old = self.grid.get(position)
        if value is None:
            if old is None:
                return False
            del self.grid[position]
        else:
            if old is not None and old.__class__ is value.__class__ and old == value:
                return False
            self.grid[position] = value
            row, col = position
            if row >= self.rows_used:
                self.rows_used = row + 1
            if col >= self.cols_used:
                self.cols_used = col + 1
        self._tick += 1
        self._columns[position[1]] = self._tick
        return True

    def column_version(self, col: int) -> int:
        """Changes whenever a value in the column does (lookup indexes of the column stay good until it does)."""
        return max(self._epoch, self._columns.get(col, 0))

    def version(self) -> int:
        """Changes whenever any value on the sheet does."""
        return self._tick

    def bump_all(self) -> None:
        """Everything may have moved: every column has changed."""
        self._tick += 1
        self._epoch = self._tick

    def refit(self) -> None:
        """Recount how far the sheet reaches and rebuild the row/column index (after cells moved or went: a
        structural edit, or loading from storage). Single-cell edits stay incremental instead — see `_note_filled`
        and `_note_emptied`, called from `WorkbookModel.store`."""
        self.rows_used = max((r for r, _ in self.grid), default=-1) + 1
        self.cols_used = max((c for _, c in self.grid), default=-1) + 1
        grouped: dict[int, list[int]] = {}
        for row, col in self.cells:
            grouped.setdefault(row, []).append(col)
        self._row_cols = {row: sorted(cols) for row, cols in grouped.items()}
        self._rows_live = _LiveMax()
        self._cols_live = _LiveMax()
        for row, cols in self._row_cols.items():
            self._rows_live.add(row)
            for col in cols:
                self._cols_live.add(col)

    # -- the row/column index: `cells_in` and `extent` cost what they return, not the size of the sheet
    def _note_filled(self, position: Position) -> None:
        """A cell that was empty now holds something."""
        row, col = position
        insort(self._row_cols.setdefault(row, []), col)
        self._rows_live.add(row)
        self._cols_live.add(col)

    def _note_emptied(self, position: Position) -> None:
        """A cell that held something is now empty; shrinks the index the same way `_note_filled` grew it."""
        row, col = position
        cols = self._row_cols.get(row)
        if cols is not None:
            at = bisect_left(cols, col)
            if at < len(cols) and cols[at] == col:
                del cols[at]
            if not cols:
                del self._row_cols[row]
        self._rows_live.discard(row)
        self._cols_live.discard(col)

    def cells_in(self, row0: int, row1: int, col0: int, col1: int) -> list[Position]:
        """Positions that hold something inside a window (both ends included), sorted by row then column. Costs the
        number of rows in the window plus the number of cells returned — never the size of the sheet."""
        found: list[Position] = []
        for row in range(row0, row1 + 1):
            cols = self._row_cols.get(row)
            if not cols:
                continue
            lo, hi = bisect_left(cols, col0), bisect_right(cols, col1)
            found.extend((row, col) for col in cols[lo:hi])
        return found

    def extent(self) -> tuple[int, int]:
        """Rows and columns that hold something (the same extent `_sheets`/`_extent` report), amortized O(1) —
        never a scan of the sheet."""
        return self._rows_live.max() + 1, self._cols_live.max() + 1

    # -- what a client displays
    def view(self, position: Position) -> dict | None:
        """The content of a cell as a client shows it: a constant as stored, a formula as the value it gave (in the
        form of a constant, ``error`` for an error) with the formula itself under ``"f"``."""
        content = self.cells.get(position)
        if content is None or content["t"] != "formula":
            return content
        value = self.grid.get(position)
        shown = content_of(0 if value is None else value)
        return {**shown, "f": content["v"]}  # type: ignore[dict-item]


class WorkbookModel(DocumentModel):
    app: ClassVar[str] = "computes"
    state_schema: ClassVar[int] = 1
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(self, functions: FunctionRegistry | None = None):
        self.sheets: dict[SheetId, Sheet] = {}
        self.calc = Calculator(self, functions or default_functions())
        self._ids: dict[str, SheetId] | None = None

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self) -> dict:
        return {"sheets": [sheet.to_data() for sheet in self.sheets.values()]}

    @classmethod
    def restore(cls, state: dict) -> Self:
        model = cls()
        for item in state["sheets"]:
            sheet = Sheet(SheetId(item["id"]), item["name"])
            sheet.cells = {(r, c): content for r, c, content in item["cells"]}
            model.sheets[sheet.id] = sheet
        model._calculate_loaded()
        return model

    def _calculate_loaded(self) -> None:
        """Fill the values from the contents: constants as they are, formulas calculated."""
        self.calc.reset()
        self._ids = None
        for sheet in self.sheets.values():
            sheet.grid = {}
            for position, content in sheet.cells.items():
                if content["t"] == "formula":
                    key = (sheet.id, *position)
                    self.calc.define(key, self.calc.compile(sheet.id, content["v"]), forced=False)
                else:
                    sheet.grid[position] = value_of(content)
            sheet.refit()
            sheet.bump_all()
        self.calc.recalculate_all()

    def settle(self, ctx) -> None:
        self.calc.settle(ctx)

    # -- names (formulas name sheets, the model knows them by id)
    def sheet_id_of(self, name: str) -> SheetId | None:
        if self._ids is None:
            self._ids = {sheet.name.casefold(): sheet.id for sheet in self.sheets.values()}
        return self._ids.get(name.casefold())

    def sheet_name_of(self, sheet_id: SheetId) -> str | None:
        sheet = self.sheets.get(sheet_id)
        return None if sheet is None else sheet.name

    # -- reading ---------------------------------------------------------------
    def sheet(self, sheet_id: SheetId) -> Sheet:
        try:
            return self.sheets[sheet_id]
        except KeyError:
            raise ValueError(f"unknown sheet {sheet_id!r}") from None

    def get(self, sheet_id: SheetId, row: int, col: int) -> Content:
        return self.sheet(sheet_id).cells.get((row, col))

    def value(self, sheet_id: SheetId, row: int, col: int) -> Value:
        """The value a cell shows (``None`` for an empty one)."""
        return self.sheet(sheet_id).grid.get((row, col))

    def region_from_data(self, data: dict) -> Region:
        from .region import CellRegion

        return CellRegion.from_data(data)

    # -- changing --------------------------------------------------------------
    def store(self, sheet: Sheet, row: int, col: int, content: Content) -> Content:
        """Put ``content`` into a cell (``None``: empty it). Returns what is stored: a formula is stored in its
        canonical text, so that a document means the same however it is rebuilt."""
        position = (row, col)
        key = (sheet.id, row, col)
        calc = self.calc
        was_filled = position in sheet.cells
        if content is not None and content["t"] == "formula":
            compiled = calc.compile(sheet.id, content["v"])
            stored = content if compiled.source == content["v"] else {"t": "formula", "v": compiled.source}
            sheet.cells[position] = stored
            calc.define(key, compiled)
            if not was_filled:
                sheet._note_filled(position)  # noqa: SLF001 (the index is Sheet's own; store() is its one writer)
            return stored
        if key in calc.formulas:
            calc.remove(key)
        if content is None:
            sheet.cells.pop(position, None)
            if was_filled:
                sheet._note_emptied(position)  # noqa: SLF001
        else:
            sheet.cells[position] = content
            if not was_filled:
                sheet._note_filled(position)  # noqa: SLF001
        if sheet.set_value(position, value_of(content)):
            calc.touch(key)
        return content

    def add_sheet(self, sheet: Sheet, index: int | None) -> None:
        ordered = list(self.sheets.values())
        ordered.insert(len(ordered) if index is None else index, sheet)
        self.sheets = {s.id: s for s in ordered}
        self._ids = None

    def restructure(self, edit: StructuralEdit) -> tuple[Cells, dict[SheetId, Cells]]:
        """Insert or delete rows or columns: cells move, formulas follow them and keep pointing at what they pointed at.

        Returns the cells that were deleted, and for every sheet the formulas whose text had to change (as they were),
        which an undo needs to put back exactly (deleting what a formula pointed at cannot be undone by a reference)."""
        sheet = self.sheet(edit.sheet)
        limit = MAX_ROWS if edit.axis == "row" else MAX_COLS
        if edit.at >= limit or (not edit.insert and edit.at + edit.count > limit):
            raise ValueError("structural edit is outside the sheet")
        index = 0 if edit.axis == "row" else 1

        def remap(position: Position) -> Position | None:
            new = edit.map_index(position[index])
            if new is None:
                return None
            return (new, position[1]) if index == 0 else (position[0], new)

        moved: dict[Position, dict] = {}
        destroyed: Cells = []
        for position, content in sheet.cells.items():
            target = remap(position)
            if target is None:
                destroyed.append((position[0], position[1], content))
            else:
                moved[target] = content
        if any(r >= MAX_ROWS or c >= MAX_COLS for r, c in moved):
            raise ValueError("structural edit would push cells off the sheet")

        plan = self._plan_restructure(edit, remap)
        # nothing can fail from here on: change the state
        calc = self.calc
        for key in [k for k in calc.by_sheet.get(edit.sheet, ()) if remap((k[1], k[2])) is None]:
            calc.remove(key)
        for old_key, _, _, _ in plan:
            calc.remove(old_key)
        sheet.cells = moved
        sheet.grid = {
            target: value for position, value in sheet.grid.items() if (target := remap(position)) is not None
        }
        sheet.refit()
        sheet.bump_all()
        restores = self._redefine(edit, plan)
        calc.everything = True
        return destroyed, restores

    def _plan_restructure(self, edit: StructuralEdit, remap) -> list:
        """The formulas a structural edit touches: (old key, new key, formula after the edit, compiled before)."""
        calc = self.calc
        plan = []
        for key in set(calc.by_sheet.get(edit.sheet, ())) | calc.referring.get(edit.sheet, set()):
            home, row, col = key
            old = calc.formulas[key]
            formula = adjusted(old.formula, edit, home, self.sheet_name_of)
            target_key = key
            if home == edit.sheet:
                target = remap((row, col))
                if target is None:
                    continue  # (the formula goes with its cell)
                target_key = (home, *target)
            plan.append((key, target_key, formula, old))
        return plan

    def _redefine(self, edit: StructuralEdit, plan: list) -> dict[SheetId, Cells]:
        """Put the formulas of a plan back in the calculator at their new places; returns the texts an undo restores."""
        calc = self.calc
        restores: dict[SheetId, Cells] = defaultdict(list)
        for old_key, new_key, formula, old in plan:
            rewritten = formula is not old.formula
            if rewritten:
                compiled = calc.compile_formula(old_key[0], formula)
                content = {"t": "formula", "v": formula.source}
                self.sheets[new_key[0]].cells[(new_key[1], new_key[2])] = content
                if not edit.insert or ("#REF!" in formula.source and "#REF!" not in old.source):
                    restores[old_key[0]].append((old_key[1], old_key[2], {"t": "formula", "v": old.source}))
            else:
                compiled = old
            calc.define(new_key, compiled, forced=rewritten)
        return restores

    def drop_sheet(self, sheet_id: SheetId) -> dict[SheetId, Cells]:
        """Remove a sheet. Formulas elsewhere that pointed into it break (``#REF!``); returns, for every sheet, those
        formulas as they were, which an undo puts back."""
        self.sheet(sheet_id)
        calc = self.calc
        plan = []
        for key in calc.referring.get(sheet_id, ()):
            if key[0] == sheet_id:
                continue
            old = calc.formulas[key]
            formula = without_sheet(old.formula, sheet_id, self.sheet_name_of)
            if formula is not old.formula:
                plan.append((key, formula, old))
        for key in list(calc.by_sheet.get(sheet_id, ())):
            calc.remove(key)
        self.sheets = {s.id: s for s in self.sheets.values() if s.id != sheet_id}
        self._ids = None
        restores: dict[SheetId, Cells] = defaultdict(list)
        for key, formula, old in plan:
            content = {"t": "formula", "v": formula.source}
            self.sheets[key[0]].cells[(key[1], key[2])] = content
            restores[key[0]].append((key[1], key[2], {"t": "formula", "v": old.source}))
            calc.define(key, calc.compile_formula(key[0], formula))
        calc.everything = True
        return restores
