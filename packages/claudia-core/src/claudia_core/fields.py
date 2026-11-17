"""Fields: something in the middle of a paragraph's words that the document works out (step H of
``claudiaoffice-log/notes/text-structure-across-apps.md``; design in ``e9-composes-outline-references-toc.md``, 6).

A field sits at one U+FFFC (OBJECT REPLACEMENT CHARACTER) of the paragraph's text; the *k*-th U+FFFC is the *k*-th of
the paragraph's ``fields``. So a field needs no following of its own: carets, zones, suggestions, authorship and locks
treat it as one ordinary character, typing carries the fields of the U+FFFC it puts in or takes out, and splitting or
joining a paragraph partitions or joins the tuple by counting U+FFFC. Words that come from a person (typing, paste, a
whole replacement, an import) have U+FFFC taken out (:func:`~claudia_core.plain`), so a field is only ever made by a
command that makes one.

* :class:`RefField` (kind ``ref``) is a reference: the id of the thing it points at (a paragraph, an object) and what
  it shows, its number, its words, both, its page or its name. What it shows is derived
  (:meth:`~claudia_core.TextStructure.shown`), so it never goes stale.
* :class:`SetField` changes what a field shows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol

from .commands import Command, CommandRegistry, core_commands

if TYPE_CHECKING:
    from .context import Context
    from .region import Region

#: The character a field stands at in a paragraph's text.
FIELD_CHAR = "￼"
type Show = Literal["number", "text", "number-text", "page", "name"]
#: What a reference can show: the target's number, its words, both, its page (from the layout) or its name.
SHOWS: tuple[Show, ...] = ("number", "text", "number-text", "page", "name")


def plain(text: str) -> str:
    """``text`` without U+FFFC: words a person wrote cannot make a field."""
    return text.replace(FIELD_CHAR, "")


def fields_before(text: str, offset: int) -> int:
    """How many fields stand before ``offset`` in a paragraph's ``text``: the index of the next field."""
    return text.count(FIELD_CHAR, 0, offset)


@dataclass(frozen=True)
class RefField:
    """A reference to a thing of the document: ``target`` is its id (a paragraph, an object; D550, D554), ``show`` what
    the reference reads as."""

    kind: ClassVar[str] = "ref"
    target: str
    show: Show = "number"

    def check(self) -> None:
        """``ValueError`` with a sentence if the field makes no sense."""
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("a reference needs the id of what it points at")
        if self.show not in SHOWS:
            raise ValueError(f"a reference shows one of {', '.join(SHOWS)}, not {self.show!r}")

    def with_show(self, show: Show) -> RefField:
        """The same reference, showing ``show``."""
        return RefField(self.target, show)

    def to_data(self) -> dict:
        """The plain-data form that goes into snapshots, commands and events."""
        return {"kind": self.kind, "target": self.target, "show": self.show}

    @classmethod
    def from_data(cls, data: dict) -> RefField:
        """Inverse of :meth:`to_data`."""
        return cls(data["target"], data.get("show", "number"))


type Field = RefField
#: The kinds of field, by their ``kind``: the place a new kind (a citation, a page count) registers.
FIELD_KINDS: dict[str, type[RefField]] = {RefField.kind: RefField}


def field_from_data(data: dict) -> Field:
    """A field from its plain-data form; ``ValueError`` for a kind this installation does not know."""
    kind = FIELD_KINDS.get(data.get("kind", ""))
    if kind is None:
        raise ValueError(f"a field of kind {data.get('kind')!r} is not known here")
    found = kind.from_data(data)
    found.check()
    return found


@dataclass(frozen=True)
class Shown:
    """What a field reads as now: its words, and its ``state``: ``ok``; ``broken`` (what it points at is gone);
    ``page`` (the page is the layout's to fill in; ``text`` is then empty)."""

    text: str
    state: Literal["ok", "broken", "page"] = "ok"

    def to_data(self) -> dict:
        """The plain-data form that is sent to clients."""
        return {"text": self.text, "state": self.state}


@dataclass(frozen=True)
class FieldsChanged:
    """The fields of the paragraph ``paragraph`` read as ``shown`` now, in order (wire type ``fields``)."""

    paragraph: str
    shown: tuple[Shown, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "fields", "paragraph": self.paragraph, "fields": [s.to_data() for s in self.shown]}


class FieldHost(Protocol):
    """What :class:`SetField` needs of a model: the fields of any of its paragraphs by id, whatever holds it."""

    def fields_of(self, paragraph: str) -> tuple[Field, ...]:
        """The fields of a paragraph, in order."""
        ...

    def put_fields(self, paragraph: str, fields: tuple[Field, ...]) -> tuple[object, ...]:
        """Give a paragraph other fields (as many as before); the events that tell the clients."""
        ...

    def text_regions(self, paragraph: str, start: int, end: int) -> tuple[Region, ...]:
        """What a change of these characters touches."""
        ...


def _host(ctx: Context) -> FieldHost:
    model = ctx.model
    if not all(hasattr(model, name) for name in ("fields_of", "put_fields")):
        raise TypeError(f"The {model.app} model has no fields")
    return model


@core_commands.register
@dataclass(frozen=True)
class SetField(Command):
    """Make the ``index``-th field of a paragraph ``field`` (a reference's Show As). Its inverse puts the old one
    back."""

    kind: ClassVar[str] = "core.SetField"
    paragraph: str
    index: int
    field: Field

    @property
    def label(self) -> str:
        return "Change a reference"

    @property
    def summary(self) -> str:
        return f"Made a reference show its {self.field.show.replace('-', ' and ')}"

    def apply(self, ctx: Context) -> Command:
        host = _host(ctx)
        self.field.check()
        fields = host.fields_of(self.paragraph)
        if not 0 <= self.index < len(fields):
            raise IndexError("there is no such field in this paragraph")
        old = fields[self.index]
        for event in host.put_fields(self.paragraph, (*fields[: self.index], self.field, *fields[self.index + 1 :])):
            ctx.emit(event)
        return SetField(self.paragraph, self.index, old)

    def to_data(self) -> dict:
        return {"paragraph": self.paragraph, "index": self.index, "field": self.field.to_data()}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetField:
        return cls(data["paragraph"], data["index"], field_from_data(data["field"]))

    def regions(self, model: object) -> tuple[Region, ...]:
        host: FieldHost = model  # type: ignore[assignment]
        return host.text_regions(self.paragraph, 0, 1) if hasattr(model, "text_regions") else ()

    def redacted(self) -> Command:
        return self
