"""Typing into any paragraph, character by character (step G of
``claudiaoffice-log/notes/text-structure-across-apps.md``, section 3.1).

A paragraph of a composes text and the words of a text box on a slide are the same entity (D181), so they are typed into
by the same two commands: :class:`InsertText` puts characters in at an offset, :class:`DeleteText` takes some out. Each
keeps who wrote which character (the runs), so an edit is attributed to the person who made it and not, as a whole
replacement would, to whoever saved last.

* A *span* is ``(paragraph, start, end)``: characters ``start <= i < end`` of one paragraph; a caret is an empty span.
  Carets, zones, suggestions and the commands that undo old steps hold spans, and all of them follow edits made by
  somebody else. The rule for each command lives with the command (:meth:`~claudia_core.TextCommand.follow`);
  regions, suggestions and ``shifted_by`` only ask.
* The model says how it finds a paragraph and what it tells the clients (:class:`TypingHost`): composes for the
  paragraphs of its text and the words of its floating objects, creates for the words of its objects.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar, Protocol

from .commands import Command, CommandRegistry, core_commands
from .fields import FIELD_CHAR, Field, field_from_data, plain
from .paragraphs import Run, runs_from_data, runs_to_data

if TYPE_CHECKING:
    from .context import Context
    from .region import Region

Span = tuple[str, int, int]
#: Characters of typed text a history sentence quotes.
SHOWN = 40


def _quote(text: str) -> str:
    return f"“{text if len(text) <= SHOWN else text[: SHOWN - 1] + '…'}”"


class TextCommand(Command, ABC):
    """A command that changes the words or the paragraphs of a text and therefore moves spans."""

    def follow(self, span: Span) -> Span:
        """Where ``span`` is after this command ran. Never fails: a stretch that was cut away becomes empty."""
        return span

    def breaks(self, span: Span) -> bool:
        """Does this command make ``span`` meaningless for undoing a step that was written for it?

        A colleague typing inside a passage, deleting part of it or splitting it in two does."""
        return False


class TypingHost(Protocol):
    """What :class:`InsertText` and :class:`DeleteText` need of a model: any of its paragraphs by id, whatever holds
    it. Each change returns the events that tell the clients."""

    def insert_text(
        self, paragraph: str, offset: int, text: str, runs: list[Run], fields: tuple[Field, ...]
    ) -> tuple[object, ...]:
        """Put ``text``, written as ``runs`` say and with the ``fields`` of its U+FFFC, into the paragraph at
        ``offset``."""
        ...

    def remove_text(
        self, paragraph: str, start: int, end: int
    ) -> tuple[str, list[Run], tuple[Field, ...], tuple[object, ...]]:
        """Cut ``start <= i < end`` out of the paragraph: what was cut, with its runs and fields, and the events."""
        ...

    def text_regions(self, paragraph: str, start: int, end: int) -> tuple[Region, ...]:
        """What a change of these characters touches, for the zones of the people at work."""
        ...

    def text_moved(self, command: TextCommand) -> tuple[object, ...]:
        """Let what hangs from the text follow ``command`` (suggestions, floating objects); the events that say so."""
        ...


def _host(ctx: Context) -> TypingHost:
    model = ctx.model
    if not all(hasattr(model, name) for name in ("insert_text", "remove_text", "text_moved")):
        raise TypeError(f"The {model.app} model has no paragraphs to type into")
    return model


def _emit(ctx: Context, events: tuple[object, ...]) -> None:
    for event in events:
        ctx.emit(event)


@core_commands.register
@dataclass(frozen=True)
class InsertText(TextCommand):
    """Type ``text`` into a paragraph at ``offset``. ``by`` says who wrote it when that is not whoever runs the
    command (the inverse of a delete puts back text with its original authors); ``fields`` are the fields of the
    U+FFFC in ``text`` (a reference put in, a delete's fields put back)."""

    kind: ClassVar[str] = "core.InsertText"
    paragraph: str
    offset: int
    text: str
    by: tuple[Run, ...] = ()
    fields: tuple[Field, ...] = ()

    @property
    def label(self) -> str:
        return "Type"

    @property
    def summary(self) -> str:
        return f"typed {_quote(self.text)}"

    def apply(self, ctx: Context) -> Command:
        host = _host(ctx)
        runs = list(self.by) or ([Run(len(self.text), ctx.author)] if self.text else [])
        _emit(ctx, host.insert_text(self.paragraph, self.offset, self.text, runs, self.fields))
        _emit(ctx, host.text_moved(self))
        return DeleteText(self.paragraph, self.offset, len(self.text))

    def to_data(self) -> dict:
        data: dict = {"paragraph": self.paragraph, "offset": self.offset, "text": self.text}
        if self.by:
            data["by"] = runs_to_data(list(self.by))
        if self.fields:
            data["fields"] = [f.to_data() for f in self.fields]
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> InsertText:
        by = tuple(runs_from_data(data.get("by", [])))
        fields = tuple(field_from_data(f) for f in data.get("fields", ()))
        return cls(data["paragraph"], data["offset"], data["text"], by, fields)

    def regions(self, model: object) -> tuple[Region, ...]:
        host: TypingHost = model  # type: ignore[assignment]
        return host.text_regions(self.paragraph, self.offset, self.offset + max(1, len(self.text)))

    def follow(self, span: Span) -> Span:
        paragraph, start, end = span
        n = len(self.text)
        if paragraph != self.paragraph:
            return span
        if self.offset <= start:
            return (paragraph, start + n, end + n)
        if self.offset < end:
            return (paragraph, start, end + n)
        return span

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

    def redacted(self) -> Command:
        # same length, so later offsets still hold; the U+FFFC stay with their fields (an id, not words)
        return replace(self, text="".join(c if c == FIELD_CHAR else "█" for c in self.text))


@core_commands.register
@dataclass(frozen=True)
class DeleteText(TextCommand):
    """Delete ``length`` characters of a paragraph from ``offset`` on."""

    kind: ClassVar[str] = "core.DeleteText"
    paragraph: str
    offset: int
    length: int

    @property
    def label(self) -> str:
        return "Delete text"

    @property
    def summary(self) -> str:
        return f"deleted {self.length} character{'' if self.length == 1 else 's'}"

    def apply(self, ctx: Context) -> Command:
        host = _host(ctx)
        text, runs, fields, events = host.remove_text(self.paragraph, self.offset, self.offset + self.length)
        _emit(ctx, events)
        _emit(ctx, host.text_moved(self))
        return InsertText(self.paragraph, self.offset, text, tuple(runs), fields)

    def to_data(self) -> dict:
        return {"paragraph": self.paragraph, "offset": self.offset, "length": self.length}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> DeleteText:
        return cls(data["paragraph"], data["offset"], data["length"])

    def regions(self, model: object) -> tuple[Region, ...]:
        host: TypingHost = model  # type: ignore[assignment]
        return host.text_regions(self.paragraph, self.offset, self.offset + max(1, self.length))

    def follow(self, span: Span) -> Span:
        paragraph, start, end = span
        if paragraph != self.paragraph:
            return span
        cut = self.offset

        def moved(position: int) -> int:
            return position - min(max(position - cut, 0), self.length)

        return (paragraph, moved(start), moved(end))

    def breaks(self, span: Span) -> bool:
        paragraph, start, end = span
        return paragraph == self.paragraph and start < end and self.offset < end and self.offset + self.length > start

    def shifted_by(self, other: Command) -> Command | None:
        """Deleting what I typed: follow colleagues' typing before it; refuse if they typed in it or cut part of it."""
        if not isinstance(other, TextCommand):
            return self
        span = (self.paragraph, self.offset, self.offset + self.length)
        if other.breaks(span):
            return None
        paragraph, start, end = other.follow(span)
        return replace(self, paragraph=paragraph, offset=start, length=end - start)

    def redacted(self) -> Command:
        return self


def word_changes(paragraph: str, old: str, new: str) -> tuple[TextCommand, ...]:
    """The steps that turn the words ``old`` of a paragraph into ``new`` by changing only what differs between them
    (the common start and end stay, with who wrote them, and their fields): a delete and an insert, either or both, or
    nothing. What is put in makes no field: a U+FFFC in it that is not one of the kept ones is left out."""
    start = 0
    while start < min(len(old), len(new)) and old[start] == new[start]:
        start += 1
    end = 0
    while end < min(len(old), len(new)) - start and old[len(old) - 1 - end] == new[len(new) - 1 - end]:
        end += 1
    removed, added = old[start : len(old) - end], plain(new[start : len(new) - end])
    steps: list[TextCommand] = []
    if removed:
        steps.append(DeleteText(paragraph, start, len(removed)))
    if added:
        steps.append(InsertText(paragraph, start, added))
    return tuple(steps)
