"""The sealed store: documents in their sealed document files, and their people (E2.1 to E2.3, E2.7).

``SealedDocuments`` is both of the server's storage interfaces at once: the ``DocumentProvider`` (documents) and the
``UserDirectory`` (who may open them). They cannot be separate, because the people of a document are the key slots in
its file, and a person's password is the only thing that opens them.

Layout under the root folder::

    docs/<id>.claudia            the document file: manifest, key slots, sealed list of people, and the changes so far
                                 as sealed blocks with their head record and a snapshot (see ``claudia_document_file``)
    docs/<id>.claudia.journal    the sealed changes since then (see :mod:`claudia_document_file.journal`)

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
import os
import re
import threading
import time
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from claudia_core import ChatRecord, CommandLog, Document, DocumentModel, Import, Snapshot
from claudia_document_file import (
    AuditRecord,
    ConsentRecord,
    DocumentFileError,
    JournalError,
    JournalWriter,
    KdfParams,
    Part,
    RenewalInterrupted,
    Role,
    WeakPassword,
    add_user,
    begin,
    change_password,
    change_role,
    clean_details,
    create_document,
    derive_login_material,
    forget_original,
    format_recovery_key,
    journal_path,
    leave_document,
    new_recovery_key,
    pack_journal,
    parse_recovery_key,
    read_audit,
    read_consent,
    read_manifest,
    read_original,
    read_people,
    read_state,
    record_audit,
    record_consent,
    recover_access,
    remove_person,
    remove_user,
    rewrite_journal,
    sealed_copy,
    set_details,
    set_recovery_key,
    transfer_owner,
    unlock,
    unlock_with_recovery,
    warm,
    write_original,
)

from .auth import AI_USER, Account, AuthRefused, Credentials, is_reserved
from .filestore import JournalStore, chat_items, history_items, replay
from .hub import DocumentSealed, DuplicateDocument, StoredInfo
from .i18n import msg
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
    """The name as the document file stores it: Unicode-compatible, single-spaced. A name with a control character (a
    line break, say) is refused, not tidied up."""
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
    else under the history key. It counts what the journal holds since the last packing. ``path`` is the document
    file; ``keys`` are the document's keys, which a redaction needs to seal the file anew."""

    def __init__(self, path: Path, writer: JournalWriter, keys: Mapping[Part, bytes]):
        super().__init__(path)
        self.writer = writer
        self.keys = keys
        self.unpacked = 0

    def _write(self, kind: str, data) -> None:
        self.writer.append(Part.CHAT if kind == "chat" else Part.HISTORY, _payload(kind, data))
        self.unpacked += 1

    def rewrite(self, log: CommandLog, chat: Sequence[ChatRecord]) -> None:
        """As ``DocumentStore.rewrite`` (D725, SEC-05): the blocks of the file are sealed anew from the redacted log and
        chat alone, without a snapshot, and the journal is replaced by an empty one, so no copy of the redacted
        content is left in either. The journal's records are part of what is written, so nothing waits to be packed.
        """
        history = [_payload(kind, data) for kind, data in history_items(log)]
        chat_payloads = [_payload(kind, data) for kind, data in chat_items(chat)]
        try:
            self.writer = rewrite_journal(self.path, self.keys, self.writer, history=history, chat=chat_payloads)
        except BaseException:
            # As after a failed packing: go on with whichever journal is on disk. If the file was already sealed anew,
            # the redaction holds in the file and the old journal is behind it, so ``begin`` replaces it.
            with contextlib.suppress(Exception):
                self.writer.close()
            with contextlib.suppress(Exception):
                self.writer = begin(self.path, self.keys)
            raise
        self.unpacked = 0

    def close(self) -> None:
        """Let go of the journal."""
        self.writer.close()


def _payload(kind: str, data) -> bytes:
    return json.dumps({"t": kind, "d": data}, separators=(",", ":"), ensure_ascii=False).encode()


@dataclass
class _Held:
    """An open document: its keys, the store that writes its journal, and the document itself (for snapshots)."""

    keys: dict[Part, bytes]
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


def _snapshot_of(held: _Held) -> bytes | None:
    """The snapshot of an open document as it is written into its file, or ``None`` if it has none."""
    snapshot = held.document.snapshot() if held.document is not None else None
    return None if snapshot is None else json.dumps(snapshot.to_data(), separators=(",", ":")).encode()


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

    ``kdf`` sets the cost of the password hashing of *new* documents (default: claudia-document-file's), either as one
    fixed value or as a function asked each time a document is made (``KdfPolicy.current``); existing ones keep theirs.
    ``key_ttl`` is how long after a login the keys wait for the document to be opened. ``pack_every`` is after how many
    changes an open document is packed into its file (see the module text). ``options`` go to every ``Document`` (clock,
    lock clock)."""

    def __init__(
        self,
        root: str | Path,
        model_cls: type[DocumentModel],
        *,
        kdf: KdfParams | Callable[[], KdfParams] | None = None,
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
        self._pending: dict[str, tuple[dict[Part, bytes], float]] = {}
        self._open: dict[str, _Held] = {}
        self._transfers: dict[str, tuple[str, str, str, float]] = {}  # doc_id -> (old, old_pw, new, expires)
        private_dir(self.root / "docs")

    @property
    def app(self) -> str:
        """The kind of documents kept in the folder."""
        return self.model_cls.app

    @property
    def state_schema(self) -> int:
        """The shape of the state of those documents."""
        return self.model_cls.state_schema

    # -- where things are ---------------------------------------------------------------------
    def _new_kdf(self) -> KdfParams | None:
        """The cost of hashing for a document made now: fixed, or asked from a policy that measures the machine
        (``kdf_policy.py``); ``None`` is claudia-document-file's default."""
        return self._kdf() if callable(self._kdf) else self._kdf

    def _file(self, doc_id: str) -> Path:
        return self.root / "docs" / f"{_check_id(doc_id)}{SUFFIX}"

    def exists(self, doc_id: str) -> bool:
        """Is there a document with this id?"""
        try:
            return self._file(doc_id).is_file()
        except ValueError:
            return False

    # -- the keys in memory -------------------------------------------------------------------
    def _take_pending(self, doc_id: str) -> dict[Part, bytes] | None:
        with self._lock:
            now = self._clock()
            for stale in [d for d, (_, expires) in self._pending.items() if expires <= now]:
                del self._pending[stale]
            entry = self._pending.pop(doc_id, None)
            return entry[0] if entry else None

    def _keep_pending(self, doc_id: str, keys: dict[Part, bytes]) -> None:
        with self._lock:
            self._pending[doc_id] = (keys, self._clock() + self._key_ttl)

    def _all_keys(self, doc_id: str) -> dict[Part, bytes]:
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
            raise AuthRefused(msg("The name “{name}” belongs to the AI assistant. Choose another name.", name=AI_USER))
        if not (isinstance(name, str) and isinstance(password, str)):
            return None
        try:
            path = self._file(doc_id)
        except ValueError:
            path = None
        if path is None or not path.is_file():
            # Hash anyway, so the time does not tell whether the document exists (SEC-04).
            derive_login_material(password, name, b"\0" * 16, self._new_kdf() or KdfParams.default())
            return None
        try:
            unlocked = unlock(path, name, password)
        except (DocumentFileError, OSError) as error:
            log.warning("cannot unlock %s: %s", path.name, error)
            return None
        if unlocked is None:
            return None
        if set(unlocked.keys) == set(Part):
            self._keep_pending(doc_id, unlocked.keys)
        return Account(unlocked.name, unlocked.role.value)

    def warm(self, doc_id: str, name: str, password: str) -> None:
        """Hash ``name``'s ``password`` for this document ahead of the call that needs it (SEC-21): the server does
        it in a worker thread, so the call itself, which runs on its event loop, finds the result and does not hash.
        Whatever is wrong (no such document, an unreadable file, something that is no text) is left for that call to
        say."""
        if not (isinstance(name, str) and isinstance(password, str)):
            return
        try:
            path = self._file(doc_id)
            if path.is_file():
                warm(path, name, password)
        except (ValueError, DocumentFileError, OSError):
            return

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
            name=doc_id,
            app=self.model_cls.app,
            owner=account.user,
            password=password,
            kdf=self._new_kdf(),
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

    # -- roles and removal, with the keys renewed (E2.3, D1263) --------------------------------
    def set_role(self, doc_id: str, name: str, role: str) -> Account:
        """Give ``name`` this role in the open document. A role that takes keys away (editor to viewer) renews them."""
        if role not in (Role.EDITOR, Role.VIEWER):
            raise ValueError("a person's role is editor or viewer; ownership is handed over")
        return self._change_people(doc_id, name, Role(role))

    def remove_person(self, doc_id: str, name: str) -> Account:
        """Remove ``name`` from the open document and renew the keys she held."""
        return self._change_people(doc_id, name, None)

    def _change_people(self, doc_id: str, name: str, role: Role | None) -> Account:
        clean = _clean_name(name)
        path = self._file(doc_id)
        with self._lock:
            held = self._open.get(doc_id)
            if held is None:
                raise DocumentSealed(_SEALED)
            target = next((p for p in read_people(path, held.keys) if _same_name(p.name, clean)), None)
            if target is None:
                raise KeyError(name)
            if target.role is Role.OWNER:
                raise ValueError("an owner stays: ownership is handed over, not taken away")
            snapshot = _snapshot_of(held)
            try:
                if role is None:
                    done = remove_person(path, held.keys, held.store.writer, target.name, snapshot=snapshot)
                else:
                    done = change_role(path, held.keys, held.store.writer, target.name, role, snapshot=snapshot)
            except RenewalInterrupted as interrupted:
                # the file has the new keys; go on with them, and start the journal again
                held.keys = held.store.keys = interrupted.keys
                held.store.writer = begin(path, interrupted.keys)
                held.store.unpacked = 0
                return Account(target.name, (role or target.role).value)
            if done.renewed:
                held.keys = held.store.keys = done.keys
                held.store.writer = done.writer
                held.store.unpacked = 0
        return Account(target.name, (role or target.role).value)

    def _is_empty(self, doc_id: str, keys: Mapping[Part, bytes]) -> bool:
        try:
            state = read_state(self._file(doc_id), keys)
        except (DocumentFileError, JournalError, OSError):
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

    def change_password(self, doc_id: str, name: str, old_password: str, new_password: str) -> bool:
        """``name`` gets ``new_password`` for this document (D448): the document's keys are sealed for them again under
        the new one, nothing else changes and the old password stops working at once. Needs no other key, so a
        viewer can do it too. ``False`` for a wrong current password; ``ValueError`` with a sentence for a weak new
        one."""
        try:
            return change_password(self._file(doc_id), _clean_name(name), old_password, new_password)
        except WeakPassword as problem:
            raise ValueError(explain(problem)) from problem
        except (DocumentFileError, OSError) as error:
            log.warning("cannot change a password in %s: %s", doc_id, error)
            return False

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

    def set_details(self, doc_id: str, owner: str, owner_password: str, description: str, tags: Sequence[str]) -> bool:
        """Say what the document is about, for everybody who can list the server: the description and tags go into the
        file's plain manifest (D103), not into its history, and not under a key. ``owner`` is the person who says it
        and ``owner_password`` their own password; an editor or an owner may, a viewer may not. ``False`` if the
        password is wrong or the person is a viewer (the same refusal either way, nothing changes then);
        ``ValueError`` with a sentence if the text does not fit."""
        path = self._file(doc_id)
        clean_details(description, tags)  # a text that does not fit costs no password check
        unlocked = unlock(path, owner, owner_password)
        if unlocked is None or unlocked.role is Role.VIEWER:
            return False
        with self._lock:
            set_details(path, unlocked.keys, description, tags)
        return True

    def sealed_copy(self, doc_id: str, name: str, password: str) -> bytes | None:
        """The document as a sealed file for ``name`` to keep (D110; see ``claudia_document_file.sealed_copy`` for what
        each role gets). An open document is packed first, so the file holds what has been said so far, and has a
        fresh snapshot for a viewer's copy. ``None`` for a wrong name or password."""
        with self._lock:
            held = self._open.get(doc_id)
        if held is not None:
            self._pack(doc_id, held)
        try:
            return sealed_copy(self._file(doc_id), name, password)
        except (DocumentFileError, OSError) as error:
            raise ValueError(f"the document cannot be copied: {error}") from error

    # -- what left the document (D1271) -------------------------------------------------------
    def record_audit(self, doc_id: str, record: AuditRecord) -> None:
        """Add ``record`` to the document's audit chain, with the keys the open document holds: the one who asked may
        be a viewer, who holds none of them. ``DocumentSealed`` if nobody holding all the keys has opened the document
        since the server started (a document cannot be exported then either)."""
        keys = self._all_keys(doc_id)
        with self._lock:
            record_audit(self._file(doc_id), keys, record)

    def audit_rows(self, doc_id: str) -> list[AuditRecord]:
        """Everything recorded for the document, oldest first."""
        keys = self._all_keys(doc_id)
        with self._lock:
            return read_audit(self._file(doc_id), keys)

    # -- the owners' consent to a remote AI provider (E7.11, D264) ------------------------------
    def consent_rows(self, doc_id: str) -> list[ConsentRecord]:
        """Every decision of the owners about a remote AI provider, oldest first."""
        keys = self._all_keys(doc_id)
        with self._lock:
            return read_consent(self._file(doc_id), keys)

    def record_consent(self, doc_id: str, record: ConsentRecord) -> None:
        """Add ``record`` to the document's consent, with the keys the open document holds."""
        keys = self._all_keys(doc_id)
        with self._lock:
            record_consent(self._file(doc_id), keys, record)

    def describe(self, doc_id: str, description: str, tags: Sequence[str]) -> None:
        """Give a document its maker has just made (whose keys are still held) a description and tags: the one
        way to set them without a password, because whoever holds the keys of a new document made it a moment ago.
        ``ValueError`` if the text does not fit, ``DocumentSealed`` if the keys are no longer held."""
        keys = self._all_keys(doc_id)
        with self._lock:
            set_details(self._file(doc_id), keys, description, tags)

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

    def _bring_up(self, doc_id: str, keys: dict[Part, bytes], *, fresh: bool) -> Document:
        path = self._file(doc_id)
        log_: CommandLog = CommandLog()
        chat: list[ChatRecord] = []
        snapshot = None
        pending = 0
        try:
            if not fresh:
                if (app := read_manifest(path).app) != self.model_cls.app:  # one place per app (D431)
                    raise ValueError(f"{doc_id} is a document of {app}, not of {self.model_cls.app}")
                state = read_state(path, keys)
                log_, chat = self._replayed(state.history, state.chat)
                snapshot, pending = _snapshot_from(state.snapshot), state.pending
            writer = begin(path, keys)
        except (DocumentFileError, JournalError) as error:
            raise ValueError(f"the document is damaged or has been changed: {error}") from error
        store = SealedStore(path, writer, keys)
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
        document.on_purge(lambda revisions: self._forget_redacted_original(doc_id, held, revisions))
        return document

    def _forget_redacted_original(self, doc_id: str, held: _Held, revisions: tuple) -> None:
        """A redacted import takes the kept original of the file with it (D723): the file holds what was blanked."""
        document = held.document
        if document is not None and any(isinstance(document.log.get(rev).command, Import) for rev in revisions):
            forget_original(self._file(doc_id), held.keys)

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
            held.store.writer = pack_journal(self._file(doc_id), held.keys, held.store.writer, _snapshot_of(held))
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
    # -- the original of an import, and a file taken in as it is (D439, D442) ------------------------------------
    def keep_original(self, doc_id: str, data: bytes) -> None:
        """Seal the file the open document was imported from into its document file."""
        with self._lock:
            held = self._open.get(doc_id)
            if held is None:
                raise DocumentSealed(_SEALED)
            write_original(self._file(doc_id), held.keys, data)

    def original(self, doc_id: str) -> bytes | None:
        """The file the open document was imported from, if it is kept; ``None`` when not, or not open."""
        with self._lock:
            held = self._open.get(doc_id)
            keys = None if held is None else dict(held.keys)
        if keys is None:
            return None
        try:
            return read_original(self._file(doc_id), keys)
        except DocumentFileError:
            log.exception("the kept original of %s does not open", doc_id)
            return None

    def place(self, doc_id: str, data: bytes) -> None:
        """Take in a Claudia document file as it is, still sealed, as ``doc_id`` (which its manifest must name), and
        with the uid it has (D533). ``FileExistsError`` if a document of that name is here; ``DuplicateDocument`` if
        a document with the same uid is here already, whatever its name; ``ValueError`` if the file is not a document
        of this app or is damaged. Never overwrites, and nothing is left behind when it fails."""
        target = self._file(doc_id)
        temp = target.with_name(f".{target.name}.{threading.get_ident()}.incoming")
        temp.write_bytes(data)
        try:
            manifest = read_manifest(temp)
            if manifest.name != doc_id:
                raise ValueError(f"the file is {manifest.name}, not {doc_id}")
            if manifest.app != self.model_cls.app:
                raise ValueError(f"it is a document of {manifest.app}, not of {self.model_cls.app}")
            twin = self.find(manifest.uid)
            if twin is not None:
                raise DuplicateDocument(twin.id)
            os.link(temp, target)  # fails if the target exists: never overwrites
        except DocumentFileError as error:
            raise ValueError(str(error)) from error
        finally:
            temp.unlink(missing_ok=True)

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
        except (DocumentFileError, OSError) as error:
            log.warning("cannot recover %s: %s", path.name, error)
            return None
        if person is None or unlocked is None:
            return None
        if person.role is not Role.VIEWER:
            self._keep_pending(doc_id, unlocked.keys)
        return Account(person.name, person.role.value)

    def uid_of(self, doc_id: str) -> str | None:
        """The uid of a stored document (D533), or ``None`` if there is no such document or it cannot be read."""
        try:
            return read_manifest(self._file(doc_id)).uid
        except (DocumentFileError, OSError, ValueError):
            return None

    def find(self, uid: str) -> StoredInfo | None:
        """The stored document of this app with exactly this uid, or ``None`` (D533). A scan of the manifests, which
        is cheap next to a password hash; the caller limits how often it may be asked."""
        return next((info for info in self.documents() if info.uid == uid), None)

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
            except (DocumentFileError, OSError, ValueError):
                continue  # not a document of ours; never break the list for it
            if manifest.app != self.model_cls.app:
                continue  # another app's file in this app's place (D431): not listed, never opened
            stamp = datetime.fromtimestamp(changed, UTC).isoformat(timespec="milliseconds")
            found.append(
                StoredInfo(
                    manifest.name,
                    manifest.app,
                    stamp.replace("+00:00", "Z"),
                    manifest.description,
                    manifest.tags,
                    manifest.uid,
                )
            )
        return sorted(found, key=lambda info: (info.modified, info.id), reverse=True)
