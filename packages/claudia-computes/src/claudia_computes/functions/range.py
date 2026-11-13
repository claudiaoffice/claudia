"""A rectangle of cells as a formula sees it: the value of ``A1:C5``, and what a function gets for a range argument.

A sheet is sparse (only cells that hold something exist), and a range may be huge (``A:A`` is a million rows), so a
``Range`` never lists its empty cells unless it is asked to. ``present()`` and ``numbers()`` visit only the cells
that hold something, whichever is fewer: the cells in the rectangle or the cells on the sheet. ``dense()`` and
iteration give every position, ``None`` for empty ones, and refuse rectangles too big to list.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

from ..refs import Position
from ..values import VALUE, ErrorValue, FormulaError, Value

MAX_DENSE = 4_000_000  # positions listed one by one; beyond this a function must ask for what is present


class Grid(Protocol):
    """What a range reads: the values the cells of a sheet show, and how far the sheet reaches."""

    grid: dict[Position, Value]
    rows_used: int
    cols_used: int


class _Constant:
    """A single value as a sheet of one cell."""

    rows_used = cols_used = 1

    def __init__(self, value: Value):
        self.grid: dict[Position, Value] = {} if value is None else {(0, 0): value}


@dataclass(slots=True)
class FrozenGrid:
    """A ``Grid`` snapshot holding only the cells one ``Range``'s footprint reached, and nothing else -- no live
    ``Sheet``, no lock, no connection, nothing that cannot cross a process boundary. This is the copy a deferred
    heavy call (:class:`~claudia_computes.functions.base.Deferred`) runs on in a worker, instead of the live
    sheet it was first read from (D37, D291): plain data, pickled once and read many times.

    Not ``frozen=True``: a :class:`Grid` is a plain, writable-attribute :class:`~typing.Protocol`, and a truly
    immutable dataclass does not structurally match it (its fields are read-only descriptors, not plain
    attributes). Nothing here writes to a ``FrozenGrid`` once built -- the name is the contract, not the
    enforcement.
    """

    grid: dict[Position, Value] = field(default_factory=dict)
    rows_used: int = 0
    cols_used: int = 0

    @classmethod
    def of(cls, source: Grid, row0: int, col0: int, row1: int, col1: int) -> FrozenGrid:
        """A snapshot of ``source`` covering just ``row0..row1``/``col0..col1`` -- the footprint a single
        ``Range`` reaches, not the whole sheet, so a huge sheet costs only what the call actually reads."""
        last_row = min(row1, source.rows_used - 1)
        last_col = min(col1, source.cols_used - 1)
        if last_row < row0 or last_col < col0:
            return cls({}, source.rows_used, source.cols_used)
        full = source.grid
        positions = (last_row - row0 + 1) * (last_col - col0 + 1)
        grid: dict[Position, Value]
        if positions <= len(full):
            grid = {
                (r, c): v
                for r in range(row0, last_row + 1)
                for c in range(col0, last_col + 1)
                if (v := full.get((r, c))) is not None
            }
        else:
            grid = {(r, c): v for (r, c), v in full.items() if row0 <= r <= last_row and col0 <= c <= last_col}
        return cls(grid, source.rows_used, source.cols_used)


def freeze(value: object) -> object:
    """``value`` as it crosses a process boundary: a :class:`Range` comes back pointed at a :class:`FrozenGrid`
    snapshot of just the cells it reaches, instead of its live sheet; anything else passes through unchanged.

    This is what a deferred heavy call's arguments are run through before the call is handed to a worker (D37,
    D291) -- not a general deep-copy, just enough to take the live, mutable sheet out of the picture."""
    if isinstance(value, Range):
        snapshot = FrozenGrid.of(value.sheet, value.row0, value.col0, value.row1, value.col1)
        return Range(snapshot, value.row0, value.col0, value.row1, value.col1, sheet_id=value.sheet_id)
    return value


class Range:
    """The cells from (``row0``, ``col0``) to (``row1``, ``col1``) of one sheet, both ends included, zero-based."""

    __slots__ = ("col0", "col1", "row0", "row1", "sheet", "sheet_id")

    def __init__(self, sheet: Grid, row0: int, col0: int, row1: int, col1: int, *, sheet_id: str | None = None):
        self.sheet = sheet
        self.sheet_id = sheet_id
        self.row0, self.col0, self.row1, self.col1 = row0, col0, row1, col1

    @classmethod
    def of_value(cls, value: Value) -> Range:
        """A range of one cell holding ``value`` (what a function gets when a formula passes it a single value)."""
        return cls(_Constant(value), 0, 0, 0, 0)

    # -- shape
    @property
    def n_rows(self) -> int:
        return self.row1 - self.row0 + 1

    @property
    def n_cols(self) -> int:
        return self.col1 - self.col0 + 1

    def __len__(self) -> int:
        return self.n_rows * self.n_cols

    def is_vector(self) -> bool:
        """One row or one column (a single cell is both)."""
        return self.n_rows == 1 or self.n_cols == 1

    def _used(self) -> tuple[int, int]:
        """The last row and column of the range that can hold anything (beyond them the sheet is empty)."""
        return min(self.row1, self.sheet.rows_used - 1), min(self.col1, self.sheet.cols_used - 1)

    # -- reading
    def at(self, row: int, col: int) -> Value:
        """The value ``row`` rows down and ``col`` columns right of the top left corner; empty outside the sheet."""
        return self.sheet.grid.get((self.row0 + row, self.col0 + col))

    def present(self) -> Iterator[Value]:
        """The values of the cells that hold something, in no particular order."""
        last_row, last_col = self._used()
        if last_row < self.row0 or last_col < self.col0:
            return iter(())
        grid = self.sheet.grid
        positions = (last_row - self.row0 + 1) * (last_col - self.col0 + 1)
        if positions <= len(grid):
            get = grid.get
            return (
                value
                for row in range(self.row0, last_row + 1)
                for col in range(self.col0, last_col + 1)
                if (value := get((row, col))) is not None
            )
        row0, col0 = self.row0, self.col0
        return (value for (row, col), value in grid.items() if row0 <= row <= last_row and col0 <= col <= last_col)

    def cells(self) -> list[tuple[int, int, Value]]:
        """``(row, col, value)`` of the cells that hold something, row by row; row and col count from this range."""
        last_row, last_col = self._used()
        if last_row < self.row0 or last_col < self.col0:
            return []
        found = [
            (row - self.row0, col - self.col0, value)
            for (row, col), value in self.sheet.grid.items()
            if self.row0 <= row <= last_row and self.col0 <= col <= last_col
        ]
        found.sort(key=lambda item: item[:2])
        return found

    def numbers(self, *, strict: bool = True) -> list[int | float]:
        """The numbers in the range (text, TRUE/FALSE and empty cells are skipped, as SUM does). An error in the range
        is raised, the first one row by row, unless ``strict`` is false (as COUNT sees it)."""
        out: list[int | float] = []
        for value in self.present():
            cls = value.__class__
            if cls is int or cls is float:
                out.append(value)  # type: ignore[arg-type]
            elif strict and cls is ErrorValue:
                raise self.first_error().raised()  # type: ignore[union-attr]
        return out

    def first_error(self) -> ErrorValue | None:
        """The first error in the range, row by row, or ``None``."""
        for _, _, value in self.cells():
            if value.__class__ is ErrorValue:
                return value
        return None

    def dense(self) -> tuple[tuple[Value, ...], ...]:
        """Every position, row by row, as rows of values (``None`` for an empty cell)."""
        if len(self) > MAX_DENSE:
            raise FormulaError(VALUE, f"this range has {len(self):,} cells: too many to read one by one")
        get = self.sheet.grid.get
        return tuple(
            tuple(get((row, col)) for col in range(self.col0, self.col1 + 1)) for row in range(self.row0, self.row1 + 1)
        )

    @property
    def rows(self) -> tuple[tuple[Value, ...], ...]:
        return self.dense()

    def vector(self) -> list[Value]:
        """The values of a row or a column, top to bottom or left to right, ending at the last cell that can hold
        something (an entire column is not listed down to the last row of the sheet)."""
        if not self.is_vector():
            raise FormulaError(VALUE, "this needs a single row or a single column")
        last_row, last_col = self._used()
        get = self.sheet.grid.get
        if self.n_cols == 1:
            return [get((row, self.col0)) for row in range(self.row0, max(last_row, self.row0 - 1) + 1)]
        return [get((self.row0, col)) for col in range(self.col0, max(last_col, self.col0 - 1) + 1)]

    def __iter__(self) -> Iterator[Value]:
        return (value for row in self.dense() for value in row)

    # -- parts
    def sub(self, row0: int, col0: int, row1: int, col1: int) -> Range:
        """The part from ``row0``, ``col0`` to ``row1``, ``col1`` (counted from this range's corner, ends included)."""
        corner = (self.row0 + row0, self.col0 + col0, self.row0 + row1, self.col0 + col1)
        return Range(self.sheet, *corner, sheet_id=self.sheet_id)

    def row(self, index: int) -> Range:
        return self.sub(index, 0, index, self.n_cols - 1)

    def column(self, index: int) -> Range:
        return self.sub(0, index, self.n_rows - 1, index)

    def __repr__(self) -> str:
        return f"Range(rows {self.row0}..{self.row1}, cols {self.col0}..{self.col1})"
