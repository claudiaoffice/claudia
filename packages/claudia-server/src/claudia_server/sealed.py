"""The sealed store: documents in the encrypted container, and their people (E2.1 to E2.3, E2.7).

``SealedDocuments`` is both of the server's storage interfaces at once: the ``DocumentProvider`` (documents) and the
``UserDirectory`` (who may open them). They cannot be separate, because the people of a document are the key slots in
its file, and a person's password is the only thing that opens them.

Layout under the root folder::

    docs/<id>.claudia            the document file: manifest, key slots, sealed list of people, and the changes so far
                                 as sealed blocks with their head record and a snapshot (see ``claudia_container``)
    docs/<id>.claudia.journal    the sealed changes since then (see :mod:`claudia_container.journal`)

Every change is appended to the journal when it happens. **Packing** folds the journal into the blocks of the file,
writes a fresh snapshot (a cache of the document's state, so that opening does not replay everything) and starts a new
journal. It happens when a document is let go (``release``), when one is opened with unpacked work left over from a
crash, and every ``pack_every`` changes while it is open. A failed packing loses nothing: the journal still has it.

**Keys live in memory only**, and only as long as they are needed:

* a successful login by an owner or editor puts the document's keys in a short-lived *pending* place. The next
  ``open`` takes them out again; if nobody opens the document within ``key_ttl`` seconds they are forgotten;
* while a document is open its keys are kept so that changes can be sealed and people added. ``release`` (the hub calls
  it when it unloads an idle document) forgets them.

A viewer holds only the content key, so a viewer cannot bring a document up: if nobody with all the keys has opened it
since the server started, the viewer is told to ask an editor. The viewer has logged in correctly by then, so the
message gives nothing away.

Who is an owner and who an editor is enforced by the server, not by the keys: both hold all three (D101).
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import threading
import time
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from claudia_container import (
    ContainerError,
    Domain,
    JournalError,
    JournalWriter,
    KdfParams,
    Role,
    WeakPassword,
    add_user,
    begin,
    create_document,
    derive_login_material,
    format_recovery_key,
    journal_path,
    leave_document,
    new_recovery_key,
    pack_journal,
    parse_recovery_key,
    read_manifest,
    read_people,
    read_state,
    recover_access,
    remove_user,
    set_recovery_key,
    transfer_owner,
    unlock,
    unlock_with_recovery,
)
from claudia_core import ChatRecord, CommandLog, Document, DocumentModel, Snapshot

from .auth import AI_USER, Account, AuthRefused, Credentials, is_reserved
from .filestore import JournalStore, replay
from .hub import DocumentSealed, StoredInfo
from .state import private_dir

log = logging.getLogger(__name__)

SUFFIX = ".claudia"
DEFAULT_PACK_EVERY = 500
"""After how many changes an open document is folded into its file."""
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_SEALED = "this document is sealed: an owner or editor has to open it first"
_PROBLEMS = {
    "too_short": "at least 8 characters",
    "no_capital": "a capital letter",
    "no_small": "a small letter",
    "no_digit": "a digit",
}


def _check_id(doc_id: object) -> str:
    if not isinstance(doc_id, str) or not _ID.fullmatch(doc_id):
        raise ValueError(f"{doc_id!r} is not a valid document id")
    return doc_id


def _clean_name(name: str) -> str:
    """The name as the container stores it: Unicode-compatible, single-spaced. A name with a control character (a line
    break, say) is refused, not tidied up."""
    text = unicodedata.normalize("NFKC", name)
    if any(unicodedata.category(c).startswith("C") for c in text):
        raise ValueError("a name cannot contain control characters")
    return " ".join(text.split())


def _same_name(a: str, b: str) -> bool:
    return _clean_name(a).casefold() == _clean_name(b).casefold()


def explain(problem: WeakPassword) -> str:
    """The broken password rules as a sentence for the person: "The password needs a capital letter and a digit."."""
    needs = [_PROBLEMS[code] for code in problem.problems]
    text = needs[0] if len(needs) == 1 else ", ".join(needs[:-1]) + " and " + needs[-1]
    return f"The password needs {text}."


class SealedStore(JournalStore):
    """``DocumentStore`` that seals every change into the journal of the document: chat under the chat key, everything
    else under the history key. It counts what the journal holds since the last packing."""

    def __init__(self, path: Path, writer: JournalWriter):
        super().__init__(path)
        self.writer = writer
        self.unpacked = 0

    def _write(self, kind: str, data) -> None:
        payload = json.dumps({"t": kind, "d": data}, separators=(",", ":"), ensure_ascii=False).encode()
        self.writer.append(Domain.CHAT if kind == "chat" else Domain.HISTORY, payload)
        self.unpacked += 1

    def close(self) -> None:
        """Let go of the journal."""
        self.writer.close()


@dataclass
class _Held:
    """An open document: its keys, the store that writes its journal, and the document itself (for snapshots)."""

    keys: dict[Domain, bytes]
    store: SealedStore
    document: Document | None = None


def _items(payloads: Iterable[bytes], what: str) -> list[tuple[str, object]]:
    items = []
    for number, payload in enumerate(payloads, start=1):
        try:
            item = json.loads(payload)
            items.append((item["t"], item["d"]))
        except (ValueError, KeyError, TypeError) as error:
            raise JournalError(f"{what} {number} is not a change") from error
    return items


def _snapshot_from(data: bytes | None) -> Snapshot | None:
    """The snapshot of a file, or ``None`` if there is none or it cannot be read (it is only a cache)."""
    if data is None:
        return None
    try:
        return Snapshot.from_data(json.loads(data))
    except (ValueError, KeyError, TypeError):
        return None


class SealedDocuments:
    """``DocumentProvider`` and ``UserDirectory`` over a folder of document files (see the module text).

    ``kdf`` sets the cost of the password hashing of *new* documents (default: the container's); existing ones keep
    theirs. ``key_ttl`` is how long after a login the keys wait for the document to be opened. ``pack_every`` is after
    how many changes an open document is packed into its file (see the module text). ``options`` go to every
    ``Document`` (clock, lock clock)."""

    def __init__(
        self,
        root: str | Path,
        model_cls: type[DocumentModel],
        *,
        kdf: KdfParams | None = None,
        key_ttl: float = 60.0,
        transfer_ttl: float = 300.0,
        pack_every: int = DEFAULT_PACK_EVERY,
        clock: Callable[[], float] = time.monotonic,
        **options,
    ):
        if pack_every < 1:
            raise ValueError("pack_every must be at least 1")
        self.root = Path(root)
        self.model_cls = model_cls
        self._kdf = kdf
        self._key_ttl = key_ttl
        self._transfer_ttl = transfer_ttl
        self._pack_every = pack_every
        self._clock = clock
        self._options = options
        self._lock = threading.RLock()  # logins run in threads
        self._pending: dict[str, tuple[dict[Domain, bytes], float]] = {}
        self._open: dict[str, _Held] = {}
        self._transfers: dict[str, tuple[str, str, str, float]] = {}  # doc_id -> (old, old_pw, new, expires)
        private_dir(self.root / "docs")

    @property
    def app(self) -> str:
        """The kind of documents kept in the folder."""
        return self.model_cls.app

    # -- where things are ---------------------------------------------------------------------
    def _file(self, doc_id: str) -> Path:
        return self.root / "docs" / f"{_check_id(doc_id)}{SUFFIX}"

    def exists(self, doc_id: str) -> bool:
        """Is there a document with this id?"""
        try:
            return self._file(doc_id).is_file()
        except ValueError:
            return False

    # -- the keys in memory -------------------------------------------------------------------
    def _take_pending(self, doc_id: str) -> dict[Domain, bytes] | None:
        with self._lock:
            now = self._clock()
            for stale in [d for d, (_, expires) in self._pending.items() if expires <= now]:
                del self._pending[stale]
            entry = self._pending.pop(doc_id, None)
            return entry[0] if entry else None

    def _keep_pending(self, doc_id: str, keys: dict[Domain, bytes]) -> None:
        with self._lock:
            self._pending[doc_id] = (keys, self._clock() + self._key_ttl)

    def _all_keys(self, doc_id: str) -> dict[Domain, bytes]:
        """The keys of an open document (or one that was just made), or ``ValueError`` if it is sealed."""
        with self._lock:
            held = self._open.get(doc_id)
            if held is not None:
                return held.keys
            entry = self._pending.get(doc_id)
            if entry is not None and entry[1] > self._clock():
                return entry[0]
        raise DocumentSealed(_SEALED)

    # -- UserDirectory ------------------------------------------------------------------------
    def verify(self, doc_id: str, credentials: Credentials) -> Account | None:
        """The account if the name and password open a slot of the document, else ``None``.

        A missing document, a wrong name and a wrong password cost the same time and give the same answer. An owner or
        editor who gets in leaves the keys waiting for ``open``."""
        name, password = credentials.user, credentials.password
        if isinstance(name, str) and is_reserved(name):
            raise AuthRefused(f"The name “{AI_USER}” belongs to the AI assistant. Choose another name.")
        if not (isinstance(name, str) and isinstance(password, str)):
            return None
        try:
            path = self._file(doc_id)
        except ValueError:
            path = None
        if path is None or not path.is_file():
            # Hash anyway, so the time does not tell whether the document exists (SEC-04).
            derive_login_material(password, name, b"\0" * 16, self._kdf or KdfParams.default())
            return None
        try:
            unlocked = unlock(path, name, password)
        except (ContainerError, OSError) as error:
            log.warning("cannot unlock %s: %s", path.name, error)
            return None
        if unlocked is None:
            return None
        if set(unlocked.keys) == set(Domain):
            self._keep_pending(doc_id, unlocked.keys)
        return Account(unlocked.name, unlocked.role.value)

    def add_user(self, doc_id: str, name: str, password: str, role: str = "editor") -> Account:
        """Add a person. The first one of a document is its owner and makes the document file.

        ``ValueError`` with a message for the person: a name or role that is not acceptable, a name taken, a weak
        password, or a document that is sealed (nobody holding its keys has opened it)."""
        _check_id(doc_id)
        clean = _clean_name(name)
        account = Account(clean, role)  # checks the name, the role and the reserved name
        try:
            if not self.exists(doc_id):
                return self._start(doc_id, account, password)
            keys = self._all_keys(doc_id)
            person = add_user(self._file(doc_id), keys, clean, password, Role(role))
        except WeakPassword as problem:
            raise ValueError(explain(problem)) from problem
        return Account(person.name, role)

    def _start(self, doc_id: str, account: Account, password: str) -> Account:
        if account.role != "owner":
            raise ValueError("a new document starts with its owner")
        unlocked = create_document(
            self._file(doc_id),
            doc_id=doc_id,
            app=self.model_cls.app,
            title=doc_id,
            owner=account.user,
            password=password,
            kdf=self._kdf,
        )
        self._keep_pending(doc_id, unlocked.keys)
        return Account(unlocked.name, "owner")

    def remove_user(self, doc_id: str, name: str) -> None:
        """Remove a person; ``KeyError`` if there is nobody of that name.

        The only person of a document that has no changes yet takes the document with them: that is how the server
        takes back a document whose creation failed. A document with content keeps at least one owner."""
        keys = self._all_keys(doc_id)
        path = self._file(doc_id)
        people = read_people(path, keys)
        if len(people) == 1 and self._is_empty(doc_id, keys):
            if _clean_name(people[0].name).casefold() != _clean_name(name).casefold():
                raise KeyError(name)
            self.release(doc_id)
            journal_path(path).unlink(missing_ok=True)
            path.unlink()
            return
        remove_user(path, keys, name)

    def _is_empty(self, doc_id: str, keys: Mapping[Domain, bytes]) -> bool:
        try:
            state = read_state(self._file(doc_id), keys)
        except (ContainerError, JournalError, OSError):
            return False  # something is wrong with it: never delete what might be somebody's work
        return not state.history and not state.chat

    def list_people(self, doc_id: str) -> list[Account]:
        """Everybody who may log in to this document, not just who is connected now, in the order they were added.

        A live request always reaches this with the document already open (an owner or editor had to open it to
        get this far), so there is always a set of keys at hand."""
        keys = self._all_keys(doc_id)
        people = read_people(self._file(doc_id), keys)
        return [Account(p.name, p.role.value) for p in people]

    # -- leaving and handing over ownership (E2.3) ---------------------------------------------
    def leave(self, doc_id: str, name: str, password: str) -> bool:
        """``name`` removes themself, proving it with their own current password. Needs none of the document's
        keys, so a viewer (who only ever holds the content key) can leave too.

        ``False`` for a wrong password (the same refusal as everywhere else, D50). ``ValueError`` with a sentence
        if ``name`` is the document's only owner."""
        return leave_document(self._file(doc_id), name, password)

    def propose_owner_transfer(self, doc_id: str, old_owner: str, old_owner_password: str, new_owner: str) -> bool:
        """``old_owner`` asks ``new_owner`` (who must already be an editor) to become the owner instead. Waits
        ``transfer_ttl`` seconds for ``new_owner`` to accept (``accept_owner_transfer``); a later proposal for the
        same document replaces one that was not accepted yet.

        ``False`` if ``old_owner_password`` is wrong. ``ValueError`` with a sentence if ``old_owner`` is not the
        document's owner, ``new_owner`` is not currently an editor, or they are the same person."""
        path = self._file(doc_id)
        unlocked = unlock(path, old_owner, old_owner_password)
        if unlocked is None:
            return False
        if unlocked.role is not Role.OWNER:
            raise ValueError(f"{old_owner!r} is not the owner of this document")
        people = read_people(path, self._all_keys(doc_id))
        new_person = next((p for p in people if _same_name(p.name, new_owner)), None)
        if new_person is None or new_person.role is not Role.EDITOR:
            raise ValueError(f"{new_owner!r} must already be an editor before becoming the owner")
        if _same_name(unlocked.name, new_person.name):
            raise ValueError("choose somebody else to become the new owner")
        with self._lock:
            self._transfers[doc_id] = (
                unlocked.name,
                old_owner_password,
                new_person.name,
                self._clock() + self._transfer_ttl,
            )
        return True

    def accept_owner_transfer(self, doc_id: str, new_owner: str, new_owner_password: str) -> Account | None:
        """``new_owner`` accepts a transfer proposed to them, with their own password. The new account (now the
        owner), or ``None`` for anything that keeps it from going through: nothing was proposed to them, it already
        went through, it expired, or the password is wrong — the same answer whichever it is (D50)."""
        with self._lock:
            now = self._clock()
            for stale in [d for d, (_, _, _, expires) in self._transfers.items() if expires <= now]:
                del self._transfers[stale]
            pending = self._transfers.get(doc_id)
            if pending is None or not _same_name(pending[2], new_owner):
                return None
            old_owner, old_owner_password, accepted_as, _ = pending
            del self._transfers[doc_id]
        ok = transfer_owner(
            self._file(doc_id),
            old_owner=old_owner,
            old_owner_password=old_owner_password,
            new_owner=accepted_as,
            new_owner_password=new_owner_password,
        )
        return Account(accepted_as, "owner") if ok else None

    def delete_document(self, doc_id: str, owner: str, owner_password: str) -> bool:
        """Remove the document for good: its file, its history and its chat. ``False`` if ``owner_password`` is
        wrong or ``owner`` is not currently an owner (the same refusal either way); nothing is removed then."""
        path = self._file(doc_id)
        unlocked = unlock(path, owner, owner_password)
        if unlocked is None or unlocked.role is not Role.OWNER:
            return False
        self.release(doc_id)
        journal_path(path).unlink(missing_ok=True)
        path.unlink()
        return True

    # -- DocumentProvider ---------------------------------------------------------------------
    def create(self, doc_id: str) -> Document:
        """Start the journal of a document whose owner was just added, and return the empty document."""
        path = self._file(doc_id)
        if journal_path(path).exists():
            raise ValueError(f"{doc_id} exists")
        keys = self._all_keys(doc_id)
        document = self._bring_up(doc_id, keys, fresh=True)
        self._take_pending(doc_id)
        return document

    def open(self, doc_id: str) -> Document:
        """Rebuild a document from its file and journal. ``ValueError`` if nobody holding all its keys has logged in
        lately (sealed) or the document is damaged or has been changed."""
        keys = None
        with self._lock:
            held = self._open.get(doc_id)
            keys = held.keys if held is not None else self._take_pending(doc_id)
        if keys is None:
            raise DocumentSealed(_SEALED)
        return self._bring_up(doc_id, keys, fresh=False)

    def _bring_up(self, doc_id: str, keys: dict[Domain, bytes], *, fresh: bool) -> Document:
        path = self._file(doc_id)
        log_: CommandLog = CommandLog()
        chat: list[ChatRecord] = []
        snapshot = None
        pending = 0
        try:
            if not fresh:
                state = read_state(path, keys)
                log_, chat = self._replayed(state.history, state.chat)
                snapshot, pending = _snapshot_from(state.snapshot), state.pending
            writer = begin(path, keys)
        except (ContainerError, JournalError) as error:
            raise ValueError(f"the document is damaged or has been changed: {error}") from error
        store = SealedStore(path, writer)
        if fresh:
            document = Document(self.model_cls.empty(), log=log_, store=store, **self._options)
        else:
            document = Document.open(self.model_cls, log_, snapshot=snapshot, store=store, chat=chat, **self._options)
        held = _Held(keys, store, document)
        with self._lock:
            previous = self._open.get(doc_id)
            self._open[doc_id] = held
        if previous is not None:
            previous.store.close()
        store.unpacked = pending
        if pending:
            self._pack(doc_id, held)  # work that a crash left in the journal goes into the file now
        document.subscribe_batches(lambda _events: self._after_change(doc_id, held))
        return document

    def _replayed(self, history: list[bytes], chat: list[bytes]) -> tuple[CommandLog, list[ChatRecord]]:
        items = [*_items(history, "history record"), *_items(chat, "chat record")]
        try:
            return replay(items, self.model_cls)
        except (ValueError, KeyError, TypeError) as error:
            raise JournalError(str(error)) from error

    def _after_change(self, doc_id: str, held: _Held) -> None:
        """Called after every command, chat message and the like: pack once the journal has grown enough."""
        if held.store.unpacked >= self._pack_every:
            self._pack(doc_id, held)

    def _pack(self, doc_id: str, held: _Held) -> None:
        """Fold the journal of an open document into its file and leave a snapshot. A failure is logged and loses
        nothing (the journal has it all); the next try comes after another ``pack_every`` changes."""
        try:
            snapshot = held.document.snapshot() if held.document is not None else None
            data = None if snapshot is None else json.dumps(snapshot.to_data(), separators=(",", ":")).encode()
            held.store.writer = pack_journal(self._file(doc_id), held.keys, held.store.writer, data)
        except Exception:
            log.exception("cannot pack %s; its changes are safe in the journal", doc_id)
            # `pack_journal` closes the old writer before it tries to put the new journal in its place (closed,
            # because Windows refuses to replace a file that is still open), but only once it gets that far: a
            # failure earlier in `pack_journal` (folding the journal into the file, say) leaves `held.store.writer`
            # still open. Closing it here too, before asking `begin` for a fresh one, means nothing of ours is ever
            # left holding the old journal open underneath `begin`'s own attempt to replace it -- closing an
            # already-closed writer is a no-op, so this is safe either way. `begin` reopens whichever journal is
            # actually on disk (the old one if the replace never happened, the new one if it did), so writing can
            # carry on either way -- matching "loses nothing" above for the writer itself, not just the records.
            with contextlib.suppress(Exception):
                held.store.writer.close()
            with contextlib.suppress(Exception):
                held.store.writer = begin(self._file(doc_id), held.keys)
        finally:
            held.store.unpacked = 0

    def release(self, doc_id: str) -> None:
        """Forget the keys of a document, pack what is in its journal into the file, and let go of the journal."""
        with self._lock:
            held = self._open.pop(doc_id, None)
            self._pending.pop(doc_id, None)
        if held is None:
            return
        try:
            if held.store.unpacked:
                self._pack(doc_id, held)
        finally:
            with contextlib.suppress(OSError):
                held.store.close()

    # -- the recovery key (D105) ---------------------------------------------------------------
    def new_recovery_key(self, doc_id: str) -> str:
        """Make a new recovery key for an open document, written as people write it down. A key the document had
        before stops working. The server keeps nothing of it: whoever asks must show it to the owner now.

        ``ValueError`` if the document is sealed."""
        keys = self._all_keys(doc_id)
        key = new_recovery_key()
        set_recovery_key(self._file(doc_id), keys, key)
        return format_recovery_key(key)

    def recover(self, doc_id: str, recovery_key: str, name: str, new_password: str) -> Account | None:
        """Get a person back in with the recovery key: they get ``new_password`` and keep their role (somebody who is
        not in the document becomes an owner). ``None`` for a key that is not the document's, a document that does not
        exist or has no recovery key: all the same answer.

        ``ValueError`` with a sentence for the person if the key is not a recovery key at all, the name is not
        acceptable or the new password is weak."""
        try:
            key = parse_recovery_key(recovery_key)
        except ValueError as error:
            raise ValueError(f"This is not a recovery key. {error}.") from error
        clean = _clean_name(name)
        Account(clean, "owner")  # checks the name and the reserved name
        try:
            path = self._file(doc_id)
        except ValueError:
            return None
        if not path.is_file():
            return None
        try:
            person = recover_access(path, key, clean, new_password)
            unlocked = unlock_with_recovery(path, key) if person is not None else None
        except WeakPassword as problem:
            raise ValueError(explain(problem)) from problem
        except (ContainerError, OSError) as error:
            log.warning("cannot recover %s: %s", path.name, error)
            return None
        if person is None or unlocked is None:
            return None
        if person.role is not Role.VIEWER:
            self._keep_pending(doc_id, unlocked.keys)
        return Account(person.name, person.role.value)

    def documents(self) -> list[StoredInfo]:
        """Every document file that can be read, the most recently changed first."""
        found = []
        for path in (self.root / "docs").glob(f"*{SUFFIX}"):
            try:
                manifest = read_manifest(path)
                changed = path.stat().st_mtime
                journal = journal_path(path)
                if journal.exists():
                    changed = max(changed, journal.stat().st_mtime)
            except (ContainerError, OSError, ValueError):
                continue  # not a document of ours; never break the list for it
            stamp = datetime.fromtimestamp(changed, UTC).isoformat(timespec="milliseconds")
            found.append(StoredInfo(manifest.id, manifest.app, stamp.replace("+00:00", "Z")))
        return sorted(found, key=lambda info: (info.modified, info.id), reverse=True)
