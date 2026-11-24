"""Tables of a text in office files, whatever the format (E9.32, D1201-D1213): the part both converters share.

A file's table is first read into a :class:`FileTable`, a plain grid of what the format says (the words of each cell,
how far a cell reaches, which rows are the header, the widths), and only then turned into a
``TableDef``; and the other way round, a table definition becomes a grid of :class:`WriteCell` that
a format puts into its own elements. The formats therefore only know their own elements, and the rules about what a
table of a text is live here once:

* **A regular table** is one the model can hold: 1 to 100 rows and 1 to 10 columns, every cell one paragraph of plain
  words (a cell of several paragraphs, a picture, a table in a cell or a field is not regular), and merges that are
  rectangles. A table that is not regular stays in the file as it was, and the import says so (``"table"``).
* **A cell is its words.** The look of a table in a file (borders, shading, fonts of a cell) is not read: the table
  gets one of the text's own looks. A column is a number column when every filled box of its body reads as a number in
  the document's language, and then it is aligned right.
* **A total row is written as words.** Totals are derived in a text (D1204); a file has a row of words, which is what a
  reader of the file sees. Read back, that row is an ordinary body row.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count

from claudia_composes import ParagraphAnchor, TextModel, table_body
from claudia_core import (
    MAX_COLUMNS,
    MAX_ROWS,
    MAX_WIDTH,
    MIN_WIDTH,
    Column,
    Merge,
    Paragraph,
    TableDef,
    VisualObject,
    colour_of,
    entry_id,
    free_name,
    parse_number,
    plain,
)
from claudia_odf_io import points_of
from claudia_opc_io import EMU_PER_POINT

#: How wide a column is at least, in hundredths of a percent of the table (the column check's own limit).
_LEAST_COLUMN = 100


@dataclass(frozen=True)
class FileCell:
    """One position of the grid of a table in a file: the words of the cell that starts here, how many columns and rows
    it reaches over (``cols``, ``rows``), or ``covered`` when a cell that starts elsewhere reaches over this one."""

    text: str = ""
    cols: int = 1
    rows: int = 1
    covered: bool = False


@dataclass(frozen=True)
class FileTable:
    """A table as a file says it: ``grid`` has a row for every row, each with a position for every column of the grid
    (a cell that reaches over several has the covered positions after it), ``header_rows`` the rows the file repeats
    as a header, ``widths`` the width of every column in the file's own unit (only their proportions count) and
    ``width`` how much of the line the table takes, in hundredths of a percent, when the file says."""

    grid: tuple[tuple[FileCell, ...], ...]
    header_rows: int = 0
    widths: tuple[int, ...] | None = None
    width: int | None = None


# --------------------------------------------------------------------------------------------------- reading
def read_table(found: FileTable, table_id: str, language: str | None = None) -> TableDef | None:
    """The ``TableDef`` the text holds for ``found``, or ``None`` when it is not a regular table."""
    grid = found.grid
    rows, cols = len(grid), len(grid[0]) if grid else 0
    if not 1 <= rows <= MAX_ROWS or not 1 <= cols <= MAX_COLUMNS or any(len(line) != cols for line in grid):
        return None
    if not 0 <= found.header_rows <= rows:
        return None
    merges = _merges(grid)
    if merges is None:
        return None
    columns = _columns(found, grid, cols, language)
    definition = TableDef(
        table_id,
        tuple(Column(f"c{n}", kind, width=width) for n, (kind, width) in enumerate(columns, 1)),
        tuple(f"r{n}" for n in range(1, rows + 1)),
        dict(_entries(table_id, grid, merges)),
        tuple(Merge(f"r{r + 1}", f"c{c + 1}", high, wide) for r, c, high, wide in merges),
        header_rows=found.header_rows,
        width=found.width if found.width is not None and MIN_WIDTH <= found.width <= MAX_WIDTH else None,
    )
    try:
        definition.check()
    except ValueError:
        return None
    return definition


def _merges(grid: tuple[tuple[FileCell, ...], ...]) -> list[tuple[int, int, int, int]] | None:
    """The rectangles the cells reach over as ``(row, column, rows, columns)``, or ``None`` when the grid says one that
    does not fit (it leaves the table, crosses another, or covers a position the file did not mark as covered)."""
    rows, cols = len(grid), len(grid[0])
    taken: set[tuple[int, int]] = set()
    found: list[tuple[int, int, int, int]] = []
    for r, line in enumerate(grid):
        for c, cell in enumerate(line):
            if cell.covered:
                continue
            if cell.rows < 1 or cell.cols < 1 or r + cell.rows > rows or c + cell.cols > cols:
                return None
            if cell.rows == cell.cols == 1:
                continue
            rectangle = {(r + i, c + j) for i in range(cell.rows) for j in range(cell.cols)} - {(r, c)}
            if rectangle & taken or any(not grid[i][j].covered for i, j in rectangle):
                return None
            taken |= rectangle
            found.append((r, c, cell.rows, cell.cols))
    covered = {(r, c) for r, line in enumerate(grid) for c, cell in enumerate(line) if cell.covered}
    return found if covered == taken else None


def _entries(
    table_id: str, grid: tuple[tuple[FileCell, ...], ...], merges: list[tuple[int, int, int, int]]
) -> list[tuple[tuple[str, str], Paragraph]]:
    """The boxes that have words: the words of every cell on one line, and the words of the boxes a merge covers joined
    to its first box with a space, as merging cells in the text does."""
    words: dict[tuple[int, int], list[str]] = {}
    owner = {(r + i, c + j): (r, c) for r, c, high, wide in merges for i in range(high) for j in range(wide)}
    for r, line in enumerate(grid):
        for c, cell in enumerate(line):
            text = " ".join(plain(cell.text).split())
            if text:
                words.setdefault(owner.get((r, c), (r, c)), []).append(text)
    return [
        (
            (f"r{r + 1}", f"c{c + 1}"),
            Paragraph(entry_id(table_id, f"r{r + 1}", f"c{c + 1}"), "", " ".join(parts)).written_by(None),
        )
        for (r, c), parts in sorted(words.items())
    ]


def _columns(
    found: FileTable, grid: tuple[tuple[FileCell, ...], ...], cols: int, language: str | None
) -> list[tuple[str, int | None]]:
    """The kind and width of each column."""
    given = found.widths
    shares: list[int | None] = [None] * cols
    if given is not None and len(given) == cols and all(each > 0 for each in given):
        total = sum(given)
        rounded = [max(_LEAST_COLUMN, round(each * 10_000 / total)) for each in given]
        rounded[-1] = max(_LEAST_COLUMN, rounded[-1] - (sum(rounded) - 10_000))  # the rounding lands on the last
        shares = list(rounded)
    body = grid[found.header_rows :]
    kinds = []
    for c in range(cols):
        words = [" ".join(plain(line[c].text).split()) for line in body if not line[c].covered]
        filled = [each for each in words if each]
        numbers = bool(filled) and all(parse_number(each, language) is not None for each in filled)
        kinds.append("number" if numbers else "text")
    return list(zip(kinds, shares, strict=True))


# --------------------------------------------------------------------------------------------------- writing
@dataclass(frozen=True)
class WriteCell:
    """One position of the grid to write: ``style`` is the paragraph style of the words (the box's own, or the look's
    for its ``role``), ``number`` says to align the words right, and ``covered`` that another cell reaches over this
    one."""

    text: str
    role: str
    style: str
    cols: int = 1
    rows: int = 1
    covered: bool = False
    number: bool = False


def write_grid(definition: TableDef, language: str | None = None) -> list[list[WriteCell]]:
    """The grid of ``definition`` to write, header rows first and the total row last (as words, when a column has a
    total)."""
    column_ids = definition.column_ids()
    spans = {(m.row, m.col): m for m in definition.merges}
    out: list[list[WriteCell]] = []
    for index, row in enumerate(definition.rows):
        role = definition.role_of(index)
        line = []
        for column in definition.columns:
            paragraph = definition.paragraph(row, column.id)
            style = paragraph.style or f"table-{definition.look}-{role}"
            span = spans.get((row, column.id))
            cover = definition.cover_of(row, column.id)
            # below the first row of a merge its left column carries the width of the merge (as a file's continuing
            # cell does); the positions to its right are skipped by the writers
            below = (
                cover if cover is not None and span is None and cover.col == column.id and cover.row != row else None
            )
            line.append(
                WriteCell(
                    paragraph.text,
                    role,
                    style,
                    span.cols if span else (below.cols if below else 1),
                    span.rows if span else 1,
                    covered=cover is not None and span is None,
                    number=column.kind == "number" and role != "header",
                )
            )
        out.append(line)
    if definition.has_total():
        totals = definition.totals(language)
        style = f"table-{definition.look}-total"
        out.append(
            [
                WriteCell(totals.get(c, ""), "total", style, number=column.kind == "number")
                for c, column in zip(column_ids, definition.columns, strict=True)
            ]
        )
    return out


def column_shares(definition: TableDef) -> list[int]:
    """The width of each column of ``definition`` in hundredths of a percent of the table: the ones that were set count
    as they are and the others share what is left equally."""
    given = [column.width for column in definition.columns]
    free = given.count(None)
    left = max(0, 10_000 - sum(each for each in given if each is not None))
    each = max(_LEAST_COLUMN, left // free) if free else 0
    return [each if share is None else share for share in given]


# --------------------------------------------------------------------------------------------------- looks
@dataclass(frozen=True)
class CellLook:
    """What a role style says about the box of a cell, in values a file holds: the fill, and the colour and width (in
    EMU) of each side's line (top, right, bottom, left; ``None`` for none)."""

    fill: tuple[int, int, int] | None
    sides: tuple[tuple[tuple[int, int, int], int] | None, ...]


def cell_look(model: TextModel, style_id: str) -> CellLook:
    """The box of the cells that have the paragraph style ``style_id``, as ``model``'s styles and palette give it."""
    colours = model.palette.colours()
    css = model.styles.resolved(style_id, colours) if style_id in model.styles.ids() else {}
    page = colours.get("page")
    sides = []
    for side in ("top", "right", "bottom", "left"):
        colour = colour_of(css, f"border-{side}", page)
        sides.append((colour, round(points_of(css.get(f"border-{side}")) * EMU_PER_POINT)) if colour else None)
    return CellLook(colour_of(css, "background-color", page), tuple(sides))


# --------------------------------------------------------------------------------------------------- in the model
def put_tables(model: TextModel, placed: list[tuple[str, int, TableDef]]) -> None:
    """Take the tables a file had into ``model``, each shown by an object of its own that hangs from the paragraph
    ``paragraph`` at ``offset`` (a table in the flow is printed after the paragraph it hangs from). ``placed`` is in
    the order of the file, which is the order the objects stack in."""
    for paragraph, offset, definition in placed:
        model.tables.define(definition)
        object_id = next(f"o{n}" for n in count(1) if f"o{n}" not in model.objects)
        name = free_name("Table", model.names_in_use())
        model.insert_object(VisualObject(table_body(object_id, definition, name), ParagraphAnchor(paragraph, offset)))


def tables_after(model: TextModel, paragraph_id: str) -> list[TableDef]:
    """The tables that hang from the paragraph ``paragraph_id``, in the order they are drawn after it: by where they
    hang, and one that hangs where another does, in the order they stack. A floating table is written in the flow
    too."""
    found = []
    for object_id in model.stack_of(paragraph_id):
        obj = model.get_object(object_id)
        table = obj.body.table
        if table is not None and table in model.tables:
            found.append((obj.anchor.offset, model.tables[table]))
    return [definition for _, definition in sorted(found, key=lambda each: each[0])]


def table_styles(definition: TableDef) -> set[str]:
    """The ids of the styles a table is written with: those of the roles its rows have, and its boxes' own."""
    roles = {definition.role_of(index) for index in range(len(definition.rows))}
    if definition.has_total():
        roles.add("total")
    return {f"table-{definition.look}-{role}" for role in roles} | {
        p.style for p in definition.all_paragraphs() if p.style
    }


def table_changes(baseline: TextModel, current: TextModel) -> dict[str, tuple[list[TableDef], list[TableDef]]]:
    """The paragraphs whose tables differ between ``baseline`` and ``current`` (a table changed, moved, removed or
    added), each with the tables that hung from it and those that hang from it now. A paragraph that is gone has
    no tables left."""
    changes = {}
    for paragraph_id in dict.fromkeys([*(b.id for b in baseline.paragraphs), *(b.id for b in current.paragraphs)]):
        before, after = tables_after(baseline, paragraph_id), tables_after(current, paragraph_id)
        if before != after:
            changes[paragraph_id] = (before, after)
    return changes
