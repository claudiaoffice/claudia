"""A table: columns and rows with ids, the words of each of its boxes, the merges, and how it looks (D1201–D1207).

A table in a text is an object (``kind == "table"``) whose body names a :class:`TableDef` by id, as a container
names its definition (D390). The definition is plain data and is the same wherever it is read. This module is all the
kernel knows about tables; it knows no text, no page and no sheet, and it never reads a number out of a sheet: what
computes and composes share is :class:`TableSource`, the small protocol a linked table, a chart and the AI read, and
the commands (``claudia_core.table_commands``).

* **Ids, never positions.** Rows and columns have ids that are never given twice, not even after a row is deleted (the
  definition keeps a counter), so undo brings back the same ids and the AI can say "the Harvest column".
* **A box is one paragraph** (D1203). It is stored only when it has words or a style of its own, and its paragraph id is
  ``<table>/<row>/<column>`` (:func:`entry_id`), so typing in it is the ordinary text command. A paragraph with the
  style ``""`` follows the table's look (D1206); a style that is named is the person's own choice for that box.
* **Merges are rectangles** (D1205): the words of a merged box are in its top-left box and the boxes it covers hold
  none.
* **Numbers are words** (D1203): what is typed is what is stored. :func:`parse_number` reads a value with the
  *document's* language, which is what a total (:meth:`TableDef.totals`) or a sort (:meth:`TableDef.sort_order`) uses.

Everything here is immutable: an operation returns a new definition, because a command builds its inverse from the
state it found.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Protocol, runtime_checkable

from .errors import Refusal
from .fields import FIELD_CHAR
from .paragraphs import Paragraph

if TYPE_CHECKING:
    from .commands import Command

#: The most rows and columns a table of a text has (D1207). More is a linked table, or a table of computes.
MAX_ROWS = 100
MAX_COLUMNS = 10

#: The version of the plain-data form below.
FORMAT = 1

COLUMN_KINDS = ("text", "number")
#: What a column's total may be. ``count`` counts the boxes that hold a number.
TOTAL_FUNCTIONS = ("sum", "mean", "count", "min", "max")
PLACEMENTS = ("flow", "float")
ROLES = ("header", "body", "band", "total")
#: A table is as wide as the line, or this many hundredths of a percent of it at most (and at least 10 %).
MAX_WIDTH = 10_000
MIN_WIDTH = 1_000

_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}")
_PART = re.compile(r"[a-z][a-z0-9_-]{0,19}")
#: What a redacted character becomes (D720), the same filler as an object's words.
FILLER = "█"
_LOOK = re.compile(r"[a-z][a-z0-9-]{0,39}")


def _whole(value: object) -> bool:
    return type(value) is int


# --------------------------------------------------------------------------- ids of boxes
def entry_id(table: str, row: str, col: str) -> str:
    """The id of the paragraph in the box where ``row`` and ``col`` cross: ``t1/r4/c2``."""
    return f"{table}/{row}/{col}"


def parse_entry_id(paragraph_id: str) -> tuple[str, str, str] | None:
    """``(table, row, column)`` of a paragraph id that names a box of a table, ``None`` for any other id."""
    parts = paragraph_id.split("/")
    if len(parts) == 3 and _ID.fullmatch(parts[0]) and _PART.fullmatch(parts[1]) and _PART.fullmatch(parts[2]):
        return parts[0], parts[1], parts[2]
    return None


# --------------------------------------------------------------------------- numbers read from words
#: Languages that write a decimal comma. Everything else, and a text whose language is not known, writes a point.
_COMMA_LANGUAGES = frozenset(
    [
        "bg",
        "ca",
        "cs",
        "da",
        "de",
        "el",
        "es",
        "et",
        "eu",
        "fi",
        "fr",
        "gl",
        "hr",
        "hu",
        "id",
        "it",
        "lt",
        "lv",
        "nb",
        "nl",
        "nn",
        "no",
        "pl",
        "pt",
        "ro",
        "ru",
        "sk",
        "sl",
        "sr",
        "sv",
        "tr",
        "uk",
        "vi",
    ]
)
_SPACES = "    '’"


def decimal_comma(language: str | None) -> bool:
    """Does text in ``language`` (a BCP 47 tag, or ``None``) write 1,5 for one and a half?"""
    return language is not None and language.replace("_", "-").split("-")[0].lower() in _COMMA_LANGUAGES


def parse_number(text: str, language: str | None = None) -> Decimal | None:
    """The number these words are, read by the writing conventions of ``language``, or ``None`` when they are not one.

    Words are a number when they are only digits, with an optional sign, a decimal separator and group separators
    in the right places: ``1.234,5`` in German, ``1,234.5`` in English. ``1.234`` is 1234 in a German text and one and
    a bit in an English one; that is the point of reading by the document's language (D1203)."""
    word = text.strip().replace("−", "-")
    if not word:
        return None
    sign = ""
    if word[0] in "+-":
        sign, word = word[0], word[1:].lstrip()
    point, group = (",", ".") if decimal_comma(language) else (".", ",")
    for space in _SPACES:
        word = word.replace(space, group)
    whole, found, fraction = word.partition(point)
    if group in fraction or (found and not fraction):
        return None
    if not re.fullmatch(r"\d+|\d{1,3}(?:" + re.escape(group) + r"\d{3})+", whole or "0"):
        return None
    if fraction and not fraction.isdigit():
        return None
    try:
        return Decimal(f"{sign}{whole.replace(group, '') or '0'}" + (f".{fraction}" if fraction else ""))
    except InvalidOperation:  # pragma: no cover - the patterns above only let digits through
        return None


def format_number(value: Decimal, language: str | None = None) -> str:
    """The number as words in ``language``: its decimal separator, no group separators, as many decimals as it has."""
    text = format(value, "f")
    return text.replace(".", ",") if decimal_comma(language) else text


def _sort_text(text: str) -> str:
    """The words as they sort: capitals and accents do not matter (Ä after A, not after Z)."""
    folded = unicodedata.normalize("NFKD", text).casefold()
    return "".join(c for c in folded if not unicodedata.combining(c))


# --------------------------------------------------------------------------- the parts
@dataclass(frozen=True)
class Column:
    """A column: its id, whether it holds ``number`` or ``text`` (what aligns it and what a total reads), the total
    its last row shows (``None``: no total) and its width as a share of the table, in hundredths of a percent
    (``None``: as wide as its words need)."""

    id: str
    kind: str = "text"
    total: str | None = None
    width: int | None = None

    def check(self) -> None:
        """``ValueError`` with a sentence if the column makes no sense."""
        if not isinstance(self.id, str) or not _PART.fullmatch(self.id):
            raise ValueError(
                f"column id {str(self.id)[:40]!r}: lower-case letters, digits, '-' and '_', first a letter"
            )
        if self.kind not in COLUMN_KINDS:
            raise ValueError(f"a column holds {' or '.join(COLUMN_KINDS)}, not {self.kind!r}")
        if self.total is not None and self.total not in TOTAL_FUNCTIONS:
            raise ValueError(f"a total is one of {', '.join(TOTAL_FUNCTIONS)}, not {self.total!r}")
        if self.width is not None and (not _whole(self.width) or not 100 <= self.width <= MAX_WIDTH):
            raise ValueError("a column's width is a whole number of hundredths of a percent, from 1 % to 100 %")

    def to_data(self) -> dict:
        """The plain-data form."""
        return {"id": self.id, "kind": self.kind, "total": self.total, "width": self.width}

    @classmethod
    def from_data(cls, data: dict) -> Column:
        """Inverse of :meth:`to_data`."""
        return cls(data["id"], data.get("kind", "text"), data.get("total"), data.get("width"))


@dataclass(frozen=True)
class Merge:
    """Neighbouring boxes made one (D1205): the rectangle that starts at the box where ``row`` and ``col`` cross and
    is ``rows`` rows high and ``cols`` columns wide."""

    row: str
    col: str
    rows: int = 1
    cols: int = 1

    def to_data(self) -> dict:
        """The plain-data form."""
        return {"row": self.row, "col": self.col, "rows": self.rows, "cols": self.cols}

    @classmethod
    def from_data(cls, data: dict) -> Merge:
        """Inverse of :meth:`to_data`."""
        return cls(data["row"], data["col"], data["rows"], data["cols"])


@dataclass(frozen=True)
class RowSpec:
    """A row to put in: its id, the id of the row it goes behind (``None``: first), and the words of its boxes."""

    id: str
    after: str | None = None
    entries: tuple[tuple[str, Paragraph], ...] = ()

    def to_data(self) -> dict:
        """The plain-data form."""
        return {"id": self.id, "after": self.after, "entries": [[col, p.to_data()] for col, p in self.entries]}

    @classmethod
    def from_data(cls, data: dict) -> RowSpec:
        """Inverse of :meth:`to_data`."""
        return cls(data["id"], data["after"], tuple((col, Paragraph.from_data(p)) for col, p in data["entries"]))


@dataclass(frozen=True)
class ColumnSpec:
    """A column to put in: the column, the id of the one it goes behind (``None``: first), and its boxes' words."""

    column: Column
    after: str | None = None
    entries: tuple[tuple[str, Paragraph], ...] = ()

    def to_data(self) -> dict:
        """The plain-data form."""
        return {
            "column": self.column.to_data(),
            "after": self.after,
            "entries": [[row, p.to_data()] for row, p in self.entries],
        }

    @classmethod
    def from_data(cls, data: dict) -> ColumnSpec:
        """Inverse of :meth:`to_data`."""
        return cls(
            Column.from_data(data["column"]),
            data["after"],
            tuple((row, Paragraph.from_data(p)) for row, p in data["entries"]),
        )


@dataclass(frozen=True)
class TableLook:
    """A named bundle of four styles that draws a table (D1206): one paragraph style per role. A paragraph style holds a
    box and words, so it fills both slots of a box at once, as a cell style does in computes (D311)."""

    id: str
    name: str
    header: str
    body: str
    band: str
    total: str

    def style_for(self, role: str) -> str:
        """The id of the style of a role (``header``, ``body``, ``band`` or ``total``)."""
        if role not in ROLES:
            raise ValueError(f"a table look has the roles {', '.join(ROLES)}, not {role!r}")
        return getattr(self, role)

    def styles(self) -> tuple[str, ...]:
        """The four styles, by role."""
        return (self.header, self.body, self.band, self.total)


@runtime_checkable
class TableSource(Protocol):
    """A table something else can read, wherever its boxes live: an own table of a text, a named range of a sheet.

    Reading is by position, in the order the person sees: row 0 is the first row, and the first
    :meth:`header_rows` rows are the header. It is what a linked table pulls (D1209), what a chart is drawn from and
    what the AI is shown, so none of them needs to know which app the table is from."""

    @property
    def source_id(self) -> str:
        """The id the table is known by in its document."""

    def column_count(self) -> int:
        """How many columns."""

    def row_count(self) -> int:
        """How many rows, the header's included."""

    def header_rows(self) -> int:
        """How many of the first rows are the header."""

    def text(self, row: int, col: int) -> str:
        """The words in the box where this row and column cross, as the person reads them."""


# --------------------------------------------------------------------------- the definition
@dataclass(frozen=True)
class TableDef:
    """One table. ``entries`` holds the boxes that have words or a style of their own, by ``(row id, column id)``.

    ``header_rows`` is how many of the first rows are the header (they repeat on every page); the name of a column is
    the words of its last header box. ``banded`` shades every second body row. ``look`` names the bundle of four role
    styles that draws the table (D1206). ``placement`` is ``flow`` or ``float`` (D1202) and ``width`` its share of the
    line (``None``: the whole line). ``next_row`` and ``next_col`` count the ids that were given, so none is given
    twice."""

    id: str
    columns: tuple[Column, ...]
    rows: tuple[str, ...]
    entries: Mapping[tuple[str, str], Paragraph] = field(default_factory=dict)
    merges: tuple[Merge, ...] = ()
    header_rows: int = 1
    banded: bool = False
    look: str = "rules"
    placement: str = "flow"
    width: int | None = None
    next_row: int = 0
    next_col: int = 0

    kind: ClassVar[str] = "table"

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", MappingProxyType(dict(self.entries)))
        object.__setattr__(self, "merges", tuple(sorted(self.merges, key=lambda m: (m.row, m.col))))
        highest_row = max((int(r[1:]) for r in self.rows if re.fullmatch(r"r\d+", r)), default=0)
        highest_col = max((int(c.id[1:]) for c in self.columns if re.fullmatch(r"c\d+", c.id)), default=0)
        object.__setattr__(self, "next_row", max(self.next_row, highest_row))
        object.__setattr__(self, "next_col", max(self.next_col, highest_col))

    # -- construction ------------------------------------------------------------------------------------------
    @classmethod
    def blank(cls, table_id: str, rows: int, cols: int, *, header_rows: int = 1, **options) -> TableDef:
        """An empty table of ``rows`` by ``cols`` boxes, with ids ``r1``… and ``c1``…; the options are the fields."""
        if not 1 <= rows <= MAX_ROWS or not 1 <= cols <= MAX_COLUMNS:
            raise Refusal(
                "a table has 1 to {max_rows} rows and 1 to {max_columns} columns",
                max_rows=MAX_ROWS,
                max_columns=MAX_COLUMNS,
            )
        return cls(
            table_id,
            tuple(Column(f"c{n}") for n in range(1, cols + 1)),
            tuple(f"r{n}" for n in range(1, rows + 1)),
            header_rows=min(header_rows, rows),
            **options,
        )

    # -- reading -----------------------------------------------------------------------------------------------
    @property
    def source_id(self) -> str:
        """The id this table is known by (:class:`TableSource`)."""
        return self.id

    def column_count(self) -> int:
        """How many columns (:class:`TableSource`)."""
        return len(self.columns)

    def row_count(self) -> int:
        """How many rows (:class:`TableSource`)."""
        return len(self.rows)

    def entry(self, row: str, col: str) -> Paragraph | None:
        """The paragraph stored for a box, ``None`` while it has neither words nor a style of its own."""
        return self.entries.get((row, col))

    def paragraph(self, row: str, col: str) -> Paragraph:
        """The paragraph of a box: the stored one, or an empty one that follows the table's look."""
        return self.entries.get((row, col)) or Paragraph(entry_id(self.id, row, col), "")

    def text(self, row: int, col: int) -> str:
        """The words of the box at these positions (:class:`TableSource`)."""
        return self.paragraph(self.rows[row], self.columns[col].id).text

    def header_row_count(self) -> int:
        """How many of the first rows are the header (:class:`TableSource` calls this ``header_rows``)."""
        return self.header_rows

    def column_ids(self) -> tuple[str, ...]:
        """The ids of the columns, left to right."""
        return tuple(c.id for c in self.columns)

    def column(self, col: str) -> Column:
        """The column with this id; ``KeyError`` if there is none."""
        for found in self.columns:
            if found.id == col:
                return found
        raise KeyError(f"no column {col!r}")

    def column_name(self, col: str) -> str:
        """What the column is called: the words of its last header box, ``""`` when there is none."""
        if not self.header_rows:
            return ""
        return self.paragraph(self.rows[self.header_rows - 1], col).text.strip()

    def role_of(self, row_index: int) -> str:
        """What the row at this position is for: ``header``, ``band`` (every second body row of a banded table) or
        ``body``. The total row is not a row of the table; its role is ``total``."""
        if row_index < self.header_rows:
            return "header"
        return "band" if self.banded and (row_index - self.header_rows) % 2 == 1 else "body"

    def has_total(self) -> bool:
        """Does any column have a total, so that the table ends in a total row?"""
        return any(c.total for c in self.columns)

    def cover_of(self, row: str, col: str) -> Merge | None:
        """The merge a box is part of, if it is."""
        r, c = self.rows.index(row), self.column_ids().index(col)
        for found, r0, r1, c0, c1 in self._rects():
            if r0 <= r <= r1 and c0 <= c <= c1:
                return found
        return None

    def covered(self, row: str, col: str) -> bool:
        """Is this box one a merge covers, that is, part of a merge but not its top-left box?"""
        found = self.cover_of(row, col)
        return found is not None and (found.row, found.col) != (row, col)

    def _rects(self) -> list[tuple[Merge, int, int, int, int]]:
        cols = self.column_ids()
        return [
            (
                m,
                self.rows.index(m.row),
                self.rows.index(m.row) + m.rows - 1,
                cols.index(m.col),
                cols.index(m.col) + m.cols - 1,
            )
            for m in self.merges
        ]

    def all_paragraphs(self) -> Iterable[Paragraph]:
        """The stored paragraphs, row by row."""
        for row in self.rows:
            for col in self.columns:
                if (row, col.id) in self.entries:
                    yield self.entries[row, col.id]

    # -- totals and sorting ------------------------------------------------------------------------------------
    def totals(self, language: str | None = None) -> dict[str, str]:
        """The words of the total row, by column id: only the columns that have a total. Reads the body rows (not the
        header) that no merge covers, with the document's ``language`` (D1203); a box that is not a number is
        skipped, and ``count`` counts the ones that are."""
        out: dict[str, str] = {}
        for column in self.columns:
            if column.total is None:
                continue
            values: list[Decimal] = []
            for index, row in enumerate(self.rows):
                if index < self.header_rows or self.covered(row, column.id):
                    continue
                number = parse_number(self.paragraph(row, column.id).text, language)
                if number is not None:
                    values.append(number)
            out[column.id] = self._aggregate(column.total, values, language)
        return out

    @staticmethod
    def _aggregate(function: str, values: list[Decimal], language: str | None) -> str:
        if function == "count":
            return str(len(values))
        if not values:
            return ""
        if function == "sum":
            result = sum(values, Decimal(0))
        elif function == "min":
            result = min(values)
        elif function == "max":
            result = max(values)
        else:
            digits = max((-exponent for v in values if isinstance(exponent := v.as_tuple().exponent, int)), default=0)
            result = (sum(values, Decimal(0)) / len(values)).quantize(Decimal(1).scaleb(-max(digits, 2)))
        return format_number(result, language)

    def sort_order(self, col: str, descending: bool = False, language: str | None = None) -> tuple[str, ...]:
        """The order of the rows with the body rows sorted by this column: numbers first (as numbers, by the
        document's language), then words (capitals and accents do not count), empty boxes last whichever way it goes.
        The header stays where it is and equal rows keep their order, so sorting twice changes nothing.

        ``ValueError`` when a merge spans rows of the body: sorting would tear it apart (D1205)."""
        self.column(col)
        body = self.rows[self.header_rows :]
        if any(m.rows > 1 and self.rows.index(m.row) >= self.header_rows for m in self.merges):
            raise Refusal("a table with merged rows cannot be sorted: split them first")
        numbers: list[tuple[str, Decimal]] = []
        texts: list[tuple[str, str]] = []
        empty: list[str] = []
        for row in body:
            words = self.paragraph(row, col).text.strip()
            number = parse_number(words, language)
            if number is not None:
                numbers.append((row, number))
            elif words:
                texts.append((row, words))
            else:
                empty.append(row)
        numbers.sort(key=lambda each: each[1], reverse=descending)
        texts.sort(key=lambda each: _sort_text(each[1]), reverse=descending)
        by_kind = [row for row, _ in texts] + [row for row, _ in numbers]
        ordered = by_kind if descending else by_kind[len(texts) :] + by_kind[: len(texts)]
        return (*self.rows[: self.header_rows], *ordered, *empty)

    # -- changing: boxes ---------------------------------------------------------------------------------------
    def with_entries(self, changes: Iterable[tuple[str, str, Paragraph | None]]) -> TableDef:
        """The table with these boxes changed; ``None`` takes a box's paragraph away (it is empty again).

        ``ValueError`` for a box that is not in the table, one a merge covers, or a paragraph with another id than
        its box's."""
        entries = dict(self.entries)
        for row, col, paragraph in changes:
            if row not in self.rows or col not in self.column_ids():
                raise ValueError(f"the table has no box where row {row!r} and column {col!r} cross")
            if paragraph is None:
                entries.pop((row, col), None)
                continue
            if paragraph.id != entry_id(self.id, row, col):
                raise ValueError("the paragraph of a box has the id of the box")
            if self.covered(row, col) and (paragraph.text or paragraph.style):
                raise ValueError("a merged box holds its words in its top-left box")
            entries[row, col] = paragraph
        return replace(self, entries=entries)

    # -- changing: rows ----------------------------------------------------------------------------------------
    def insert_rows(self, specs: Iterable[RowSpec], merges: Iterable[Merge] | None = None) -> TableDef:
        """The table with these rows put in, one after the other, each behind the row it names (``None``: first).

        A merge that a row is put inside grows by it; ``merges``, when given, are the merges afterwards instead (what
        an undo hands back)."""
        table = self
        for spec in specs:
            table = table._insert_row(spec)
        if len(table.rows) > MAX_ROWS:
            raise Refusal(
                "a table has at most {max_rows} rows: use a linked table or computes for more", max_rows=MAX_ROWS
            )
        return table if merges is None else table._with_merges(tuple(merges))

    def _insert_row(self, spec: RowSpec) -> TableDef:
        if spec.id in self.rows:
            raise ValueError(f"the table has a row {spec.id!r} already")
        if spec.after is not None and spec.after not in self.rows:
            raise ValueError(f"the table has no row {spec.after!r} to put a row behind")
        at = 0 if spec.after is None else self.rows.index(spec.after) + 1
        rects = [(m, r0, r1, c0, c1) for m, r0, r1, c0, c1 in self._rects()]
        rows = (*self.rows[:at], spec.id, *self.rows[at:])
        grown = []
        for found, r0, r1, _c0, _c1 in rects:
            grown.append(replace(found, rows=found.rows + 1) if r0 < at <= r1 else found)
        table = replace(self, rows=rows, merges=tuple(grown), next_row=max(self.next_row, _number(spec.id)))
        return table.with_entries((spec.id, col, p) for col, p in spec.entries)

    def delete_rows(self, ids: Iterable[str]) -> TableDef:
        """The table without these rows (and the words in them). A merge loses the rows it had among them and stops
        being one when only a single box is left; a table keeps at least one row."""
        gone = set(ids)
        if not gone <= set(self.rows):
            raise ValueError(f"the table has no row {sorted(gone - set(self.rows))[0]!r}")
        if len(gone) == len(self.rows):
            raise Refusal("a table keeps at least one row")
        rows = tuple(r for r in self.rows if r not in gone)
        merges = self._shrunk(gone, axis=0)
        entries = {k: p for k, p in self.entries.items() if k[0] not in gone}
        header = min(self.header_rows, sum(1 for r in self.rows[: self.header_rows] if r not in gone))
        return replace(self, rows=rows, entries=entries, merges=merges, header_rows=min(header, len(rows)))

    def row_order(self, order: Iterable[str]) -> TableDef:
        """The table with its rows in this order, which has to be the rows it has: the header stays first and no merge
        may be torn apart (a merged box's rows stay together, in their order)."""
        order = tuple(order)
        if sorted(order) != sorted(self.rows):
            raise ValueError("the new order has to hold exactly the rows of the table")
        if order[: self.header_rows] != self.rows[: self.header_rows]:
            raise Refusal("the header stays at the top of the table")
        for found in self.merges:
            if found.rows > 1:
                first = self.rows.index(found.row)
                together = self.rows[first : first + found.rows]
                at = order.index(together[0])
                if order[at : at + found.rows] != together:
                    raise Refusal("a merged box cannot be torn apart: split it first")
        return replace(self, rows=order)

    # -- changing: columns -------------------------------------------------------------------------------------
    def insert_columns(self, specs: Iterable[ColumnSpec], merges: Iterable[Merge] | None = None) -> TableDef:
        """The table with these columns put in; the counterpart of :meth:`insert_rows`."""
        table = self
        for spec in specs:
            table = table._insert_column(spec)
        if len(table.columns) > MAX_COLUMNS:
            raise Refusal(
                "a table has at most {max_columns} columns: use a linked table or computes for more",
                max_columns=MAX_COLUMNS,
            )
        return table if merges is None else table._with_merges(tuple(merges))

    def _insert_column(self, spec: ColumnSpec) -> TableDef:
        ids = self.column_ids()
        col = spec.column
        if col.id in ids:
            raise ValueError(f"the table has a column {col.id!r} already")
        if spec.after is not None and spec.after not in ids:
            raise ValueError(f"the table has no column {spec.after!r} to put a column behind")
        at = 0 if spec.after is None else ids.index(spec.after) + 1
        grown = []
        for found, _r0, _r1, c0, c1 in self._rects():
            grown.append(replace(found, cols=found.cols + 1) if c0 < at <= c1 else found)
        columns = (*self.columns[:at], col, *self.columns[at:])
        table = replace(self, columns=columns, merges=tuple(grown), next_col=max(self.next_col, _number(col.id)))
        return table.with_entries((row, col.id, p) for row, p in spec.entries)

    def delete_columns(self, ids: Iterable[str]) -> TableDef:
        """The table without these columns (and the words in them); the counterpart of :meth:`delete_rows`."""
        gone = set(ids)
        if not gone <= set(self.column_ids()):
            raise ValueError(f"the table has no column {sorted(gone - set(self.column_ids()))[0]!r}")
        if len(gone) == len(self.columns):
            raise Refusal("a table keeps at least one column")
        columns = tuple(c for c in self.columns if c.id not in gone)
        entries = {k: p for k, p in self.entries.items() if k[1] not in gone}
        return replace(self, columns=columns, entries=entries, merges=self._shrunk(gone, axis=1))

    def column_order(self, order: Iterable[str]) -> TableDef:
        """The table with its columns in this order, which has to be the columns it has; no merge may be torn apart."""
        order = tuple(order)
        ids = self.column_ids()
        if sorted(order) != sorted(ids):
            raise ValueError("the new order has to hold exactly the columns of the table")
        for found in self.merges:
            if found.cols > 1:
                first = ids.index(found.col)
                together = ids[first : first + found.cols]
                at = order.index(together[0])
                if order[at : at + found.cols] != together:
                    raise Refusal("a merged box cannot be torn apart: split it first")
        by_id = {c.id: c for c in self.columns}
        return replace(self, columns=tuple(by_id[i] for i in order))

    def with_column(self, column: Column) -> TableDef:
        """The table with this column's settings (kind, total, width) in place of the one with its id."""
        column.check()
        self.column(column.id)
        return replace(self, columns=tuple(column if c.id == column.id else c for c in self.columns))

    # -- changing: merges --------------------------------------------------------------------------------------
    def with_merge(self, row: str, col: str, rows: int, cols: int) -> TableDef:
        """The table with the rectangle starting at this box, ``rows`` high and ``cols`` wide, merged; 1 by 1 splits a
        merge that starts there. ``ValueError`` when the rectangle leaves the table or meets another merge, or when
        it covers words (a merge starts from boxes that hold none besides the first: move the words first)."""
        ids = self.column_ids()
        if row not in self.rows or col not in ids:
            raise ValueError("a merge starts at a box of the table")
        if not _whole(rows) or not _whole(cols) or rows < 1 or cols < 1:
            raise ValueError("a merge is at least one box")
        r, c = self.rows.index(row), ids.index(col)
        if r + rows > len(self.rows) or c + cols > len(ids):
            raise Refusal("a merge cannot reach beyond the table")
        kept = tuple(m for m in self.merges if (m.row, m.col) != (row, col))
        if rows == 1 and cols == 1:
            return replace(self, merges=kept)
        merged = Merge(row, col, rows, cols)
        probe = replace(self, merges=(*kept, merged))
        probe._check_merges()
        for rr in self.rows[r : r + rows]:
            for cc in ids[c : c + cols]:
                if (rr, cc) != (row, col) and (p := self.entries.get((rr, cc))) is not None and (p.text or p.style):
                    raise Refusal("the boxes a merge covers must be empty: move their words first")
        return probe

    def _with_merges(self, merges: tuple[Merge, ...]) -> TableDef:
        table = replace(self, merges=merges)
        table._check_merges()
        return table

    def _shrunk(self, gone: set[str], axis: int) -> tuple[Merge, ...]:
        """The merges after the rows (``axis`` 0) or columns (1) in ``gone`` are taken out."""
        order = self.rows if axis == 0 else self.column_ids()
        out = []
        for found in self.merges:
            start = order.index(found.row if axis == 0 else found.col)
            span = found.rows if axis == 0 else found.cols
            left = [i for i in order[start : start + span] if i not in gone]
            rows, cols = (len(left), found.cols) if axis == 0 else (found.rows, len(left))
            if not left or rows * cols == 1:
                continue
            row, col = (left[0], found.col) if axis == 0 else (found.row, left[0])
            out.append(Merge(row, col, rows, cols))
        return tuple(out)

    # -- changing: options -------------------------------------------------------------------------------------
    def with_options(self, **changes: object) -> TableDef:
        """The table with ``header_rows``, ``banded``, ``look``, ``placement`` or ``width`` changed."""
        unknown = set(changes) - {"header_rows", "banded", "look", "placement", "width"}
        if unknown:
            raise ValueError(f"a table has no option {sorted(unknown)[0]!r}")
        table = replace(self, **changes)  # type: ignore[arg-type]
        table.check()
        return table

    # -- checking ----------------------------------------------------------------------------------------------
    def check(self) -> None:
        """``ValueError`` with a sentence unless the table holds together."""
        if not isinstance(self.id, str) or not _ID.fullmatch(self.id):
            raise ValueError(f"table id {str(self.id)[:40]!r}: lower-case letters, digits, '-' and '_', first a letter")
        if not 1 <= len(self.rows) <= MAX_ROWS:
            raise Refusal(
                "a table has 1 to {max_rows} rows: use a linked table or computes for more", max_rows=MAX_ROWS
            )
        if not 1 <= len(self.columns) <= MAX_COLUMNS:
            raise Refusal(
                "a table has 1 to {max_columns} columns: use a linked table or computes for more",
                max_columns=MAX_COLUMNS,
            )
        if len(set(self.rows)) != len(self.rows) or not all(_PART.fullmatch(r) for r in self.rows):
            raise ValueError("the rows of a table have different ids of lower-case letters, digits, '-' and '_'")
        for column in self.columns:
            column.check()
        if len(set(self.column_ids())) != len(self.columns):
            raise ValueError("the columns of a table have different ids")
        if not _whole(self.header_rows) or not 0 <= self.header_rows <= len(self.rows):
            raise ValueError("a table's header is from none of its rows up to all of them")
        if type(self.banded) is not bool:
            raise ValueError("banded must be true or false")
        if not isinstance(self.look, str) or not _LOOK.fullmatch(self.look):
            raise ValueError(f"look {str(self.look)[:40]!r}: lower-case letters, digits and '-', first a letter")
        if self.placement not in PLACEMENTS:
            raise ValueError(f"a table is placed {' or '.join(PLACEMENTS)}, not {self.placement!r}")
        if self.width is not None and (not _whole(self.width) or not MIN_WIDTH <= self.width <= MAX_WIDTH):
            raise Refusal("a table is from 10 % to 100 % of the line wide")
        self._check_merges()
        self._check_entries()

    def _check_entries(self) -> None:
        rows, cols = set(self.rows), set(self.column_ids())
        for (row, col), paragraph in self.entries.items():
            if row not in rows or col not in cols:
                raise ValueError(f"words in a box that is not in the table: {row!r}, {col!r}")
            if paragraph.id != entry_id(self.id, row, col):
                raise ValueError("the paragraph of a box has the id of the box")
            paragraph.check()
            if paragraph.generated is not None or paragraph.item is not None:
                raise ValueError("a table box holds plain words (D1203)")
            if self.covered(row, col) and (paragraph.text or paragraph.style):
                raise ValueError("a merged box holds its words in its top-left box")

    def _check_merges(self) -> None:
        rows, cols = self.rows, self.column_ids()
        taken: set[tuple[int, int]] = set()
        for found in self.merges:
            if found.row not in rows or found.col not in cols:
                raise ValueError("a merge starts at a box of the table")
            if not _whole(found.rows) or not _whole(found.cols) or found.rows < 1 or found.cols < 1:
                raise ValueError("a merge is at least one box")
            if found.rows * found.cols == 1:
                raise ValueError("a merge is more than one box")
            r, c = rows.index(found.row), cols.index(found.col)
            if r + found.rows > len(rows) or c + found.cols > len(cols):
                raise ValueError("a merge cannot reach beyond the table")
            spans = {(r + i, c + j) for i in range(found.rows) for j in range(found.cols)}
            if spans & taken:
                raise ValueError("two merges cannot share a box")
            taken |= spans

    # -- redaction ---------------------------------------------------------------------------------------------
    def blanked(self, *, keep_length: bool = False) -> TableDef:
        """The table with its words gone (D720): every box keeps its place and its style. With ``keep_length`` each
        character becomes a filler of the same length and the authors' runs stay (an import, where later steps edit by
        place); otherwise the words are emptied."""
        out: dict[tuple[str, str], Paragraph] = {}
        for key, p in self.entries.items():
            if keep_length:
                out[key] = p.with_text("".join(c if c == FIELD_CHAR else FILLER for c in p.text), p.runs)
            else:
                out[key] = replace(p.with_text("", ()), fields=())
        return replace(self, entries=out)

    # -- the plain-data form -----------------------------------------------------------------------------------
    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        ordered = [
            [row, col.id, self.entries[row, col.id].to_data()]
            for row in self.rows
            for col in self.columns
            if (row, col.id) in self.entries
        ]
        return {
            "format": FORMAT,
            "id": self.id,
            "columns": [c.to_data() for c in self.columns],
            "rows": list(self.rows),
            "entries": ordered,
            "merges": [m.to_data() for m in self.merges],
            "header_rows": self.header_rows,
            "banded": self.banded,
            "look": self.look,
            "placement": self.placement,
            "width": self.width,
            "next_row": self.next_row,
            "next_col": self.next_col,
        }

    @classmethod
    def from_data(cls, data: dict) -> TableDef:
        """Inverse of :meth:`to_data`; ``ValueError`` if the data is not a table of a format this reads."""
        if data.get("format") != FORMAT:
            raise ValueError(f"a table of format {data.get('format')!r}: this server reads format {FORMAT}")
        return cls(
            data["id"],
            tuple(Column.from_data(c) for c in data["columns"]),
            tuple(data["rows"]),
            {(row, col): Paragraph.from_data(p) for row, col, p in data["entries"]},
            tuple(Merge.from_data(m) for m in data["merges"]),
            data["header_rows"],
            data["banded"],
            data["look"],
            data["placement"],
            data["width"],
            data["next_row"],
            data["next_col"],
        )


def _number(ident: str) -> int:
    """The number in an id like ``r12`` or ``c3``, 0 for an id that is not made of a letter and digits."""
    found = re.fullmatch(r"[a-z](\d+)", ident)
    return int(found.group(1)) if found else 0


# --------------------------------------------------------------------------- the region
@dataclass(frozen=True)
class TableRegion:
    """Some rows and columns of one table: what somebody is in, holds or changes (D17). ``None`` for the rows or the
    columns means all of them, so a command about the whole table holds it all."""

    kind: ClassVar[str] = "table"
    table: str
    rows: frozenset[str] | None = None
    cols: frozenset[str] | None = None

    def overlaps(self, other: object) -> bool:
        """Do the two regions share a box of the same table?"""
        return (
            isinstance(other, TableRegion)
            and self.table == other.table
            and _meet(self.rows, other.rows)
            and _meet(self.cols, other.cols)
        )

    def transformed(self, command: Command) -> TableRegion | None:
        """The region after a command: it loses the rows and columns that were deleted and is gone when none is left."""
        if getattr(command, "table", None) != self.table:
            return self
        if command.kind == "core.DeleteRows" and self.rows is not None:
            rest = self.rows - frozenset(command.ids)  # type: ignore[attr-defined]
            return replace(self, rows=rest) if rest else None
        if command.kind == "core.DeleteColumns" and self.cols is not None:
            rest = self.cols - frozenset(command.ids)  # type: ignore[attr-defined]
            return replace(self, cols=rest) if rest else None
        if command.kind == "core.ForgetTable":
            return None
        return self

    def to_data(self) -> dict:
        """The plain-data form for the wire (regions are never stored in the log)."""
        return {
            "kind": self.kind,
            "table": self.table,
            "rows": None if self.rows is None else sorted(self.rows),
            "cols": None if self.cols is None else sorted(self.cols),
        }

    @classmethod
    def from_data(cls, data: dict) -> TableRegion:
        """Read a region sent by a client; ``ValueError`` if it is not one."""
        table, rows, cols = data.get("table"), data.get("rows"), data.get("cols")
        for part in (rows, cols):
            if part is not None and (not isinstance(part, list) or not all(isinstance(i, str) for i in part)):
                raise ValueError("a table region names a table and lists of row and column ids, or none for all")
        if not isinstance(table, str):
            raise ValueError("a table region names a table")
        return cls(table, None if rows is None else frozenset(rows), None if cols is None else frozenset(cols))


def _meet(a: frozenset[str] | None, b: frozenset[str] | None) -> bool:
    return a is None or b is None or bool(a & b)
