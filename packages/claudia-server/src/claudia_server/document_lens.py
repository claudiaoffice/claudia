"""The AI's lens on a text (E7.10, D680): paragraphs by id and words by quoting them, and every change reported as a
re-read of the paragraphs it touched.

A model cannot count characters, so it is never asked to: it names a paragraph by its id (``b3``) and the words in it
by quoting them, through the methods of :mod:`claudia_server.composes_words`. It starts with how that works, the
paragraph styles it may give, the headings, the first paragraphs and the one the asker's cursor is in. Everything that
comes out of the text is somebody's writing, so it is fenced as data (``lens.fence``).

In *act* it changes the text (``replace_words``, ``add_paragraphs``, ``set_style``); in *suggest* it proposes
(``suggest_words``), which is composes' suggest mode as built (D262). Not here yet: what the asker has selected (the
client's, a wire change; E7.5), and how the text falls onto pages.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from claudia_composes import TextModel, TextRange
from claudia_composes.events import (
    ItemChanged,
    ParagraphsJoined,
    ParagraphSplit,
    StyleChanged,
    SuggestionsChanged,
    TextChanged,
)
from claudia_core import Document, TableDef, TablesChanged, parse_entry_id

from .composes_words import paragraph_view
from .lens import HELP_METHODS, fence, look_first, shorten, show_help
from .lens import count as _count
from .tables import table_view

PREVIEW_PARAGRAPHS = 12  # paragraphs from the start shown at the beginning
AROUND_ASKER = 2  # paragraphs before and after the asker's shown with it
MAX_OUTLINE = 30  # headings named at the start
MAX_STYLES = 30  # paragraph styles named at the start
MAX_TEXT = 300  # characters of one paragraph shown at the start and in a report
MAX_READ_TEXT = 2000  # characters of one paragraph shown when the model asked to read it
MAX_REPORTED = 25  # paragraphs of one change report shown
MAX_PURPOSE = 60  # characters of a style's purpose shown
MAX_SUGGESTIONS = 30  # open suggestions listed
MAX_TABLES = 10  # tables named at the start
MAX_TABLE_ROWS = 40  # rows of one table shown
MAX_BOX = 60  # characters of one box shown
MAX_REPORTED_TABLES = 3  # tables of one change report shown

ORIENTATION = (
    "The text is a list of paragraphs. Each has an id (b1, b2, ...) and a paragraph style. Name a paragraph by its id "
    "and words in it by quoting them exactly as they are written (find); an empty find means the paragraph's whole "
    "text. Never count characters. A line break in new text starts a new paragraph. Read paragraphs before you change "
    "them.{example}"
)
START_IS_PART = " The start of the text below is only a part of it."
TABLES_HELP = (
    "A table is made of boxes named by the ids of their row and column (r2, c3), never by place. Read tables with "
    "tables; change boxes with set_entries, or some words in one box with replace_words and the box's id "
    "(table/row/column)."
)
ACT_EXAMPLE = (
    ' A request looks like {"method": "replace_words", "params": {"paragraph": "b3", "find": "in order to", '
    '"text": "to"}}.'
)
SUGGEST_EXAMPLE = (
    ' You may only propose changes, which people accept or reject. A request looks like {"method": "suggest_words", '
    '"params": {"paragraph": "b3", "find": "in order to", "replacement": "to", "reason": "shorter"}}.'
)  # neither when the asker's mode or role lets the AI change nothing: it would only invite a refused request


def _flat(text: str, limit: int) -> str:
    """A paragraph's text on one line, cut to ``limit``."""
    return shorten(" ".join(text.split()), limit)


def describe_paragraph(view: dict, limit: int = MAX_TEXT) -> str:
    """One paragraph for the model: ``b3 (body): "The words."``, a list item with its marker
    (``b4 (list-item, 2.): "..."``), a named one with its name."""
    style = view["style"]
    if view.get("label"):
        style += f", {view['label']}"
    if view.get("name"):
        style += f", named {_flat(view['name'], 40)!r}"
    text = view["text"]
    shown = f'"{_flat(text, limit)}"' if text.strip() else "(empty)"
    return f"{view['id']} ({style}): {shown}"


def describe_table(data: dict, name: str = "") -> str:
    """One table for the model, boxes by the ids of their row and column: a header line of the column ids (a number
    column with its total), a line per row (``r2: Roof | 8``), the totals as the text reads them and the merges. A
    long table is cut at its 40th row and a long box at 60 characters; the whole is in ``tables``."""
    table = TableDef.from_data(data)
    totals = data.get("totals") or table.totals()
    columns = []
    for column in table.columns:
        kinds = [column.kind] if column.kind != "text" else []
        if column.total:
            kinds.append(f"total {column.total}")
        columns.append(column.id + (f" ({', '.join(kinds)})" if kinds else ""))
    facts = [
        f"{_count(len(table.rows), 'row', 'rows')}, {_count(len(table.columns), 'column', 'columns')}",
        f"header: {_count(table.header_rows, 'row', 'rows')}",
        f"look {table.look}",
    ]
    lines = [f"Table {table.id}" + (f' "{name}"' if name else "") + f" ({'; '.join(facts)})", " | ".join(columns)]
    for row in table.rows[:MAX_TABLE_ROWS]:
        boxes = [_flat(table.paragraph(row, col).text, MAX_BOX) for col in table.column_ids()]
        lines.append(f"{row}: " + " | ".join(boxes))
    if len(table.rows) > MAX_TABLE_ROWS:
        lines.append(f"... and {len(table.rows) - MAX_TABLE_ROWS} more rows (the rest is in tables)")
    lines += [f"total: {col} = {words}" for col, words in totals.items()]
    lines += [
        f"merged: {m.row}/{m.col} spans {_count(m.rows, 'row', 'rows')}, {_count(m.cols, 'column', 'columns')}"
        for m in table.merges
    ]
    return "\n".join(lines)


def describe_suggestion(item: dict) -> str:
    """One open suggestion: ``s2 by ai on b3: "in order to" -> "to" (shorter)``, a remark without the arrow."""
    original = '"' + _flat(item["original"], 80) + '"'
    if item.get("replacement") is None:
        change = f"remark on {original}"
    else:
        change = f'{original} -> "{_flat(item["replacement"], 80)}"'
    line = f"{item['id']} by {item.get('author') or 'somebody'} on {item['paragraph']}: {change}"
    if item.get("reason"):
        line += f" ({_flat(item['reason'], 80)})"
    return line + (" [outdated]" if item.get("outdated") else "")


class DocumentLens:
    """The lens for composes."""

    look_methods: tuple[str, ...] = ("read_paragraphs", "outline", "styles", "suggestions", "tables", *HELP_METHODS)

    # -- where the model starts
    def orient(
        self,
        document: Document,
        *,
        can_write: bool,
        asker: str | None = None,
        writes: frozenset[str] | None = None,
    ) -> str:
        """How paragraphs and words are named, the paragraph styles, the headings, the first paragraphs and the
        asker's own, and how many suggestions are open."""
        model = document.model
        assert isinstance(model, TextModel)
        text = ORIENTATION.format(example=START_IS_PART + self._example(can_write, writes))
        labels = model.labels()
        paragraphs = model.paragraphs
        text += f"\nThe text has {len(paragraphs)} paragraph{'s' if len(paragraphs) != 1 else ''}."
        text += self._tables(model)
        text += "\nParagraph styles (id: name, what it is for):\n" + self._styles(model)
        headings = [at for at, paragraph in enumerate(paragraphs) if model.paragraph_kind(paragraph) == "heading"]
        if headings:
            shown = [describe_paragraph(paragraph_view(model, at, labels), 80) for at in headings[:MAX_OUTLINE]]
            if len(headings) > MAX_OUTLINE:
                shown.append(f"... and {len(headings) - MAX_OUTLINE} more headings (ask for the outline)")
            text += "\nHeadings:\n" + fence("\n".join(shown))
        first = [
            describe_paragraph(paragraph_view(model, at, labels))
            for at in range(min(PREVIEW_PARAGRAPHS, len(paragraphs)))
        ]
        if len(paragraphs) > PREVIEW_PARAGRAPHS:
            first.append(f"... {len(paragraphs) - PREVIEW_PARAGRAPHS} more paragraphs (read them with paragraphs)")
        text += "\nThe start of the text:\n" + fence("\n".join(first))
        here = self._asker_at(document, model, asker)
        if here is not None:
            text += f"\n{asker}'s cursor is in paragraph {paragraphs[here].id}"
            if here >= PREVIEW_PARAGRAPHS:
                around = range(max(here - AROUND_ASKER, 0), min(here + AROUND_ASKER + 1, len(paragraphs)))
                text += ", here with the paragraphs around it:\n" + fence(
                    "\n".join(describe_paragraph(paragraph_view(model, at, labels)) for at in around)
                )
            else:
                text += " (shown above)."
        return text + self._open_suggestions(model)

    def outline(
        self,
        document: Document,
        *,
        can_write: bool,
        asker: str | None = None,
        writes: frozenset[str] | None = None,
    ) -> str:
        """How paragraphs and words are named, how many paragraphs, headings, tables and open suggestions there are,
        and the id (not the words) of the paragraph the asker is in; nothing a person wrote (D1568)."""
        model = document.model
        assert isinstance(model, TextModel)
        text = ORIENTATION.format(example=self._example(can_write, writes))
        paragraphs = model.paragraphs
        headings = sum(1 for p in paragraphs if model.paragraph_kind(p) == "heading")
        text += f"\nThe text has {_count(len(paragraphs), 'paragraph', 'paragraphs')}"
        text += f", {_count(headings, 'heading', 'headings')}, {_count(len(model.tables), 'table', 'tables')}."
        here = self._asker_at(document, model, asker)
        if here is not None:
            text += f"\nThe asker's cursor is in paragraph {paragraphs[here].id}."
        return f"{text}{self._open_suggestions(model)}\n{look_first('outline, styles, tables or read_paragraphs')}"

    @staticmethod
    def _open_suggestions(model: TextModel) -> str:
        open_now = len(model.visible_suggestions())
        if not open_now:
            return ""
        return f"\n{open_now} suggestion{'s are' if open_now != 1 else ' is'} open (ask for the suggestions)."

    @staticmethod
    def _tables(model: TextModel) -> str:
        """The tables of the text, one line each (id, name, size, header, where it hangs), and how boxes are named;
        nothing for a text without a table."""
        if not model.tables:
            return ""
        lines = []
        for table_id, definition in sorted(model.tables.items())[:MAX_TABLES]:
            users = model.tables.users(table_id)
            shown = model.get_object(users[0]) if users else None
            name = f' "{_flat(shown.body.name, 40)}"' if shown is not None and shown.body.name else ""
            where = f", hangs from {shown.anchor.paragraph}" if shown is not None else ""
            header = " | ".join(
                _flat(definition.paragraph(definition.rows[definition.header_rows - 1], c).text, 20)
                for c in definition.column_ids()
            )
            size = (
                f"{_count(len(definition.rows), 'row', 'rows')}, {_count(len(definition.columns), 'column', 'columns')}"
            )
            lines.append(f"{table_id}{name}: {size}{where}; " + (f"header {header}" if definition.header_rows else ""))
        if len(model.tables) > MAX_TABLES:
            lines.append(f"... and {len(model.tables) - MAX_TABLES} more tables (ask for the tables)")
        count = _count(len(model.tables), "table", "tables")
        return f"\nThe text has {count}. {TABLES_HELP}\n" + fence("\n".join(lines))

    @staticmethod
    def _example(can_write: bool, writes: frozenset[str] | None) -> str:
        if not can_write:
            return ""
        if writes is None or "replace_words" in writes:
            return ACT_EXAMPLE
        return SUGGEST_EXAMPLE if "suggest_words" in writes else ""

    @staticmethod
    def _styles(model: TextModel) -> str:
        lines = []
        for style in model.styles:
            try:
                model.check_style(style.id)
            except ValueError:
                continue  # not one a paragraph can have
            purpose = _flat(style.purpose or "", MAX_PURPOSE)
            lines.append(f"{style.id}: {_flat(style.name, 40)}" + (f", {purpose}" if purpose else ""))
        if len(lines) > MAX_STYLES:
            lines = [*lines[:MAX_STYLES], f"... and {len(lines) - MAX_STYLES} more (ask for the styles)"]
        return fence("\n".join(lines))

    @staticmethod
    def _asker_at(document: Document, model: TextModel, asker: str | None) -> int | None:
        """The index of the paragraph the asker's cursor is in, if she shows one."""
        hold = document.presence.of(asker) if asker else None
        for region in hold.regions if hold else ():
            if isinstance(region, TextRange):
                try:
                    return model.index_of(region.paragraph)
                except KeyError:
                    continue
        return None

    # -- what the read requests show
    def show(self, method: str, params: dict, result: Any) -> str:
        """The answer of a read request, fenced as data (help is not data, it is the product's own text)."""
        if method in HELP_METHODS:
            return show_help(method, result)
        if method == "read_paragraphs":
            lines = [describe_paragraph(view, MAX_READ_TEXT) for view in result["paragraphs"]]
            if not lines:
                lines.append("No paragraph" + (" contains that." if params.get("containing") else " here."))
            if result.get("more"):
                lines.append(f"... more from {result['more']} (ask with first={result['more']})")
            return fence(f"{result['total']} paragraphs in all.\n" + "\n".join(lines))
        if method == "outline":
            lines = [describe_paragraph(view, 120) for view in result["headings"]] or ["There are no headings."]
            return fence("\n".join(lines))
        if method == "suggestions":
            items = list(result)
            lines = [describe_suggestion(item) for item in items[:MAX_SUGGESTIONS]] or ["No suggestion is open."]
            if len(items) > MAX_SUGGESTIONS:
                lines.append(f"... and {len(items) - MAX_SUGGESTIONS} more")
            return fence("\n".join(lines))
        if method == "styles":
            return fence(self._style_list(result))
        if method == "tables":
            return fence("\n\n".join(describe_table(item) for item in result) or "The text has no table.")
        return fence(json.dumps(result, separators=(",", ":"), ensure_ascii=False))

    @staticmethod
    def _style_list(result: Any) -> str:
        styles = result.get("styles", result) if isinstance(result, dict) else result
        lines = []
        for style in styles:
            purpose = _flat(style.get("purpose") or "", MAX_PURPOSE)
            lines.append(
                f"{style['id']}: {style.get('name', '')} ({style.get('kind', 'paragraph')}) {purpose}".rstrip()
            )
        return "Styles (id: name (kind) what it is for); a paragraph takes a paragraph style:\n" + "\n".join(lines)

    # -- what a change did
    def recorder(self, document: Document) -> TextRecorder:
        """Hold round one write request."""
        return TextRecorder(document)


class TextRecorder:
    """Listens while one request runs, then re-reads the paragraphs it touched and names the suggestions it made."""

    def __init__(self, document: Document):
        self._document = document
        self._touched: list[str] = []
        self._joined: list[str] = []
        self._suggestions: dict[str, dict] = {}
        self._tables: list[str] = []
        self._stop: Callable[[], None] | None = None

    def __enter__(self) -> TextRecorder:
        self._stop = self._document.subscribe(self._hear)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._stop is not None:
            self._stop()
            self._stop = None

    def _touch(self, *paragraphs: str) -> None:
        self._touched += [paragraph for paragraph in paragraphs if paragraph not in self._touched]

    def _table_touched(self, table_id: str) -> None:
        if table_id not in self._tables:
            self._tables.append(table_id)

    def _hear(self, event: object) -> None:
        if isinstance(event, TablesChanged):
            self._table_touched(event.table_id)
        elif isinstance(event, (TextChanged, StyleChanged, ItemChanged)) and (box := parse_entry_id(event.paragraph)):
            self._table_touched(box[0])  # the words of a box, not a paragraph of the text
        elif isinstance(event, (TextChanged, StyleChanged, ItemChanged)):
            self._touch(event.paragraph)
        elif isinstance(event, ParagraphSplit):
            self._touch(event.paragraph, event.new_id)
        elif isinstance(event, ParagraphsJoined):
            self._touch(event.into)
            self._joined.append(event.paragraph)
        elif isinstance(event, SuggestionsChanged):
            for item in event.items:
                self._suggestions[item["id"]] = item

    def report(self) -> str:
        """The touched paragraphs as they are now, in the order of the text, and the suggestions made; fenced."""
        model = self._document.model
        assert isinstance(model, TextModel)
        labels = model.labels()
        where = {
            paragraph: model.index_of(paragraph)
            for paragraph in self._touched
            if paragraph in {b.id for b in model.paragraphs}
        }
        order = sorted(where, key=where.__getitem__)
        lines = [
            describe_paragraph(paragraph_view(model, where[paragraph], labels)) for paragraph in order[:MAX_REPORTED]
        ]
        if len(order) > MAX_REPORTED:
            lines.append(f"... and {len(order) - MAX_REPORTED} more paragraphs changed.")
        gone = [paragraph for paragraph in self._joined if paragraph not in where]
        if gone:
            lines.append("Joined into the paragraph before them, so gone: " + ", ".join(gone))
        lines += self._table_report(model)
        made = [item for item in self._suggestions.values() if item.get("state", "open") == "open"]
        if made:
            lines.append("Suggestions now open:")
            lines += [describe_suggestion(model.suggestion_data(model.suggestion(item["id"]))) for item in made]
        return fence("\n".join(lines) or "Nothing changed.")

    def _table_report(self, model: TextModel) -> list[str]:
        """The tables the request touched as they are now (the first three, in the order they were touched), and the
        ones that are gone."""
        lines: list[str] = []
        for table_id in self._tables[:MAX_REPORTED_TABLES]:
            if table_id not in model.tables:
                lines.append(f"Table {table_id} is gone.")
                continue
            users = model.tables.users(table_id)
            name = model.get_object(users[0]).body.name if users else ""
            lines.append(describe_table(table_view(model, table_id), name or ""))
        if len(self._tables) > MAX_REPORTED_TABLES:
            lines.append(f"... and {len(self._tables) - MAX_REPORTED_TABLES} more tables changed.")
        return lines


__all__ = ["DocumentLens", "TextRecorder", "describe_paragraph", "describe_suggestion", "describe_table"]
