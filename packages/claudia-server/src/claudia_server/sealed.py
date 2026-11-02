"""The sealed store: documents in the encrypted container, and their people (E2.1 to E2.3, E2.7).

``SealedDocuments`` is both of the server's storage interfaces at once: the ``DocumentProvider`` (documents) and the
``UserDirectory`` (who may open them). They cannot be separate, because the people of a document are the key slots in
its file, and a person's password is the only thing that opens them.

Layout under the root folder::

    docs/<id>.claudia            the document file: manifest, key slots, sealed list of people
    docs/<id>.claudia.journal    the sealed changes of the document (see :mod:`claudia_container.journal`)

**Keys live in memory only**, and only as long as they are needed:

* a successful login by an owner or editor puts the document's keys in a short-lived *pending* place. The next
  ``open`` takes them out again; if nobody opens the document within ``key_ttl`` seconds they are forgotten;
* while a document is open its keys are kept so that changes can be sealed and people added. ``release`` (the hub calls
  it when it unloads an idle document) forgets them.

A viewer holds only the content key, so a viewer cannot bring a document up: if nobody with all the keys has opened it
since the server started, the viewer is told to ask an editor. The viewer has logged in correctly by then, so the
message gives nothing away.

Who is an owner and who an editor is enforced by the server, not by the keys: both hold all three (D71).
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import threading
import time
import unicodedata
from collections.abc import Callable, Mapping
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
    create_document,
    derive_login_material,
    journal_path,
    read_journal,
    read_manifest,
    read_people,
    remove_user,
    unlock,
)
from claudia_core import ChatRecord, CommandLog, Document, DocumentModel

from .auth import AI_USER, Account, AuthRefused, Credentials, is_reserved
from .filestore import JournalStore, replay
from .hub import StoredInfo
from .state import private_dir

log = logging.getLogger(__name__)

SUFFIX = ".claudia"
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


def explain(problem: WeakPassword) -> str:
    """The broken password rules as a sentence for the person: "The password needs a capital letter and a digit."."""
    needs = [_PROBLEMS[code] for code in problem.problems]
    text = needs[0] if len(needs) == 1 else ", ".join(needs[:-1]) + " and " + needs[-1]
    return f"The password needs {text}."


class SealedStore(JournalStore):
    """``DocumentStore`` that seals every change into the journal of the document: chat under the chat key, everything
    else under the history key."""

    def __init__(self, path: Path, writer: JournalWriter):
        super().__init__(path)
        self._writer = writer

    def _write(self, kind: str, data) -> None:
        payload = json.dumps({"t": kind, "d": data}, separators=(",", ":"), ensure_ascii=False).encode()
        self._writer.append(Domain.CHAT if kind == "chat" else Domain.HISTORY, payload)

    def close(self) -> None:
        """Let go of the journal."""
        self._writer.close()


@dataclass
class _Held:
    """The keys of a document that is open, and the store that writes its journal."""

    keys: dict[Domain, bytes]
    store: SealedStore | None = None


class SealedDocuments:
    """``DocumentProvider`` and ``UserDirectory`` over a folder of document files (see the module text).

    ``kdf`` sets the cost of the password hashing of *new* documents (default: the container's); existing ones keep
    theirs. ``key_ttl`` is how long after a login the keys wait for the document to be opened. ``options`` go to every
    ``Document`` (clock, lock clock)."""

    def __init__(
        self,
        root: str | Path,
        model_cls: type[DocumentModel],
        *,
        kdf: KdfParams | None = None,
        key_ttl: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        **options,
    ):
        self.root = Path(root)
        self.model_cls = model_cls
        self._kdf = kdf
        self._key_ttl = key_ttl
        self._clock = clock
        self._options = options
        self._lock = threading.RLock()  # logins run in threads
        self._pending: dict[str, tuple[dict[Domain, bytes], float]] = {}
        self._open: dict[str, _Held] = {}
        private_dir(self.root / "docs")

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
        raise ValueError(_SEALED)

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
        journal = journal_path(self._file(doc_id))
        if not journal.exists():
            return True
        try:
            return not read_journal(journal, doc_id, keys)
        except JournalError:
            return False  # something is wrong with it: never delete what might be somebody's work

    # -- DocumentProvider ---------------------------------------------------------------------
    def create(self, doc_id: str) -> Document:
        """Start the journal of a document whose owner was just added, and return the empty document."""
        path = self._file(doc_id)
        if journal_path(path).exists():
            raise ValueError(f"{doc_id} exists")
        keys = self._all_keys(doc_id)
        document = self._bring_up(doc_id, keys, journal_exists=False)
        self._take_pending(doc_id)
        return document

    def open(self, doc_id: str) -> Document:
        """Rebuild a document from its journal. ``ValueError`` if nobody holding all its keys has logged in lately
        (sealed) or the journal is damaged."""
        keys = None
        with self._lock:
            held = self._open.get(doc_id)
            keys = held.keys if held is not None else self._take_pending(doc_id)
        if keys is None:
            raise ValueError(_SEALED)
        return self._bring_up(doc_id, keys, journal_exists=journal_path(self._file(doc_id)).exists())

    def _bring_up(self, doc_id: str, keys: dict[Domain, bytes], *, journal_exists: bool) -> Document:
        path = self._file(doc_id)
        journal = journal_path(path)
        log_: CommandLog = CommandLog()
        chat: list[ChatRecord] = []
        try:
            if journal_exists:
                log_, chat = self._replayed(doc_id, journal, keys)
                writer = JournalWriter.open(journal, doc_id, keys)
            else:
                writer = JournalWriter.create(journal, doc_id, keys)
        except JournalError as error:
            raise ValueError(f"the document is damaged or has been changed: {error}") from error
        store = SealedStore(journal, writer)
        with self._lock:
            previous = self._open.get(doc_id)
            self._open[doc_id] = _Held(keys, store)
        if previous is not None and previous.store is not None:
            previous.store.close()
        if journal_exists:
            return Document.open(self.model_cls, log_, store=store, chat=chat, **self._options)
        return Document(self.model_cls.empty(), log=log_, store=store, **self._options)

    def _replayed(
        self, doc_id: str, journal: Path, keys: Mapping[Domain, bytes]
    ) -> tuple[CommandLog, list[ChatRecord]]:
        items = []
        for record in read_journal(journal, doc_id, keys):
            try:
                item = json.loads(record.payload)
                items.append((item["t"], item["d"]))
            except (ValueError, KeyError, TypeError) as error:
                raise JournalError(f"record {record.seq} is not a change") from error
        try:
            return replay(items, self.model_cls)
        except (ValueError, KeyError, TypeError) as error:
            raise JournalError(str(error)) from error

    def release(self, doc_id: str) -> None:
        """Forget the keys of a document and let go of its journal."""
        with self._lock:
            held = self._open.pop(doc_id, None)
            self._pending.pop(doc_id, None)
        if held is not None and held.store is not None:
            with contextlib.suppress(OSError):
                held.store.close()

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
