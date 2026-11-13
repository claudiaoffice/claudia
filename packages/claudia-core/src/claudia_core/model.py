"""DocumentModel: the small interface each app implements (E1.1).

The kernel never looks inside a document. It asks the model to

* ``apply`` a command and hand back the inverse,
* ``describe_regions`` a command will touch,
* ``serialize`` / ``restore`` its state (a snapshot is only a cache, D15) and say which ``state_schema`` that is,
* ``settle`` once after each command (recalculation lives here, not in the kernel),
* list what it ``requirements`` the server must provide (fonts, UserFunctions; E1.9).

Nothing in this module or its siblings does I/O.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Self

from .revision import Revision

if TYPE_CHECKING:
    from .commands import Command, CommandRegistry
    from .context import Context
    from .manifest import Requirements
    from .region import Region


class DocumentModel(ABC):
    """What an app (computes, composes, creates) implements so that the kernel can run its documents.

    A model holds the state, applies commands to it (through ``Command.apply``), serializes it for snapshots, and
    describes the regions a command touches. It never does I/O and never decides who may do what."""

    app: ClassVar[str]  # "computes", "composes", "creates", or a test app
    state_schema: ClassVar[int] = 1
    registry: ClassVar[CommandRegistry]  # the commands this app (and its extensions) understand

    # -- lifecycle ---------------------------------------------------------------
    @classmethod
    @abstractmethod
    def empty(cls) -> Self:
        """A new, empty document: the state before the first command."""

    @classmethod
    def setup_commands(cls, language: str | None) -> tuple[Command, ...]:
        """What a new document starts with beyond :meth:`empty`, as commands: a workbook its first sheet, a text its
        language. ``language`` is the language of its maker's interface (D915), or ``None`` when that is not a language
        tag. The server runs them once, when it creates the document, as one :class:`~claudia_core.Setup` entry: in
        the history, but nobody's undo step (UX-33). None by default."""
        return ()

    @abstractmethod
    def serialize(self) -> dict:
        """Plain JSON-able state. Equal states must serialize equally (tests compare them)."""

    @classmethod
    @abstractmethod
    def restore(cls, state: dict) -> Self:
        """Build a model from ``serialize()``'s output (a snapshot)."""

    # -- the three verbs ---------------------------------------------------------
    def apply(self, command: Command, ctx: Context) -> Command:
        """Apply ``command`` and return its inverse. Models may wrap this; the default delegates."""
        return command.apply(ctx)

    def describe_regions(self, command: Command) -> tuple[Region, ...]:
        """The regions ``command`` would touch, for locks and undo refusal."""
        return command.regions(self)

    def settle(self, ctx: Context) -> None:
        """Called once after every command (also after a rolled-back one, ``ctx.failed``): recalculate here."""

    # -- regions on the wire -----------------------------------------------------
    def region_from_data(self, data: dict) -> Region:
        """Read a region sent by a client (its ``to_data`` form)."""
        raise NotImplementedError(f"{self.app} cannot read regions from data")

    # -- requirements ------------------------------------------------------------
    def requirements(self) -> Requirements:
        """The functions and fonts this document needs from the server it is opened on."""
        from .manifest import Requirements

        return Requirements()

    def mark_stale(self, functions: Iterable[str]) -> None:
        """The digest of these functions changed: results computed by them are out of date."""


@dataclass(frozen=True)
class Snapshot:
    """A cache of the state at one revision. Deleting it never loses anything (E1.2)."""

    rev: Revision
    app: str
    state_schema: int
    state: dict

    def to_data(self) -> dict:
        """The plain-data form of the snapshot."""
        return {"rev": str(self.rev), "app": self.app, "state_schema": self.state_schema, "state": self.state}

    @classmethod
    def from_data(cls, data: dict) -> Snapshot:
        """Inverse of ``to_data``."""
        return cls(Revision.parse(data["rev"]), data["app"], data["state_schema"], data["state"])
