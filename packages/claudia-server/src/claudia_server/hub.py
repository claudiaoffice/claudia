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

from .auth import AI_COLOR, Account, UserDirectory
from .protocol import PROTOCOL_VERSION, Context, Limits, MethodTable, RequestError, core_methods, parse_request

if TYPE_CHECKING:
    from .assistant import Assistant

log = logging.getLogger("claudia_server")

# Colours that show who is where; a new connection gets the first one nobody else in the document uses. Rose and
# apricot are colours of the suite; teal (the table's own selection) and Iris (the assistant) are kept out.
PALETTE = ("#d6477a", "#f2a057", "#3d7dd8", "#8d6e63", "#7cb342", "#b0408f", "#607d8b", "#c9a400")

_DOC_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


class HubError(Exception):
    """Opening a document failed; ``code`` is one of ``protocol.ERROR_CODES``."""

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

    def exists(self, doc_id: str) -> bool:
        """Is there a document with this id?"""

    def create(self, doc_id: str) -> Document:
        """Make an empty document. Everything that happens to it must reach storage through the kernel's store."""

    def open(self, doc_id: str) -> Document:
        """Load a document from its log. Raises (``ValueError`` for a document that cannot be opened) with a message fit
        for the person."""

    def documents(self) -> list[StoredInfo]:
        """Every stored document, the most recently changed first."""


class MemoryProvider:
    """Documents kept in memory (tests, a development server). Unloading a document loses nothing: the log stays
    here."""

    def __init__(self, model_cls: type[DocumentModel], **options):
        self._model_cls = model_cls
        self._options = options  # clock, lock_clock
        self._stored: dict[str, tuple[CommandLog, MemoryStore]] = {}
        self._created: dict[str, str] = {}

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

    def __init__(self, hosted: HostedDocument, account: Account, send: Callable[[str], None]):
        self.hosted = hosted
        self.account = account
        self._send = send
        self.id = hosted.new_connection_id()
        self.color = AI_COLOR if account.system else hosted.pick_color()
        self.closed = False
        self.broken = False  # sending failed (client gone or too slow): the transport should drop it

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
            "people": [c.person() for c in self.hosted.connections if c is not self],
            "presence": [
                {"user": hold.owner, "regions": [r.to_data() for r in hold.regions], "locked": hold.expires is not None}
                for hold in doc.presence.holds()
                if hold.owner != self.account.user
            ],
            "checkpoints": [{"number": c.number, "label": c.label, "author": c.author} for c in doc.checkpoints],
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
            )
            result = hosted.methods.dispatch(context, name, params)
            frame = {"id": request_id, "ok": True, "result": result}
            json.dumps(frame, allow_nan=False)  # make sure it can be sent before claiming success
        except RequestError as error:
            frame = {"id": request_id, "ok": False, "error": error.to_dict()}
        except Exception:
            log.exception("request failed in %s", hosted.id)
            frame = {"id": request_id, "ok": False, "error": {"code": "internal", "message": "internal server error"}}
        hosted.touch()
        self.deliver(frame)

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
        document.subscribe(self._on_event)

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

    def humans(self) -> list[Connection]:
        """The connections of people (the assistant is not one)."""
        return [c for c in self.connections if not c.account.system]

    def connect(self, account: Account, send: Callable[[str], None]) -> Connection:
        """Add a window. ``HubError('unavailable')`` if the document is full."""
        if not account.system and len(self.humans()) >= self.max_connections:
            raise HubError("unavailable", f"{self.id} already has {self.max_connections} connections")
        connection = Connection(self, account, send)
        self.connections.add(connection)
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
        frame = {"event": data.get("type", "state"), "data": data}
        for connection in self._audience(event):
            connection.deliver(frame)

    def sweep(self) -> None:
        """Tell the others about locks that ran out (the kernel turns them into plain presence on its own)."""
        now_locked = {hold.owner for hold in self.document.presence.holds() if hold.expires is not None}
        for owner in sorted(self._locked - now_locked):
            hold = self.document.presence.of(owner)
            if hold is not None:
                self.document.publish(
                    "presence", owner, {"regions": [r.to_data() for r in hold.regions], "locked": False}
                )
            self._locked.discard(owner)


class Hub:
    """The documents of one server."""

    def __init__(
        self,
        provider: DocumentProvider,
        *,
        methods: MethodTable = core_methods,
        limits: Limits | None = None,
        allow_create: bool = True,
        idle_unload: float = 120.0,
        edit_timeout: float = 300.0,
        max_connections: int = 50,
        sweep_interval: float = 1.0,
        assistant: Callable[[], Assistant] | None = None,
        directory: UserDirectory | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.provider = provider
        self.methods = methods
        self.limits = limits or Limits()
        self.allow_create = allow_create
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
            raise HubError("bad_request", "document ids are 1-64 letters, digits, '-' or '_'")
        return doc_id

    def exists(self, doc_id: str) -> bool:
        """Is there a document with this id (open or in storage)?"""
        return doc_id in self._documents or self.provider.exists(doc_id)

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
                except ValueError as exc:
                    raise HubError("bad_request", f"{doc_id} cannot be opened: {exc}") from exc
                except OSError as exc:
                    log.exception("cannot read %s", doc_id)
                    raise HubError("internal", f"{doc_id} cannot be read") from exc
            elif create and self.allow_create:
                document = await asyncio.to_thread(self.provider.create, doc_id)
            else:
                raise HubError("not_found", f"no document {doc_id!r}")
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
            return hosted

    # -- housekeeping ------------------------------------------------------------------------
    def sweep(self) -> None:
        """Tell people about lapsed locks and unload documents nobody has used for a while."""
        now = self._clock()
        for doc_id, hosted in list(self._documents.items()):
            hosted.sweep()
            if now - hosted.last_active > self.idle_unload and not hosted.humans():
                del self._documents[doc_id]  # nothing is lost: every change reached storage when it happened

    async def _sweep_loop(self) -> None:
        while True:
            await asyncio.sleep(self.sweep_interval)
            try:
                self.sweep()
            except Exception:
                log.exception("housekeeping failed; will retry")

    async def start(self) -> None:
        """Start the housekeeping."""
        if self._task is None:
            self._task = asyncio.create_task(self._sweep_loop())

    async def stop(self) -> None:
        """Stop the housekeeping."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
