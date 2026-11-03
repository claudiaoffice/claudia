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
from .formula.compiler import Compiler, Evaluator
from .formula.operators import single
from .formula.scope import Scope
from .functions.range import Range
from .functions.registry import FunctionRegistry
from .refs import Position, SheetId
from .values import CIRC, SYNTAX, ErrorValue, FormulaError, Value

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


class Compiled:
    """A formula cell as the calculator holds it: the formula, how to evaluate it and what it reads."""

    __slots__ = ("cells", "dynamic", "evaluate", "formula", "ranges", "reads")

    def __init__(self, formula: Formula, evaluate: Evaluator | None, home: SheetId):
        self.formula = formula
        self.evaluate = evaluate
        self.dynamic = formula.dynamic
        cells: list[Key] = []
        ranges: list[Rect] = []
        for area in formula.refs:
            sheet = area.sheet or home
            first, last = area.first, area.last
            if first.row == last.row and first.col == last.col:
                cells.append((sheet, first.row, first.col))
            else:
                ranges.append((sheet, first.row, first.col, last.row, last.col))
        self.cells: tuple[Key, ...] = tuple(cells)
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
        scope.reads = [] if compiled.dynamic else None
        value = calc._evaluate(compiled, scope)
        if compiled.dynamic:
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
        self.referring: dict[SheetId, set[Key]] = defaultdict(set)  # the formulas that name cells of a sheet
        self._cell_readers: dict[Key, set[Key]] = defaultdict(set)
        self._column_readers: dict[tuple[SheetId, int], ColumnReaders] = {}
        self._wide_readers: dict[Key, list[Rect]] = {}
        self._lookup_indexes: dict[tuple, tuple[int, object]] = {}
        self.touched: set[Key] = set()  # cells whose value changed since the last settle
        self.forced: set[Key] = set()  # formulas that must be calculated: new, rewritten or moved
        self.everything = False  # calculate every formula (after structure changed)

    # ------------------------------------------------------------------ making formulas
    def compile(self, home: SheetId, text: str) -> Compiled:
        """Read ``text`` (a formula with its ``=``) typed on ``home``. The formula is kept in its canonical text, so
        that a document means the same however it is rebuilt."""
        formula = parse_formula(text, self.model.sheet_id_of)
        canonical = print_formula(formula, self.model.sheet_name_of)
        if canonical != formula.source:
            formula = replace(formula, source=canonical)
        return self.compile_formula(home, formula)

    def compile_formula(self, home: SheetId, formula: Formula) -> Compiled:
        evaluate = None if formula.ast is None else self.compiler.compile(formula.ast)
        return Compiled(formula, evaluate, home)

    # ------------------------------------------------------------------ the index
    def define(self, key: Key, compiled: Compiled, *, forced: bool = True) -> None:
        """``key`` holds this formula from now on."""
        self.remove(key)
        self.formulas[key] = compiled
        sheet = key[0]
        self.by_sheet[sheet].add(key)
        if compiled.dynamic:
            self.dynamic.add(key)
        for target in {area.sheet or sheet for area in compiled.formula.refs}:
            self.referring[target].add(key)
        for cell in compiled.cells:
            self._cell_readers[cell].add(key)
        self._enter_rects(key, compiled.ranges)
        if forced:
            self.forced.add(key)

    def remove(self, key: Key) -> Compiled | None:
        """``key`` holds no formula any more."""
        compiled = self.formulas.pop(key, None)
        if compiled is None:
            return None
        sheet = key[0]
        self.by_sheet[sheet].discard(key)
        self.dynamic.discard(key)
        for target in {area.sheet or sheet for area in compiled.formula.refs}:
            self.referring[target].discard(key)
        for cell in compiled.cells:
            readers = self._cell_readers.get(cell)
            if readers is not None:
                readers.discard(key)
                if not readers:
                    del self._cell_readers[cell]
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
        self.referring.clear()
        self._cell_readers.clear()
        self._column_readers.clear()
        self._wide_readers.clear()
        self._lookup_indexes.clear()
        self.touched.clear()
        self.forced.clear()

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
            return
        if not (self.touched or self.forced or self.everything):
            return
        todo = self.closure()
        forced = {key for key in self.forced if key in self.formulas}
        self.touched.clear()
        self.forced.clear()
        self.everything = False
        shown = self._calculate(todo)
        for sheet, row, col in forced:  # (new or rewritten formulas are shown even when the value came out the same)
            shown[sheet].add((row, col))
        if not ctx.failed:
            self._tell(ctx, shown)

    def recalculate_all(self) -> None:
        """Calculate every formula (a document was opened from a snapshot)."""
        self._calculate(set(self.formulas))
        self.touched.clear()
        self.forced.clear()
        self.everything = False

    def _scope(self) -> Scope:
        scope = Scope(self.model.sheets, self.model.sheet_id_of)
        scope.indexes = self._lookup_indexes
        return scope

    def _calculate(self, todo: set[Key]) -> dict[SheetId, set[Position]]:
        """Calculate the formulas in ``todo``, each after the waiting formulas it reads. Returns where something
        changed that people see."""
        return Round(self, todo).run()

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
