"""Events a Document tells its subscribers, and the bus that delivers them in order.

Models raise their own state events through ``Context.emit`` (any object with ``to_data()``); the kernel
adds the events below. ``CommandApplied`` is always the last event of a command, and one command is one
batch: batch listeners (a network layer) see everything a command caused, after every plain listener has.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .commands import Command
    from .log import Entry
    from .messages import ChatRecord, Ephemeral
    from .revision import Revision

Event = Any  # anything with a to_data() method; the kernel's own events are below


@dataclass(frozen=True)
class CommandApplied:
    """A command finished. ``origin`` is do, undo or redo."""

    entry: Entry
    inverse: Command

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "command",
            "revision": self.entry.rev.to_data(),
            "author": self.entry.author,
            "origin": self.entry.origin,
            "time": self.entry.time,
            "label": self.entry.command.label,
            "summary": self.entry.command.summary,
        }


@dataclass(frozen=True)
class HistoryChanged:
    """The undo/redo stacks of one author changed."""

    author: str | None
    can_undo: bool
    can_redo: bool
    undo_label: str
    redo_label: str

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "history",
            "author": self.author,
            "can_undo": self.can_undo,
            "can_redo": self.can_redo,
            "undo_label": self.undo_label,
            "redo_label": self.redo_label,
        }


@dataclass(frozen=True)
class CheckpointSaved:
    number: int
    label: str
    author: str | None
    marks: Revision

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "checkpoint",
            "number": self.number,
            "label": self.label,
            "author": self.author,
            "marks": self.marks.to_data(),
        }


@dataclass(frozen=True)
class ChatPosted:
    record: ChatRecord

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "chat", **self.record.to_data()}


@dataclass(frozen=True)
class EphemeralPublished:
    """Presence, preview values, typing indicators. Delivered, never stored (E1.6)."""

    message: Ephemeral

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "ephemeral", **self.message.to_data()}


@dataclass(frozen=True)
class Redacted:
    """The content of these revisions was removed (exported as ``RedactedEvent``): views must reload."""

    revisions: tuple[Revision, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "redacted", "revisions": [r.to_data() for r in self.revisions]}


@dataclass(frozen=True)
class BranchSwitched:
    """The document continues on another line (a checkpoint was restored): views must reload."""

    old: str
    new: str
    fork_point: Revision | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "branch",
            "old": self.old,
            "new": self.new,
            "fork_point": self.fork_point.to_data() if self.fork_point else None,
        }


@dataclass(frozen=True)
class Rebuilt:
    """The whole state was rebuilt from the log (after a redaction): views must reload."""

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "rebuilt"}


@dataclass(frozen=True)
class ResultsStale:
    """UserFunctions whose digest changed: what they computed is out of date (E1.9)."""

    functions: tuple[str, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "stale", "functions": list(self.functions)}


class EventBus:
    """Ordered delivery. An event raised by a listener waits until the current one reached everybody."""

    def __init__(self):
        self._listeners: list[Callable[[Event], None]] = []
        self._batch_listeners: list[Callable[[list[Event]], None]] = []
        self._pending: deque[Event] = deque()
        self._dispatching = False
        self._holds = 0

    def subscribe(self, callback: Callable[[Event], None]) -> Callable[[], None]:
        """Call ``callback`` for every event; returns the function that unsubscribes."""
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback) if callback in self._listeners else None

    def subscribe_batches(self, callback: Callable[[list[Event]], None]) -> Callable[[], None]:
        """Call ``callback`` with the list of events of each batch; returns the function that unsubscribes."""
        self._batch_listeners.append(callback)
        return lambda: self._batch_listeners.remove(callback) if callback in self._batch_listeners else None

    def emit(self, event: Event) -> None:
        """Deliver an event now, or at the end of the batch that is open."""
        self._pending.append(event)
        if not self._dispatching and not self._holds:
            self._drain()

    def _drain(self) -> None:
        self._dispatching = True
        delivered: list[Event] = []
        try:
            while self._pending:
                current = self._pending.popleft()
                delivered.append(current)
                for callback in list(self._listeners):
                    callback(current)
        except BaseException:
            self._pending.clear()
            raise
        finally:
            self._dispatching = False
        for callback in list(self._batch_listeners):
            callback(delivered)

    @contextmanager
    def batching(self):
        """Hold events back until the block ends, so one command is one batch."""
        self._holds += 1
        try:
            yield
        finally:
            self._holds -= 1
            if not self._holds and not self._dispatching and self._pending:
                self._drain()
