"""Errors the kernel raises. Each carries a message that can be shown to a person.

That message is English prose, fixed at the raise site — fine for a log or a traceback, not for translation. Every
error also carries ``code``: a short, stable, machine-readable name for *which* error this is, independent of
wording. It is the groundwork for i18n (E5.7, D31): a server or client that wants the message in another language
looks up ``code`` in its own catalog and renders it from the error's existing instance attributes (``kind`` on
``UnknownCommand``, ``holders`` on ``RegionHeld``, and so on) instead of re-parsing the English sentence. The kernel
itself does no translating and depends on no catalog — it only names what happened.

``code`` is a plain class attribute, not part of ``__init__``: adding or reading it never changes a class's public
signature (docs/versioning.md), so this is additive and needs no version bump of its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar


class KernelError(Exception):
    """Base of everything the kernel raises on purpose.

    ``code`` identifies the kind of error for translation and client branching; subclasses that are raised with no
    arguments inherit it unless they set their own."""

    code: ClassVar[str] = "kernel_error"


class UnknownCommand(KernelError):
    """A log holds a command kind no installed code understands (usually a missing extension)."""

    code: ClassVar[str] = "unknown_command"

    def __init__(self, kind: str):
        super().__init__(
            f"The document uses the command {kind!r}, which this installation does not know. "
            "It probably comes from an extension (a UserFunction or plugin) that is not installed here."
        )
        self.kind = kind


class SchemaTooNew(KernelError):
    """A command was written by a newer version than this one understands."""

    code: ClassVar[str] = "schema_too_new"

    def __init__(self, kind: str, found: int, known: int):
        super().__init__(
            f"The document was written by a newer version of Claudia: command {kind!r} has "
            f"schema {found}, this version understands up to {known}. Please update Claudia."
        )
        self.kind, self.found, self.known = kind, found, known


class MissingUpcaster(KernelError):
    """A command of an old schema cannot be brought up to date (a bug in the code base)."""

    code: ClassVar[str] = "missing_upcaster"

    def __init__(self, kind: str, schema: int):
        super().__init__(f"No upcaster for command {kind!r} from schema {schema}.")
        self.kind, self.schema = kind, schema


class RevisionMismatch(KernelError):
    """An entry was offered out of order (its revision or parent is not the next one)."""

    code: ClassVar[str] = "revision_mismatch"


class RegionHeld(KernelError):
    """The change would touch a region somebody else holds (a lock)."""

    code: ClassVar[str] = "region_held"

    def __init__(self, holders: Sequence[tuple[str, object]]):
        names = ", ".join(sorted({owner for owner, _ in holders}))
        super().__init__(f"{names} is working there right now. Try again when they are done.")
        self.holders = holders


class StaleEdit(KernelError):
    """An edit was written against a view that is not part of the document's current line any more.

    Happens to edits in flight when somebody restores a checkpoint or switches the line: the change was meant for
    a state that no longer exists, so it is refused instead of landing on a different one."""

    code: ClassVar[str] = "stale_edit"

    def __init__(self, base: object, line: str):
        super().__init__(
            f"The document changed under you (it now continues on the line “{line}”). "
            "Your change was made on a view that is gone, so it was not applied. Reload the document and try again."
        )
        self.base = base
        self.line = line


class UndoRefused(RegionHeld):
    """Undo or redo would touch a region somebody else holds."""

    code: ClassVar[str] = "undo_refused"


class UndoConflict(KernelError):
    """Undo or redo is not possible without damaging somebody else's later work, or no longer applies at all."""

    code: ClassVar[str] = "undo_conflict"


class RedactionError(KernelError):
    """A redaction request that cannot be carried out."""

    code: ClassVar[str] = "redaction_error"


class ReplayError(KernelError):
    """Replaying a log failed at one entry (a command that cannot be applied any more)."""

    code: ClassVar[str] = "replay_error"

    def __init__(self, revision: object, cause: BaseException):
        super().__init__(f"Replay failed at revision {revision}: {cause}")
        self.revision = revision
        self.__cause__ = cause
