"""The text model: named paragraphs, who wrote each stretch, and the AI's open suggestions (E9.1, D62, D63).

A document is a list of paragraphs. Each has an id that is never reused, a style (by name: you mark text by what it is
for, D62), its text and the runs that say who wrote what. Suggestions are proposals anchored to a stretch of text; they
are state of the document like the paragraphs, but they change no text until somebody accepts them.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import ClassVar, Self

from claudia_core import CommandRegistry, DocumentModel, Region, StyleBook, StyleDef, new_registry

from .region import TextRange
from .runs import Run, delete_runs, insert_runs, runs_from_data, runs_to_data, slice_runs, total
from .spans import TextCommand

DEFAULT_STYLE = "body"
FIRST_BLOCK = "b1"
_NUMBERED = re.compile(r"[bs](\d+)")


_SANS = "Inter, system-ui, 'Segoe UI', sans-serif"
_SERIF = "Fraunces, Georgia, serif"
_INK = "#1F1A33"


def _style(style_id: str, name: str, purpose: str, **css: str) -> StyleDef:
    return StyleDef(style_id, name, purpose, None if style_id == DEFAULT_STYLE else DEFAULT_STYLE, css)


#: The styles every text starts with, all based on Body text (D73): a change to Body text reaches the others where they
#: have not set the property themselves. They are made by the model, not by commands, so they are in every log's past.
BUILTIN_STYLES: tuple[StyleDef, ...] = (
    _style(
        "body",
        "Body text",
        "running text",
        **{
            "font-family": _SANS,
            "font-size": "12pt",
            "line-height": "1.75",
            "color": _INK,
            "text-align": "left",
            "margin-top": "0",
            "margin-bottom": "0.9em",
        },
    ),
    _style(
        "title",
        "Title",
        "names the document",
        **{
            "font-family": _SERIF,
            "font-size": "30pt",
            "font-weight": "500",
            "line-height": "1.15",
            "letter-spacing": "-0.01em",
            "margin-bottom": "0.5em",
        },
    ),
    _style(
        "heading-1",
        "Heading 1",
        "a section",
        **{
            "font-family": _SERIF,
            "font-size": "19pt",
            "font-weight": "500",
            "line-height": "1.25",
            "margin-top": "1.6em",
            "margin-bottom": "0.5em",
        },
    ),
    _style(
        "heading-2",
        "Heading 2",
        "a subsection",
        **{
            "font-family": _SERIF,
            "font-size": "14.5pt",
            "font-weight": "500",
            "line-height": "1.3",
            "margin-top": "1.3em",
            "margin-bottom": "0.4em",
        },
    ),
    _style(
        "quote",
        "Quote",
        "words of someone else",
        **{
            "font-family": _SERIF,
            "font-style": "italic",
            "font-size": "14pt",
            "line-height": "1.7",
            "color": "rgba(31, 26, 51, 0.82)",
            "border-left": "3px solid #F2A057",
            "padding-left": "1.1em",
        },
    ),
    _style(
        "remark",
        "Remark",
        "a note to the reader or co-author",
        **{
            "font-size": "11pt",
            "line-height": "1.6",
            "color": "rgba(31, 26, 51, 0.78)",
            "background-color": "rgba(214, 71, 122, 0.07)",
            "border-left": "3px solid #D6477A",
            "padding-top": "0.55em",
            "padding-bottom": "0.55em",
            "padding-left": "0.9em",
            "padding-right": "0.9em",
        },
    ),
    _style(
        "definition",
        "Definition",
        "says what a term means",
        **{
            "background-color": "rgba(231, 225, 244, 0.55)",
            "border-left": "3px solid #5B4BC4",
            "padding-top": "0.5em",
            "padding-bottom": "0.5em",
            "padding-left": "0.9em",
            "padding-right": "0.9em",
        },
    ),
)
_BUILTIN_IDS = frozenset(s.id for s in BUILTIN_STYLES)


def builtin_styles() -> StyleBook:
    """A new style book with the built-in styles."""
    return StyleBook(BUILTIN_STYLES)


def next_style(styles: StyleBook, style_id: str) -> str:
    """The style of the paragraph that starts when a writer ends one in ``style_id`` (Enter at its end): body text
    after a heading, a quote or a remark, and more of the same after body text. A style made by deviating follows the
    built-in style it comes from."""
    root = next(s for s in reversed(styles.chain(style_id)) if s.id in _BUILTIN_IDS)
    return style_id if root.id == DEFAULT_STYLE else DEFAULT_STYLE


@dataclass
class Block:
    """One paragraph: ``runs`` always add up to the length of ``text``."""

    id: str
    style: str
    text: str = ""
    runs: list[Run] = field(default_factory=list)

    def to_data(self) -> dict:
        """The plain-data form: ``{id, style, text, runs}``."""
        return {"id": self.id, "style": self.style, "text": self.text, "runs": runs_to_data(self.runs)}


@dataclass(frozen=True)
class Suggestion:
    """A proposal: replace ``original`` (the text at ``anchor`` when it was made) by ``replacement``.

    ``replacement`` is ``None`` for a remark, which suggests no change. ``state`` is ``open``, ``accepted``,
    ``rejected``, ``dismissed`` (a remark) or ``withdrawn`` (the proposal was undone and does not exist any more)."""

    id: str
    author: str | None
    anchor: TextRange
    original: str
    replacement: str | None
    reason: str
    state: str = "open"


class TextModel(DocumentModel):
    """The paragraphs of a document and its suggestions."""

    app: ClassVar[str] = "composes"
    state_schema: ClassVar[int] = 3
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(self, blocks: list[Block] | None = None, styles: StyleBook | None = None):
        self.blocks: list[Block] = blocks if blocks is not None else [Block(FIRST_BLOCK, DEFAULT_STYLE)]
        self.styles: StyleBook = styles if styles is not None else builtin_styles()
        self.suggestions: dict[str, Suggestion] = {}
        self._last = {"b": _highest(b.id for b in self.blocks), "s": 0}

    # -- lifecycle ---------------------------------------------------------------
    @classmethod
    def empty(cls) -> Self:
        """A document with one empty body paragraph."""
        return cls()

    def serialize(self) -> dict:
        """The state as plain data (a snapshot is a cache of it)."""
        return {
            "blocks": [b.to_data() for b in self.blocks],
            "styles": self.styles.to_data(),
            "suggestions": [self.suggestion_data(s, with_state=True) for s in self.suggestions.values()],
            "last": dict(self._last),
        }

    @classmethod
    def restore(cls, state: dict) -> Self:
        """Build a model from ``serialize()``'s output; the older shape (a list of strings) is understood too."""
        raw = state["blocks"]
        if raw and isinstance(raw[0], str):  # state schema 1: the stub, which could not hold more than strings
            blocks = [Block(f"b{i}", DEFAULT_STYLE, t, [Run(len(t), None)] if t else []) for i, t in enumerate(raw, 1)]
            return cls(blocks)
        styles = StyleBook.from_data(state["styles"]) if "styles" in state else None  # schema 2 had the built-in ones
        model = cls([Block(b["id"], b["style"], b["text"], runs_from_data(b["runs"])) for b in raw], styles)
        for item in state.get("suggestions", []):
            model.suggestions[item["id"]] = _suggestion_from_data(item)
        model._last = dict(state.get("last", model._last))
        return model

    def region_from_data(self, data: dict) -> Region:
        """Read a region a client sent: ``{"kind": "text", "block", "start", "end"}``."""
        if data.get("kind") != TextRange.kind:
            raise ValueError(f"composes knows only text regions, not {data.get('kind')!r}")
        block, start, end = data["block"], data["start"], data["end"]
        if not (isinstance(block, str) and isinstance(start, int) and isinstance(end, int) and 0 <= start <= end):
            raise ValueError("a text region names a paragraph and 0 <= start <= end")
        return TextRange(block, start, end)

    # -- reading -----------------------------------------------------------------
    def block(self, block_id: str) -> Block:
        """The paragraph with this id; ``KeyError`` if there is none."""
        for block in self.blocks:
            if block.id == block_id:
                return block
        raise KeyError(f"no paragraph {block_id!r}")

    def index_of(self, block_id: str) -> int:
        """The place of the paragraph in the document; ``KeyError`` if there is none."""
        self.block(block_id)
        return next(i for i, b in enumerate(self.blocks) if b.id == block_id)

    def fresh_ids(self, count: int) -> list[str]:
        """``count`` ids for new paragraphs. Ids are never used twice, not even after a join, so undo can bring one
        back."""
        return [f"b{self._last['b'] + n}" for n in range(1, count + 1)]

    def fresh_id(self) -> str:
        """An id for a new paragraph (see ``fresh_ids``)."""
        return self.fresh_ids(1)[0]

    def style_in_use(self, style_id: str) -> bool:
        """Does any paragraph have this style? (Asked by the style commands before they take a style back.)"""
        return any(b.style == style_id for b in self.blocks)

    def style_uses(self) -> dict[str, int]:
        """How many paragraphs have each style that is in use."""
        return dict(Counter(b.style for b in self.blocks))

    def fresh_suggestion_id(self) -> str:
        """An id for a new suggestion."""
        return f"s{self._last['s'] + 1}"

    def suggestion(self, suggestion_id: str) -> Suggestion:
        """The suggestion with this id; ``KeyError`` if there is none."""
        try:
            return self.suggestions[suggestion_id]
        except KeyError:
            raise KeyError(f"no suggestion {suggestion_id!r}") from None

    def is_outdated(self, suggestion: Suggestion) -> bool:
        """Has the text under a suggestion changed since it was made? It then cannot be accepted any more."""
        a = suggestion.anchor
        try:
            current = self.block(a.block).text[a.start : a.end]
        except KeyError:
            return True
        return current != suggestion.original

    def suggestion_data(self, suggestion: Suggestion, *, with_state: bool = False) -> dict:
        """A suggestion as sent to clients (``with_state`` also keeps the ones that are over, for snapshots)."""
        a = suggestion.anchor
        data = {
            "id": suggestion.id,
            "author": suggestion.author,
            "block": a.block,
            "start": a.start,
            "end": a.end,
            "original": suggestion.original,
            "replacement": suggestion.replacement,
            "reason": suggestion.reason,
            "state": suggestion.state,
        }
        if not with_state:
            data["outdated"] = self.is_outdated(suggestion)
        return data

    def visible_suggestions(self) -> list[dict]:
        """The suggestions people may still act on, in the order they were made."""
        return [self.suggestion_data(s) for s in self.suggestions.values() if s.state == "open"]

    # -- changing text (used by the commands) ------------------------------------
    def insert(self, block_id: str, offset: int, text: str, runs: list[Run]) -> None:
        """Put ``text`` into a paragraph at ``offset``; ``runs`` say who wrote it."""
        block = self.block(block_id)
        if not 0 <= offset <= len(block.text):
            raise IndexError("insert outside the text")
        if total(runs) != len(text):
            raise ValueError("the runs must cover exactly the inserted text")
        block.text = block.text[:offset] + text + block.text[offset:]
        block.runs = insert_runs(block.runs, offset, runs)

    def remove(self, block_id: str, start: int, end: int) -> tuple[str, list[Run]]:
        """Cut ``start <= i < end`` out of a paragraph; returns what was cut, with its runs."""
        block = self.block(block_id)
        if not 0 <= start <= end <= len(block.text):
            raise IndexError("delete outside the text")
        removed = block.text[start:end], slice_runs(block.runs, start, end)
        block.text = block.text[:start] + block.text[end:]
        block.runs = delete_runs(block.runs, start, end)
        return removed

    def split(self, block_id: str, offset: int, new_id: str, style: str) -> None:
        """Cut a paragraph at ``offset``; the rest becomes the paragraph ``new_id`` right behind it."""
        block = self.block(block_id)
        if not 0 <= offset <= len(block.text):
            raise IndexError("split outside the text")
        if any(b.id == new_id for b in self.blocks):
            raise ValueError(f"the paragraph {new_id!r} exists already")
        self.check_style(style)
        rest = Block(new_id, style, block.text[offset:], slice_runs(block.runs, offset, len(block.text)))
        block.text, block.runs = block.text[:offset], slice_runs(block.runs, 0, offset)
        self.blocks.insert(self.index_of(block_id) + 1, rest)
        self._note_id(new_id)

    def join(self, block_id: str, into: str, at: int) -> str:
        """Put paragraph ``block_id`` at the end of ``into`` (the one right before it, ``at`` characters long).

        Returns the style of the paragraph that went away."""
        first, second = self.block(into), self.block(block_id)
        if self.index_of(block_id) != self.index_of(into) + 1:
            raise ValueError("a paragraph can only be joined to the one right before it")
        if len(first.text) != at:
            raise ValueError("the paragraph before it is not as long as the command says")
        first.text += second.text
        first.runs = insert_runs(first.runs, at, second.runs)
        self.blocks.remove(second)
        return second.style

    def check_style(self, style: str) -> None:
        """``ValueError`` unless the document has a style with this id."""
        if style not in self.styles:
            raise ValueError(f"no style {style!r}")

    # -- suggestions (used by the commands) --------------------------------------
    def add_suggestion(self, suggestion: Suggestion) -> None:
        """Add a new suggestion."""
        if suggestion.id in self.suggestions:
            raise ValueError(f"the suggestion {suggestion.id!r} exists already")
        a = suggestion.anchor
        if not 0 <= a.start <= a.end <= len(self.block(a.block).text):
            raise IndexError("a suggestion must lie inside the text")
        self.suggestions[suggestion.id] = suggestion
        self._note_id(suggestion.id)

    def put_suggestion(self, suggestion: Suggestion) -> None:
        """Replace a suggestion by a changed version of it."""
        self.suggestions[suggestion.id] = suggestion

    def move_suggestions(self, command: TextCommand) -> list[dict]:
        """Let the open suggestions follow ``command``; returns the ones that moved, as sent to clients."""
        moved = []
        for suggestion in list(self.suggestions.values()):
            if suggestion.state != "open":
                continue
            span = command.follow(suggestion.anchor.span)
            if span != suggestion.anchor.span:
                updated = replace(suggestion, anchor=TextRange(*span))
                self.suggestions[suggestion.id] = updated
                moved.append(self.suggestion_data(updated))
        return moved

    def _note_id(self, ident: str) -> None:
        """Remember numbered ids that were used so that ``fresh_id`` never hands one out twice."""
        found = _NUMBERED.fullmatch(ident)
        if found:
            self._last[ident[0]] = max(self._last[ident[0]], int(found.group(1)))


def _highest(ids) -> int:
    return max((int(m.group(1)) for i in ids if i.startswith("b") and (m := _NUMBERED.fullmatch(i))), default=0)


def _suggestion_from_data(item: dict) -> Suggestion:
    anchor = TextRange(item["block"], item["start"], item["end"])
    return Suggestion(
        item["id"], item["author"], anchor, item["original"], item["replacement"], item["reason"], item["state"]
    )
