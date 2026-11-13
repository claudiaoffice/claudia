"""Hosting documents: which documents are open, who is connected, what each of them receives (E3.1).

No web framework in here. A ``Connection`` is given a ``send(text)`` callable by whatever transport carries it (the
WebSocket endpoint, or a list in a test) and is fed incoming frames with ``handle(text)``. Everything is synchronous and
runs on one thread (the event loop), which is exactly the threading rule of the kernel (D16): a ``Document`` is only
ever touched from one thread, so no locks are needed around edits.

The kernel does the work; this module only carries it to people:

* a ``HostedDocument`` is a kernel ``Document`` plus its connections. It listens to the document's events and delivers
  each of them to the connections that may see it;
* a ``Connection`` is one person's window: the account, a colour, and the protocol (``protocol.py``) bound to the
document;
* the ``Hub`` is the set of open documents, loaded and created through a ``DocumentProvider`` (storage is E2).

Because undo steps and checkpoints come from the log, they survive a person leaving, a server restart and a document
being unloaded; presence and locks are per *name*, not per window, and end with the last window of that name.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from claudia_core import (
    ChatPosted,
    CommandLog,
    Document,
    DocumentModel,
    EphemeralPublished,
    HistoryChanged,
    MemoryStore,
)
from claudia_core.clock import utc_now

from .auth import AI_COLOR, ROLES, Account, UserDirectory
from .i18n import localized, msg
from .protocol import (
    DEFAULT_LOCALE,
    PROTOCOL_VERSION,
    Context,
    Limits,
    MethodTable,
    RequestError,
    core_methods,
    normalize_locale,
    parse_request,
)
from .restore import Resolution, RestoreCoordinator
from .workers import DEFAULT_WORKERS, WorkerPool

if TYPE_CHECKING:
    from .assistant import Assistant

log = logging.getLogger("claudia_server")

# Colours that show who is where; a new connection gets the first one nobody else in the document uses. Rose and
# apricot are colours of the suite; teal (the table's own selection) and Iris (the assistant) are kept out.
PALETTE = ("#d6477a", "#f2a057", "#3d7dd8", "#8d6e63", "#7cb342", "#b0408f", "#607d8b", "#c9a400")

_DOC_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
DEFAULT_MAX_DOCUMENTS = 1000  # room for a team for years, but not for anybody who can reach the server (SEC-02)


class HubError(Exception):
    """Opening a document failed; ``code`` is one of ``protocol.ERROR_CODES``; ``message`` is English or a
    ``claudia_server.i18n.Message`` that the connection says in its own language."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class StoredInfo:
    """What a provider knows about a stored document without opening it."""

    id: str
    app: str
    modified: str  # ISO 8601 UTC, when the document last changed


class DocumentProvider(Protocol):
    """Where documents come from and go to. E2 implements it with the container file; ``MemoryProvider`` is the
    stand-in."""

    @property
    def app(self) -> str:
        """The kind of documents this provider holds (``DocumentModel.app``): a server hosts one kind."""

    def exists(self, doc_id: str) -> bool:
        """Is there a document with this id?"""

    def create(self, doc_id: str) -> Document:
        """Make an empty document. Everything that happens to it must reach storage through the kernel's store."""

    def open(self, doc_id: str) -> Document:
        """Load a document from its log. Raises (``ValueError`` for a document that cannot be opened) with a message fit
        for the person."""

    def release(self, doc_id: str) -> None:
        """The hub unloaded the document from memory (nobody uses it any more). A store that holds files or keys for
        an open document lets go of them here; the document stays stored."""

    def documents(self) -> list[StoredInfo]:
        """Every stored document, the most recently changed first."""


class DocumentSealed(ValueError):
    """The document is stored, but nobody who holds all its keys has opened it since the server started."""


class MemoryProvider:
    """Documents kept in memory (tests, a development server). Unloading a document loses nothing: the log stays
    here."""

    def __init__(self, model_cls: type[DocumentModel], **options):
        self._model_cls = model_cls
        self._options = options  # clock, lock_clock
        self._stored: dict[str, tuple[CommandLog, MemoryStore]] = {}
        self._created: dict[str, str] = {}

    @property
    def app(self) -> str:
        """The kind of documents kept here."""
        return self._model_cls.app

    def exists(self, doc_id: str) -> bool:
        """Is there a document with this id?"""
        return doc_id in self._stored

    def create(self, doc_id: str) -> Document:
        """Make an empty document."""
        log_, store = CommandLog(), MemoryStore()
        self._stored[doc_id] = (log_, store)
        self._created[doc_id] = utc_now()
        return Document(self._model_cls.empty(), log=log_, store=store, **self._options)

    def open(self, doc_id: str) -> Document:
        """Rebuild a document from its log."""
        log_, store = self._stored[doc_id]
        return Document.open(self._model_cls, log_, store=store, chat=store.chat, **self._options)

    def release(self, doc_id: str) -> None:
        """Nothing is held for an open document."""

    def documents(self) -> list[StoredInfo]:
        """Every stored document, the most recently changed first."""
        found = []
        for doc_id, (log_, _store) in self._stored.items():
            head = log_.head(log_.active)
            modified = log_.get(head).time if head is not None and log_.has(head) else self._created[doc_id]
            found.append(StoredInfo(doc_id, self._model_cls.app, modified))
        return sorted(found, key=lambda info: (info.modified, info.id), reverse=True)


class Connection:
    """One window of one person on one document."""

    def __init__(
        self, hosted: HostedDocument, account: Account, send: Callable[[str], None], *, locale: str = DEFAULT_LOCALE
    ):
        self.hosted = hosted
        self.account = account
        self._send = send
        self.id = hosted.new_connection_id()
        self.color = AI_COLOR if account.system else hosted.pick_color()
        self.closed = False
        self.broken = False  # sending failed (client gone or too slow): the transport should drop it
        self.locale = normalize_locale(locale)  # the window's own locale (E5.7); re-normalized, never trusted raw

    # -- outgoing -----------------------------------------------------------------------
    def deliver(self, message: dict) -> None:
        """Send one frame. A dead or slow client never breaks the edit that is being broadcast."""
        try:
            self._send(json.dumps(message, allow_nan=False, separators=(",", ":")))
        except Exception:
            self.broken = True

    def welcome(self) -> dict:
        """What a client needs to start: who it is, where the document is, who else is here."""
        doc = self.hosted.document
        revision = doc.revision
        return {
            "protocol": PROTOCOL_VERSION,
            "user": self.account.user,
            "role": self.account.role,
            "doc": self.hosted.id,
            "app": doc.model.app,
            "state_schema": doc.model.state_schema,
            "line": doc.branch,
            "revision": None if revision is None else revision.to_data(),
            "limits": self.hosted.limits.to_dict(),
            "id": self.id,
            "color": self.color,
            "locale": self.locale,
            "people": [c.person() for c in self.hosted.connections if c is not self],
            "presence": [
                {"user": hold.owner, "regions": [r.to_data() for r in hold.regions], "locked": hold.expires is not None}
                for hold in doc.presence.holds()
                if hold.owner != self.account.user
            ],
            "checkpoints": [{"number": c.number, "label": c.label, "author": c.author} for c in doc.checkpoints],
            "lines": [
                {"name": x.name, "head": None if x.head is None else x.head.to_data(), "active": x.active}
                for x in doc.lines()
            ],
            "proposal": None if (p := self.hosted.restore.open_proposal) is None else p.to_data(),
            "returned": None if self.account.system else self.hosted.restore.notice_for(self.account.user, doc.branch),
        }

    def person(self) -> dict:
        """This window as the others see it."""
        return {"id": self.id, "user": self.account.user, "color": self.color}

    # -- incoming -----------------------------------------------------------------------
    def handle(self, raw: str | bytes) -> None:
        """Process one request frame; exactly one response frame is sent for it."""
        hosted = self.hosted
        request_id = None
        try:
            request_id, name, params = parse_request(raw, hosted.limits)
            context = Context(
                hosted.document,
                self.account,
                hosted.limits,
                hosted.users,
                hosted.edit_timeout,
                hosted.directory,
                hosted.id,
                self.locale,
                hosted.editors,
                hosted.restore,
                hosted.broadcast,
                hosted.note_ai_mode,
                self.set_locale,
            )
            result = hosted.methods.dispatch(context, name, params)
            frame = {"id": request_id, "ok": True, "result": result}
            json.dumps(frame, allow_nan=False)  # make sure it can be sent before claiming success
        except RequestError as error:
            frame = {"id": request_id, "ok": False, "error": error.to_dict(self.locale)}
        except Exception:
            log.exception("request failed in %s", hosted.id)
            internal = localized(msg("internal server error"), self.locale)
            frame = {"id": request_id, "ok": False, "error": {"code": "internal", "message": internal}}
        hosted.touch()
        self.deliver(frame)

    def set_locale(self, locale: str) -> None:
        """The person chose another interface language in this window (D294): later answers are in it."""
        self.locale = normalize_locale(locale)

    def close(self) -> None:
        """The window is gone. What its person shows or holds goes with their last window."""
        if self.closed:
            return
        self.closed = True
        hosted = self.hosted
        hosted.connections.discard(self)
        if not any(c.account.user == self.account.user for c in hosted.connections):
            hosted.document.presence.release(self.account.user)
            hosted.document.publish("presence", self.account.user, {"regions": [], "gone": True})
            if not self.account.system:
                outcome = hosted.restore.left(self.account.user, hosted.document.branch)
                if outcome is not None:
                    hosted.broadcast({"event": "restore_resolved", "data": {"outcome": outcome}})
        hosted.broadcast({"event": "left", "data": {"id": self.id, "user": self.account.user}})
        hosted.touch()


class HostedDocument:
    """A kernel ``Document`` with the people connected to it."""

    def __init__(
        self,
        doc_id: str,
        document: Document,
        *,
        limits: Limits,
        methods: MethodTable,
        max_connections: int,
        edit_timeout: float,
        clock: Callable[[], float],
        directory: UserDirectory | None = None,
    ):
        self.id = doc_id
        self.document = document
        self.limits = limits
        self.methods = methods
        self.max_connections = max_connections
        self.edit_timeout = edit_timeout
        self.directory = directory
        self._clock = clock
        self.connections: set[Connection] = set()
        self.assistant: Assistant | None = None  # the AI participant, if the hub gives documents one
        self.last_active = clock()
        self._connection_ids = 0
        self._locked: set[str] = set()  # who held a lock at the last look, to tell the others when one lapses
        self.restore = RestoreCoordinator(self._apply_proposal, clock=clock)
        self._ai_modes: dict[str, str] = {}  # the mode of a person's next request to the AI (D262), until it is heard
        document.subscribe(self._on_event)

    # -- how a person wants the AI to treat her request (D262) --------------------------------
    def note_ai_mode(self, user: str, mode: str | None) -> None:
        """Remember the mode a person sent with the message she is about to post, for the moment the AI hears it;
        ``None`` forgets it again (the ``chat`` method does, right after posting, so a message that was not for the AI
        leaves nothing behind)."""
        if mode is None:
            self._ai_modes.pop(user, None)
        else:
            self._ai_modes[user] = mode

    def ai_mode_of(self, user: str) -> str | None:
        """The mode noted for the message ``user`` is posting now (``None``: none was noted)."""
        return self._ai_modes.get(user)

    def role_of(self, user: str) -> str | None:
        """The role of a person connected now (the strongest of her windows); ``None`` when she is not connected."""
        roles = [c.account.role for c in self.connections if c.account.user == user and not c.account.system]
        if not roles:
            return None
        return min(roles, key=ROLES.index)  # ROLES run from the strongest to the weakest

    # -- people ------------------------------------------------------------------------
    def new_connection_id(self) -> int:
        """The next connection number (unique in this document while it is loaded)."""
        self._connection_ids += 1
        return self._connection_ids

    def pick_color(self) -> str:
        """The first colour nobody here has; when everybody is taken, colours are shared."""
        used = {c.color for c in self.connections}
        return next((c for c in PALETTE if c not in used), PALETTE[self._connection_ids % len(PALETTE)])

    def users(self) -> list[str]:
        """The names of the people connected now, once each: the addresses for chat messages."""
        return sorted({c.account.user for c in self.connections}, key=str.casefold)

    def editors(self) -> list[str]:
        """The names of the people connected now who may write (owners and editors, not viewers or the assistant):
        who must be asked before a restore or a switch happens (E3.7)."""
        writers = {c.account.user for c in self.connections if c.account.can_write and not c.account.system}
        return sorted(writers, key=str.casefold)

    def humans(self) -> list[Connection]:
        """The connections of people (the assistant is not one)."""
        return [c for c in self.connections if not c.account.system]

    def connect(self, account: Account, send: Callable[[str], None], *, locale: str = DEFAULT_LOCALE) -> Connection:
        """Add a window. ``HubError('unavailable')`` if the document is full."""
        if not account.system and len(self.humans()) >= self.max_connections:
            raise HubError(
                "unavailable", msg("{id} already has {limit} connections", id=self.id, limit=self.max_connections)
            )
        connection = Connection(self, account, send, locale=locale)
        self.connections.add(connection)
        if not account.system:
            self.restore.joined(account.user, account.can_write)
        self.broadcast({"event": "joined", "data": connection.person()}, skip=connection)
        self.touch()
        return connection

    def broadcast(self, message: dict, skip: Connection | None = None) -> None:
        """Send a frame to every window (except ``skip``)."""
        for connection in list(self.connections):
            if connection is not skip:
                connection.deliver(message)

    def touch(self) -> None:
        """Note that something happened (for unloading idle documents)."""
        self.last_active = self._clock()

    # -- what the kernel tells us ------------------------------------------------------------
    def _audience(self, event: object) -> list[Connection]:
        """The windows that may receive this event."""
        everyone = list(self.connections)
        if isinstance(event, HistoryChanged):  # your undo state is yours
            return [c for c in everyone if c.account.user == event.author]
        if isinstance(event, ChatPosted) and event.record.to:  # a private message: sender and recipient
            names = {event.record.author.casefold(), event.record.to.casefold()}
            return [c for c in everyone if c.account.user.casefold() in names]
        if isinstance(event, EphemeralPublished):  # presence is not echoed to the one who sent it
            return [c for c in everyone if c.account.user != event.message.sender]
        return everyone

    def _on_event(self, event: object) -> None:
        data = event.to_data()  # type: ignore[attr-defined]
        if isinstance(event, EphemeralPublished) and event.message.kind == "presence":
            (self._locked.add if event.message.data.get("locked") else self._locked.discard)(event.message.sender or "")
        event_type = data.get("type", "state")
        # An event may offer `to_data_for(viewer)` to mask part of its payload per connection (e.g. an imported
        # image's source path, hidden from everyone but the person who imported it). Duck-typed, not imported by
        # name, so this stays app-agnostic: no app's event types are known here.
        to_data_for = getattr(event, "to_data_for", None)
        for connection in self._audience(event):
            payload = data if to_data_for is None else to_data_for(connection.account.user)
            connection.deliver({"event": event_type, "data": payload})

    def sweep(self) -> None:
        """Tell the others about locks that ran out (the kernel turns them into plain presence on its own), and
        resolve an open restore/switch suggestion whose deadline has passed (E3.7)."""
        now_locked = {hold.owner for hold in self.document.presence.holds() if hold.expires is not None}
        for owner in sorted(self._locked - now_locked):
            hold = self.document.presence.of(owner)
            if hold is not None:
                self.document.publish(
                    "presence", owner, {"regions": [r.to_data() for r in hold.regions], "locked": False}
                )
            self._locked.discard(owner)
        outcome = self.restore.sweep()
        if outcome is not None:
            self.broadcast({"event": "restore_resolved", "data": {"outcome": outcome}})

    # -- restoring and switching, with consent (E3.7) -----------------------------------
    def _apply_proposal(self, record: dict) -> None:
        """Carry out an agreed suggestion (``RestoreCoordinator``'s ``apply``): call the kernel, and if the line
        actually moved, remember what happened to the one left behind, for whoever was away when it did."""
        old = self.document.branch
        if record["kind"] == "restore":
            moved = self.document.restore_checkpoint(record["checkpoint"], author=record["by"]) is not None
        else:
            moved = self.document.switch_to(record["line"], author=record["by"]) is not None
        if moved:
            self.restore.record_resolution(
                old, Resolution(by=record["by"], kind=record["kind"], label=record["label"], agreed=record["agreed"])
            )


class Hub:
    """The documents of one server.

    ``max_documents`` is the most documents the server holds: past it nobody can make another (``ensure_room``), so that
    whoever can reach the server cannot fill its disk. ``workers`` is the pool slow or CPU-bound request handling can
    offload to, off the one thread every document here is otherwise served from (D134); it starts no process until
    something is first submitted to it."""

    def __init__(
        self,
        provider: DocumentProvider,
        *,
        methods: MethodTable = core_methods,
        limits: Limits | None = None,
        allow_create: bool = True,
        max_documents: int = DEFAULT_MAX_DOCUMENTS,
        idle_unload: float = 120.0,
        edit_timeout: float = 300.0,
        max_connections: int = 50,
        sweep_interval: float = 1.0,
        assistant: Callable[[], Assistant] | None = None,
        directory: UserDirectory | None = None,
        clock: Callable[[], float] = time.monotonic,
        max_workers: int = DEFAULT_WORKERS,
    ):
        self.provider = provider
        self.methods = methods
        self.limits = limits or Limits()
        self.allow_create = allow_create
        self.max_documents = max_documents
        self.workers = WorkerPool(max_workers=max_workers)
        self._known: set[str] = (
            set()
        )  # the ids of the stored documents: found when first asked, and every one opened since
        self._counted = False
        self.idle_unload = idle_unload
        self.edit_timeout = edit_timeout
        self.max_connections = max_connections
        self.sweep_interval = sweep_interval
        self.assistant = assistant
        self.directory = directory  # where people are kept, so that owners can add more (create_app fills it in)
        self._clock = clock
        self._documents: dict[str, HostedDocument] = {}
        self._open_lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    # -- documents ---------------------------------------------------------------------
    @staticmethod
    def check_id(doc_id: object) -> str:
        """The id if it is a valid document id, else ``HubError('bad_request')``."""
        if not isinstance(doc_id, str) or not _DOC_ID.fullmatch(doc_id):
            raise HubError("bad_request", msg("document ids are 1-64 letters, digits, '-' or '_'"))
        return doc_id

    def exists(self, doc_id: str) -> bool:
        """Is there a document with this id (open or in storage)?"""
        return doc_id in self._documents or self.provider.exists(doc_id)

    @property
    def app(self) -> str:
        """The kind of documents this server hosts (``"computes"``, ``"creates"``, ...)."""
        return self.provider.app

    def listing(self) -> list[dict]:
        """The documents on this server: ``{id, app, modified, online}``, most recently changed first.

        ``online`` is the number of different people connected now. No names and no content: whoever may reach the
        server may see that a document exists, and still needs its password to open it."""
        found = []
        for info in self.provider.documents():
            hosted = self._documents.get(info.id)
            online = len({c.account.user.casefold() for c in hosted.humans()}) if hosted else 0
            found.append({"id": info.id, "app": info.app, "modified": info.modified, "online": online})
        return found

    def is_loaded(self, doc_id: str) -> bool:
        """Is the document open in memory now?"""
        return doc_id in self._documents

    async def ensure_room(self) -> None:
        """``HubError('unavailable')`` if the server already holds as many documents as it may.

        Reading every document of the store is slow, so the store is read once, in a thread; after that every document
        the hub opens is added to what is known. Ids, not a number: a store may make a document's file before the hub
        opens it (the sealed store does, when it adds the first person), and counting the same document twice must not
        matter. (A document put into the folder by hand is only counted after a restart.)"""
        if not self._counted:
            self._known.update(info.id for info in await asyncio.to_thread(self.provider.documents))
            self._counted = True
        if len(self._known) >= self.max_documents:
            raise HubError(
                "unavailable",
                msg("this server holds {limit} documents, the most it may hold", limit=self.max_documents),
            )

    async def open(self, doc_id: str, create: bool = False) -> HostedDocument:
        """The open document, loaded from storage (or created, if allowed) first."""
        self.check_id(doc_id)
        async with self._open_lock:
            hosted = self._documents.get(doc_id)
            if hosted is not None:
                hosted.touch()
                return hosted
            if self.provider.exists(doc_id):
                try:
                    document = await asyncio.to_thread(self.provider.open, doc_id)
                except DocumentSealed as exc:
                    raise HubError("sealed", msg("{id} cannot be opened yet: {reason}", id=doc_id, reason=exc)) from exc
                except ValueError as exc:
                    raise HubError(
                        "bad_request", msg("{id} cannot be opened: {reason}", id=doc_id, reason=exc)
                    ) from exc
                except OSError as exc:
                    log.exception("cannot read %s", doc_id)
                    raise HubError("internal", msg("{id} cannot be read", id=doc_id)) from exc
            elif create and self.allow_create:
                await self.ensure_room()
                document = await asyncio.to_thread(self.provider.create, doc_id)
            else:
                raise HubError("not_found", msg("no document {id!r}", id=doc_id))
            hosted = HostedDocument(
                doc_id,
                document,
                limits=self.limits,
                methods=self.methods,
                max_connections=self.max_connections,
                edit_timeout=self.edit_timeout,
                clock=self._clock,
                directory=self.directory,
            )
            if self.assistant is not None:
                self.assistant().attach(hosted)
            self._documents[doc_id] = hosted
            self._known.add(doc_id)
            return hosted

    # -- housekeeping ------------------------------------------------------------------------
    def _unload_idle(self) -> list[str]:
        """Tell people about lapsed locks and take documents nobody has used for a while out of memory (not yet
        released from storage). Returns their ids."""
        now = self._clock()
        gone = []
        for doc_id, hosted in list(self._documents.items()):
            hosted.sweep()
            if now - hosted.last_active > self.idle_unload and not hosted.humans():
                del self._documents[doc_id]  # nothing is lost: every change reached storage when it happened
                gone.append(doc_id)
        return gone

    def sweep(self) -> None:
        """Tell people about lapsed locks and unload documents nobody has used for a while (all in the caller's
        thread; the running server uses :meth:`housekeeping`, which lets go of storage in a thread)."""
        for doc_id in self._unload_idle():
            self.provider.release(doc_id)  # a sealed store forgets the document's keys

    async def housekeeping(self) -> None:
        """As :meth:`sweep`, but letting go of a document may take time (a sealed store packs it into its file), so
        that runs in a thread, and nobody can open the document again before it is done."""
        async with self._open_lock:
            for doc_id in self._unload_idle():
                try:
                    await asyncio.to_thread(self.provider.release, doc_id)
                except Exception:
                    log.exception("cannot let go of %s", doc_id)

    async def _sweep_loop(self) -> None:
        while True:
            await asyncio.sleep(self.sweep_interval)
            try:
                await self.housekeeping()
            except Exception:
                log.exception("housekeeping failed; will retry")

    async def start(self) -> None:
        """Start the housekeeping."""
        if self._task is None:
            self._task = asyncio.create_task(self._sweep_loop())

    async def stop(self) -> None:
        """Stop the housekeeping, let go of every open document (a sealed store packs them into their files), and
        let go of the worker pool's processes."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        async with self._open_lock:
            for doc_id in list(self._documents):
                del self._documents[doc_id]
                try:
                    await asyncio.to_thread(self.provider.release, doc_id)
                except Exception:
                    log.exception("cannot let go of %s", doc_id)
        await self.workers.stop()
