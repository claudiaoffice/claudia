"""Tables on the wire: the methods that make and change a table, the same for every app that holds objects (E9.32).

A table is a *definition* (rows, columns, the words of its boxes, merges, a look) and an object that shows it, as a
rendered container is (:mod:`claudia_server.rendered`). The kernel's commands do the work and carry their exact
inverses (:mod:`claudia_core.table_commands`); this module is what a request is made of. Rows, columns and boxes are
named by id, never by position, so a request made against a colleague's newer table cannot hit the wrong row; the
ids are what ``tables`` lists.

* ``tables``: the definitions, each with the total row the way it is read now (derived, never stored, D1203).
* ``add_table``, ``remove_table``: a table comes into the text, with words if the request has them, and goes with
  its object.
* ``set_entries``: words into boxes, or out of them.
* ``insert_rows``, ``delete_rows``, ``move_rows``, ``sort_rows`` and the same for columns.
* ``set_column``, ``set_table_options``, ``merge_cells``, ``split_cell``.

Typing into a box is not here: it is ``replace_text`` (and ``replace_words`` for a model) with the box's id, which is
``<table>/<row>/<column>``. A box is one paragraph (D1210); a line break written into it becomes a space (D1212).

Every request is one step in the history. A refusal names what is wrong and leaves the table as it was.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace

from claudia_core import (
    AddObject,
    Batch,
    Column,
    ColumnSpec,
    DefineTable,
    DeleteColumns,
    DeleteRows,
    ForgetTable,
    InsertColumns,
    InsertRows,
    ObjectBody,
    ObjectModel,
    Paragraph,
    RemoveObject,
    RowSpec,
    SetColumn,
    SetColumnOrder,
    SetEntries,
    SetMerge,
    SetRowOrder,
    SetTableOptions,
    TableDef,
    entry_id,
    plain,
)
from claudia_core.tables import MAX_COLUMNS, MAX_ROWS

from .i18n import msg
from .object_methods import Placement
from .protocol import Context, MethodTable, RequestError
from .thing_names import default_name
from .wire import done, fresh_id

#: The frame a table's object has; a table is drawn by its look (D1206), the frame only says how big it is.
TABLE_STYLE = "plain-box"
DEFAULT_WIDTH = 480  # CSS pixels: the nominal width of a new table's object (a flow table takes the line)
ROW_HEIGHT = 24  # CSS pixels per row of a new table's object, until a client has measured it
COLUMN_SETTINGS = ("kind", "total", "width")
#: The methods that change a table. The assistant may call them (``apps.MODEL_METHODS``): a table is read by ids, not
#: by counting, so a model can work in it; they are changes, so in *suggest* mode it makes none of them.
TABLE_METHODS = (
    "add_table",
    "remove_table",
    "set_entries",
    "insert_rows",
    "delete_rows",
    "move_rows",
    "sort_rows",
    "insert_columns",
    "delete_columns",
    "move_columns",
    "set_column",
    "set_table_options",
    "merge_cells",
    "split_cell",
)


# ------------------------------------------------------------------------------------------------------ helpers
def one_line(text: str) -> str:
    """The words of a box as the wire takes them: one line, and no field (a box is one paragraph, D1212)."""
    return " ".join(plain(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"))


def _box(table: str, row: str, col: str, text: str, style: str, author: str | None) -> Paragraph:
    """The paragraph of a box, written by ``author``."""
    return Paragraph(entry_id(table, row, col), style, text).written_by(author)


def _data(steps: Sequence[tuple[str, str, Paragraph | None]]) -> tuple[tuple[str, str, dict | None], ...]:
    return tuple((r, c, None if p is None else p.to_data()) for r, c, p in steps)


def _table(model: ObjectModel, table_id: str) -> TableDef:
    try:
        return model.get_table(table_id)
    except ValueError:
        raise RequestError("command_error", msg("this document has no table {id!r}", id=table_id)) from None


def _refused(error: ValueError) -> RequestError:
    return RequestError("command_error", str(error))


def _missing(noun: str, given: str) -> RequestError:
    text = (
        msg("the table has no row {id!r}", id=given)
        if noun == "row"
        else msg("the table has no column {id!r}", id=given)
    )
    return RequestError("command_error", text)


def _position(order: Sequence[str], after: str | None, before: str | None, noun: str) -> str | None:
    """The id of the row or column a new one goes behind (``None``: first), from ``after`` / ``before`` (neither: the
    end)."""
    if after is not None and before is not None:
        raise RequestError("bad_request", msg("say after or before, not both"))
    for given in (after, before):
        if given is not None and given not in order:
            raise _missing(noun, given)
    if before is not None:
        at = order.index(before)
        return order[at - 1] if at else None
    return after if after is not None else (order[-1] if order else None)


def _count(count: int, noun: str, limit: int) -> int:
    if not 1 <= count <= limit:
        text = (
            msg("count is from 1 to {limit} rows", limit=limit)
            if noun == "rows"
            else msg("count is from 1 to {limit} columns", limit=limit)
        )
        raise RequestError("bad_request", text)
    return count


def _moved(order: Sequence[str], ids: Sequence[str], before: str | None, noun: str) -> tuple[str, ...]:
    """``order`` with ``ids`` (in the order they are named) taken out and put in front of ``before``, or at the end."""
    moving = list(dict.fromkeys(ids))
    for given in (*moving, *([before] if before is not None else [])):
        if given not in order:
            raise _missing(noun, given)
    if before in moving:
        text = (
            msg("a row cannot be moved in front of itself")
            if noun == "row"
            else msg("a column cannot be moved in front of itself")
        )
        raise RequestError("command_error", text)
    rest = [i for i in order if i not in moving]
    at = len(rest) if before is None else rest.index(before)
    return (*rest[:at], *moving, *rest[at:])


# ------------------------------------------------------------------------------------------------------ reading
def table_view(model: ObjectModel, table_id: str) -> dict:
    """One table as `tables` gives it: its plain data, the ids of the objects that show it and its derived totals."""
    definition = model.tables[table_id]
    language = getattr(model, "language", None)
    return {**definition.to_data(), "used_by": model.users_of_table(table_id), "totals": definition.totals(language)}


def _tables(model_of: Callable[[Context], ObjectModel]):
    def tables(ctx: Context) -> list[dict]:
        """The tables this document holds, each as `{format, id, columns, rows, entries, merges, header_rows, banded,
        look, placement, width, next_row, next_col}` (see `add_table`) plus `used_by` (the ids of the objects that show
        it) and `totals`, the words of its total row by column id: derived from the body rows with the language of the
        text and never stored, so it is always as the boxes say. `columns` are `{id, kind, total, width}`; `entries`
        are the boxes that have words or a style of their own, `[row, column, paragraph]` (a box that is not there is
        empty). A box's id, to type in it, is `<table>/<row>/<column>`. Rows and columns are named by id, never by
        place: the ids are what every other table method takes."""
        model = model_of(ctx)
        return [table_view(model, table_id) for table_id in sorted(model.tables)]

    return tables


# ------------------------------------------------------------------------------------------------------ a table comes
def _grid(cells: list | None, rows: int | None, cols: int | None) -> tuple[int, int, list[list[str]]]:
    """``(rows, cols, cells)`` of a request: what the words need unless the request says more."""
    if cells is None:
        if rows is None or cols is None:
            raise RequestError("bad_request", msg("give the table's rows and cols, or the words as cells"))
        return rows, cols, []
    if not all(isinstance(line, list) and all(isinstance(x, str) for x in line) for line in cells):
        raise RequestError("bad_request", msg("cells is a list of rows, each a list of words"))
    wide = max((len(line) for line in cells), default=0)
    rows, cols = rows if rows is not None else len(cells), cols if cols is not None else wide
    if len(cells) > rows or wide > cols:
        raise RequestError("bad_request", msg("the cells are more than the table's rows and cols"))
    return rows, cols, cells


def _add(model_of: Callable[[Context], ObjectModel], placement: Placement):
    def add_table(ctx: Context, *, rows, cols, cells, header_rows, look, w, base, **where):
        """Put a table where the person points. Say its size with `rows` and `cols` (at most 100 and 10), or just
        give the words as `cells`, a list of rows each a list of texts, and the table is as big as they are (more
        `rows` or `cols` leave the rest empty). The first `header_rows` rows (default 1) are the header: they repeat on
        every page, and a column is named by its last header box. `look` is one of the table looks the text has
        (`rules` if left out), `w` the nominal width in CSS pixels. The new table has the ids `r1`.. and `c1`..; a
        table is shown by an object that has a name of its own. Returns `{object, table, revision}`."""
        model = model_of(ctx)
        anchor = placement.anchor(model, None, **where)
        rows, cols, cells = _grid(cells, rows, cols)
        table_id = fresh_id("t", model.tables)
        options = {} if look is None else {"look": look}
        try:
            blank = TableDef.blank(table_id, rows, cols, header_rows=header_rows, **options)
            entries = [
                (f"r{r}", f"c{c}", _box(table_id, f"r{r}", f"c{c}", one_line(text), "", ctx.user))
                for r, line in enumerate(cells, 1)
                for c, text in enumerate(line, 1)
                if one_line(text)
            ]
            definition = blank.with_entries(entries)
            model.check_table(definition)
        except ValueError as error:
            raise _refused(error) from None
        object_id = fresh_id("o", model.objects)
        body = ObjectBody(
            object_id,
            "table",
            w or DEFAULT_WIDTH,
            ROW_HEIGHT * rows,
            TABLE_STYLE,
            ref=table_id,
            name=default_name(ctx, "table"),
        )
        command = Batch((DefineTable(definition.to_data()), AddObject(body, anchor)), name="Add table")
        return done(ctx, command, base, object=object_id, table=table_id)

    return add_table


def _remove(model_of: Callable[[Context], ObjectModel]):
    def remove_table(ctx: Context, *, id, base):  # noqa: A002 - the wire name
        """Take a table away with the objects that show it. Undo brings all of it back, words included."""
        model = model_of(ctx)
        _table(model, id)
        steps = [*(RemoveObject(object_id) for object_id in model.users_of_table(id)), ForgetTable(id)]
        return done(ctx, Batch(tuple(steps), name="Remove table"), base)

    return remove_table


# ------------------------------------------------------------------------------------------------------ boxes
def _set_entries(model_of: Callable[[Context], ObjectModel]):
    def set_entries(ctx: Context, *, table, changes, base):
        """Put words in boxes or take them out: `changes` is a list of `[row, column, text]` (ids as `tables` lists
        them); `text` null empties the box. A box keeps the style it has of its own. One step. For a few words in one
        box, `replace_words` with the box's id works as in a paragraph. `command_error` for a box that is not there or
        one a merge covers (its words are in the merge's top-left box)."""
        definition = _table(model_of(ctx), table)
        steps: list[tuple[str, str, Paragraph | None]] = []
        for change in changes:
            if not isinstance(change, list) or len(change) != 3 or not all(isinstance(x, str) for x in change[:2]):
                raise RequestError("bad_request", msg("each change is [row, column, text or null]"))
            row, col, text = change
            if text is not None and not isinstance(text, str):
                raise RequestError("bad_request", msg("each change is [row, column, text or null]"))
            held = definition.entry(row, col) if row in definition.rows and col in definition.column_ids() else None
            style = "" if held is None else held.style
            words = one_line(text or "")
            steps.append((row, col, _box(table, row, col, words, style, ctx.user) if words or style else None))
        _try(definition.with_entries, steps)
        return done(ctx, SetEntries(table, _data(steps)), base)

    return set_entries


# ------------------------------------------------------------------------------------------------------ rows
def _insert_rows(model_of: Callable[[Context], ObjectModel]):
    def insert_rows(ctx: Context, *, table, count, after, before, base):
        """Put `count` empty rows in the table (at most 100 rows in all): behind the row `after`, in front of the row
        `before`, or at the end if neither is given. A merge the new rows land inside grows by them. Returns
        `{rows, revision}`: the ids of the new rows."""
        definition = _table(model_of(ctx), table)
        _count(count, "rows", MAX_ROWS)
        behind = _position(definition.rows, after, before, "row")
        ids = [f"r{definition.next_row + n}" for n in range(1, count + 1)]
        specs = tuple(RowSpec(rid, behind if n == 0 else ids[n - 1]) for n, rid in enumerate(ids))
        _try(definition.insert_rows, specs)
        return done(ctx, InsertRows(table, specs), base, rows=ids)

    return insert_rows


def _delete_rows(model_of: Callable[[Context], ObjectModel]):
    def delete_rows(ctx: Context, *, table, ids, base):
        """Take rows out with the words in them (a table keeps at least one row). A merge loses the rows it had among
        them. Undo puts them back where they were, words and merges included."""
        definition = _table(model_of(ctx), table)
        _try(definition.delete_rows, ids)
        return done(ctx, DeleteRows(table, tuple(ids)), base)

    return delete_rows


def _move_rows(model_of: Callable[[Context], ObjectModel]):
    def move_rows(ctx: Context, *, table, ids, before, base):
        """Move rows, in the order they are named, in front of the row `before` (or to the end). The header stays at
        the top and a merge's rows stay together, or the request is refused."""
        definition = _table(model_of(ctx), table)
        order = _moved(definition.rows, ids, before, "row")
        _try(definition.row_order, order)
        return done(ctx, SetRowOrder(table, order), base)

    return move_rows


def _sort_rows(model_of: Callable[[Context], ObjectModel]):
    def sort_rows(ctx: Context, *, table, column, descending, base):
        """Sort the body rows by the column `column` (an id): numbers first, read in the language of the text, then
        words, empty boxes last. The header stays, rows keep their ids, equal rows keep their order, so sorting twice
        changes nothing. A table with merged rows is not sorted (split them first). One step; undo brings the old
        order back."""
        model = model_of(ctx)
        definition = _table(model, table)
        order = _try(definition.sort_order, column, descending, getattr(model, "language", None))
        return done(ctx, SetRowOrder(table, order, sorted_by=column), base)

    return sort_rows


# ------------------------------------------------------------------------------------------------------ columns
def _insert_columns(model_of: Callable[[Context], ObjectModel]):
    def insert_columns(ctx: Context, *, table, count, after, before, base):
        """Put `count` empty columns in the table (at most 10 in all), placed as `insert_rows` places rows. They hold
        words until `set_column` says they hold numbers. Returns `{columns, revision}`: the ids of the new columns."""
        definition = _table(model_of(ctx), table)
        _count(count, "columns", MAX_COLUMNS)
        behind = _position(definition.column_ids(), after, before, "column")
        ids = [f"c{definition.next_col + n}" for n in range(1, count + 1)]
        specs = tuple(ColumnSpec(Column(cid), behind if n == 0 else ids[n - 1]) for n, cid in enumerate(ids))
        _try(definition.insert_columns, specs)
        return done(ctx, InsertColumns(table, specs), base, columns=ids)

    return insert_columns


def _delete_columns(model_of: Callable[[Context], ObjectModel]):
    def delete_columns(ctx: Context, *, table, ids, base):
        """Take columns out with the words in them (a table keeps at least one column). Undo puts them back."""
        definition = _table(model_of(ctx), table)
        _try(definition.delete_columns, ids)
        return done(ctx, DeleteColumns(table, tuple(ids)), base)

    return delete_columns


def _move_columns(model_of: Callable[[Context], ObjectModel]):
    def move_columns(ctx: Context, *, table, ids, before, base):
        """Move columns, with their words, in front of the column `before` (or to the end)."""
        definition = _table(model_of(ctx), table)
        order = _moved(definition.column_ids(), ids, before, "column")
        _try(definition.column_order, order)
        return done(ctx, SetColumnOrder(table, order), base)

    return move_columns


def _set_column(model_of: Callable[[Context], ObjectModel]):
    def set_column(ctx: Context, *, table, column, changes, base):
        """Change what a column is: `changes` has any of `kind` (`text` or `number`: a number column is aligned and
        sorted and totalled as numbers), `total` (`sum`, `mean`, `count`, `min`, `max`, or null for none: the last row
        then shows it, derived) and `width` (hundredths of a percent of the table, or null for as wide as its words
        need). What `changes` leaves out stays."""
        definition = _table(model_of(ctx), table)
        unknown = sorted(set(changes) - set(COLUMN_SETTINGS))
        if unknown:
            raise RequestError("command_error", msg("a column has no setting {name!r}", name=unknown[0]))
        try:
            current = definition.column(column)
            changed = replace(current, **changes)
            changed.check()
            definition.with_column(changed)
        except ValueError as error:
            raise _refused(error) from None
        return done(ctx, SetColumn(table, changed), base)

    return set_column


def _set_options(model_of: Callable[[Context], ObjectModel]):
    def set_table_options(ctx: Context, *, table, options, base):
        """Change how a table is set: `options` has any of `header_rows` (how many top rows are the header), `banded`
        (every second body row shaded), `look` (one of the table looks the text has: `rules`, `grid` or `plain`, or one
        of its own), `placement` (`flow`: in the line of text, or `float`: it hangs from its paragraph and the text
        wraps) and `width` (hundredths of a percent of the line, or null for all of it)."""
        model = model_of(ctx)
        definition = _table(model, table)
        try:
            changed = definition.with_options(**options)
            model.check_table(changed)
        except (ValueError, TypeError) as error:
            raise _refused(ValueError(str(error))) from None
        return done(ctx, SetTableOptions(table, tuple(options.items())), base)

    return set_table_options


# ------------------------------------------------------------------------------------------------------ merging
def _merge_cells(model_of: Callable[[Context], ObjectModel]):
    def merge_cells(ctx: Context, *, table, row, col, rows, cols, base):
        """Make the rectangle that starts at the box where `row` and `col` cross, `rows` high and `cols` wide, one
        box. The words of the boxes it covers are joined, with a space, to those of the first. It may not meet another
        merge or leave the table. One step; undo gives the boxes and their words back. `split_cell` takes it apart."""
        definition = _table(model_of(ctx), table)
        if rows * cols < 2:
            raise RequestError("bad_request", msg("a merge is at least two boxes; split_cell undoes one"))
        if row not in definition.rows or col not in definition.column_ids():
            raise RequestError(
                "command_error",
                msg("the table has no box where row {row!r} and column {col!r} cross", row=row, col=col),
            )
        first, ids = definition.rows.index(row), definition.column_ids()
        start = ids.index(col)
        covered = [(r, c) for r in definition.rows[first : first + rows] for c in ids[start : start + cols]]
        covered = [(r, c) for r, c in covered if (r, c) != (row, col)]
        said = [definition.paragraph(row, col).text, *(definition.paragraph(r, c).text for r, c in covered)]
        joined = " ".join(words for words in said if words)
        origin = definition.entry(row, col)
        steps: list[tuple[str, str, Paragraph | None]] = [(r, c, None) for r, c in covered if definition.entry(r, c)]
        if joined != said[0]:
            steps.append((row, col, _box(table, row, col, joined, "" if origin is None else origin.style, ctx.user)))
        _try(lambda: definition.with_entries(steps).with_merge(row, col, rows, cols))
        commands = [*([SetEntries(table, _data(steps))] if steps else []), SetMerge(table, row, col, rows, cols)]
        return done(ctx, commands[0] if len(commands) == 1 else Batch(tuple(commands), name="Merge cells"), base)

    return merge_cells


def _split_cell(model_of: Callable[[Context], ObjectModel]):
    def split_cell(ctx: Context, *, table, row, col, base):
        """Give back the boxes of the merge that starts at the box where `row` and `col` cross; the words stay in
        the first. `command_error` if no merged box starts there."""
        definition = _table(model_of(ctx), table)
        if not any((m.row, m.col) == (row, col) for m in definition.merges):
            raise RequestError(
                "command_error", msg("no merged box starts at row {row!r}, column {col!r}", row=row, col=col)
            )
        return done(ctx, SetMerge(table, row, col, 1, 1), base)

    return split_cell


def _try(make, *args):
    """What ``make(*args)`` gives, or a ``command_error`` that says why the table cannot be that."""
    try:
        return make(*args)
    except ValueError as error:
        raise _refused(error) from None


def add_table_methods(
    table: MethodTable,
    *,
    model_of: Callable[[Context], ObjectModel],
    placement: Placement,
) -> None:
    """Register ``tables`` and the methods that change tables on ``table``. ``placement`` says where an app puts an
    object (the same one :func:`~claudia_server.object_methods.add_object_methods` takes); an app that has no
    tables simply does not call this."""
    table.method("tables")(_tables(model_of))
    table.method(
        "add_table",
        f"{placement.new} rows:int? cols:int? cells:list? header_rows:int=1 look:str? w:int? base:revision?",
        write=True,
    )(_add(model_of, placement))
    table.method("remove_table", "id:str base:revision?", write=True)(_remove(model_of))
    table.method("set_entries", "table:str changes:list base:revision?", write=True)(_set_entries(model_of))
    table.method("insert_rows", "table:str count:int=1 after:str? before:str? base:revision?", write=True)(
        _insert_rows(model_of)
    )
    table.method("delete_rows", "table:str ids:list base:revision?", write=True)(_delete_rows(model_of))
    table.method("move_rows", "table:str ids:list before:str? base:revision?", write=True)(_move_rows(model_of))
    table.method("sort_rows", "table:str column:str descending:bool=false base:revision?", write=True)(
        _sort_rows(model_of)
    )
    table.method("insert_columns", "table:str count:int=1 after:str? before:str? base:revision?", write=True)(
        _insert_columns(model_of)
    )
    table.method("delete_columns", "table:str ids:list base:revision?", write=True)(_delete_columns(model_of))
    table.method("move_columns", "table:str ids:list before:str? base:revision?", write=True)(_move_columns(model_of))
    table.method("set_column", "table:str column:str changes:dict base:revision?", write=True)(_set_column(model_of))
    table.method("set_table_options", "table:str options:dict base:revision?", write=True)(_set_options(model_of))
    table.method("merge_cells", "table:str row:str col:str rows:int=1 cols:int=1 base:revision?", write=True)(
        _merge_cells(model_of)
    )
    table.method("split_cell", "table:str row:str col:str base:revision?", write=True)(_split_cell(model_of))


__all__ = ["TABLE_METHODS", "add_table_methods", "one_line", "table_view"]
