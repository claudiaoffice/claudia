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
from claudia_composes.events import BlocksJoined, BlockSplit, ItemChanged, StyleChanged, SuggestionsChanged, TextChanged
from claudia_core import Document

from .composes_words import paragraph_view
from .lens import fence, shorten

PREVIEW_PARAGRAPHS = 12  # paragraphs from the start shown at the beginning
AROUND_ASKER = 2  # paragraphs before and after the asker's shown with it
MAX_OUTLINE = 30  # headings named at the start
MAX_STYLES = 30  # paragraph styles named at the start
MAX_TEXT = 300  # characters of one paragraph shown at the start and in a report
MAX_READ_TEXT = 2000  # characters of one paragraph shown when the model asked to read it
MAX_REPORTED = 25  # paragraphs of one change report shown
MAX_PURPOSE = 60  # characters of a style's purpose shown
MAX_SUGGESTIONS = 30  # open suggestions listed

ORIENTATION = (
    "The text is a list of paragraphs. Each has an id (b1, b2, ...) and a paragraph style. Name a paragraph by its id "
    "and words in it by quoting them exactly as they are written (find); an empty find means the paragraph's whole "
    "text. Never count characters. A line break in new text starts a new paragraph. Read paragraphs before you change "
    "them: the start of the text below is only a part of it.{example}"
)
ACT_EXAMPLE = (
    ' A request looks like {"method": "replace_words", "params": {"block": "b3", "find": "in order to", "text": "to"}}.'
)
SUGGEST_EXAMPLE = (
    ' You may only propose changes, which people accept or reject. A request looks like {"method": "suggest_words", '
    '"params": {"block": "b3", "find": "in order to", "replacement": "to", "reason": "shorter"}}.'
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


def describe_suggestion(item: dict) -> str:
    """One open suggestion: ``s2 by ai on b3: "in order to" -> "to" (shorter)``, a remark without the arrow."""
    original = '"' + _flat(item["original"], 80) + '"'
    if item.get("replacement") is None:
        change = f"remark on {original}"
    else:
        change = f'{original} -> "{_flat(item["replacement"], 80)}"'
    line = f"{item['id']} by {item.get('author') or 'somebody'} on {item['block']}: {change}"
    if item.get("reason"):
        line += f" ({_flat(item['reason'], 80)})"
    return line + (" [outdated]" if item.get("outdated") else "")


class DocumentLens:
    """The lens for composes."""

    look_methods: tuple[str, ...] = ("paragraphs", "outline", "styles", "suggestions")

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
        text = ORIENTATION.format(example=self._example(can_write, writes))
        labels = model.labels()
        blocks = model.blocks
        text += f"\nThe text has {len(blocks)} paragraph{'s' if len(blocks) != 1 else ''}."
        text += "\nParagraph styles (id: name, what it is for):\n" + self._styles(model)
        headings = [at for at, block in enumerate(blocks) if model.block_kind(block) == "heading"]
        if headings:
            shown = [describe_paragraph(paragraph_view(model, at, labels), 80) for at in headings[:MAX_OUTLINE]]
            if len(headings) > MAX_OUTLINE:
                shown.append(f"... and {len(headings) - MAX_OUTLINE} more headings (ask for the outline)")
            text += "\nHeadings:\n" + fence("\n".join(shown))
        first = [
            describe_paragraph(paragraph_view(model, at, labels)) for at in range(min(PREVIEW_PARAGRAPHS, len(blocks)))
        ]
        if len(blocks) > PREVIEW_PARAGRAPHS:
            first.append(f"... {len(blocks) - PREVIEW_PARAGRAPHS} more paragraphs (read them with paragraphs)")
        text += "\nThe start of the text:\n" + fence("\n".join(first))
        here = self._asker_at(document, model, asker)
        if here is not None:
            text += f"\n{asker}'s cursor is in paragraph {blocks[here].id}"
            if here >= PREVIEW_PARAGRAPHS:
                around = range(max(here - AROUND_ASKER, 0), min(here + AROUND_ASKER + 1, len(blocks)))
                text += ", here with the paragraphs around it:\n" + fence(
                    "\n".join(describe_paragraph(paragraph_view(model, at, labels)) for at in around)
                )
            else:
                text += " (shown above)."
        open_now = len(model.visible_suggestions())
        if open_now:
            text += f"\n{open_now} suggestion{'s are' if open_now != 1 else ' is'} open (ask for the suggestions)."
        return text

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
                    return model.index_of(region.block)
                except KeyError:
                    continue
        return None

    # -- what the read requests show
    def show(self, method: str, params: dict, result: Any) -> str:
        """The answer of a read request, fenced as data."""
        if method == "paragraphs":
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
        self._stop: Callable[[], None] | None = None

    def __enter__(self) -> TextRecorder:
        self._stop = self._document.subscribe(self._hear)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._stop is not None:
            self._stop()
            self._stop = None

    def _touch(self, *blocks: str) -> None:
        self._touched += [block for block in blocks if block not in self._touched]

    def _hear(self, event: object) -> None:
        if isinstance(event, (TextChanged, StyleChanged, ItemChanged)):
            self._touch(event.block)
        elif isinstance(event, BlockSplit):
            self._touch(event.block, event.new_id)
        elif isinstance(event, BlocksJoined):
            self._touch(event.into)
            self._joined.append(event.block)
        elif isinstance(event, SuggestionsChanged):
            for item in event.items:
                self._suggestions[item["id"]] = item

    def report(self) -> str:
        """The touched paragraphs as they are now, in the order of the text, and the suggestions made; fenced."""
        model = self._document.model
        assert isinstance(model, TextModel)
        labels = model.labels()
        where = {block: model.index_of(block) for block in self._touched if block in {b.id for b in model.blocks}}
        order = sorted(where, key=where.__getitem__)
        lines = [describe_paragraph(paragraph_view(model, where[block], labels)) for block in order[:MAX_REPORTED]]
        if len(order) > MAX_REPORTED:
            lines.append(f"... and {len(order) - MAX_REPORTED} more paragraphs changed.")
        gone = [block for block in self._joined if block not in where]
        if gone:
            lines.append("Joined into the paragraph before them, so gone: " + ", ".join(gone))
        made = [item for item in self._suggestions.values() if item.get("state", "open") == "open"]
        if made:
            lines.append("Suggestions now open:")
            lines += [describe_suggestion(model.suggestion_data(model.suggestion(item["id"]))) for item in made]
        return fence("\n".join(lines) or "Nothing changed.")


__all__ = ["DocumentLens", "TextRecorder", "describe_paragraph", "describe_suggestion"]
