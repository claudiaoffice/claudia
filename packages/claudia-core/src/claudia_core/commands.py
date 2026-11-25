"""Commands: every change to a document is a serializable, invertible command (E1.1, E1.3).

Contract
--------
* ``apply(ctx)`` performs the change and **returns its inverse**, itself a command. Undo is executing the
  inverse as a new command; nothing is ever rewound.
* A command that fails leaves the model unchanged (validate first, or use ``Batch``, which rolls back its
  children with their own inverses).
* Commands carry **final values**, never "work this out again": a random draw, a worker's result, a
  timestamp are all stored in the command, so replaying the log is deterministic.
* Commands are immutable plain data. ``kind`` is namespaced (``computes.SetCells``); ``schema`` is bumped
  whenever the data layout changes and an *upcaster* is registered for the old layout (E1.3).

Envelope (what the log stores): ``{"k": kind, "s": schema, "d": data}``.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Literal

from .errors import MissingUpcaster, SchemaTooNew, ServerOnly, UnknownCommand
from .revision import Revision

if TYPE_CHECKING:
    from .context import Context
    from .model import DocumentModel
    from .region import Region

#: Who may send a command kind (D2007): see :attr:`Command.sender`.
Sender = Literal["person", "server"]

_KIND = re.compile(r"[a-z][a-z0-9_]*\.[A-Za-z][A-Za-z0-9_.]*")


class Command(ABC):
    """One change to a document: immutable, serializable, and able to return its exact inverse.

    Subclasses set ``kind`` (namespaced, e.g. ``computes.SetCells``) and ``schema``, implement ``apply``,
    ``to_data`` and ``from_data``, and may override ``regions``, ``shifted_by`` (collaborative undo) and
    ``redacted`` (E1.8). ``apply`` mutates the model and returns the command that undoes it."""

    kind: ClassVar[str]
    schema: ClassVar[int] = 1
    undoable = True  # False for commands that are nobody's undo step (chat-like, checkpoints, ...)
    meta: ClassVar[bool] = False  # True: changes no model state, only the log (checkpoint, redaction)
    #: Who may send this command (D2007): ``"person"`` (the app or a script sends it), or ``"server"``, which makes it
    #: only through its own methods and their checks; :meth:`CommandRegistry.for_persons` refuses those.
    sender: ClassVar[Sender] = "person"

    @property
    def label(self) -> str:
        """Short human text for the history ("Insert rows")."""
        return self.kind

    @property
    def summary(self) -> str:
        """One sentence about what this command does ("B3 = 40"), for the history panel. Defaults to the label.

        It may name values, so it is not part of what survives redaction: a redacted command says what ``Redacted``
        says."""
        return self.label

    @abstractmethod
    def apply(self, ctx: Context) -> Command:
        """Change ``ctx.model`` and return the command that undoes exactly this change.

        Raise to refuse; the caller rolls back."""

    @abstractmethod
    def to_data(self) -> dict:
        """The plain-data (JSON-compatible) form that is stored in the log."""

    @classmethod
    @abstractmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> Command:
        """Rebuild the command from ``to_data``'s output; ``registry`` is for commands that contain commands."""

    def regions(self, model: DocumentModel) -> tuple[Region, ...]:
        """What this command will touch, in the coordinates of the *current* state of ``model``.

        Used for lock checks (undo refusal, editing a held region). Default: nothing lockable."""
        return ()

    def leaves(self) -> Iterator[Command]:
        """The commands that really change something: ``self``, or the parts of a ``Batch`` in order."""
        yield self

    def shifted_by(self, other: Command) -> Command | None:
        """This command as it must read after the *leaf* command ``other`` (by someone else) ran in between.

        Used when an author undoes an old step although colleagues have worked since. Commands that name
        things by address or id (cell A1, object 7) are unaffected: the default returns ``self``. Commands
        that name things by position (the 3rd character, row 12) shift. Return ``None`` if ``other`` makes
        this command meaningless or would make it undo someone else's work: the undo is then refused (E1.4)."""
        return self

    def ends_paragraph(self, paragraph_id: str) -> bool:
        """Does this command make the paragraph ``paragraph_id`` part of another one, or take it away? A command that
        names a paragraph by id (one that makes it a list item) cannot be undone past one that does. Default: no."""
        return False

    def redacted(self) -> Command:
        """A replacement that keeps what other commands depend on but not the content (E1.8).

        The contract (D720): the replacement keeps the *shape* of the change — the ids of what it makes, the places
        and lengths it touches — and loses everything a person wrote, typed, picked or imported, so that the steps
        after it still apply. A command whose later steps refer to what it created (a sheet, an object, the length
        of a text) overrides this and blanks in place; the default is a no-op tombstone, and a step that then no
        longer applies is blanked too (D722)."""
        return tombstone(self)

    def redacted_in(self, model: type[DocumentModel]) -> Command:
        """:meth:`redacted` for a command whose content only the app can blank (an import, a chart): ``model`` is
        the class of the document's model. Everything else ignores it."""
        return self.redacted()

    def stub(self) -> dict:
        """The non-secret identifying data that survives redaction (ids only, no content)."""
        return {}


def tombstone(command: Command) -> Command:
    """The content-free no-op a step becomes when nothing of its shape can be kept (D720, D722): its kind and the ids
    of ``stub`` only."""
    return Redacted(command.kind, command.stub())


def encode(command: Command) -> dict:
    """The stored form of a command: ``{"k": kind, "s": schema, "d": data}``."""
    return {"k": command.kind, "s": command.schema, "d": command.to_data()}


# --------------------------------------------------------------------------- registry
class CommandRegistry:
    """Kinds -> classes, plus the upcasters that bring old data up to the current schema."""

    def __init__(self):
        self._classes: dict[str, type[Command]] = {}
        self._upcasters: dict[tuple[str, int], Callable[[dict], dict]] = {}
        self._persons_only = False

    def register(self, cls: type[Command]) -> type[Command]:
        """Class decorator. Extensions (UserFunction/plugin commands) register the same way."""
        kind = getattr(cls, "kind", None)
        if not isinstance(kind, str) or not _KIND.fullmatch(kind):
            raise ValueError(f"{cls.__name__}.kind must be namespaced like 'computes.SetCells', got {kind!r}")
        if kind in self._classes and self._classes[kind] is not cls:
            raise ValueError(f"command kind {kind!r} is registered twice")
        self._classes[kind] = cls
        return cls

    def upcaster(self, kind: str, from_schema: int) -> Callable:
        """Decorator: ``fn(data) -> data`` turns schema ``from_schema`` data into ``from_schema + 1`` data."""

        def wrap(fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
            self._upcasters[(kind, from_schema)] = fn
            return fn

        return wrap

    def known(self, kind: str) -> bool:
        """Does the registry know this command kind?"""
        return kind in self._classes

    def schemas(self) -> dict[str, int]:
        """Every kind this registry understands -> its current schema (for the manifest check)."""
        return {kind: cls.schema for kind, cls in self._classes.items()}

    def class_of(self, kind: str) -> type[Command]:
        """The class registered for ``kind``; raises ``UnknownCommand``, or ``ServerOnly`` in a registry
        :meth:`for_persons` for a kind only the server makes."""
        try:
            cls = self._classes[kind]
        except KeyError:
            raise UnknownCommand(kind) from None
        if self._persons_only and cls.sender != "person":
            raise ServerOnly(kind)
        return cls

    def for_persons(self) -> CommandRegistry:
        """This registry as it decodes what a person sends (SEC-25, D2007): a command only the server makes is refused
        with ``ServerOnly``, at any depth, since a command that holds commands decodes them through the same
        registry."""
        persons = CommandRegistry()
        persons._classes, persons._upcasters, persons._persons_only = dict(self._classes), dict(self._upcasters), True
        return persons

    def decode(self, envelope: dict) -> Command:
        """Turn a stored envelope into a command, upcasting old schemas; ``SchemaTooNew`` if it is from the future."""
        kind, schema, data = envelope["k"], envelope["s"], envelope["d"]
        cls = self.class_of(kind)
        if schema > cls.schema:
            raise SchemaTooNew(kind, schema, cls.schema)
        while schema < cls.schema:
            step = self._upcasters.get((kind, schema))
            if step is None:
                raise MissingUpcaster(kind, schema)
            data = step(data)
            schema += 1
        return cls.from_data(data, self)

    def merged(self, other: CommandRegistry) -> CommandRegistry:
        """A new registry with everything of both (the core commands plus an app's)."""
        both = CommandRegistry()
        both._classes = {**self._classes, **other._classes}
        both._upcasters = {**self._upcasters, **other._upcasters}
        return both


# --------------------------------------------------------------------------- core commands
core_commands = CommandRegistry()


@core_commands.register
@dataclass(frozen=True)
class Batch(Command):
    """Several commands, one undo step, all or nothing."""

    kind: ClassVar[str] = "core.Batch"
    commands: tuple[Command, ...]
    name: str | None = None

    @property
    def label(self) -> str:
        return self.name or (self.commands[0].label if len(self.commands) == 1 else f"{len(self.commands)} changes")

    @property
    def summary(self) -> str:
        if self.name:
            return self.name
        shown = "; ".join(c.summary for c in self.commands[:3])
        return shown if len(self.commands) <= 3 else f"{shown}; and {len(self.commands) - 3} more"

    @property
    def undoable(self) -> bool:  # type: ignore[override]
        return all(c.undoable for c in self.commands)

    def apply(self, ctx: Context) -> Command:
        inverses: list[Command] = []
        try:
            for command in self.commands:
                inverses.append(command.apply(ctx))  # noqa: PERF401  (a failure must leave the list as far as it got)
        except BaseException:
            for inverse in reversed(inverses):  # roll back what already happened
                inverse.apply(ctx)
            raise
        return Batch(tuple(reversed(inverses)), self.name)

    def to_data(self) -> dict:
        return {"name": self.name, "items": [encode(c) for c in self.commands]}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> Batch:
        return cls(tuple(registry.decode(item) for item in data["items"]), data.get("name"))

    def regions(self, model: DocumentModel) -> tuple[Region, ...]:
        return tuple(r for c in self.commands for r in c.regions(model))

    def leaves(self) -> Iterator[Command]:
        for command in self.commands:
            yield from command.leaves()

    def shifted_by(self, other: Command) -> Command | None:
        shifted = [c.shifted_by(other) for c in self.commands]
        return None if any(c is None for c in shifted) else Batch(tuple(shifted), self.name)  # type: ignore[arg-type]

    def redacted(self) -> Command:
        return Batch(tuple(c.redacted() for c in self.commands), self.name)

    def redacted_in(self, model: type[DocumentModel]) -> Command:
        return Batch(tuple(c.redacted_in(model) for c in self.commands), self.name)


@core_commands.register
@dataclass(frozen=True)
class Setup(Batch):
    """What a new document starts with, made by the server when it creates the document (UX-33): the commands of
    ``DocumentModel.setup_commands`` as one entry. It is in the history, under its maker's name, but it is nobody's undo
    step: a person's first Ctrl+Z must not take away the first sheet of a workbook or the language of a text."""

    kind: ClassVar[str] = "core.Setup"
    sender: ClassVar[Sender] = "server"

    @property
    def label(self) -> str:
        return self.name or "Set up the document"

    @property
    def undoable(self) -> bool:  # type: ignore[override]
        return False

    def redacted(self) -> Command:
        return Setup(tuple(c.redacted() for c in self.commands), self.name)

    def redacted_in(self, model: type[DocumentModel]) -> Command:
        return Setup(tuple(c.redacted_in(model) for c in self.commands), self.name)


@dataclass(frozen=True)
class OriginalLine:
    """One line of the history of the document an export was made of (D2005): ``when`` it happened, ``who`` did it (a
    name as text, ``None``: unknown) and ``what``: the step as that document's history said it, or the words of a
    message for everybody in its chat (``said``). Text only: nobody named here is given anything."""

    when: str
    who: str | None
    what: str
    said: bool = False

    def to_data(self) -> dict:
        """The plain-data form: ``{when, who, what, said}``."""
        return {"when": self.when, "who": self.who, "what": self.what, "said": self.said}

    @classmethod
    def from_data(cls, data: dict) -> OriginalLine:
        """Inverse of :meth:`to_data`."""
        return cls(data["when"], data["who"], data["what"], bool(data.get("said", False)))


@core_commands.register
@dataclass(frozen=True)
class Import(Command):
    """First entry of an imported document (D438): the state an import made of a file (a docx, an xlsx, ...), as the
    model's own ``serialize()`` form, and what the file was. The file itself is not in the log; when it is kept, it
    sits sealed in the document file and ``sha256`` says which bytes it is (D439).

    It is in the history, under the name of who imported it, but nobody's undo step. It is redacted by blanking the
    state it carries, in full or in parts, with the model's own :meth:`~claudia_core.DocumentModel.blank`, which keeps
    every id and length so that the later entries, all changes of that state, still apply (D723).

    An owner's export brings the history and chat of the document it was made of: they come in as ``original``, one
    read-only note of this step, oldest line first (D2005). It is part of the import, so it is nobody's undo step
    either."""

    kind: ClassVar[str] = "core.Import"
    sender: ClassVar[Sender] = "server"
    undoable = False
    name: str  # the file's name, as the person's computer called it
    fmt: str  # "docx", "odt", "xlsx", "ods", "pptx" or "odp"
    state: dict = field(repr=False)
    sha256: str | None = None  # of the original file's bytes
    kept: bool = False  # is the original file kept in the document?
    original: tuple[OriginalLine, ...] = ()  # the history of the original, when the file is an owner's export

    @property
    def label(self) -> str:
        return f"Imported {self.name}"

    def apply(self, ctx: Context) -> Command:
        before = ctx.model.serialize()
        ctx.model.load_state(self.state)
        return Import(self.name, self.fmt, before)

    def to_data(self) -> dict:
        data: dict = {"name": self.name, "fmt": self.fmt, "state": self.state, "sha256": self.sha256, "kept": self.kept}
        if self.original:
            data["original"] = [line.to_data() for line in self.original]
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> Import:
        return cls(
            data["name"],
            data["fmt"],
            data["state"],
            data.get("sha256"),
            bool(data.get("kept", False)),
            tuple(OriginalLine.from_data(line) for line in data.get("original", ())),
        )

    def redacted(self) -> Command:
        """Only the app can blank an import: see :meth:`redacted_in`. Without the model nothing is taken away."""
        return self

    def redacted_in(self, model: type[DocumentModel]) -> Command:
        return self.blanked(model)

    def blanked(self, model: type[DocumentModel], parts: frozenset[str] | None = None) -> Import:
        """The import with its content blanked by ``model`` (D723): all of it, or only the things in ``parts`` (ids
        the app knows: paragraphs, sheets and cell ranges, slides, objects). The file goes in either case: its
        digest and the kept original say what the file held. A full blanking also forgets the file's name and the
        history of the original (D2005), which can say as much as what was in it; blanking in parts keeps both, since
        the person chose what to take away."""
        state = model.restore(self.state)
        state.blank(parts)
        if parts is None:
            return Import("", self.fmt, state.serialize(), None, False)
        return Import(self.name, self.fmt, state.serialize(), None, False, self.original)


@core_commands.register
@dataclass(frozen=True)
class Redacted(Command):
    """What a command becomes when it is redacted: kind and ids stay, the content is gone. Applies as a no-op."""

    kind: ClassVar[str] = "core.Redacted"
    sender: ClassVar[Sender] = "server"
    undoable = False
    meta: ClassVar[bool] = False  # not meta: its place in the order still counts as a state revision
    original_kind: str
    ids: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return "Redacted"

    def apply(self, ctx: Context) -> Command:
        return self

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"original_kind": self.original_kind, "ids": self.ids}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> Redacted:
        return cls(data["original_kind"], data.get("ids", {}))

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class Checkpoint(Command):
    """A label on a revision (File > Save). Changes no state; ``marks`` is the state revision it labels."""

    kind: ClassVar[str] = "core.Checkpoint"
    sender: ClassVar[Sender] = "server"
    undoable = False
    meta: ClassVar[bool] = True
    label_text: str
    marks: Revision

    @property
    def label(self) -> str:
        return f"Checkpoint: {self.label_text}"

    def apply(self, ctx: Context) -> Command:
        return self

    def to_data(self) -> dict:
        return {"label": self.label_text, "marks": self.marks.to_data()}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> Checkpoint:
        return cls(data["label"], Revision.parse(data["marks"]))

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class Redaction(Command):
    """The record that these revisions and chat messages were redacted. Carries no content. A no-op when replayed.

    ``chat`` holds the numbers of the chat messages (D724); a record written before chat could be redacted has
    none, and one that names none is written without it, so the older form reads and writes the same."""

    kind: ClassVar[str] = "core.Redaction"
    sender: ClassVar[Sender] = "server"
    undoable = False
    meta: ClassVar[bool] = True
    targets: tuple[Revision, ...]
    chat: tuple[int, ...] = ()

    @property
    def label(self) -> str:
        parts = [_count(len(self.targets), "change")] if self.targets or not self.chat else []
        if self.chat:
            parts.append(_count(len(self.chat), "message"))
        return "Redacted " + " and ".join(parts)

    def apply(self, ctx: Context) -> Command:
        return self

    def to_data(self) -> dict:
        data: dict = {"targets": [t.to_data() for t in self.targets]}
        if self.chat:
            data["chat"] = list(self.chat)
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> Redaction:
        return cls(tuple(Revision.parse(t) for t in data["targets"]), tuple(data.get("chat", ())))

    def redacted(self) -> Command:
        return self


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


@core_commands.register
@dataclass(frozen=True)
class Restore(Command):
    """First entry of the line a checkpoint restore starts: who went back to which state, and from which line."""

    kind: ClassVar[str] = "core.Restore"
    sender: ClassVar[Sender] = "server"
    undoable = False
    meta: ClassVar[bool] = True
    label_text: str
    marks: Revision
    from_branch: str

    @property
    def label(self) -> str:
        return f"Restored “{self.label_text}”"

    def apply(self, ctx: Context) -> Command:
        return self

    def to_data(self) -> dict:
        return {"label": self.label_text, "marks": self.marks.to_data(), "from": self.from_branch}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> Restore:
        return cls(data["label"], Revision.parse(data["marks"]), data["from"])

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class Switch(Command):
    """First entry after the document moved to an existing line (the way back after a restore): who, and from where."""

    kind: ClassVar[str] = "core.Switch"
    sender: ClassVar[Sender] = "server"
    undoable = False
    meta: ClassVar[bool] = True
    from_branch: str

    @property
    def label(self) -> str:
        return f"Switched from the line “{self.from_branch}”"

    def apply(self, ctx: Context) -> Command:
        return self

    def to_data(self) -> dict:
        return {"from": self.from_branch}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> Switch:
        return cls(data["from"])

    def redacted(self) -> Command:
        return self


def new_registry() -> CommandRegistry:
    """A registry that already knows the core commands; an app registers its own on top."""
    return CommandRegistry().merged(core_commands)
