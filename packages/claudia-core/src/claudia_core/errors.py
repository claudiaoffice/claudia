"""Errors the kernel raises. Each carries a message that can be shown to a person."""

from __future__ import annotations

from collections.abc import Sequence


class KernelError(Exception):
    """Base of everything the kernel raises on purpose."""


class UnknownCommand(KernelError):
    """A log holds a command kind no installed code understands (usually a missing extension)."""

    def __init__(self, kind: str):
        super().__init__(
            f"The document uses the command {kind!r}, which this installation does not know. "
            "It probably comes from an extension (a UserFunction or plugin) that is not installed here."
        )
        self.kind = kind


class SchemaTooNew(KernelError):
    """A command was written by a newer version than this one understands."""

    def __init__(self, kind: str, found: int, known: int):
        super().__init__(
            f"The document was written by a newer version of Claudia: command {kind!r} has "
            f"schema {found}, this version understands up to {known}. Please update Claudia."
        )
        self.kind, self.found, self.known = kind, found, known


class MissingUpcaster(KernelError):
    """A command of an old schema cannot be brought up to date (a bug in the code base)."""

    def __init__(self, kind: str, schema: int):
        super().__init__(f"No upcaster for command {kind!r} from schema {schema}.")


class RevisionMismatch(KernelError):
    """An entry was offered out of order (its revision or parent is not the next one)."""


class RegionHeld(KernelError):
    """The change would touch a region somebody else holds (a lock)."""

    def __init__(self, holders: Sequence[tuple[str, object]]):
        names = ", ".join(sorted({owner for owner, _ in holders}))
        super().__init__(f"{names} is working there right now. Try again when they are done.")
        self.holders = holders


class StaleEdit(KernelError):
    """An edit was written against a view that is not part of the document's current line any more.

    Happens to edits in flight when somebody restores a checkpoint or switches the line: the change was meant for
    a state that no longer exists, so it is refused instead of landing on a different one."""

    def __init__(self, base: object, line: str):
        super().__init__(
            f"The document changed under you (it now continues on the line “{line}”). "
            "Your change was made on a view that is gone, so it was not applied. Reload the document and try again."
        )
        self.base = base
        self.line = line


class UndoRefused(RegionHeld):
    """Undo or redo would touch a region somebody else holds."""


class UndoConflict(KernelError):
    """Undo or redo is not possible without damaging somebody else's later work, or no longer applies at all."""


class RedactionError(KernelError):
    """A redaction request that cannot be carried out."""


class ReplayError(KernelError):
    """Replaying a log failed at one entry (a command that cannot be applied any more)."""

    def __init__(self, revision: object, cause: BaseException):
        super().__init__(f"Replay failed at revision {revision}: {cause}")
        self.revision = revision
        self.__cause__ = cause
