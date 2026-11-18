"""The commands that change a table (D1201, D1210): what a person does with its rows, columns, boxes and merges.

Every command carries final values and returns its exact inverse, as any command does (``claudia_core.commands``).
They name rows and columns by id, never by position, so one author's undo is not shifted by what a colleague did
elsewhere in the table; a command whose rows or columns a colleague deleted is refused instead (:meth:`shifted_by`).
Typing into a box is not here: it is the ordinary :class:`~claudia_core.InsertText` on the box's paragraph id.

Each change tells the clients the whole table (:class:`TablesChanged`): a table is at most 100 rows by 10 columns, and
a structure change is rare next to typing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar

from .commands import Batch, Command, CommandRegistry, core_commands
from .objects import ObjectModel
from .paragraphs import Paragraph
from .tables import Column, ColumnSpec, Merge, RowSpec, TableDef, TableRegion, entry_id, parse_entry_id

if TYPE_CHECKING:
    from .context import Context
    from .model import DocumentModel
    from .region import Region


@dataclass(frozen=True)
class TablesChanged:
    """The document learned a table (``definition`` is it), forgot one (``definition`` is ``None``), or changed one."""

    table_id: str
    definition: TableDef | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "table",
            "id": self.table_id,
            "definition": None if self.definition is None else self.definition.to_data(),
        }


def _host(ctx: Context) -> ObjectModel:
    model = ctx.model
    if not isinstance(model, ObjectModel):
        raise TypeError(f"The {model.app} model holds no tables")
    return model


def _change(ctx: Context, table_id: str, new: TableDef) -> TableDef:
    """Put ``new`` in place of the table ``table_id``; returns the one it replaces and tells the clients."""
    old = _host(ctx).replace_table(new)
    ctx.emit(TablesChanged(table_id, new))
    return old


def _emptied(paragraph: Paragraph) -> Paragraph:
    """The paragraph with its words gone (redaction, D720): its id and its style stay."""
    return replace(paragraph.with_text("", ()), fields=())


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


class TableCommand(Command):
    """A command about one table: it names the table, and it is meaningless once the table is gone."""

    table: str

    def touched(self) -> tuple[frozenset[str] | None, frozenset[str] | None]:
        """The rows and the columns it changes (``None``: all of them)."""
        return None, None

    def regions(self, model: DocumentModel) -> tuple[Region, ...]:
        rows, cols = self.touched()
        return (TableRegion(self.table, rows, cols),)

    def needs(self) -> tuple[frozenset[str], frozenset[str]]:
        """The ids of the rows and the columns that have to be there for the command to mean anything."""
        return frozenset(), frozenset()

    def overwrites(self) -> tuple[frozenset[str] | None, frozenset[str] | None]:
        """The rows and columns whose words the command would lose or put back over what is there: a colleague's
        typing there since makes it refuse, as an undo never destroys a colleague's work (E1.4). ``None``: all."""
        return frozenset(), frozenset()

    def shifted_by(self, other: Command) -> Command | None:
        typed = parse_entry_id(getattr(other, "paragraph", "") or "")
        if typed is not None and typed[0] == self.table:
            rows, cols = self.overwrites()
            if (rows is None or typed[1] in rows) and (cols is None or typed[2] in cols):
                return None
            return self
        if getattr(other, "table", None) != self.table:
            return self
        if other.kind == "core.ForgetTable":
            return None
        if other.kind == "core.SetEntries" and self.kind == "core.SetEntries":
            mine = {(r, c) for r, c, _ in self.changes}  # type: ignore[attr-defined]
            if mine & {(r, c) for r, c, _ in other.changes}:  # type: ignore[attr-defined]
                return None
        rows, cols = self.needs()
        if other.kind == "core.DeleteRows" and rows & frozenset(other.ids):  # type: ignore[attr-defined]
            return None
        if other.kind == "core.DeleteColumns" and cols & frozenset(other.ids):  # type: ignore[attr-defined]
            return None
        return self


# --------------------------------------------------------------------------- the table itself
@core_commands.register
@dataclass(frozen=True)
class DefineTable(Command):
    """Take a table's definition into the document (the inverse of :class:`ForgetTable`)."""

    kind: ClassVar[str] = "core.DefineTable"
    definition: dict

    @property
    def label(self) -> str:
        return "Define table"

    @property
    def summary(self) -> str:
        return "The document takes a table"

    def apply(self, ctx: Context) -> Command:
        definition = TableDef.from_data(self.definition)
        _host(ctx).define_table(definition)
        ctx.emit(TablesChanged(definition.id, definition))
        return ForgetTable(definition.id)

    def to_data(self) -> dict:
        return {"definition": self.definition}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> DefineTable:
        return cls(data["definition"])

    def shifted_by(self, other: Command) -> Command | None:
        return (
            None if isinstance(other, DefineTable) and other.definition.get("id") == self.definition.get("id") else self
        )

    def redacted(self) -> Command:
        return DefineTable(TableDef.from_data(self.definition).blanked().to_data())


@core_commands.register
@dataclass(frozen=True)
class ForgetTable(TableCommand):
    """Let go of a table that no object shows (the inverse of :class:`DefineTable`)."""

    kind: ClassVar[str] = "core.ForgetTable"
    table: str

    @property
    def label(self) -> str:
        return "Forget table"

    @property
    def summary(self) -> str:
        return f"The document lets go of the table {self.table}"

    def apply(self, ctx: Context) -> Command:
        definition = _host(ctx).forget_table(self.table)
        ctx.emit(TablesChanged(self.table, None))
        return DefineTable(definition.to_data())

    def to_data(self) -> dict:
        return {"table": self.table}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> ForgetTable:
        return cls(data["table"])

    def redacted(self) -> Command:
        return self


# --------------------------------------------------------------------------- the boxes
@core_commands.register
@dataclass(frozen=True)
class SetEntries(TableCommand):
    """Put words in boxes, or take them away (``None``): a paste, a fill, a clear. Typing is :class:`InsertText`."""

    kind: ClassVar[str] = "core.SetEntries"
    table: str
    changes: tuple[tuple[str, str, dict | None], ...]

    @property
    def label(self) -> str:
        return "Set boxes"

    @property
    def summary(self) -> str:
        return f"Changed {_plural(len(self.changes), 'box', 'boxes')} of a table"

    def apply(self, ctx: Context) -> Command:
        old = _host(ctx).get_table(self.table)
        changes = [(r, c, None if p is None else Paragraph.from_data(p)) for r, c, p in self.changes]
        new = old.with_entries(changes)
        before = tuple((r, c, None if (e := old.entry(r, c)) is None else e.to_data()) for r, c, _ in self.changes)
        _change(ctx, self.table, new)
        return SetEntries(self.table, before)

    def to_data(self) -> dict:
        return {"table": self.table, "changes": [[r, c, p] for r, c, p in self.changes]}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetEntries:
        return cls(data["table"], tuple((r, c, p) for r, c, p in data["changes"]))

    def touched(self):
        return frozenset(r for r, _, _ in self.changes), frozenset(c for _, c, _ in self.changes)

    def needs(self):
        return self.touched()

    def overwrites(self):
        return self.touched()

    def redacted(self) -> Command:
        blank = tuple(
            (r, c, None if p is None else _emptied(Paragraph.from_data(p)).to_data()) for r, c, p in self.changes
        )
        return SetEntries(self.table, blank)


# --------------------------------------------------------------------------- rows
@core_commands.register
@dataclass(frozen=True)
class InsertRows(TableCommand):
    """Put rows in, each behind the row it names. ``merges``, when it is given, are the merges afterwards (an undo
    hands back what a delete took away)."""

    kind: ClassVar[str] = "core.InsertRows"
    table: str
    rows: tuple[RowSpec, ...]
    merges: tuple[Merge, ...] | None = None

    @property
    def label(self) -> str:
        return "Insert rows"

    @property
    def summary(self) -> str:
        return f"Inserted {_plural(len(self.rows), 'row', 'rows')} in a table"

    def apply(self, ctx: Context) -> Command:
        old = _host(ctx).get_table(self.table)
        _change(ctx, self.table, old.insert_rows(self.rows, self.merges))
        return DeleteRows(self.table, tuple(r.id for r in self.rows), old.merges)

    def to_data(self) -> dict:
        data: dict = {"table": self.table, "rows": [r.to_data() for r in self.rows]}
        if self.merges is not None:
            data["merges"] = [m.to_data() for m in self.merges]
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> InsertRows:
        merges = data.get("merges")
        return cls(
            data["table"],
            tuple(RowSpec.from_data(r) for r in data["rows"]),
            None if merges is None else tuple(Merge.from_data(m) for m in merges),
        )

    def touched(self):
        return frozenset(r.after for r in self.rows if r.after), None

    def needs(self):
        return frozenset(
            r.after for r in self.rows if r.after and r.after not in {s.id for s in self.rows}
        ), frozenset()

    def redacted(self) -> Command:
        rows = tuple(replace(r, entries=tuple((c, _emptied(p)) for c, p in r.entries)) for r in self.rows)
        return replace(self, rows=rows)


@core_commands.register
@dataclass(frozen=True)
class DeleteRows(TableCommand):
    """Take rows out, with the words in them. ``merges``, when it is given, are the merges afterwards."""

    kind: ClassVar[str] = "core.DeleteRows"
    table: str
    ids: tuple[str, ...]
    merges: tuple[Merge, ...] | None = None

    @property
    def label(self) -> str:
        return "Delete rows"

    @property
    def summary(self) -> str:
        return f"Deleted {_plural(len(self.ids), 'row', 'rows')} of a table"

    def apply(self, ctx: Context) -> Command:
        old = _host(ctx).get_table(self.table)
        new = old.delete_rows(self.ids)
        if self.merges is not None:
            new = replace(new, merges=self.merges)
            new.check()
        gone = set(self.ids)
        specs = []
        for index, row in enumerate(old.rows):
            if row in gone:
                entries = tuple((c, old.entry(row, c)) for c in old.column_ids() if old.entry(row, c) is not None)
                specs.append(RowSpec(row, old.rows[index - 1] if index else None, entries))  # type: ignore[arg-type]
        _change(ctx, self.table, new)
        back: Command = InsertRows(self.table, tuple(specs), old.merges)
        if new.header_rows != old.header_rows:
            back = Batch((back, SetTableOptions(self.table, (("header_rows", old.header_rows),))))
        return back

    def to_data(self) -> dict:
        data: dict = {"table": self.table, "ids": list(self.ids)}
        if self.merges is not None:
            data["merges"] = [m.to_data() for m in self.merges]
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> DeleteRows:
        merges = data.get("merges")
        return cls(
            data["table"], tuple(data["ids"]), None if merges is None else tuple(Merge.from_data(m) for m in merges)
        )

    def touched(self):
        return frozenset(self.ids), None

    def needs(self):
        return frozenset(self.ids), frozenset()

    def overwrites(self):
        return frozenset(self.ids), None

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class SetRowOrder(TableCommand):
    """Put the rows in this order: a move, or a sort (D1204). It has to hold exactly the rows there are."""

    kind: ClassVar[str] = "core.SetRowOrder"
    table: str
    order: tuple[str, ...]
    sorted_by: str | None = None

    @property
    def label(self) -> str:
        return "Sort rows" if self.sorted_by else "Move rows"

    @property
    def summary(self) -> str:
        return "Sorted the rows of a table" if self.sorted_by else "Moved rows of a table"

    def apply(self, ctx: Context) -> Command:
        old = _host(ctx).get_table(self.table)
        _change(ctx, self.table, old.row_order(self.order))
        return SetRowOrder(self.table, old.rows, self.sorted_by)

    def to_data(self) -> dict:
        data: dict = {"table": self.table, "order": list(self.order)}
        if self.sorted_by:
            data["sorted_by"] = self.sorted_by
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetRowOrder:
        return cls(data["table"], tuple(data["order"]), data.get("sorted_by"))

    def touched(self):
        return None, None

    def shifted_by(self, other: Command) -> Command | None:
        # an order names every row, so it means nothing once a colleague added or took away a row or moved them
        if getattr(other, "table", None) == self.table and other.kind in (
            "core.InsertRows",
            "core.DeleteRows",
            "core.SetRowOrder",
            "core.ForgetTable",
        ):
            return None
        return self

    def redacted(self) -> Command:
        return self


# --------------------------------------------------------------------------- columns
@core_commands.register
@dataclass(frozen=True)
class InsertColumns(TableCommand):
    """Put columns in, each behind the column it names; see :class:`InsertRows`."""

    kind: ClassVar[str] = "core.InsertColumns"
    table: str
    columns: tuple[ColumnSpec, ...]
    merges: tuple[Merge, ...] | None = None

    @property
    def label(self) -> str:
        return "Insert columns"

    @property
    def summary(self) -> str:
        return f"Inserted {_plural(len(self.columns), 'column', 'columns')} in a table"

    def apply(self, ctx: Context) -> Command:
        old = _host(ctx).get_table(self.table)
        _change(ctx, self.table, old.insert_columns(self.columns, self.merges))
        return DeleteColumns(self.table, tuple(c.column.id for c in self.columns), old.merges)

    def to_data(self) -> dict:
        data: dict = {"table": self.table, "columns": [c.to_data() for c in self.columns]}
        if self.merges is not None:
            data["merges"] = [m.to_data() for m in self.merges]
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> InsertColumns:
        merges = data.get("merges")
        return cls(
            data["table"],
            tuple(ColumnSpec.from_data(c) for c in data["columns"]),
            None if merges is None else tuple(Merge.from_data(m) for m in merges),
        )

    def touched(self):
        return None, frozenset(c.after for c in self.columns if c.after)

    def needs(self):
        own = {c.column.id for c in self.columns}
        return frozenset(), frozenset(c.after for c in self.columns if c.after and c.after not in own)

    def redacted(self) -> Command:
        cols = tuple(replace(c, entries=tuple((r, _emptied(p)) for r, p in c.entries)) for c in self.columns)
        return replace(self, columns=cols)


@core_commands.register
@dataclass(frozen=True)
class DeleteColumns(TableCommand):
    """Take columns out, with the words in them."""

    kind: ClassVar[str] = "core.DeleteColumns"
    table: str
    ids: tuple[str, ...]
    merges: tuple[Merge, ...] | None = None

    @property
    def label(self) -> str:
        return "Delete columns"

    @property
    def summary(self) -> str:
        return f"Deleted {_plural(len(self.ids), 'column', 'columns')} of a table"

    def apply(self, ctx: Context) -> Command:
        old = _host(ctx).get_table(self.table)
        new = old.delete_columns(self.ids)
        if self.merges is not None:
            new = replace(new, merges=self.merges)
            new.check()
        gone = set(self.ids)
        specs = []
        ids = old.column_ids()
        for index, column in enumerate(old.columns):
            if column.id in gone:
                entries = tuple((r, old.entry(r, column.id)) for r in old.rows if old.entry(r, column.id) is not None)
                specs.append(ColumnSpec(column, ids[index - 1] if index else None, entries))  # type: ignore[arg-type]
        _change(ctx, self.table, new)
        return InsertColumns(self.table, tuple(specs), old.merges)

    def to_data(self) -> dict:
        data: dict = {"table": self.table, "ids": list(self.ids)}
        if self.merges is not None:
            data["merges"] = [m.to_data() for m in self.merges]
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> DeleteColumns:
        merges = data.get("merges")
        return cls(
            data["table"], tuple(data["ids"]), None if merges is None else tuple(Merge.from_data(m) for m in merges)
        )

    def touched(self):
        return None, frozenset(self.ids)

    def needs(self):
        return frozenset(), frozenset(self.ids)

    def overwrites(self):
        return None, frozenset(self.ids)

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class SetColumnOrder(TableCommand):
    """Put the columns in this order; it has to hold exactly the columns there are."""

    kind: ClassVar[str] = "core.SetColumnOrder"
    table: str
    order: tuple[str, ...]

    @property
    def label(self) -> str:
        return "Move columns"

    @property
    def summary(self) -> str:
        return "Moved columns of a table"

    def apply(self, ctx: Context) -> Command:
        old = _host(ctx).get_table(self.table)
        _change(ctx, self.table, old.column_order(self.order))
        return SetColumnOrder(self.table, old.column_ids())

    def to_data(self) -> dict:
        return {"table": self.table, "order": list(self.order)}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetColumnOrder:
        return cls(data["table"], tuple(data["order"]))

    def touched(self):
        return None, None

    def shifted_by(self, other: Command) -> Command | None:
        if getattr(other, "table", None) == self.table and other.kind in (
            "core.InsertColumns",
            "core.DeleteColumns",
            "core.SetColumnOrder",
            "core.ForgetTable",
        ):
            return None
        return self

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class SetColumn(TableCommand):
    """Give a column other settings: whether it holds numbers, its total and its width."""

    kind: ClassVar[str] = "core.SetColumn"
    table: str
    column: Column

    @property
    def label(self) -> str:
        return "Set column"

    @property
    def summary(self) -> str:
        return "Changed the settings of a column of a table"

    def apply(self, ctx: Context) -> Command:
        old = _host(ctx).get_table(self.table)
        before = old.column(self.column.id)
        _change(ctx, self.table, old.with_column(self.column))
        return SetColumn(self.table, before)

    def to_data(self) -> dict:
        return {"table": self.table, "column": self.column.to_data()}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetColumn:
        return cls(data["table"], Column.from_data(data["column"]))

    def touched(self):
        return None, frozenset({self.column.id})

    def needs(self):
        return frozenset(), frozenset({self.column.id})

    def redacted(self) -> Command:
        return self


# --------------------------------------------------------------------------- options and merges
@core_commands.register
@dataclass(frozen=True)
class SetTableOptions(TableCommand):
    """Change the options of a table: ``header_rows``, ``banded``, ``look``, ``placement``, ``width``."""

    kind: ClassVar[str] = "core.SetTableOptions"
    table: str
    options: tuple[tuple[str, object], ...]

    @property
    def label(self) -> str:
        return "Table options"

    @property
    def summary(self) -> str:
        return "Changed the options of a table"

    def apply(self, ctx: Context) -> Command:
        old = _host(ctx).get_table(self.table)
        changes = dict(self.options)
        new = old.with_options(**changes)
        _change(ctx, self.table, new)
        return SetTableOptions(self.table, tuple((name, getattr(old, name)) for name, _ in self.options))

    def to_data(self) -> dict:
        return {"table": self.table, "options": dict(self.options)}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetTableOptions:
        return cls(data["table"], tuple(data["options"].items()))

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class SetMerge(TableCommand):
    """Merge the rectangle that starts at a box, ``rows`` by ``cols`` boxes; 1 by 1 splits a merge that starts there."""

    kind: ClassVar[str] = "core.SetMerge"
    table: str
    row: str
    col: str
    rows: int = 1
    cols: int = 1

    @property
    def label(self) -> str:
        return "Split cell" if (self.rows, self.cols) == (1, 1) else "Merge cells"

    @property
    def summary(self) -> str:
        return "Split a merged box of a table" if (self.rows, self.cols) == (1, 1) else "Merged boxes of a table"

    def apply(self, ctx: Context) -> Command:
        old = _host(ctx).get_table(self.table)
        before = next((m for m in old.merges if (m.row, m.col) == (self.row, self.col)), None)
        _change(ctx, self.table, old.with_merge(self.row, self.col, self.rows, self.cols))
        return SetMerge(self.table, self.row, self.col, *((before.rows, before.cols) if before else (1, 1)))

    def to_data(self) -> dict:
        return {"table": self.table, "row": self.row, "col": self.col, "rows": self.rows, "cols": self.cols}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetMerge:
        return cls(data["table"], data["row"], data["col"], data["rows"], data["cols"])

    def touched(self):
        return frozenset({self.row}), frozenset({self.col})

    def needs(self):
        return frozenset({self.row}), frozenset({self.col})

    def shifted_by(self, other: Command) -> Command | None:
        shifted = super().shifted_by(other)
        if (
            shifted is not None
            and getattr(other, "table", None) == self.table
            and other.kind
            in (
                "core.InsertRows",
                "core.InsertColumns",
                "core.SetRowOrder",
                "core.SetColumnOrder",
            )
        ):
            return None  # the rectangle it names is somewhere else now
        return shifted

    def redacted(self) -> Command:
        return self


def entry_paragraph(table: str, row: str, col: str, text: str, style: str = "", author: str | None = None) -> dict:
    """The plain data of a box's paragraph: what a command that sets boxes carries."""
    return Paragraph(entry_id(table, row, col), style, text).written_by(author).to_data()
