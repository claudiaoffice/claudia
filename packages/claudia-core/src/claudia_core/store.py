"""What the kernel needs from storage. The kernel never opens a file: E2 (container, encryption) implements this.

Only three kinds of thing ever reach a store, matching the message classes of E1.6: log entries, chat records
and snapshots. There is deliberately no method for ephemeral messages.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .log import Entry
from .messages import ChatRecord
from .model import Snapshot
from .revision import Branch, Revision


class DocumentStore(Protocol):
    """What the kernel needs from storage: log entries, lines, chat records and snapshot caches. E2 implements it."""

    def append_entry(self, entry: Entry) -> None:
        """Persist one log entry. Raise if it cannot be made durable: the change then did not happen."""

    def replace_entries(self, entries: Sequence[Entry]) -> None:
        """Redaction: these entries (same revisions) replace the stored ones; rewrite what holds them."""

    def write_branch(self, branch: Branch, active: bool) -> None:
        """A line was created (restore); ``active``: the document continues on it from now on."""

    def discard_entries(self, revisions: Sequence[Revision]) -> None:
        """Permanently forget these entries (the owner discarded the abandoned future)."""

    def append_chat(self, record: ChatRecord) -> None:
        """Persist one chat record (chat is not part of the command log)."""

    def write_snapshot(self, snapshot: Snapshot) -> None:
        """Keep a snapshot as a cache; it may be dropped at any time."""

    def drop_snapshots(self) -> None:
        """Caches built from content that was redacted must go."""


class MemoryStore:
    """The reference implementation, in memory. Tests use it; it records every call in ``calls``."""

    def __init__(self):
        self.entries: dict = {}
        self.chat: list[ChatRecord] = []
        self.snapshots: list[Snapshot] = []
        self.calls: list[str] = []
        self.active = "main"
        self.branches: dict[str, Branch] = {}
        self.discarded: list[Revision] = []

    def append_entry(self, entry: Entry) -> None:
        """As ``DocumentStore.append_entry``, in memory."""
        self.calls.append("append_entry")
        self.entries[entry.rev] = entry

    def replace_entries(self, entries: Sequence[Entry]) -> None:
        """As ``DocumentStore.replace_entries``, in memory."""
        self.calls.append("replace_entries")
        for entry in entries:
            self.entries[entry.rev] = entry

    def write_branch(self, branch: Branch, active: bool) -> None:
        """As ``DocumentStore.write_branch``, in memory."""
        self.calls.append("write_branch")
        self.branches[branch.name] = branch
        if active:
            self.active = branch.name

    def discard_entries(self, revisions: Sequence[Revision]) -> None:
        """As ``DocumentStore.discard_entries``, in memory."""
        self.calls.append("discard_entries")
        for rev in revisions:
            self.entries.pop(rev, None)
        self.discarded += list(revisions)

    def append_chat(self, record: ChatRecord) -> None:
        """As ``DocumentStore.append_chat``, in memory."""
        self.calls.append("append_chat")
        self.chat.append(record)

    def write_snapshot(self, snapshot: Snapshot) -> None:
        """As ``DocumentStore.write_snapshot``, in memory."""
        self.calls.append("write_snapshot")
        self.snapshots.append(snapshot)

    def drop_snapshots(self) -> None:
        """As ``DocumentStore.drop_snapshots``, in memory."""
        self.calls.append("drop_snapshots")
        self.snapshots.clear()
