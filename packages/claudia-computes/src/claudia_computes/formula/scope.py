"""What a formula can see while it is evaluated: the sheets, and where it stands."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from ..functions.range import Grid, Range
from ..names import Anchor, Names, Rect, select
from ..refs import Position, SheetId, column_name
from ..values import REF, FormulaError, Value, format_value


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
        self.spills: dict[Anchor, Rect] = {}  # where the SQL() cells put their results, as of the last calculation
        self.names: Names = Names()  # (set by the calculator)
        self.mentioned: set[str] = set()  # the names a query looked up while the cell was calculated

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

    def result_area(
        self, anchor: Anchor, text: str, items: tuple[str, ...], first: str | None, last: str | None
    ) -> Range:
        """The cells a reference to a query result (``text``, filled by the ``SQL()`` cell ``anchor``) means now."""
        spilled = self.spills.get(anchor)
        if spilled is None:
            raise FormulaError(REF, f"{text} has no result: its SQL() formula gave none")
        sheet, row0, col0, _, col1 = spilled
        grid = self.sheets[sheet].grid
        headers = [format_value(grid.get((row0, col))) for col in range(col0, col1 + 1)]
        chosen = select(
            text,
            spilled,
            header=True,
            headers=headers,
            items=items,
            first=first,
            last=last,
            row=self.row if sheet == self.home else None,
        )
        return self.area(chosen[0], *chosen[1:])

    def table_data(self, text: str) -> tuple[list[str], tuple[tuple[Value, ...], ...]] | None:
        """For ``SQL()``: the columns and rows of the table ``text`` names (a named range, with its header cells as
        column names when it has any, or the result of another ``SQL()``), or ``None`` when ``text`` names nothing.
        What it reads is recorded, so the query is calculated again when it changes."""
        self.mentioned.add(text.casefold())
        named = self.names.resolve(self.home, text)
        if named is None:
            return None
        header = named.header
        if named.anchor is not None:
            header = True
            region = self.spills.get(named.anchor)
            if region is None:
                if self.reads is not None:  # (wait for the formula that makes it: it is looked at once it has)
                    sheet_id, row, col = named.anchor
                    self.reads.append((sheet_id, row, col, row, col))
                raise FormulaError(REF, f"{text} has no result: its SQL() formula gave none")
        else:
            area = named.range
            assert area is not None and area.sheet is not None
            region = (area.sheet, area.first.row, area.first.col, area.last.row, area.last.col)
        sheet_id, row0, col0, row1, col1 = region
        if header:
            self.area(sheet_id, row0, col0, row0, col1)
            grid = self.sheets[sheet_id].grid
            headers = [format_value(grid.get((row0, col))) for col in range(col0, col1 + 1)]
        else:
            headers = [column_name(col) for col in range(col0, col1 + 1)]
        top = row0 + 1 if header else row0
        rows = self.area(sheet_id, top, col0, row1, col1).dense() if top <= row1 else ()
        return headers, rows
