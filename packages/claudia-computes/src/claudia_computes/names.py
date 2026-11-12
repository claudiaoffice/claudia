"""Named ranges and tables (E6.5, D600): one concept.

A *name* points at cells. A name whose first row is a header is a *table*: its columns have names, it can be written
``Sales[Amount]`` in a formula and queried as ``FROM Sales`` in ``SQL()``. A name may be scoped to a sheet, and then
it shadows a workbook-wide name of the same text on that sheet. A table may *grow with its last row*: typing into the
row below it makes that row part of it.

A name is either a **range** (it holds a rectangle of one sheet, which moves with the edits to the sheet, like a
:class:`~claudia_computes.CellRegion`) or a **result** (it is what a ``SQL()`` cell filled: the rectangle is
whatever the formula spilled, so it is not stored here but asked of the calculator).

Purposes colour a table's cells by what they are for — *input* (typed by people), *data*, *calculation* and
*result* — per column, a column without one of its own taking the table's.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import ClassVar

from .limits import MAX_COLS, MAX_ROWS
from .refs import RangeRef, SheetId, column_index
from .values import REF, VALUE, FormulaError

PURPOSES = ("input", "data", "calc", "result")
DEFAULT_PURPOSE = "data"
MAX_NAME_LENGTH = 255

NameKey = tuple[SheetId | None, str]  # (the sheet it is scoped to or None, its text without regard to case)
Rect = tuple[SheetId, int, int, int, int]  # (sheet, row0, col0, row1, col1)
Anchor = tuple[SheetId, int, int]  # the cell of a SQL() formula

_NAME = re.compile(r"[^\W\d][\w.]*", re.UNICODE)
_CELL_LIKE = re.compile(r"([A-Za-z]{1,3})([0-9]+)")
_RESERVED = frozenset({"TRUE", "FALSE"})


def name_problem(text: str) -> str | None:
    """Why ``text`` cannot be a name (or ``None`` when it can): a name is a word, and not a cell, since a formula
    could not tell the two apart."""
    if not text:
        return "a name needs some text"
    if len(text) > MAX_NAME_LENGTH:
        return f"a name has at most {MAX_NAME_LENGTH} characters"
    if _NAME.fullmatch(text) is None:
        return "a name starts with a letter and has only letters, digits, _ and ."
    if text.upper() in _RESERVED:
        return f"{text} is a value, not a name"
    cell = _CELL_LIKE.fullmatch(text)
    if cell is not None and column_index(cell[1]) < MAX_COLS and 0 < int(cell[2]) <= MAX_ROWS:
        return f"{text} is a cell, not a name"
    return None


def key_of(scope: SheetId | None, name: str) -> NameKey:
    """The key the registry files ``name`` under."""
    return scope, name.casefold()


@dataclass(frozen=True)
class NamedRange:
    """One name. ``range`` is the rectangle (always on a sheet) of a range; a result has none and is instead tied to
    the ``SQL()`` cell ``anchor``, whose spill is its rectangle. ``header`` says the first row names the columns,
    ``grows`` that the table takes in the row typed right below it, ``purpose`` is the table's and
    ``column_purposes`` the ones of single columns, as (offset from the first column, purpose)."""

    kind: ClassVar[str] = "name"
    name: str
    scope: SheetId | None
    range: RangeRef | None = None
    header: bool = False
    grows: bool = False
    purpose: str = DEFAULT_PURPOSE
    column_purposes: tuple[tuple[int, str], ...] = ()
    anchor: Anchor | None = None

    def __post_init__(self) -> None:
        if (self.range is None) == (self.anchor is None):
            raise ValueError("a name is either a range or a result, not both and not neither")
        if self.range is not None and self.range.sheet is None:
            raise ValueError("the range of a name is on a sheet")
        if self.purpose not in PURPOSES:
            raise ValueError(f"unknown purpose {self.purpose!r}")
        if any(purpose not in PURPOSES for _, purpose in self.column_purposes):
            raise ValueError("unknown purpose for a column")

    @property
    def key(self) -> NameKey:
        """The key the registry files this name under."""
        return key_of(self.scope, self.name)

    @property
    def is_result(self) -> bool:
        """Whether it is what a ``SQL()`` formula filled."""
        return self.anchor is not None

    @property
    def sheet(self) -> SheetId:
        """The sheet the cells are on."""
        if self.anchor is not None:
            return self.anchor[0]
        assert self.range is not None and self.range.sheet is not None  # (checked in __post_init__)
        return self.range.sheet

    def purpose_of(self, offset: int) -> str:
        """The purpose of the column ``offset`` columns from the first one."""
        return dict(self.column_purposes).get(offset, self.purpose)

    def with_range(self, area: RangeRef) -> NamedRange:
        """The same name on other cells (a table that grew, or moved)."""
        return replace(self, range=area)

    def to_data(self) -> dict:
        """The name as plain data: what the log stores and clients are sent."""
        data: dict = {
            "name": self.name,
            "scope": self.scope,
            "header": self.header,
            "grows": self.grows,
            "purpose": self.purpose,
            "column_purposes": [[offset, purpose] for offset, purpose in self.column_purposes],
        }
        if self.range is not None:
            data["range"] = self.range.to_dict()
        if self.anchor is not None:
            data["anchor"] = list(self.anchor)
        return data

    @classmethod
    def from_data(cls, data: dict) -> NamedRange:
        """Inverse of :meth:`to_data`; ``ValueError`` when the data is not a name."""
        try:
            area = RangeRef.from_dict(data["range"]) if data.get("range") else None
            anchor = data.get("anchor")
            return cls(
                data["name"],
                None if data.get("scope") is None else SheetId(data["scope"]),
                area,
                bool(data.get("header", False)),
                bool(data.get("grows", False)),
                data.get("purpose", DEFAULT_PURPOSE),
                tuple((int(o), p) for o, p in data.get("column_purposes", ())),
                None if anchor is None else (SheetId(anchor[0]), int(anchor[1]), int(anchor[2])),
            )
        except (KeyError, TypeError, IndexError) as problem:
            raise ValueError(f"this is not a name: {problem}") from None


class Names:
    """The names of a workbook: ``(scope, text)`` -> name. Looking one up for a sheet prefers the sheet's own."""

    def __init__(self) -> None:
        self._by_key: dict[NameKey, NamedRange] = {}

    def __len__(self) -> int:
        return len(self._by_key)

    def __iter__(self):
        return iter(self._by_key.values())

    def __contains__(self, key: object) -> bool:
        return key in self._by_key

    def get(self, key: NameKey) -> NamedRange | None:
        """The name filed under ``key`` (a scope and a text without regard to case), or ``None``."""
        return self._by_key.get(key)

    def put(self, name: NamedRange | None, key: NameKey | None = None) -> None:
        """File ``name`` (replacing the one under its key), or with ``name`` ``None`` take out the one under ``key``."""
        if name is None:
            if key is not None:
                self._by_key.pop(key, None)
            return
        self._by_key[name.key] = name

    def resolve(self, home: SheetId, text: str) -> NamedRange | None:
        """What ``text`` means for a formula on ``home``: the sheet's own name, else the workbook's."""
        folded = text.casefold()
        return self._by_key.get((home, folded)) or self._by_key.get((None, folded))

    def sorted(self) -> list[NamedRange]:
        """Every name, workbook-wide ones first, each group by text."""
        return sorted(self._by_key.values(), key=lambda n: (n.scope is not None, str(n.scope), n.name.casefold()))

    def to_data(self) -> list[dict]:
        """Every name as plain data, in a fixed order."""
        return [name.to_data() for name in self.sorted()]

    @classmethod
    def from_data(cls, data: Sequence[dict]) -> Names:
        """Inverse of :meth:`to_data`."""
        names = cls()
        for item in data:
            names.put(NamedRange.from_data(item))
        return names

    def clear(self) -> None:
        """Forget every name."""
        self._by_key.clear()


# ------------------------------------------------------------------------------------ which cells a reference means
HEADERS, DATA, ALL, THIS_ROW = "#Headers", "#Data", "#All", "#This Row"


def column_of(headers: Sequence[str], wanted: str, table: str) -> int:
    """The offset of the column called ``wanted`` (without regard to case or the spaces around it)."""
    folded = wanted.strip().casefold()
    for offset, text in enumerate(headers):
        if text.strip().casefold() == folded:
            return offset
    raise FormulaError(REF, f"{table} has no column called {wanted!r}")


def select(
    table: str,
    region: Rect,
    *,
    header: bool,
    headers: Sequence[str],
    items: tuple[str, ...],
    first: str | None,
    last: str | None,
    row: int | None,
) -> Rect:
    """The cells ``table[...]`` means: ``region`` is the whole table (header row included when ``header``),
    ``headers`` the text of each column's header, ``row`` the row of the cell the formula is on (for ``@``).

    Raises :class:`FormulaError`: ``#REF!`` for a column or a header the table lacks, ``#VALUE!`` for ``@`` outside
    the table's rows."""
    sheet, row0, col0, row1, col1 = region
    data0 = row0 + (1 if header else 0)
    if (first is not None or HEADERS in items or ALL in items) and not header:
        raise FormulaError(REF, f"{table} has no header row to name columns by")
    if first is not None:
        left = col0 + column_of(headers, first, table)
        right = left if last is None else col0 + column_of(headers, last, table)
        left, right = min(left, right), max(left, right)
    else:
        left, right = col0, col1
    if THIS_ROW in items:
        if row is None or not data0 <= row <= row1:
            raise FormulaError(VALUE, f"this cell is not in a data row of {table}")
        return sheet, row, left, row, right
    if ALL in items or (HEADERS in items and DATA in items):
        top, bottom = row0, row1
    elif HEADERS in items:
        top, bottom = row0, row0
    else:
        top, bottom = data0, row1
    bottom = max(top, bottom)  # (a table with a header and nothing below it: the row where the first one goes)
    return sheet, top, left, bottom, right
