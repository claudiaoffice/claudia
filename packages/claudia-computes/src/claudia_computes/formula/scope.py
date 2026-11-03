"""What a formula can see while it is evaluated: the sheets, and where it stands."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from ..functions.range import Grid, Range
from ..refs import Position, SheetId
from ..values import REF, FormulaError, Value


class Sheet(Grid, Protocol):
    """A sheet as the evaluator reads it: ``Grid`` plus a counter that changes whenever a column does."""

    def column_version(self, col: int) -> int: ...

    def version(self) -> int: ...


class Scope:
    """The sheets of a workbook and the cell being evaluated (``home``, ``row``, ``col``).

    One scope is reused for every evaluation; ``enter`` sets it to the next cell. Lookups keep their indexes here
    (see ``forms.lookup``): an index of a column stays good until that column changes."""

    def __init__(self, sheets: Mapping[SheetId, Sheet], sheet_id: Callable[[str], SheetId | None]):
        self.sheets = sheets
        self.sheet_id = sheet_id  # a sheet's name -> its id (INDIRECT)
        self.home = SheetId("")
        self.row = 0
        self.col = 0
        self.grid: dict[Position, Value] = {}
        self.indexes: dict[tuple, tuple[int, object]] = {}
        self.reads: list[tuple[SheetId, int, int, int, int]] | None = None  # where OFFSET/INDIRECT looked, when asked

    def enter(self, sheet: SheetId, row: int, col: int) -> None:
        """Evaluate next on ``sheet`` at (``row``, ``col``)."""
        self.home, self.row, self.col = sheet, row, col
        self.grid = self.sheets[sheet].grid

    def read(self, sheet: SheetId, position: Position) -> Value:
        """The value of one cell of another sheet."""
        try:
            return self.sheets[sheet].grid.get(position)
        except KeyError:
            raise FormulaError(REF, "that sheet does not exist") from None

    def area(self, sheet: SheetId | None, row0: int, col0: int, row1: int, col1: int) -> Range:
        """The cells from (``row0``, ``col0``) to (``row1``, ``col1``) of ``sheet`` (``None``: the sheet being
        evaluated)."""
        target = sheet or self.home
        if self.reads is not None:
            self.reads.append((target, row0, col0, row1, col1))
        try:
            return Range(self.sheets[target], row0, col0, row1, col1, sheet_id=target)
        except KeyError:
            raise FormulaError(REF, "that sheet does not exist") from None
