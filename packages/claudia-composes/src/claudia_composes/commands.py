"""Commands of the text model (E9.1). Every one carries final values and returns its exact inverse.

Text is addressed by paragraph id and offset, and a paragraph that is split or joined keeps its identity through its
id, so a command written for the old structure can follow later structural edits (``follow`` and ``breaks``).
Typing, deleting, splitting, joining and styling are the ways people change a document; accepting a suggestion is an
ordinary edit by the person who accepts it (D63), made of the same steps.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar

from claudia_core import Batch, Command, Context, Region

from .events import BlocksJoined, BlockSplit, StyleChanged, SuggestionsChanged, TextChanged
from .model import Suggestion, TextModel
from .region import TextRange
from .runs import Run, runs_from_data, runs_to_data
from .spans import Span, TextCommand

register = TextModel.registry.register
SHOWN = 40  # characters of typed text a history sentence quotes


def _quote(text: str) -> str:
    return f"“{text if len(text) <= SHOWN else text[: SHOWN - 1] + '…'}”"


def _moved(ctx: Context[TextModel], command: TextCommand) -> None:
    """Let the open suggestions and the floating objects follow a text command, and tell the clients about those
    that moved (see :mod:`claudia_composes.anchors` for why an object's anchor follows the text here, where a
    sheet's is deliberately frozen)."""
    moved = ctx.model.move_suggestions(command)
    if moved:
        ctx.emit(SuggestionsChanged(tuple(moved)))
    for container in dict.fromkeys(obj["anchor"]["container"] for obj in ctx.model.move_objects(command)):
        ctx.emit(ctx.model.objects_changed(container, changed=tuple(ctx.model.objects_on(container))))


# ------------------------------------------------------------------------------ typing
@register
@dataclass(frozen=True)
class InsertText(TextCommand):
    """Type ``text`` into a paragraph at ``offset``. ``by`` says who wrote it when that is not whoever runs the
    command (the inverse of a delete puts back text with its original authors)."""

    kind: ClassVar[str] = "composes.InsertText"
    schema: ClassVar[int] = 2
    block: str
    offset: int
    text: str
    by: tuple[Run, ...] = ()

    @property
    def label(self) -> str:
        return "Type"

    @property
    def summary(self) -> str:
        return f"typed {_quote(self.text)}"

    def apply(self, ctx: Context[TextModel]) -> Command:
        runs = list(self.by) or ([Run(len(self.text), ctx.author)] if self.text else [])
        ctx.model.insert(self.block, self.offset, self.text, runs)
        if self.text:
            ctx.emit(TextChanged(self.block, self.offset, 0, self.text, tuple(runs)))
        _moved(ctx, self)
        return DeleteText(self.block, self.offset, len(self.text))

    def to_data(self) -> dict:
        data: dict = {"block": self.block, "offset": self.offset, "text": self.text}
        if self.by:
            data["by"] = runs_to_data(list(self.by))
        return data

    @classmethod
    def from_data(cls, data, registry) -> InsertText:
        return cls(data["block"], data["offset"], data["text"], tuple(runs_from_data(data.get("by", []))))

    def regions(self, model) -> tuple[Region, ...]:
        return (TextRange(self.block, self.offset, self.offset + max(1, len(self.text))),)

    def follow(self, span: Span) -> Span:
        block, start, end = span
        n = len(self.text)
        if block != self.block:
            return span
        if self.offset <= start:
            return (block, start + n, end + n)
        if self.offset < end:
            return (block, start, end + n)
        return span

    def breaks(self, span: Span) -> bool:
        block, start, end = span
        return block == self.block and start < self.offset < end

    def shifted_by(self, other: Command) -> Command | None:
        if not isinstance(other, TextCommand):
            return self
        span = (self.block, self.offset, self.offset)
        if other.breaks(span):
            return None
        block, offset, _ = other.follow(span)
        return replace(self, block=block, offset=offset)

    def redacted(self) -> Command:
        return replace(self, text="█" * len(self.text))  # same length, so later offsets still hold


@register
@dataclass(frozen=True)
class DeleteText(TextCommand):
    """Delete ``length`` characters of a paragraph from ``offset`` on."""

    kind: ClassVar[str] = "composes.DeleteText"
    schema: ClassVar[int] = 2
    block: str
    offset: int
    length: int

    @property
    def label(self) -> str:
        return "Delete text"

    @property
    def summary(self) -> str:
        return f"deleted {self.length} character{'' if self.length == 1 else 's'}"

    def apply(self, ctx: Context[TextModel]) -> Command:
        text, runs = ctx.model.remove(self.block, self.offset, self.offset + self.length)
        if self.length:
            ctx.emit(TextChanged(self.block, self.offset, self.length, ""))
        _moved(ctx, self)
        return InsertText(self.block, self.offset, text, tuple(runs))

    def to_data(self) -> dict:
        return {"block": self.block, "offset": self.offset, "length": self.length}

    @classmethod
    def from_data(cls, data, registry) -> DeleteText:
        return cls(data["block"], data["offset"], data["length"])

    def regions(self, model) -> tuple[Region, ...]:
        return (TextRange(self.block, self.offset, self.offset + max(1, self.length)),)

    def follow(self, span: Span) -> Span:
        block, start, end = span
        if block != self.block:
            return span
        cut = self.offset, self.offset + self.length

        def moved(position: int) -> int:
            return position - min(max(position - cut[0], 0), self.length)

        return (block, moved(start), moved(end))

    def breaks(self, span: Span) -> bool:
        block, start, end = span
        return block == self.block and start < end and self.offset < end and self.offset + self.length > start

    def shifted_by(self, other: Command) -> Command | None:
        """Deleting what I typed: follow colleagues' typing before it; refuse if they typed in it or cut part of it."""
        if not isinstance(other, TextCommand):
            return self
        span = (self.block, self.offset, self.offset + self.length)
        if other.breaks(span):
            return None
        block, start, end = other.follow(span)
        return replace(self, block=block, offset=start, length=end - start)

    def redacted(self) -> Command:
        return self


# ------------------------------------------------------------------------------ structure
@register
@dataclass(frozen=True)
class SplitBlock(TextCommand):
    """Cut the paragraph ``block`` at ``offset``: the rest becomes the new paragraph ``new_id``, in ``style``."""

    kind: ClassVar[str] = "composes.SplitBlock"
    block: str
    offset: int
    new_id: str
    style: str

    @property
    def label(self) -> str:
        return "New paragraph"

    @property
    def summary(self) -> str:
        return "new paragraph"

    def apply(self, ctx: Context[TextModel]) -> Command:
        ctx.model.split(self.block, self.offset, self.new_id, self.style)
        ctx.emit(BlockSplit(self.block, self.offset, self.new_id, self.style))
        _moved(ctx, self)
        return JoinBlocks(self.new_id, self.block, self.offset)

    def to_data(self) -> dict:
        return {"block": self.block, "offset": self.offset, "new_id": self.new_id, "style": self.style}

    @classmethod
    def from_data(cls, data, registry) -> SplitBlock:
        return cls(data["block"], data["offset"], data["new_id"], data["style"])

    def regions(self, model) -> tuple[Region, ...]:
        return (TextRange(self.block, self.offset, self.offset + 1),)

    def follow(self, span: Span) -> Span:
        block, start, end = span
        if block != self.block:
            return span
        if start >= self.offset:
            return (self.new_id, start - self.offset, end - self.offset)
        return (block, start, min(end, self.offset))

    def breaks(self, span: Span) -> bool:
        block, start, end = span
        return block == self.block and start < self.offset < end

    def shifted_by(self, other: Command) -> Command | None:
        if not isinstance(other, TextCommand):
            return self
        span = (self.block, self.offset, self.offset)
        if other.breaks(span):
            return None
        block, offset, _ = other.follow(span)
        return replace(self, block=block, offset=offset)


@register
@dataclass(frozen=True)
class JoinBlocks(TextCommand):
    """Put the paragraph ``block`` at the end of ``into``, the one right before it, whose text is ``at`` long."""

    kind: ClassVar[str] = "composes.JoinBlocks"
    block: str
    into: str
    at: int

    @property
    def label(self) -> str:
        return "Join paragraphs"

    @property
    def summary(self) -> str:
        return "joined paragraphs"

    def apply(self, ctx: Context[TextModel]) -> Command:
        style = ctx.model.join(self.block, self.into, self.at)
        ctx.emit(BlocksJoined(self.block, self.into, self.at))
        _moved(ctx, self)
        return SplitBlock(self.into, self.at, self.block, style)

    def to_data(self) -> dict:
        return {"block": self.block, "into": self.into, "at": self.at}

    @classmethod
    def from_data(cls, data, registry) -> JoinBlocks:
        return cls(data["block"], data["into"], data["at"])

    def regions(self, model) -> tuple[Region, ...]:
        return (TextRange(self.into, self.at, self.at + 1), TextRange(self.block, 0, 1))

    def follow(self, span: Span) -> Span:
        block, start, end = span
        if block == self.block:
            return (self.into, start + self.at, end + self.at)
        return span

    def shifted_by(self, other: Command) -> Command | None:
        if not isinstance(other, TextCommand):
            return self
        span = (self.into, self.at, self.at)
        if other.breaks(span):
            return None
        into, at, _ = other.follow(span)
        return replace(self, into=into, at=at)


@register
@dataclass(frozen=True)
class SetStyle(TextCommand):
    """Give a paragraph another named style."""

    kind: ClassVar[str] = "composes.SetStyle"
    block: str
    style: str

    @property
    def label(self) -> str:
        return "Style"

    @property
    def summary(self) -> str:
        return f"style {self.style}"

    def apply(self, ctx: Context[TextModel]) -> Command:
        model = ctx.model
        model.check_style(self.style)
        block = model.block(self.block)
        old = block.style
        ctx.model.restyle(block.id, self.style)
        ctx.emit(StyleChanged(self.block, self.style))
        return SetStyle(self.block, old)

    def to_data(self) -> dict:
        return {"block": self.block, "style": self.style}

    @classmethod
    def from_data(cls, data, registry) -> SetStyle:
        return cls(data["block"], data["style"])

    def regions(self, model) -> tuple[Region, ...]:
        length = len(model.block(self.block).text) if isinstance(model, TextModel) else 0
        return (TextRange(self.block, 0, max(1, length)),)

    def shifted_by(self, other: Command) -> Command | None:
        if isinstance(other, JoinBlocks) and other.block == self.block:
            return None  # the paragraph is part of another one now; its style is that one's
        return self


# ------------------------------------------------------------------------------ suggestions (D63)
@register
@dataclass(frozen=True)
class ProposeSuggestion(Command):
    """Put a suggestion on the document: replace ``original`` (what is at ``start:end`` now) by ``replacement``,
    or ``None`` for a remark that suggests no change. It changes no text and is nobody's undo step."""

    kind: ClassVar[str] = "composes.ProposeSuggestion"
    undoable = False
    id: str
    block: str
    start: int
    end: int
    original: str
    replacement: str | None
    reason: str

    @property
    def label(self) -> str:
        return "Remark" if self.replacement is None else "Suggestion"

    @property
    def summary(self) -> str:
        if self.replacement is None:
            return f"remarks on {_quote(self.original)}"
        return f"suggests {_quote(self.original)} → {_quote(self.replacement)}"

    def apply(self, ctx: Context[TextModel]) -> Command:
        suggestion = Suggestion(
            self.id,
            ctx.author,
            TextRange(self.block, self.start, self.end),
            self.original,
            self.replacement,
            self.reason,
        )
        ctx.model.add_suggestion(suggestion)
        ctx.emit(SuggestionsChanged((ctx.model.suggestion_data(suggestion),)))
        return ResolveSuggestion(self.id, "withdrawn")

    def to_data(self) -> dict:
        return {
            "id": self.id,
            "block": self.block,
            "start": self.start,
            "end": self.end,
            "original": self.original,
            "replacement": self.replacement,
            "reason": self.reason,
        }

    @classmethod
    def from_data(cls, data, registry) -> ProposeSuggestion:
        return cls(
            data["id"], data["block"], data["start"], data["end"], data["original"], data["replacement"], data["reason"]
        )

    def redacted(self) -> Command:
        blank = "█" * len(self.original)
        return replace(self, original=blank, replacement=None if self.replacement is None else blank, reason="")

    def stub(self) -> dict:
        return {"id": self.id}


@register
@dataclass(frozen=True)
class ResolveSuggestion(Command):
    """Set the state of a suggestion: rejected, dismissed (a remark), accepted, open again, or withdrawn.

    ``anchor`` puts the suggestion back where it was (``[block, start, end]``); the inverse of an accept uses it."""

    kind: ClassVar[str] = "composes.ResolveSuggestion"
    id: str
    state: str
    anchor: tuple[str, int, int] | None = None

    @property
    def label(self) -> str:
        return {"rejected": "Reject suggestion", "dismissed": "Dismiss remark", "accepted": "Accept suggestion"}.get(
            self.state, "Suggestion"
        )

    @property
    def summary(self) -> str:
        return {
            "rejected": "rejected a suggestion",
            "dismissed": "dismissed a remark",
            "accepted": "accepted a suggestion",
            "open": "reopened a suggestion",
            "withdrawn": "withdrew a suggestion",
        }.get(self.state, self.label)

    def apply(self, ctx: Context[TextModel]) -> Command:
        model = ctx.model
        old = model.suggestion(self.id)
        if self.state not in ("open", "accepted", "rejected", "dismissed", "withdrawn"):
            raise ValueError(f"no suggestion state {self.state!r}")
        anchor = TextRange(*self.anchor) if self.anchor else old.anchor
        updated = replace(old, state=self.state, anchor=anchor)
        model.put_suggestion(updated)
        ctx.emit(SuggestionsChanged((model.suggestion_data(updated),)))
        return ResolveSuggestion(self.id, old.state, old.anchor.span)

    def to_data(self) -> dict:
        data: dict = {"id": self.id, "state": self.state}
        if self.anchor:
            data["anchor"] = list(self.anchor)
        return data

    @classmethod
    def from_data(cls, data, registry) -> ResolveSuggestion:
        anchor = data.get("anchor")
        return cls(data["id"], data["state"], None if anchor is None else (anchor[0], anchor[1], anchor[2]))

    def shifted_by(self, other: Command) -> Command | None:
        if self.anchor is None or not isinstance(other, TextCommand):
            return self
        return replace(self, anchor=other.follow(self.anchor))

    def stub(self) -> dict:
        return {"id": self.id}


@register
@dataclass(frozen=True)
class AcceptSuggestion(TextCommand):
    """Accept a suggestion: the person who runs this command replaces the text, and is its author; the suggestion's
    author is recorded as the one it came through (``via``). The command repeats what it does (final values) so that
    cursors and zones can follow it without looking the suggestion up."""

    kind: ClassVar[str] = "composes.AcceptSuggestion"
    id: str
    block: str
    start: int
    end: int
    replacement: str
    suggested_by: str | None = None

    @property
    def label(self) -> str:
        return "Accept suggestion"

    @property
    def summary(self) -> str:
        who = self.suggested_by or "somebody"
        what = f": {_quote(self.replacement)}" if self.replacement else " (a deletion)"
        return f"accepted a suggestion by {who}{what}"

    def _steps(self, by: str | None) -> list[Command]:
        steps: list[Command] = []
        if self.end > self.start:
            steps.append(DeleteText(self.block, self.start, self.end - self.start))
        if self.replacement:
            runs = (Run(len(self.replacement), by, self.suggested_by),)
            steps.append(InsertText(self.block, self.start, self.replacement, runs))
        return steps

    def leaves(self):
        yield from self._steps(None)

    def apply(self, ctx: Context[TextModel]) -> Command:
        model = ctx.model
        suggestion = model.suggestion(self.id)
        anchor = suggestion.anchor
        if suggestion.state != "open" or suggestion.replacement is None:
            raise ValueError("only an open suggestion that proposes a change can be accepted")
        if model.is_outdated(suggestion):
            raise ValueError("the text changed since this was suggested; look at it again")
        if (anchor.block, anchor.start, anchor.end, suggestion.replacement) != (
            self.block,
            self.start,
            self.end,
            self.replacement,
        ):
            raise ValueError("this is not the suggestion that is on the document")
        steps = [ResolveSuggestion(self.id, "accepted"), *self._steps(ctx.author)]
        inverses = [step.apply(ctx) for step in steps]
        return Batch(tuple(reversed(inverses)))

    def to_data(self) -> dict:
        return {
            "id": self.id,
            "block": self.block,
            "start": self.start,
            "end": self.end,
            "replacement": self.replacement,
            "suggested_by": self.suggested_by,
        }

    @classmethod
    def from_data(cls, data, registry) -> AcceptSuggestion:
        return cls(data["id"], data["block"], data["start"], data["end"], data["replacement"], data["suggested_by"])

    def regions(self, model) -> tuple[Region, ...]:
        return (TextRange(self.block, self.start, max(self.end, self.start + 1)),)

    def follow(self, span: Span) -> Span:
        for leaf in self.leaves():
            span = leaf.follow(span)
        return span

    def redacted(self) -> Command:
        return replace(self, replacement="█" * len(self.replacement))

    def stub(self) -> dict:
        return {"id": self.id}


# ------------------------------------------------------------------------------ documents are forever
@TextModel.registry.upcaster("composes.InsertText", 1)
@TextModel.registry.upcaster("composes.DeleteText", 1)
def _paragraph_by_id(data: dict) -> dict:
    """Schema 1 named the paragraph by its number. The only paragraph there ever was is ``b1``."""
    return {**data, "block": "b1" if data["block"] == 0 else f"b{data['block'] + 1}"}
