"""One server for several apps: the apps as modules, and which of them a request is for (D430, D431, D432).

A ``Module`` is one app on the server: its ``Hub`` (its open documents, its methods, its assistant) and its
``UserDirectory`` (who may open its documents). A ``Suite`` is the modules of one server, in the order they were
given. It is what the HTTP and WebSocket routes (``app.py``) and the settings pages (``admin_api.py``) see: they ask it
for the module of an app, for the module that holds a document, and for the list of every app's documents.

Each module keeps its own hub, so everything a hub promises — one thread, one document served from it (D16) — holds
as it always did. What the modules share is decided here: one :class:`~claudia_server.hub.Room` counts the documents
of all of them against ``max_documents`` (D432).

Ids are unique per app, not per server (D431): ``notes`` can be a workbook and a text at once. An address that names
the app (``/api/<app>/docs/<id>/ws``) is never ambiguous; the old one without it uses ``Suite.locate`` and
``Suite.for_new``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from .auth import UserDirectory
from .hub import Hub, HubError, Room, StoredInfo
from .i18n import msg

#: The apps of the suite and the document model of each (``module:Class``), in the order a server hosts them by
#: default. The first is where the old address makes a document when nobody says which app (D431).
APP_MODELS: dict[str, str] = {
    "computes": "claudia_computes.model:WorkbookModel",
    "composes": "claudia_composes:TextModel",
    "creates": "claudia_creates:SlideModel",
}


@dataclass(frozen=True)
class Module:
    """One app on a server: the hub of its documents and the people of each of them."""

    hub: Hub
    directory: UserDirectory

    @property
    def app(self) -> str:
        """The app's name, ``DocumentModel.app`` of its documents, such as ``"computes"``."""
        return self.hub.app


class Suite:
    """The modules of one server, at least one, each app at most once.

    ``max_documents`` (default: the first hub's) bounds the documents of all modules together; the hubs are made to
    share one :class:`Room` for it, and the first hub's worker pool."""

    def __init__(self, modules: Iterable[Module], *, max_documents: int | None = None):
        self._modules: dict[str, Module] = {}
        for module in modules:
            if module.app in self._modules:
                raise ValueError(f"a server hosts each app once, and {module.app} was given twice")
            self._modules[module.app] = module
        if not self._modules:
            raise ValueError("a server hosts at least one app")
        room = Room(max_documents if max_documents is not None else self.first.hub.max_documents)
        pool = self.first.hub.workers
        for module in self._modules.values():
            module.hub.share_room(room)
            module.hub.workers = pool  # one pool per process (D134), whatever the number of apps (D430)
        self._room = room

    @classmethod
    def single(cls, hub: Hub, directory: UserDirectory) -> Suite:
        """The suite of a server with one app: what every server was before D430."""
        return cls([Module(hub, directory)])

    # -- the modules ------------------------------------------------------------------------------------------------
    def __iter__(self) -> Iterator[Module]:
        return iter(self._modules.values())

    @property
    def apps(self) -> tuple[str, ...]:
        """The apps this server hosts, in order."""
        return tuple(self._modules)

    @property
    def first(self) -> Module:
        """The first module, the one that answers when nobody says which app."""
        return next(iter(self._modules.values()))

    def module(self, app: str) -> Module | None:
        """The module of ``app``, or ``None`` if this server does not host it."""
        return self._modules.get(app)

    def locate(self, doc_id: str) -> Module | None:
        """The first module, in order, that holds a document with this id (open or stored); ``None`` if none does."""
        for module in self._modules.values():
            if module.hub.exists(doc_id):
                return module
        return None

    async def find(self, uid: str) -> tuple[Module, StoredInfo] | None:
        """The module and the stored document with exactly this uid, looking in every module in order (D533);
        ``None`` if this server has none."""
        for module in self._modules.values():
            info = await module.hub.find(uid)
            if info is not None:
                return module, info
        return None

    def for_new(self, app: str | None) -> Module:
        """The module a new document goes to when the address does not say: ``app`` if given, else the first.
        ``HubError('bad_request')`` for an app this server does not host."""
        if app is None:
            return self.first
        module = self._modules.get(app) if isinstance(app, str) else None
        if module is None:
            raise HubError("bad_request", msg("this server does not host {app}", app=str(app)))
        return module

    # -- what they share --------------------------------------------------------------------------------------------
    @property
    def max_documents(self) -> int:
        """The most documents the server holds, all apps together."""
        return self._room.max_documents

    @max_documents.setter
    def max_documents(self, value: int) -> None:
        self._room.max_documents = value

    def listing(self) -> list[dict]:
        """The documents of every app (``Hub.listing``), the most recently changed first."""
        found = [entry for module in self._modules.values() for entry in module.hub.listing()]
        return sorted(found, key=lambda entry: (entry["modified"], entry["app"], entry["id"]), reverse=True)

    async def start(self) -> None:
        """Start every module's housekeeping."""
        for module in self._modules.values():
            await module.hub.start()

    async def stop(self) -> None:
        """Stop every module: each lets go of its documents (a sealed store packs them) and of its worker pool."""
        for module in self._modules.values():
            await module.hub.stop()
