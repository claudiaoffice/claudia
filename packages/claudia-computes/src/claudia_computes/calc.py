"""Recalculation: what a change to the sheet makes necessary, in what order, and what the people watching are told.

The shape of the problem
------------------------
A formula depends on cells (``=A1+B1``) and on ranges (``=SUM(A1:A9999)``). When cells change, exactly the formulas that
depend on them, and on those formulas in turn, must be calculated again, and each one after everything it reads. This
module keeps three things:

* the **index** of who depends on what: single cells in a dictionary, ranges in a list per column of intervals of rows.
  Asking "who reads any of these cells?" for a whole batch of cells costs one bisection per interval, however many cells
  there are, so pasting ten thousand cells does not cost ten thousand scans.
* the **closure**: everything that depends, however indirectly, on what changed. It is found level by level.
* the **order**: a formula is calculated when everything it reads that is itself waiting has been calculated. That is
  found while calculating, by following the formula's waiting precedents first (depth first, with an explicit stack: a
  chain of ten thousand formulas is no problem). A formula met again while it is still waiting for itself is in a cycle,
  and every formula of the cycle becomes ``#CIRC!``.

Functions that read cells their text does not name (``OFFSET``, ``INDIRECT``) are calculated whenever anything changed;
where they actually looked is recorded, to wait for the formulas they read and to be found when those cells change.

Nothing is calculated while commands apply; ``settle`` does it once after the whole command (a batch of several
changes calculates once). A rolled back command leaves the same cells marked and settles to the same state as before.
"""

from __future__ import annotations

import logging
from bisect import bisect_left
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import replace
from typing import TYPE_CHECKING

from .events import CellsChanged
from .formula import Formula, parse_formula, print_formula
from .formula.compiler import Binding, Compiler, Evaluator
from .formula.forms.alternatives import labels_of
from .formula.nodes import Call, shape_only_refs, walk
from .formula.operators import single
from .formula.scope import Scope
from .functions.range import Range
from .functions.registry import FunctionRegistry
from .limits import MAX_COLS, MAX_ROWS
from .outcomes import Outcomes
from .refs import Position, SheetId, column_name
from .spill import Table
from .values import CIRC, SPILL, SYNTAX, ErrorValue, FormulaError, Value

if TYPE_CHECKING:
    from claudia_core import Context

    from .model import WorkbookModel

log = logging.getLogger("claudia_computes.calc")

Key = tuple[SheetId, int, int]  # (sheet, row, column): a cell of the workbook
Rect = tuple[SheetId, int, int, int, int]  # (sheet, row0, col0, row1, col1)
WIDE = 64  # a range of more columns than this is searched as a list, not entered column by column
BLOCK_BITS = 8  # ranges are filed by blocks of 256 rows, so that a change only looks at the ranges near it
LONG_BLOCKS = 16  # a range longer than this many blocks is kept in a list of its own
MAX_BLOCKS = 8  # how often a formula that reads where it likes may be put off, waiting for what it found
MAX_SPILL_ROUNDS = 20  # how often what read a result is calculated again after the result changed, before giving up


def _positions_only(formula) -> set:  # noqa: ANN001 (a ``Formula``; calc reads it by duck type throughout)
    """The references a formula only asks *where* they are (``COLUMNS($B$3:B3)``): no cells it reads."""
    return shape_only_refs(formula.ast) if formula.ast is not None else set()


class Compiled:
    """A formula cell as the calculator holds it: the formula, how to evaluate it and what it reads.

    Besides the cells its text names it reads the ones its *names* stood for when it was compiled (``bound``: see
    ``Binding``), and the cells of the ``SQL()`` formulas whose results it uses (``anchors``). ``mentions`` are
    the texts of the names it uses, found or not; it is compiled again when what one of them means changes."""

    __slots__ = (
        "alternatives",
        "cells",
        "dynamic",
        "evaluate",
        "formula",
        "mentions",
        "random",
        "ranges",
        "reads",
        "records",
    )

    def __init__(
        self,
        formula: Formula,
        evaluate: Evaluator | None,
        home: SheetId,
        binding: Binding | None = None,
    ):
        self.formula = formula
        self.evaluate = evaluate
        self.dynamic = formula.dynamic
        self.random = formula.random
        # The names of the alternatives when the formula is a cell with alternatives (an input of what-if outcomes:
        # one alternative is no choice at all).
        labels = labels_of(formula.ast)
        self.alternatives: tuple[str | None, ...] | None = labels if labels is not None and len(labels) > 1 else None
        # A formula with a query reads the tables it names, which its text does not: where it looked is recorded
        # (like a dynamic formula's), but it is calculated again only when what it read changes.
        self.records = formula.ast is not None and any(
            isinstance(n, Call) and n.name == "SQL" for n in walk(formula.ast)
        )
        cells: list[Key] = []
        ranges: list[Rect] = []
        positions_only = _positions_only(formula)
        rects = [
            (area.sheet or home, area.first.row, area.first.col, area.last.row, area.last.col)
            for area in formula.refs
            if area not in positions_only
        ]
        if binding is not None:
            rects.extend(binding.rects)
            cells.extend(binding.anchors)
        for sheet, row0, col0, row1, col1 in rects:
            if (row0, col0) == (row1, col1):
                cells.append((sheet, row0, col0))
            else:
                ranges.append((sheet, row0, col0, row1, col1))
        self.mentions: frozenset[str] = frozenset(binding.mentions) if binding is not None else frozenset()
        self.cells: tuple[Key, ...] = tuple(dict.fromkeys(cells))
        self.ranges: tuple[Rect, ...] = tuple(ranges)
        self.reads: tuple[Rect, ...] = ()  # (dynamic formulas) where it looked the last time

    @property
    def source(self) -> str:
        return self.formula.source


class ColumnReaders:
    """The ranges of one column that formulas read, filed by blocks of rows: asking who reads a cell looks at the ranges
    of its block and at the few long ones, never at all the ranges of the column."""

    __slots__ = ("blocks", "long")

    def __init__(self) -> None:
        self.blocks: dict[int, dict[Key, list[tuple[int, int]]]] = {}
        self.long: dict[Key, list[tuple[int, int]]] = {}

    def add(self, key: Key, row0: int, row1: int) -> None:
        first, last = row0 >> BLOCK_BITS, row1 >> BLOCK_BITS
        if last - first >= LONG_BLOCKS:
            self.long.setdefault(key, []).append((row0, row1))
            return
        for block in range(first, last + 1):
            self.blocks.setdefault(block, {}).setdefault(key, []).append((row0, row1))

    def discard(self, key: Key, row0: int, row1: int) -> None:
        first, last = row0 >> BLOCK_BITS, row1 >> BLOCK_BITS
        if last - first >= LONG_BLOCKS:
            self._drop(self.long, key, row0, row1)
            return
        for block in range(first, last + 1):
            readers = self.blocks.get(block)
            if readers is not None:
                self._drop(readers, key, row0, row1)
                if not readers:
                    del self.blocks[block]

    @staticmethod
    def _drop(readers: dict[Key, list[tuple[int, int]]], key: Key, row0: int, row1: int) -> None:
        intervals = readers.get(key)
        if intervals is not None:
            intervals.remove((row0, row1))
            if not intervals:
                del readers[key]

    def __bool__(self) -> bool:
        return bool(self.blocks or self.long)

    def readers_of(self, rows: list[int], found: set[Key]) -> None:
        """Add to ``found`` the readers of any of the rows (sorted)."""
        candidates = [self.long]
        candidates.extend(r for block in {row >> BLOCK_BITS for row in rows} if (r := self.blocks.get(block)))
        for readers in candidates:
            for reader, intervals in readers.items():
                if reader in found:
                    continue
                for row0, row1 in intervals:
                    at = bisect_left(rows, row0)
                    if at < len(rows) and rows[at] <= row1:
                        found.add(reader)
                        break


class Waiting:
    """The formulas still to be calculated, found by place: a sorted list of rows for every column with some."""

    def __init__(self, keys: Iterable[Key]):
        self.keys: set[Key] = set(keys)
        self._rows: dict[tuple[SheetId, int], list[int]] = defaultdict(list)
        self._columns: dict[SheetId, list[int]] = defaultdict(list)
        by_column: dict[tuple[SheetId, int], list[int]] = defaultdict(list)
        for sheet, row, col in self.keys:
            by_column[(sheet, col)].append(row)
        for (sheet, col), rows in by_column.items():
            rows.sort()
            self._rows[(sheet, col)] = rows
            self._columns[sheet].append(col)
        for columns in self._columns.values():
            columns.sort()

    def done(self, key: Key) -> None:
        sheet, row, col = key
        self.keys.discard(key)
        rows = self._rows[(sheet, col)]
        del rows[bisect_left(rows, row)]
        if not rows:
            del self._rows[(sheet, col)]
            columns = self._columns[sheet]
            del columns[bisect_left(columns, col)]

    def inside(self, rect: Rect) -> list[Key]:
        """The waiting formulas in the rectangle, column by column."""
        sheet, row0, col0, row1, col1 = rect
        columns = self._columns.get(sheet)
        if not columns:
            return []
        found: list[Key] = []
        at = bisect_left(columns, col0)
        while at < len(columns) and columns[at] <= col1:
            col = columns[at]
            rows = self._rows[(sheet, col)]
            low = bisect_left(rows, row0)
            while low < len(rows) and rows[low] <= row1:
                found.append((sheet, rows[low], col))
                low += 1
            at += 1
        return found


class Frame:
    """A formula on the stack of a round: the waiting formulas it still waits for, and how often it was put off."""

    __slots__ = ("attempts", "key", "pending")

    def __init__(self, key: Key, pending: list[Key]):
        self.key = key
        self.pending = iter(pending)
        self.attempts = 0


class Round:
    """One calculation of a set of formulas (see the module documentation for the method).

    ``state`` marks a formula 1 while the formulas it waits for are calculated, and 2 once it is done; a formula met
    again while marked 1 is read by itself, through others: a cycle."""

    def __init__(self, calc: Calculator, todo: set[Key]):
        self.calc = calc
        self.todo = todo
        self.scope = calc._scope()
        self.waiting = Waiting(todo)
        self.state: dict[Key, int] = {}
        self.circular: set[Key] = set()
        self.changed: dict[SheetId, set[Position]] = defaultdict(set)
        self.spilled: set[Key] = set()  # results that changed: their formulas, and the cells they fill that did

    def run(self) -> dict[SheetId, set[Position]]:
        for seed in sorted(self.todo):
            if seed not in self.state:
                self._follow(seed)
        return self.changed

    def _follow(self, seed: Key) -> None:
        """Calculate ``seed`` and, before it, every waiting formula it reads (depth first, with a stack of our own)."""
        path = [self._enter(seed)]
        stack = [Frame(seed, self._precedents(seed))]
        while stack:
            frame = stack[-1]
            key = frame.key
            nxt = next(frame.pending, None)
            if nxt is not None:
                mark = self.state.get(nxt)
                if mark == 1:  # met again while waiting for itself: everything from there on is a cycle
                    self.circular.update(path[path.index(nxt) :])
                elif mark is None:
                    stack.append(Frame(nxt, self._precedents(nxt)))
                    path.append(self._enter(nxt))
                continue
            if key in self.circular:
                self._store(key, ErrorValue(CIRC, "this formula depends on itself"))
            else:
                blockers = self._calculate(key, frame)
                if blockers:  # it looked at cells that still wait: those first, then this one again
                    frame.pending = iter(blockers)
                    frame.attempts += 1
                    continue
            stack.pop()
            path.pop()
            self.state[key] = 2
            self.waiting.done(key)

    def _enter(self, key: Key) -> Key:
        self.state[key] = 1
        return key

    def _precedents(self, key: Key) -> list[Key]:
        """The formulas that wait and that this one names (a dynamic one may turn out to read more)."""
        compiled = self.calc.formulas[key]
        found = [cell for cell in compiled.cells if cell in self.waiting.keys]
        for rect in compiled.ranges:
            found.extend(self.waiting.inside(rect))
        return found

    def _calculate(self, key: Key, frame: Frame) -> list[Key] | None:
        """Calculate one formula and store its value. Returns the waiting formulas it turned out to read (a function
        that looks where it likes), when it must wait for them."""
        calc, scope = self.calc, self.scope
        compiled = calc.formulas[key]
        scope.enter(*key)
        scope.reads = [] if compiled.dynamic or compiled.records else None
        scope.mentioned.clear()
        value = calc._evaluate(compiled, scope)
        if scope.mentioned:
            calc._mention(key, compiled, scope.mentioned)
        if value.__class__ is Table:
            value = self._spill(key, value, scope)
        elif key in calc.spills:
            self._unspill(key)
        if compiled.dynamic or compiled.records:
            reads = tuple(dict.fromkeys(scope.reads or ()))
            scope.reads = None
            if reads != compiled.reads:
                calc._leave_rects(key, compiled.reads)
                compiled.reads = reads
                calc._enter_rects(key, reads)
            blockers = [
                other
                for rect in reads
                for other in self.waiting.inside(rect)
                if self.state.get(other) != 2 or other == key
            ]
            if blockers:
                if frame.attempts >= MAX_BLOCKS or key in blockers or any(self.state.get(o) == 1 for o in blockers):
                    value = ErrorValue(CIRC, "this formula reads cells that depend on it")
                    self.circular.add(key)
                else:
                    return blockers
        self._store(key, value)
        return None

    def _spill(self, key: Key, table: Table, scope: Scope) -> Value:
        """Put ``table`` into the cells below and beside ``key``, which owns them from now on. Returns what the formula
        cell itself shows: the first cell of the table, or ``#SPILL!`` when the table does not fit there."""
        calc = self.calc
        sheet_id, row, col = key
        sheet = calc.model.sheets[sheet_id]
        last_row, last_col = row + table.height - 1, col + table.width - 1
        name = calc.result_name(key)
        where = (
            f"{column_name(col)}{row + 1}:{column_name(min(last_col, MAX_COLS - 1))}{min(last_row, MAX_ROWS - 1) + 1}"
        )
        if last_row >= MAX_ROWS or last_col >= MAX_COLS:
            self._unspill(key)
            return ErrorValue(SPILL, f"{name} needs {where}, which does not fit on the sheet")
        blocker = sheet.blocker((row, col), (last_row, last_col), key)
        if blocker is not None:
            self._unspill(key)
            # (calculated again when anything in the way changes: every cell of the rectangle but its own)
            scope.reads = [
                *(scope.reads or ()),
                (sheet_id, row, col + 1, row, last_col),
                (sheet_id, row + 1, col, last_row, last_col),
            ]
            return ErrorValue(
                SPILL, f"{name} needs {where}, but {column_name(blocker[1])}{blocker[0] + 1} holds a value"
            )
        old = calc.spills.get(key)
        changed: set[Position] = set()
        if old is not None:
            for r in range(old[1], old[3] + 1):
                for c in range(old[2], old[4] + 1):
                    if not (row <= r <= last_row and col <= c <= last_col) and sheet.spill_clear((r, c)):
                        changed.add((r, c))
        for i in range(table.height):
            for j in range(table.width):
                if (i or j) and sheet.spill_value((row + i, col + j), table.value_at(i, j), key):
                    changed.add((row + i, col + j))
        rect = (sheet_id, row, col, last_row, last_col)
        if changed or old != rect:
            self.changed[sheet_id] |= changed
            self.spilled.add(key)
            self.spilled.update((sheet_id, r, c) for r, c in changed)
        calc.spills[key] = rect
        return table.value_at(0, 0)

    def _unspill(self, key: Key) -> None:
        """``key`` fills no cells any more (its formula gave something else): they are empty again."""
        positions = self.calc.clear_spill(key)
        if positions:
            self.changed[key[0]] |= positions
            self.spilled.add(key)
            self.spilled.update((key[0], r, c) for r, c in positions)

    def _store(self, key: Key, value: Value) -> None:
        sheet = self.calc.model.sheets[key[0]]
        position = (key[1], key[2])
        if sheet.set_value(position, value):
            self.changed[key[0]].add(position)


class Calculator:
    """Keeps the formulas of one workbook, the index of what they read, and calculates what changed."""

    def __init__(self, model: WorkbookModel, registry: FunctionRegistry):
        self.model = model
        self.registry = registry
        self.compiler = Compiler(registry)
        self.formulas: dict[Key, Compiled] = {}
        self.by_sheet: dict[SheetId, set[Key]] = defaultdict(set)  # the formulas on a sheet
        self.dynamic: set[Key] = set()  # the formulas that read where they like
        self.random: set[Key] = set()  # the formulas that draw random numbers: calculated again on a resample
        self.alternatives: dict[Key, tuple[str | None, ...]] = {}  # the cells with alternatives -> their names (D294)
        self.choice: dict[Key, int] = {}  # which alternative a cell with alternatives gives, while outcomes are run
        self.graph_version = 0  # changes whenever a formula is defined or removed (what depends on what may differ)
        self.outcomes = Outcomes(self)
        self.referring: dict[SheetId, set[Key]] = defaultdict(set)  # the formulas that name cells of a sheet
        self._name_users: dict[str, set[Key]] = defaultdict(set)  # name text (casefolded) -> the formulas using it
        self._cell_readers: dict[Key, set[Key]] = defaultdict(set)
        self._column_readers: dict[tuple[SheetId, int], ColumnReaders] = {}
        self._wide_readers: dict[Key, list[Rect]] = {}
        self._lookup_indexes: dict[tuple, tuple[int, object]] = {}
        self.spills: dict[Key, Rect] = {}  # the cells a SQL() formula fills (its own cell is the first one)
        self.orphaned: dict[SheetId, set[Position]] = defaultdict(set)  # cells emptied outside a calculation
        self.touched: set[Key] = set()  # cells whose value changed since the last settle
        self.forced: set[Key] = set()  # formulas that must be calculated: new, rewritten or moved
        self.everything = False  # calculate every formula (after structure changed)

    # ------------------------------------------------------------------ making formulas
    def compile(self, home: SheetId, text: str, at: Position | None = None) -> Compiled:
        """Read ``text`` (a formula with its ``=``) typed on ``home`` (in the cell ``at``, when that is known: the
        row of the cell is what ``Sales[@Units]`` means). The formula is kept in its canonical text, so that a
        document means the same however it is rebuilt."""
        formula = parse_formula(text, self.model.sheet_id_of)
        canonical = print_formula(formula, self.model.sheet_name_of)
        if canonical != formula.source:
            formula = replace(formula, source=canonical)
        return self.compile_formula(home, formula, at)

    def compile_formula(self, home: SheetId, formula: Formula, at: Position | None = None) -> Compiled:
        if formula.ast is None:
            return Compiled(formula, None, home)
        binding = Binding(home, None if at is None else at[0], self.model.names, self.model.header_texts)
        self.compiler.binding = binding
        self.compiler.top_args = formula.ast.args if isinstance(formula.ast, Call) else None
        try:
            evaluate = self.compiler.compile(formula.ast)
        finally:
            self.compiler.binding = None
            self.compiler.top_args = None
        return Compiled(formula, evaluate, home, binding)

    def _mention(self, key: Key, compiled: Compiled, texts: set[str]) -> None:
        """The formula looked up names that its text does not have (a query reads tables by name): it is compiled
        again when what one of them means changes."""
        new = texts - compiled.mentions
        if new:
            compiled.mentions = compiled.mentions | frozenset(new)
            for text in new:
                self._name_users[text].add(key)

    def result_name(self, key: Key) -> str:
        """What a query result is called, for a message: its name, or ``this result`` when it has none."""
        for named in self.model.names:
            if named.anchor == key:
                return named.name
        return "this result"

    def clear_spill(self, key: Key, *, report: bool = False) -> set[Position]:
        """``key``'s result is no longer shown: its cells are empty. Returns them (``report``: also tell the readers
        and the people watching, at the next settle)."""
        rect = self.spills.pop(key, None)
        if rect is None:
            return set()
        sheet_id, row0, col0, row1, col1 = rect
        sheet = self.model.sheets.get(sheet_id)
        cleared: set[Position] = set()
        if sheet is not None:
            for position in [p for p, owner in sheet.spilled.items() if owner == key]:
                if sheet.spill_clear(position):
                    cleared.add(position)
        if report and cleared:
            self.touched.update((sheet_id, r, c) for r, c in cleared)
            self.touched.add(key)
            self.orphaned[sheet_id] |= cleared
        return cleared

    def clear_spills(self, sheet_id: SheetId) -> None:
        """Every result on a sheet is cleared (rows or columns are about to move: they are put back after)."""
        for key in [k for k in self.spills if k[0] == sheet_id]:
            self.clear_spill(key)

    def users_of(self, text: str) -> list[Key]:
        """The formulas that use the name ``text`` (found or not), in order."""
        return sorted(self._name_users.get(text.casefold(), ()))

    def rebind(self, texts: Iterable[str]) -> None:
        """What the names ``texts`` mean changed: the formulas that use them are compiled again, to read the cells
        they mean now (and to be calculated again)."""
        users: set[Key] = set()
        for text in texts:
            users |= self._name_users.get(text.casefold(), set())
        for key in sorted(users):
            old = self.formulas.get(key)
            if old is not None:
                self.define(key, self.compile_formula(key[0], old.formula, (key[1], key[2])))

    # ------------------------------------------------------------------ the index
    def define(self, key: Key, compiled: Compiled, *, forced: bool = True) -> None:
        """``key`` holds this formula from now on."""
        self.remove(key)
        self.formulas[key] = compiled
        sheet = key[0]
        self.by_sheet[sheet].add(key)
        if compiled.dynamic:
            self.dynamic.add(key)
        if compiled.random:
            self.random.add(key)
        if compiled.alternatives is not None:
            self.alternatives[key] = compiled.alternatives
        self.graph_version += 1
        for target in {area.sheet or sheet for area in compiled.formula.refs}:
            self.referring[target].add(key)
        for cell in compiled.cells:
            self._cell_readers[cell].add(key)
        for text in compiled.mentions:
            self._name_users[text].add(key)
        self._enter_rects(key, compiled.ranges)
        if forced:
            self.forced.add(key)

    def remove(self, key: Key) -> Compiled | None:
        """``key`` holds no formula any more."""
        compiled = self.formulas.pop(key, None)
        if compiled is None:
            return None
        self.clear_spill(key, report=True)
        sheet = key[0]
        self.by_sheet[sheet].discard(key)
        self.dynamic.discard(key)
        self.random.discard(key)
        self.alternatives.pop(key, None)
        self.graph_version += 1
        for target in {area.sheet or sheet for area in compiled.formula.refs}:
            self.referring[target].discard(key)
        for cell in compiled.cells:
            readers = self._cell_readers.get(cell)
            if readers is not None:
                readers.discard(key)
                if not readers:
                    del self._cell_readers[cell]
        for text in compiled.mentions:
            users = self._name_users.get(text)
            if users is not None:
                users.discard(key)
                if not users:
                    del self._name_users[text]
        self._leave_rects(key, compiled.ranges + compiled.reads)
        self.forced.discard(key)
        return compiled

    def _enter_rects(self, key: Key, rects: Iterable[Rect]) -> None:
        for rect in rects:
            sheet, row0, col0, row1, col1 = rect
            if col1 - col0 >= WIDE:
                self._wide_readers.setdefault(key, []).append(rect)
                continue
            for col in range(col0, col1 + 1):
                column = self._column_readers.get((sheet, col))
                if column is None:
                    column = self._column_readers[(sheet, col)] = ColumnReaders()
                column.add(key, row0, row1)

    def _leave_rects(self, key: Key, rects: Iterable[Rect]) -> None:
        for rect in rects:
            sheet, row0, col0, row1, col1 = rect
            if col1 - col0 >= WIDE:
                wide = self._wide_readers.get(key)
                if wide is not None:
                    wide.remove(rect)
                    if not wide:
                        del self._wide_readers[key]
                continue
            for col in range(col0, col1 + 1):
                column = self._column_readers.get((sheet, col))
                if column is not None:
                    column.discard(key, row0, row1)
                    if not column:
                        del self._column_readers[(sheet, col)]

    def readers_of(self, keys: Iterable[Key]) -> set[Key]:
        """The formulas that read any of these cells, directly (a cell, or a range with the cell in it)."""
        found: set[Key] = set()
        by_column: dict[tuple[SheetId, int], list[int]] = defaultdict(list)
        for key in keys:
            direct = self._cell_readers.get(key)
            if direct:
                found |= direct
            by_column[(key[0], key[2])].append(key[1])
        for column, rows in by_column.items():
            readers = self._column_readers.get(column)
            if readers:
                rows.sort()
                readers.readers_of(rows, found)
        for rows in by_column.values():
            rows.sort()
        for reader, rects in self._wide_readers.items():
            if reader in found:
                continue
            if any(self._any_in(by_column, rect) for rect in rects):
                found.add(reader)
        return found

    @staticmethod
    def _any_in(by_column: dict[tuple[SheetId, int], list[int]], rect: Rect) -> bool:
        sheet, r0, c0, r1, c1 = rect
        for (here, col), rows in by_column.items():
            if here == sheet and c0 <= col <= c1:
                at = bisect_left(rows, r0)
                if at < len(rows) and rows[at] <= r1:
                    return True
        return False

    # ------------------------------------------------------------------ changes
    def touch(self, key: Key) -> None:
        """The value at ``key`` changed."""
        self.touched.add(key)

    def reset(self) -> None:
        """Forget every formula (the model is being rebuilt)."""
        self.formulas.clear()
        self.by_sheet.clear()
        self.dynamic.clear()
        self.random.clear()
        self.alternatives.clear()
        self.choice.clear()
        self.outcomes.reset()
        self.graph_version += 1
        self.referring.clear()
        self._name_users.clear()
        self._cell_readers.clear()
        self._column_readers.clear()
        self._wide_readers.clear()
        self._lookup_indexes.clear()
        self.spills.clear()
        self.orphaned.clear()
        self.touched.clear()
        self.forced.clear()

    def redraw(self) -> None:
        """The seed or the draw number changed: every formula that draws random numbers is calculated again."""
        self.forced |= self.random

    def closure(self) -> set[Key]:
        """Every formula that must be calculated: the forced ones, those that depend on what changed or on them, and
        the ones that read where they like (they are calculated whenever anything is)."""
        if self.everything:
            return set(self.formulas)
        todo = set(self.dynamic) if (self.touched or self.forced) else set()
        todo |= {key for key in self.forced if key in self.formulas}
        reached = set(todo)
        frontier: set[Key] = self.touched | reached
        while frontier:
            new = self.readers_of(frontier) - reached
            reached |= new
            frontier = new
        return reached

    # ------------------------------------------------------------------ settling
    def settle(self, ctx: Context) -> None:
        """Calculate what the changes of the command made necessary, and tell the watchers what changed."""
        if not self.formulas:
            self.touched.clear()
            self.forced.clear()
            self.everything = False
            for sheet, positions in self.outcomes.refresh(set()).items():  # (the last cells with alternatives went)
                self.orphaned[sheet] |= positions
            self._tell_orphans(ctx)
            return
        if not (self.touched or self.forced or self.everything):
            return
        todo = self.closure()
        forced = {key for key in self.forced if key in self.formulas}
        self.touched.clear()
        self.forced.clear()
        self.everything = False
        shown = self._calculate(todo)
        for sheet, positions in self.outcomes.refresh(todo).items():  # (alternatives and outcomes changed there)
            shown[sheet] |= positions
        for sheet, row, col in forced:  # (new or rewritten formulas are shown even when the value came out the same)
            shown[sheet].add((row, col))
        for sheet, positions in self.orphaned.items():  # (cells whose result went away)
            shown[sheet] |= positions
        self.orphaned.clear()
        if not ctx.failed:
            self._tell(ctx, shown)

    def _tell_orphans(self, ctx: Context) -> None:
        if self.orphaned and not ctx.failed:
            self._tell(ctx, dict(self.orphaned))
        self.orphaned.clear()

    def recalculate_all(self) -> None:
        """Calculate every formula (a document was opened from a snapshot)."""
        self._calculate(set(self.formulas))
        self.outcomes.refresh(None)
        self.touched.clear()
        self.forced.clear()
        self.everything = False

    def _scope(self) -> Scope:
        scope = Scope(self.model.sheets, self.model.sheet_id_of)
        scope.indexes = self._lookup_indexes
        scope.names = self.model.names
        scope.spills = self.spills
        scope.seed, scope.draw = self.model.random_seed, self.model.random_draw
        scope.choice = self.choice
        return scope

    def scope_for(self, home: SheetId) -> Scope:
        """A scope that reads the workbook as a formula on ``home`` sees it (for what evaluates outside a cell)."""
        scope = self._scope()
        scope.enter(home, 0, 0)
        return scope

    def _calculate(self, todo: set[Key]) -> dict[SheetId, set[Position]]:
        """Calculate the formulas in ``todo``, each after the waiting formulas it reads. Returns where something
        changed that people see.

        A formula that fills cells (``SQL()``) changes what the formulas that read those cells see, and they may
        have been calculated before it: they are calculated again, round after round, until no result changes."""
        changed: dict[SheetId, set[Position]] = defaultdict(set)
        for _ in range(MAX_SPILL_ROUNDS):
            current = Round(self, todo)
            for sheet, positions in current.run().items():
                changed[sheet] |= positions
            if not current.spilled:
                return changed
            todo = self._readers_closure(current.spilled)
            if not todo:
                return changed
        log.warning("results kept changing: gave up after %d rounds", MAX_SPILL_ROUNDS)
        return changed

    def _readers_closure(self, keys: set[Key]) -> set[Key]:
        """The formulas that read any of ``keys``, however indirectly."""
        reached: set[Key] = set()
        frontier = set(keys)
        while frontier:
            new = self.readers_of(frontier) - reached
            reached |= new
            frontier = new
        return reached

    def _evaluate(self, compiled: Compiled, scope: Scope) -> Value:
        if compiled.evaluate is None:
            return compiled.formula.error or ErrorValue(SYNTAX, "this is not a formula")
        try:
            value = compiled.evaluate(scope)
            if value.__class__ is Range:
                value = single(value)
        except FormulaError as problem:
            return problem.value()
        except RecursionError:
            return ErrorValue(SYNTAX, "this formula is nested too deeply")
        except Exception:  # a bug in a function must not stop the document from being edited
            log.exception("calculating %s failed", compiled.source)
            return ErrorValue(SYNTAX, "this formula failed: see the server's log")
        return 0 if value is None else value

    def _tell(self, ctx: Context, changed: dict[SheetId, set[Position]]) -> None:
        for sheet_id, positions in changed.items():
            sheet = self.model.sheets.get(sheet_id)
            if sheet is None:
                continue
            cells = tuple((r, c, sheet.view((r, c))) for r, c in sorted(positions))
            ctx.emit(CellsChanged(sheet_id, frozenset(positions), cells))
