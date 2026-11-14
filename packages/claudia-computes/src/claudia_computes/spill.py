"""What a formula that fills cells gives back: a table (E6.5, D600).

``SQL()`` is the first function that does not answer with one value. It answers with a ``Table`` — a header row and
the rows below it — and the calculator puts the table into the cells below and to the right of the formula (it
*spills*), owning them: they show the result, they are not stored in the document and they cannot be typed into.
Everything else in the model sees them as cells that show values.
"""

from __future__ import annotations

from dataclasses import dataclass

from .functions.range import Range
from .refs import Position
from .values import Value


@dataclass(frozen=True, slots=True)
class Table:
    """A result: the names of its ``columns`` and its ``rows`` of values."""

    columns: tuple[str, ...]
    rows: tuple[tuple[Value, ...], ...]

    @property
    def height(self) -> int:
        """How many rows it takes up on a sheet, counting the header."""
        return 1 + len(self.rows)

    @property
    def width(self) -> int:
        """Columns it takes up on a sheet."""
        return len(self.columns)

    def value_at(self, row: int, col: int) -> Value:
        """The value in the cell ``row`` rows down and ``col`` columns right of the top left corner."""
        return self.columns[col] if row == 0 else self.rows[row - 1][col]


class _Cells:
    """The values of a matrix as a sheet of their own, for a function that wants a ``Range``."""

    def __init__(self, rows: tuple[tuple[Value, ...], ...]):
        self.grid: dict[Position, Value] = {
            (i, j): value for i, row in enumerate(rows) for j, value in enumerate(row) if value is not None
        }
        self.rows_used = len(rows)
        self.cols_used = len(rows[0])


@dataclass(frozen=True, slots=True)
class Matrix:
    """A result that is a rectangle of values and nothing else (``SORT``, ``SEQUENCE``, ``TRANSPOSE`` ...).

    Like a ``Table`` it spills into the cells below and beside its formula; unlike a table it has no header row. Where
    another function takes it as an argument it is a ``Range`` of the same values (``as_range``); where a single value
    is wanted a matrix of one cell is that cell and a bigger one is ``#VALUE!`` (see ``operators.single``)."""

    rows: tuple[tuple[Value, ...], ...]

    def __post_init__(self) -> None:
        if not self.rows or not self.rows[0]:
            raise ValueError("a matrix has at least one cell")
        width = len(self.rows[0])
        if any(len(row) != width for row in self.rows):
            raise ValueError("every row of a matrix has as many cells as the first")

    @property
    def height(self) -> int:
        """Rows it takes up on a sheet."""
        return len(self.rows)

    @property
    def width(self) -> int:
        """Columns it takes up on a sheet."""
        return len(self.rows[0])

    def value_at(self, row: int, col: int) -> Value:
        """The value in the cell ``row`` rows down and ``col`` columns right of the top left corner."""
        return self.rows[row][col]

    def as_range(self) -> Range:
        """The same values as a range, for the functions that read ranges."""
        return Range(_Cells(self.rows), 0, 0, self.height - 1, self.width - 1)
