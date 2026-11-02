"""Per-author undo and redo (E1.4), ported from the demo and made replay-friendly.

History never rewinds anything. When an author's command ("do") has run, its inverse waits on that author's undo
stack. Undo *executes* the inverse as a new command (origin ``undo``, ``of`` = the revision it reverses), which
puts the inverse of the inverse on the redo stack.

The stacks are driven only by what the log says happened (``record``), not by who called ``undo``. Therefore
replaying a log rebuilds everybody's undo stacks exactly, and live use and replay cannot disagree. The
stacks are a cache: a document opened from a snapshot starts with empty ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .commands import Command

if TYPE_CHECKING:
    from .log import Entry
    from .revision import Revision

LIMIT = 200


@dataclass(frozen=True)
class Step:
    label: str
    command: Command  # executing it undoes (or redoes) the step
    rev: Revision  # the revision whose effect this step reverses


class History:
    """One author's undo and redo stacks, built from the log entries that author wrote."""

    def __init__(self, author: str | None, limit: int = LIMIT):
        self.author = author
        self.limit = limit
        self._undo: list[Step] = []
        self._redo: list[Step] = []

    # -- state ---------------------------------------------------------------
    @property
    def can_undo(self) -> bool:
        """Is there a step to undo?"""
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        """Is there a step to redo?"""
        return bool(self._redo)

    @property
    def undo_label(self) -> str:
        """What undoing would undo, for a menu item (empty if nothing)."""
        return self._undo[-1].label if self._undo else ""

    @property
    def redo_label(self) -> str:
        """What redoing would redo, for a menu item (empty if nothing)."""
        return self._redo[-1].label if self._redo else ""

    def next_undo(self) -> Step | None:
        """The step undo would take, without taking it."""
        return self._undo[-1] if self._undo else None

    def next_redo(self) -> Step | None:
        """The step redo would take, without taking it."""
        return self._redo[-1] if self._redo else None

    def clear(self) -> None:
        """Forget all steps (the state was rebuilt)."""
        self._undo.clear()
        self._redo.clear()

    # -- driven by the log -----------------------------------------------------
    def record(self, entry: Entry, inverse: Command) -> bool:
        """Called for every entry that was applied. Returns True if this author's stacks changed."""
        if entry.author != self.author or not entry.command.undoable:
            return False
        if entry.origin == "do":
            self._undo.append(Step(entry.command.label, inverse, entry.rev))
            del self._undo[: -self.limit]
            self._redo.clear()
        elif entry.origin == "undo":  # the step keeps its name: "Undo Insert 7" / "Redo Insert 7"
            taken = self._take(self._undo, entry.of)
            self._redo.append(Step(taken.label if taken else entry.command.label, inverse, entry.rev))
        elif entry.origin == "redo":
            taken = self._take(self._redo, entry.of)
            self._undo.append(Step(taken.label if taken else entry.command.label, inverse, entry.rev))
            del self._undo[: -self.limit]
        return True

    @staticmethod
    def _take(stack: list[Step], rev: Revision | None) -> Step | None:
        """Remove the step an undo/redo entry consumed (normally the top one)."""
        for index in range(len(stack) - 1, -1, -1):
            if stack[index].rev == rev:
                return stack.pop(index)
        return None

    def purge(self, revisions: set[Revision]) -> bool:
        """Redaction: forget steps that were derived from these revisions (their inverses hold the content)."""
        before = len(self._undo) + len(self._redo)
        self._undo = [s for s in self._undo if s.rev not in revisions]
        self._redo = [s for s in self._redo if s.rev not in revisions]
        return len(self._undo) + len(self._redo) != before
