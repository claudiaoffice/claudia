"""Commands of the text model (E9.1). Every one carries final values and returns its exact inverse.

Text is addressed by paragraph id and offset, and a paragraph that is split or joined keeps its identity through its
id, so a command written for the old structure can follow later structural edits (``follow`` and ``breaks``).
Typing, deleting, splitting, joining and styling are the ways people change a document; accepting a suggestion is an
ordinary edit by the person who accepts it (D63), made of the same steps.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar

from claudia_core import (
    Batch,
    Command,
    Context,
    DeleteText,
    InsertText,
    ObjectSet,
    PageSetup,
    Region,
    RemoveObject,
    SetLanguage,
    SetListItem,
)

from .events import (
    PageSetupChanged,
    ParagraphsJoined,
    ParagraphSplit,
    StyleChanged,
    SuggestionsChanged,
)
from .model import Suggestion, TextModel
from .region import TextRange
from .runs import Run
from .spans import Span, TextCommand

register = TextModel.registry.register
SHOWN = 40  # characters of typed text a history sentence quotes


def _quote(text: str) -> str:
    return f"“{text if len(text) <= SHOWN else text[: SHOWN - 1] + '…'}”"


def _moved(ctx: Context[TextModel], command: TextCommand) -> None:
    """Let the open suggestions and the floating objects follow a text command, and tell the clients about those
    that moved (:meth:`TextModel.text_moved`)."""
    for event in ctx.model.text_moved(command):
        ctx.emit(event)


# ------------------------------------------------------------------------------ structure
@register
@dataclass(frozen=True)
class SplitParagraph(TextCommand):
    """Cut the paragraph ``paragraph`` at ``offset``: the rest becomes the new paragraph ``new_id``, in ``style``.

    What hangs from the rest goes along with it, and so does what hangs exactly at the cut, unless ``keep``: then that
    stays where it is (D1331: an empty paragraph after a table that hangs at the end of its paragraph)."""

    kind: ClassVar[str] = "composes.SplitParagraph"
    paragraph: str
    offset: int
    new_id: str
    style: str
    #: What the new paragraph is called (D1310); ``""`` for what an older log wrote, which gave it none.
    name: str = ""
    #: What hangs exactly at the cut stays in ``paragraph`` (D1331); not written when false, so older logs read the
    #: same.
    keep: bool = False

    @property
    def label(self) -> str:
        return "New paragraph"

    @property
    def summary(self) -> str:
        return "new paragraph"

    def apply(self, ctx: Context[TextModel]) -> Command:
        ctx.model.split(self.paragraph, self.offset, self.new_id, self.style, self.name)
        ctx.emit(ParagraphSplit(self.paragraph, self.offset, self.new_id, self.style))
        _moved(ctx, self)
        return JoinParagraphs(self.new_id, self.paragraph, self.offset)

    def to_data(self) -> dict:
        data: dict = {"paragraph": self.paragraph, "offset": self.offset, "new_id": self.new_id, "style": self.style}
        if self.name:
            data["name"] = self.name
        if self.keep:
            data["keep"] = True
        return data

    @classmethod
    def from_data(cls, data, registry) -> SplitParagraph:
        return cls(
            data["paragraph"],
            data["offset"],
            data["new_id"],
            data["style"],
            data.get("name", ""),
            data.get("keep", False),
        )

    def regions(self, model) -> tuple[Region, ...]:
        return (TextRange(self.paragraph, self.offset, self.offset + 1),)

    def follow(self, span: Span) -> Span:
        paragraph, start, end = span
        if paragraph != self.paragraph:
            return span
        if start > self.offset or (start == self.offset and not (self.keep and end == start)):
            return (self.new_id, start - self.offset, end - self.offset)
        return (paragraph, start, min(end, self.offset))

    def breaks(self, span: Span) -> bool:
        paragraph, start, end = span
        return paragraph == self.paragraph and start < self.offset < end

    def shifted_by(self, other: Command) -> Command | None:
        if not isinstance(other, TextCommand):
            return self
        span = (self.paragraph, self.offset, self.offset)
        if other.breaks(span):
            return None
        paragraph, offset, _ = other.follow(span)
        return replace(self, paragraph=paragraph, offset=offset)


@register
@dataclass(frozen=True)
class JoinParagraphs(TextCommand):
    """Put the paragraph ``paragraph`` at the end of ``into``, the one right before it, whose text is ``at`` long."""

    kind: ClassVar[str] = "composes.JoinParagraphs"
    paragraph: str
    into: str
    at: int

    @property
    def label(self) -> str:
        return "Join paragraphs"

    @property
    def summary(self) -> str:
        return "joined paragraphs"

    def apply(self, ctx: Context[TextModel]) -> Command:
        # Undone, the join is a split at ``at``. What hangs there now came from ``into`` (its end) or from ``paragraph``
        # (its start). When ``paragraph`` had nothing hanging from it, it was all ``into``'s, and the split keeps it
        # there.
        kept = not ctx.model.objects_on(self.paragraph)
        gone = ctx.model.join(self.paragraph, self.into, self.at)
        ctx.emit(ParagraphsJoined(self.paragraph, self.into, self.at))
        _moved(ctx, self)
        split = SplitParagraph(self.into, self.at, self.paragraph, gone.style, keep=kept)
        if gone.item == ctx.model.paragraph(self.into).item:
            return split  # a split gives the new paragraph that item anyway
        return Batch((split, SetListItem(self.paragraph, gone.item)))  # the paragraph that went away was another kind

    def to_data(self) -> dict:
        return {"paragraph": self.paragraph, "into": self.into, "at": self.at}

    def ends_paragraph(self, paragraph_id: str) -> bool:
        return paragraph_id == self.paragraph  # it is part of ``into`` now

    @classmethod
    def from_data(cls, data, registry) -> JoinParagraphs:
        return cls(data["paragraph"], data["into"], data["at"])

    def regions(self, model) -> tuple[Region, ...]:
        return (TextRange(self.into, self.at, self.at + 1), TextRange(self.paragraph, 0, 1))

    def follow(self, span: Span) -> Span:
        paragraph, start, end = span
        if paragraph == self.paragraph:
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
    paragraph: str
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
        paragraph = model.paragraph(self.paragraph)
        old = paragraph.style
        ctx.model.restyle(paragraph.id, self.style)
        ctx.emit(StyleChanged(self.paragraph, self.style))
        return SetStyle(self.paragraph, old)

    def to_data(self) -> dict:
        return {"paragraph": self.paragraph, "style": self.style}

    @classmethod
    def from_data(cls, data, registry) -> SetStyle:
        return cls(data["paragraph"], data["style"])

    def regions(self, model) -> tuple[Region, ...]:
        length = len(model.paragraph(self.paragraph).text) if isinstance(model, TextModel) else 0
        return (TextRange(self.paragraph, 0, max(1, length)),)

    def shifted_by(self, other: Command) -> Command | None:
        if isinstance(other, JoinParagraphs) and other.paragraph == self.paragraph:
            return None  # the paragraph is part of another one now; its style is that one's
        return self


# ------------------------------------------------------------------------------ the page (D904)
@register
@dataclass(frozen=True)
class SetPageSetup(Command):
    """Lay the text out on another page: paper, orientation, margins, page numbers. One step in the history, shared
    by everybody, so every preview and every PDF of the document uses the same page."""

    kind: ClassVar[str] = "composes.SetPageSetup"
    setup: PageSetup

    @property
    def label(self) -> str:
        return "Page setup"

    @property
    def summary(self) -> str:
        return f"set the page to {self.setup.describe()}"

    def apply(self, ctx: Context[TextModel]) -> Command:
        old = ctx.model.page
        ctx.model.page = self.setup
        ctx.emit(PageSetupChanged(self.setup.to_data()))
        return SetPageSetup(old)

    def to_data(self) -> dict:
        return {"setup": self.setup.to_data()}

    @classmethod
    def from_data(cls, data, registry) -> SetPageSetup:
        return cls(PageSetup.from_data(data["setup"]))


# ------------------------------------------------------------------------------ the language (D915, D917)
@register
@dataclass(frozen=True)
class _SetLanguageAsFirstWritten(SetLanguage):
    """The kind ``SetLanguage`` had before it moved to the kernel (D917), so that a log written with it still opens.
    Its inverse is the kernel's own command."""

    kind: ClassVar[str] = "composes.SetLanguage"


# ------------------------------------------------------------------------------ suggestions (D63)
@register
@dataclass(frozen=True)
class ProposeSuggestion(Command):
    """Put a suggestion on the document: replace ``original`` (what is at ``start:end`` now) by ``replacement``,
    or ``None`` for a remark that suggests no change. It changes no text and is nobody's undo step."""

    kind: ClassVar[str] = "composes.ProposeSuggestion"
    undoable = False
    id: str
    paragraph: str
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
            TextRange(self.paragraph, self.start, self.end),
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
            "paragraph": self.paragraph,
            "start": self.start,
            "end": self.end,
            "original": self.original,
            "replacement": self.replacement,
            "reason": self.reason,
        }

    @classmethod
    def from_data(cls, data, registry) -> ProposeSuggestion:
        return cls(
            data["id"],
            data["paragraph"],
            data["start"],
            data["end"],
            data["original"],
            data["replacement"],
            data["reason"],
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

    ``anchor`` puts the suggestion back where it was (``[paragraph, start, end]``); the inverse of an accept uses it."""

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
    paragraph: str
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
            steps.append(DeleteText(self.paragraph, self.start, self.end - self.start))
        if self.replacement:
            runs = (Run(len(self.replacement), by, self.suggested_by),)
            steps.append(InsertText(self.paragraph, self.start, self.replacement, runs))
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
        if (anchor.paragraph, anchor.start, anchor.end, suggestion.replacement) != (
            self.paragraph,
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
            "paragraph": self.paragraph,
            "start": self.start,
            "end": self.end,
            "replacement": self.replacement,
            "suggested_by": self.suggested_by,
        }

    @classmethod
    def from_data(cls, data, registry) -> AcceptSuggestion:
        return cls(data["id"], data["paragraph"], data["start"], data["end"], data["replacement"], data["suggested_by"])

    def regions(self, model) -> tuple[Region, ...]:
        return (TextRange(self.paragraph, self.start, max(self.end, self.start + 1)),)

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
    return {**data, "paragraph": "b1" if data["paragraph"] == 0 else f"b{data['paragraph'] + 1}"}


_WRAP_SUMMARY = {
    "over": "put an object over the text",
    "around": "let the text flow around an object",
    "above-below": "put an object above and below the text",
    "behind": "put an object behind the text",
}


@register
@dataclass(frozen=True)
class SetObjectWrap(Command):
    """How the text flows round an object, and how far it keeps from it (D1061, D1064); where the object hangs and
    its size do not change. It is one step, so one undo takes back one press of the key that cycles the modes."""

    kind: ClassVar[str] = "composes.SetObjectWrap"
    id: str
    wrap: str
    gap: int

    @property
    def label(self) -> str:
        return "Wrap text"

    @property
    def summary(self) -> str:
        return _WRAP_SUMMARY.get(self.wrap, "changed how the text flows round an object").capitalize()

    def apply(self, ctx: Context[TextModel]) -> Command:
        model = ctx.model
        old = model.get_object(self.id)
        anchor = replace(old.anchor, wrap=self.wrap, gap=self.gap)
        anchor.check_wrap()
        new = replace(old, anchor=anchor)
        model.replace_object(new)
        ctx.emit(model.objects_changed(new.holder, changed=(new,)))
        return SetObjectWrap(self.id, old.anchor.wrap, old.anchor.gap)

    def to_data(self) -> dict:
        return {"id": self.id, "wrap": self.wrap, "gap": self.gap}

    @classmethod
    def from_data(cls, data, registry) -> SetObjectWrap:
        return cls(data["id"], data["wrap"], data["gap"])

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        return model.selection_of(self.id) if isinstance(model, TextModel) else ()

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, RemoveObject) and other.id == self.id else self

    def redacted(self) -> Command:
        return self
