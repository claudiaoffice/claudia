"""What a formula that fills cells gives back: a table (E6.5, D600).

``SQL()`` is the first function that does not answer with one value. It answers with a ``Table`` — a header row and
the rows below it — and the calculator puts the table into the cells below and to the right of the formula (it
*spills*), owning them: they show the result, they are not stored in the document and they cannot be typed into.
Everything else in the model sees them as cells that show values.
"""

from __future__ import annotations

from dataclasses import dataclass

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
