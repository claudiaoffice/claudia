"""Cell and range references, and the structural edits that move them.

(Ported unchanged from the claudia computes demo, sheetcore/refs.py. It is the model for how a Region moves
with edits, see region.py.)

Everything that points at cells (formulas, chart series, named ranges, object
anchors) uses the types in this module, and every structural edit (insert or
delete rows or columns) is applied through ``adjusted()`` here. That keeps the
"what happens to a reference when rows move" logic in exactly one place.

Conventions
-----------
* Rows and columns are zero-based internally; A1 text is one-based.
* ``sheet`` is a stable ``SheetId`` (never the sheet name, names can change).
  ``sheet=None`` means "the sheet the reference lives on".
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import ClassVar, NewType

SheetId = NewType("SheetId", str)
SheetNames = Callable[[SheetId], "str | None"]  # id -> name, for printing
SheetIds = Callable[[str], "SheetId | None"]  # name -> id, for parsing

Position = tuple[int, int]  # (row, col)


class RefParseError(ValueError):
    """Text is not a valid cell reference (or names an unknown sheet)."""


# ---------------------------------------------------------------- A1 helpers
def column_name(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA, ..."""
    name = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def column_index(letters: str) -> int:
    """A -> 0, Z -> 25, AA -> 26, ..."""
    value = 0
    for ch in letters.upper():
        value = value * 26 + (ord(ch) - 64)
    return value - 1


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_CELL_LIKE = re.compile(r"\$?[A-Za-z]{1,3}\$?\d+")  # a name like this must be quoted, or it would read as a cell
_A1 = re.compile(
    r"(?:(?P<sheet>'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)!)?"
    r"(?P<cabs>\$?)(?P<col>[A-Za-z]{1,3})(?P<rabs>\$?)(?P<row>\d+)"
)


def quote_sheet_name(name: str) -> str:
    """Quote a sheet name for use in a formula, only when needed."""
    if _IDENTIFIER.fullmatch(name) and not _CELL_LIKE.fullmatch(name) and name.upper() not in ("TRUE", "FALSE"):
        return name
    return "'" + name.replace("'", "''") + "'"


def parse_cell_ref(text: str, sheet_ids: SheetIds | None = None) -> CellRef:
    """Parse ``B3``, ``$B$3`` or ``Sheet2!B3`` / ``'My Sheet'!B3``.

    ``sheet_ids`` maps a sheet name to its id; a sheet-qualified reference to an
    unknown sheet raises RefParseError.
    """
    match = _A1.fullmatch(text.strip())
    if match is None:
        raise RefParseError(text)
    sheet: SheetId | None = None
    if match["sheet"]:
        name = match["sheet"]
        if name.startswith("'"):
            name = name[1:-1].replace("''", "'")
        sheet = sheet_ids(name) if sheet_ids else None
        if sheet is None:
            raise RefParseError(f"unknown sheet {name!r}")
    row = int(match["row"]) - 1
    if row < 0:
        raise RefParseError(text)
    return CellRef(
        row,
        column_index(match["col"]),
        sheet,
        row_abs=bool(match["rabs"]),
        col_abs=bool(match["cabs"]),
    )


def parse_range_ref(text: str, sheet_ids: SheetIds | None = None) -> RangeRef:
    """Parse ``B3`` (one cell), ``A1:B5``, ``Sheet2!A1:B5`` or ``'My Sheet'!A1:A9``.

    The sheet name goes in front of the first corner only (``Sheet2!A1:Sheet2!B5`` is
    accepted too). A range without a sheet has ``sheet=None``: it means the sheet it is
    used from. Raises RefParseError.
    """
    parts = text.strip().split(":")
    if len(parts) > 2 or not all(p.strip() for p in parts):
        raise RefParseError(text)
    first = parse_cell_ref(parts[0], sheet_ids)
    last = parse_cell_ref(parts[1], sheet_ids) if len(parts) == 2 else first
    if last.sheet is not None and first.sheet is not None and last.sheet != first.sheet:
        raise RefParseError(f"{text}: a range stays on one sheet")
    return RangeRef.between(first, last)


# ------------------------------------------------------- structural edits
@dataclass(frozen=True)
class StructuralEdit:
    """Insert or delete ``count`` rows/columns of ``sheet`` at index ``at``.

    For inserts, ``at`` is the index the first *new* line gets (existing lines
    from ``at`` on move down/right). For deletes, ``at`` is the first deleted
    line.
    """

    sheet: SheetId
    at: int
    count: int = 1

    axis: ClassVar[str] = ""  # "row" or "col"
    insert: ClassVar[bool] = True

    def __post_init__(self):
        if self.at < 0 or self.count < 1:
            raise ValueError("at must be >= 0 and count >= 1")

    def map_index(self, index: int) -> int | None:
        """Where a single row/column ends up; None if it was deleted."""
        if self.insert:
            return index + self.count if index >= self.at else index
        end = self.at + self.count
        if index < self.at:
            return index
        if index < end:
            return None
        return index - self.count

    def map_span(self, first: int, last: int) -> tuple[int, int] | None:
        """Where an inclusive span ends up; None if it was deleted entirely.

        Inserting inside a span grows it; deleting part of it shrinks it.
        """
        if self.insert:
            if first >= self.at:
                return first + self.count, last + self.count
            if first < self.at <= last:
                return first, last + self.count
            return first, last
        end = self.at + self.count
        new_first = first - max(0, min(end, first) - self.at)
        new_last = last - max(0, min(end, last + 1) - self.at)
        return None if new_last < new_first else (new_first, new_last)


@dataclass(frozen=True)
class InsertRows(StructuralEdit):
    axis: ClassVar[str] = "row"
    insert: ClassVar[bool] = True


@dataclass(frozen=True)
class DeleteRows(StructuralEdit):
    axis: ClassVar[str] = "row"
    insert: ClassVar[bool] = False


@dataclass(frozen=True)
class InsertCols(StructuralEdit):
    axis: ClassVar[str] = "col"
    insert: ClassVar[bool] = True


@dataclass(frozen=True)
class DeleteCols(StructuralEdit):
    axis: ClassVar[str] = "col"
    insert: ClassVar[bool] = False


# ------------------------------------------------------------------ CellRef
@dataclass(frozen=True, slots=True)
class CellRef:
    """One cell, by 0-based row and column, optionally on a named sheet and with ``$``-absolute parts."""

    row: int
    col: int
    sheet: SheetId | None = None
    row_abs: bool = False  # the "$" in A$1
    col_abs: bool = False  # the "$" in $A1

    @classmethod
    def parse(cls, text: str, sheet_ids: SheetIds | None = None) -> CellRef:
        """Read an A1 reference such as ``B3``, ``$B$3`` or ``'My sheet'!B3``."""
        return parse_cell_ref(text, sheet_ids)

    def to_a1(self, sheet_names: SheetNames | None = None, include_sheet: bool = True) -> str:
        """The reference in A1 notation; ``#REF!`` if it names a sheet that no longer exists."""
        body = f"{'$' if self.col_abs else ''}{column_name(self.col)}{'$' if self.row_abs else ''}{self.row + 1}"
        if self.sheet is None or not include_sheet:
            return body
        name = sheet_names(self.sheet) if sheet_names else None
        if name is None:
            return "#REF!"
        return f"{quote_sheet_name(name)}!{body}"

    def with_row(self, row: int) -> CellRef:
        """The same reference on another row."""
        return CellRef(row, self.col, self.sheet, self.row_abs, self.col_abs)

    def with_col(self, col: int) -> CellRef:
        """The same reference in another column."""
        return CellRef(self.row, col, self.sheet, self.row_abs, self.col_abs)

    def resolved(self, home: SheetId) -> CellRef:
        """Same reference with ``sheet`` filled in (``home`` if it was None)."""
        return self if self.sheet is not None else CellRef(self.row, self.col, home, self.row_abs, self.col_abs)

    def offset(self, d_row: int, d_col: int) -> CellRef | None:
        """Move for copy/paste: absolute parts stay put. None if off the sheet."""
        row = self.row if self.row_abs else self.row + d_row
        col = self.col if self.col_abs else self.col + d_col
        if row < 0 or col < 0:
            return None
        return CellRef(row, col, self.sheet, self.row_abs, self.col_abs)

    def adjusted(self, edit: StructuralEdit, home: SheetId) -> CellRef | None:
        """The reference after ``edit``; None if the cell was deleted (#REF!)."""
        if (self.sheet or home) != edit.sheet:
            return self
        if edit.axis == "row":
            new = edit.map_index(self.row)
            return None if new is None else CellRef(new, self.col, self.sheet, self.row_abs, self.col_abs)
        new = edit.map_index(self.col)
        return None if new is None else CellRef(self.row, new, self.sheet, self.row_abs, self.col_abs)

    def to_dict(self) -> dict:
        """The reference as plain data: row, column, sheet and the two absolute flags."""
        return {
            "row": self.row,
            "col": self.col,
            "sheet": self.sheet,
            "row_abs": self.row_abs,
            "col_abs": self.col_abs,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CellRef:
        """Read a reference back from :meth:`to_dict`'s plain data."""
        return cls(
            data["row"],
            data["col"],
            data.get("sheet"),
            data.get("row_abs", False),
            data.get("col_abs", False),
        )


# ----------------------------------------------------------------- RangeRef
@dataclass(frozen=True, slots=True)
class RangeRef:
    """A rectangle of cells; ``first`` is top-left, ``last`` bottom-right."""

    first: CellRef
    last: CellRef

    @classmethod
    def between(cls, a: CellRef, b: CellRef) -> RangeRef:
        """Build a normalised range from any two corners."""
        (r1, ra1), (r2, ra2) = sorted([(a.row, a.row_abs), (b.row, b.row_abs)], key=lambda t: t[0])
        (c1, ca1), (c2, ca2) = sorted([(a.col, a.col_abs), (b.col, b.col_abs)], key=lambda t: t[0])
        sheet = a.sheet if a.sheet is not None else b.sheet
        return cls(CellRef(r1, c1, sheet, ra1, ca1), CellRef(r2, c2, sheet, ra2, ca2))

    @property
    def sheet(self) -> SheetId | None:
        """The sheet the range is on (its first corner's), ``None`` for the formula's own sheet."""
        return self.first.sheet

    def intersects(self, other: RangeRef) -> bool:
        """Rectangle overlap. Resolve both to the same sheet first."""
        return not (
            self.last.row < other.first.row
            or other.last.row < self.first.row
            or self.last.col < other.first.col
            or other.last.col < self.first.col
        )

    def cells(self) -> Iterator[Position]:
        """All (row, col) positions, row by row."""
        for row in range(self.first.row, self.last.row + 1):
            for col in range(self.first.col, self.last.col + 1):
                yield row, col

    def resolved(self, home: SheetId) -> RangeRef:
        """Same range with ``sheet`` filled in (``home`` if it was None)."""
        return RangeRef(self.first.resolved(home), self.last.resolved(home))

    def to_a1(self, sheet_names: SheetNames | None = None) -> str:
        """The range in A1 notation (``A1:B4``, ``Sheet2!A1:B4``); ``#REF!`` if its sheet no longer exists."""
        head = self.first.to_a1(sheet_names)
        if head == "#REF!":
            return head
        return f"{head}:{self.last.to_a1(sheet_names, include_sheet=False)}"

    def adjusted(self, edit: StructuralEdit, home: SheetId) -> RangeRef | None:
        """The range after ``edit``; None if it was deleted entirely."""
        if (self.sheet or home) != edit.sheet:
            return self
        if edit.axis == "row":
            span = edit.map_span(self.first.row, self.last.row)
            if span is None:
                return None
            return RangeRef(self.first.with_row(span[0]), self.last.with_row(span[1]))
        span = edit.map_span(self.first.col, self.last.col)
        if span is None:
            return None
        return RangeRef(self.first.with_col(span[0]), self.last.with_col(span[1]))

    def to_dict(self) -> dict:
        """The range as plain data (both corners as :meth:`CellRef.to_dict`)."""
        return {"first": self.first.to_dict(), "last": self.last.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> RangeRef:
        """Read a range back from :meth:`to_dict`'s plain data."""
        return cls(CellRef.from_dict(data["first"]), CellRef.from_dict(data["last"]))
