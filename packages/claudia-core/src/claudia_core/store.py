"""What the kernel needs from storage. The kernel never opens a file: E2 (document file, encryption) implements this.

Only three kinds of thing ever reach a store, matching the message classes of E1.6: log entries, chat records
and snapshots. There is deliberately no method for ephemeral messages.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .log import CommandLog, Step
from .messages import ChatRecord
from .model import Snapshot
from .revision import Branch, Revision


class DocumentStore(Protocol):
    """What the kernel needs from storage: log entries, lines, chat records and snapshot caches. E2 implements it."""

    def append_entry(self, entry: Step) -> None:
        """Persist one log entry. Raise if it cannot be made durable: the change then did not happen."""

    def rewrite(self, log: CommandLog, chat: Sequence[ChatRecord]) -> None:
        """Redaction (D725): from now on the store holds exactly this log and this chat, and **nothing of what it held
        before may remain** — not in a journal, not in a packed block, not in a snapshot. Raise if that cannot be
        made durable: the redaction then did not happen."""

    def write_branch(self, branch: Branch, active: bool) -> None:
        """A line was created (restore); ``active``: the document continues on it from now on."""

    def discard_entries(self, revisions: Sequence[Revision]) -> None:
        """Permanently forget these entries (the owner discarded the abandoned future)."""

    def append_chat(self, record: ChatRecord) -> None:
        """Persist one chat record (chat is not part of the command log)."""

    def write_snapshot(self, snapshot: Snapshot) -> None:
        """Keep a snapshot as a cache; it may be dropped at any time."""


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

    def append_entry(self, entry: Step) -> None:
        """As ``DocumentStore.append_entry``, in memory."""
        self.calls.append("append_entry")
        self.entries[entry.rev] = entry

    def rewrite(self, log: CommandLog, chat: Sequence[ChatRecord]) -> None:
        """As ``DocumentStore.rewrite``, in memory: every entry of every line, the chat, no snapshot."""
        self.calls.append("rewrite")
        self.entries = {entry.rev: entry for name in log.branches for entry in log.steps_of(name)}
        self.chat = list(chat)
        self.snapshots.clear()

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
