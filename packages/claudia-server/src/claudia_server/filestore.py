"""A file store for the demo server: documents and users survive a restart (stand-in for the container, E2).

**Not the real thing.** Nothing here is encrypted or compressed, and there is one journal file per document. The
container (E2.1) replaces it, with encryption, key slots and blocks. It exists so that a demo server keeps what people
made.

Layout under the root folder::

    users.json                   the users of every document (scrypt hashes, private to the owner of the folder)
    docs/<id>/journal.jsonl      one JSON object per line, appended as things happen

Journal lines: ``entry`` (a log entry), ``branch`` (a line was created; maybe now the active one), ``chat``,
``replace`` (redaction in journals written before D725: entries rewritten) and ``discard`` (the owner forgot the
abandoned future). Reading the journal in order rebuilds the log. A last line that is cut off (the power went out
mid-write) is ignored; a damaged line anywhere else is an error, never a guess. A redaction does not add a line: it
writes the whole journal anew from the redacted log and chat (D725), so the old lines are gone.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from claudia_core import (
    Branch,
    ChatRecord,
    CommandLog,
    Document,
    DocumentModel,
    Entry,
    Revision,
    Snapshot,
)
from claudia_file_writer import write_atomically

from .auth import Account, ScryptDirectory
from .hub import StoredInfo
from .state import private_dir, write_private

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
JOURNAL = "journal.jsonl"


def _check_id(doc_id: str) -> str:
    if not isinstance(doc_id, str) or not _ID.fullmatch(doc_id):
        raise ValueError(f"{doc_id!r} is not a valid document id")
    return doc_id


class JournalStore:
    """``DocumentStore`` that appends every change to the journal of one document."""

    def __init__(self, path: Path):
        self.path = path
        self._handle: BinaryIO | None = None

    def _write(self, kind: str, data) -> None:
        handle = self._handle
        if handle is None or handle.closed:
            handle = self._handle = self.path.open("ab")
        handle.write(_line(kind, data))
        handle.flush()
        os.fsync(handle.fileno())  # the change did not happen unless it is on disk

    def close(self) -> None:
        """Let go of the file."""
        if self._handle is not None:
            self._handle.close()

    def append_entry(self, entry: Entry) -> None:
        """As ``DocumentStore.append_entry``."""
        self._write("entry", entry.to_data())

    def rewrite(self, log: CommandLog, chat: Sequence[ChatRecord]) -> None:
        """As ``DocumentStore.rewrite``: the journal is written anew from the redacted log and chat and put in place of
        the old one all at once, so a crash leaves the old journal or the new one, never a mixture."""
        self.close()
        lines = [_line(kind, data) for kind, data in [*history_items(log), *chat_items(chat)]]
        write_atomically(self.path, b"".join(lines), durable=True)

    def write_branch(self, branch: Branch, active: bool) -> None:
        """As ``DocumentStore.write_branch``."""
        self._write("branch", {"branch": branch.to_data(), "active": active})

    def discard_entries(self, revisions: Sequence[Revision]) -> None:
        """As ``DocumentStore.discard_entries``."""
        self._write("discard", [r.to_data() for r in revisions])

    def append_chat(self, record: ChatRecord) -> None:
        """As ``DocumentStore.append_chat``."""
        self._write("chat", record.to_data())

    def write_snapshot(self, snapshot: Snapshot) -> None:
        """Snapshots are only a cache; this store keeps none."""


def _line(kind: str, data) -> bytes:
    return (json.dumps({"t": kind, "d": data}, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def history_items(log: CommandLog) -> list[tuple[str, Any]]:
    """The journal items that build ``log`` again: its lines (the active one marked), then every entry in order. What a
    store writes when it writes a document anew (D725)."""
    data = log.to_data()
    lines = [
        ("branch", {"branch": branch, "active": branch["name"] == data["active"]})
        for branch in data["branches"]
        if branch["name"] != "main"
    ]
    return [*lines, *(("entry", entry) for entry in data["entries"])]


def chat_items(chat: Sequence[ChatRecord]) -> list[tuple[str, Any]]:
    """The journal items of the chat, in order."""
    return [("chat", record.to_data()) for record in chat]


def history_payloads(log: CommandLog) -> list[bytes]:
    """The history as one JSON text per change, as the sealed journal keeps it (and an unencrypted export writes it,
    D1270): the active line and every hidden side line."""
    return [_payload_of(kind, data) for kind, data in history_items(log)]


def chat_payloads(chat: Sequence[ChatRecord]) -> list[bytes]:
    """The chat as one JSON text per message."""
    return [_payload_of(kind, data) for kind, data in chat_items(chat)]


def _payload_of(kind: str, data: Any) -> bytes:
    return json.dumps({"t": kind, "d": data}, separators=(",", ":"), ensure_ascii=False).encode()


class _Replay:
    """The state a journal builds up while it is read."""

    def __init__(self) -> None:
        self.entries: dict[str, dict] = {}  # revision text -> entry data, in order
        self.branches: dict[str, dict] = {}
        self.chat: list[ChatRecord] = []
        self.active = "main"

    def entry(self, data: dict) -> None:
        self.entries[data["rev"]] = data

    def replace(self, data: list) -> None:
        for entry in data:
            self.entries[entry["rev"]] = entry

    def discard(self, data: list) -> None:
        for rev in data:
            self.entries.pop(rev, None)

    def branch(self, data: dict) -> None:
        self.branches[data["branch"]["name"]] = data["branch"]
        if data["active"]:
            self.active = data["branch"]["name"]

    def chat_record(self, data: dict) -> None:
        self.chat.append(ChatRecord.from_data(data))


def replay(items: Iterable[tuple[str, Any]], model_cls: type[DocumentModel]) -> tuple[CommandLog, list[ChatRecord]]:
    """Rebuild the log and the chat from journal items ``(kind, data)`` in the order they were written.

    ``ValueError`` for a kind nobody knows. Shared by every store that keeps the same items (plain and sealed)."""
    state = _Replay()
    handlers: dict[str, Callable] = {
        "entry": state.entry,
        "replace": state.replace,
        "discard": state.discard,
        "branch": state.branch,
        "chat": state.chat_record,
    }
    for kind, data in items:
        handler = handlers.get(kind)
        if handler is None:
            raise ValueError(f"the journal has an unknown item type {kind!r}")
        handler(data)
    log = CommandLog.from_data(
        {"active": state.active, "branches": list(state.branches.values()), "entries": list(state.entries.values())},
        model_cls.registry,
    )
    return log, state.chat


def read_journal(path: Path, model_cls: type[DocumentModel]) -> tuple[CommandLog, list[ChatRecord]]:
    """Rebuild the log and the chat of a document from its journal."""
    lines = path.read_bytes().split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    items: list[tuple[str, Any]] = []
    for number, raw in enumerate(lines, start=1):
        try:
            item = json.loads(raw)
            items.append((item["t"], item["d"]))
        except (ValueError, KeyError, TypeError) as exc:
            if number == len(lines):
                break  # cut off by a crash: the change it carried never happened
            raise ValueError(f"the journal {path} is damaged at line {number}") from exc
    try:
        return replay(items, model_cls)
    except ValueError as exc:
        raise ValueError(f"{exc} (in {path})") from exc


class FileProvider:
    """``DocumentProvider`` over a folder (see the module text)."""

    def __init__(self, root: str | Path, model_cls: type[DocumentModel], **options):
        self.root = Path(root)
        self.model_cls = model_cls
        self._options = options  # clock, lock_clock
        self._stores: dict[str, JournalStore] = {}
        private_dir(self.root / "docs")

    @property
    def app(self) -> str:
        """The kind of documents kept in the folder."""
        return self.model_cls.app

    @property
    def state_schema(self) -> int:
        """The shape of the state of those documents, which an import has to have (D1272)."""
        return self.model_cls.state_schema

    def _journal(self, doc_id: str) -> Path:
        return self.root / "docs" / _check_id(doc_id) / JOURNAL

    def exists(self, doc_id: str) -> bool:
        """Is there a document with this id?"""
        try:
            return self._journal(doc_id).is_file()
        except ValueError:
            return False

    def create(self, doc_id: str) -> Document:
        """Make an empty document and its journal."""
        path = self._journal(doc_id)
        if path.exists():
            raise ValueError(f"{doc_id} exists")
        private_dir(path.parent)
        path.touch(mode=0o600)
        store = self._store(doc_id, path)
        return Document(self.model_cls.empty(), log=CommandLog(), store=store, **self._options)

    def open(self, doc_id: str) -> Document:
        """Rebuild a document from its journal."""
        path = self._journal(doc_id)
        log, chat = read_journal(path, self.model_cls)
        return Document.open(self.model_cls, log, store=self._store(doc_id, path), chat=chat, **self._options)

    def _store(self, doc_id: str, path: Path) -> JournalStore:
        previous = self._stores.pop(doc_id, None)
        if previous is not None:
            previous.close()  # a document that was unloaded and is opened again gets a fresh handle
        store = self._stores[doc_id] = JournalStore(path)
        return store

    def release(self, doc_id: str) -> None:
        """The hub unloaded the document: let go of its file."""
        store = self._stores.pop(doc_id, None)
        if store is not None:
            store.close()

    def documents(self) -> list[StoredInfo]:
        """Every stored document, the most recently changed first."""
        found = []
        for journal in (self.root / "docs").glob(f"*/{JOURNAL}"):
            if not _ID.fullmatch(journal.parent.name):
                continue
            stamp = datetime.fromtimestamp(journal.stat().st_mtime, UTC).isoformat(timespec="milliseconds")
            found.append(StoredInfo(journal.parent.name, self.model_cls.app, stamp.replace("+00:00", "Z")))
        return sorted(found, key=lambda info: (info.modified, info.id), reverse=True)


class FileDirectory(ScryptDirectory):
    """``UserDirectory`` that keeps its users in ``<root>/users.json`` (hashes only)."""

    def __init__(self, root: str | Path, cost: int = 2**14):
        super().__init__(cost)
        self.path = Path(root) / "users.json"
        if self.path.is_file():
            try:
                self.load(json.loads(self.path.read_text(encoding="utf-8")))
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"the user file {self.path} is damaged: {exc}") from exc

    def _save(self) -> None:
        private_dir(self.path.parent)
        write_private(self.path, json.dumps(self.dump(), indent=1).encode())

    def add_user(self, doc_id: str, name: str, password: str, role: str = "editor") -> Account:
        """As ``ScryptDirectory.add_user``, and kept on disk."""
        account = super().add_user(doc_id, name, password, role)
        try:
            self._save()
        except BaseException:
            with contextlib.suppress(KeyError):
                super().remove_user(doc_id, name)
            raise
        return account

    def remove_user(self, doc_id: str, name: str) -> None:
        """As ``ScryptDirectory.remove_user``, and kept on disk."""
        super().remove_user(doc_id, name)
        self._save()
