"""The FastAPI application (E3.1).

    WebSocket  /api/docs/{doc}/ws    the live connection (see protocol.py)
    GET        /api/health           liveness, the apps it serves (and its version, to this computer only)
    GET        /api/protocol         machine-readable description of the protocol

    GET        /api/docs             the documents on this server (see Hub.listing)

The list can be switched off. It shows that a document exists and nothing else: no user names and no content. Every
document has its own users and passwords (D35), so a document is opened with its id, a name and a password that
belong to it.

WebSocket handshake: the client connects, then sends ``hello`` as its first frame (credentials travel in a frame, not in
the URL, so they do not end up in logs):

    {"id": 1, "method": "hello", "params": {"user": "ann", "password": "...", "create": false, "locale": "de"}}

``locale`` is optional and always the client's own setting (E5.7, D31): there is no account profile to keep it on
(a document's users are scoped to that document, D35), so the client sends whatever it is showing itself with —
usually the OS or browser locale, or whatever the person picked in their own client. Anything that is not a short
tag of letters, digits and hyphens is ignored and falls back to ``"en"``; the negotiated value is echoed back in the
welcome so the client can tell when its request was not honoured. Nothing is translated with it yet — this is the
plumbing a later change renders messages with, not a behaviour change.

The answer carries the welcome data (user, role, document, line, revision, people, limits, locale) and ``created``:
true if the document was made by this very ``hello``, so that the client can show the recovery key at once. After that
the connection speaks the protocol of ``protocol.py`` and receives events. With ``create: true`` for a document that
does not exist, the document is made and the person becomes its owner. A wrong password, an unknown name and a
document that does not exist are the same answer. Failures to get that far close the socket with a code: 4400 bad
request, 4401 unauthorized, 4404 no such document, 4408 no hello in time, 4403 foreign origin or host, 4429 too many
failed tries (the error carries ``retry_after``, the seconds to wait; nothing is locked), 4423 the
document is sealed (nobody who holds all its keys has opened it since the server started: a viewer tries again later),
1013 too many connections, too many people waiting to be let in, a full server or a client that is too slow.

A person who has lost their password sends ``"recovery_key": "<key>"`` with their ``user`` and a *new* ``password`` (and
no ``create``): if the key is the document's, they get that password, keep their role (somebody new becomes an owner)
and are in. A wrong key, a document that does not exist and a server without recovery keys all look alike.

A server started with an access secret lets only those who know it make documents: they add ``"access": "<secret>"`` to
``hello`` (and send ``Authorization: Bearer <secret>`` to read the list of documents). Everybody else is answered as if
the document could not be made, so nothing is learned about which documents exist.

The root of the server is never a dead end. With a built web app (``web_dir``) every address that is not under /api
(and not a file) shows its start page; without one, / shows a short page that says what this server is and how to use
it.

Browsers: a page on another origin could try to use a user's localhost server. Two rules keep it out. The server
answers only to its own names (``allowed_hosts``, see ``hosts.py``), so a page that has pointed its own name at this
computer (DNS rebinding) is refused whatever it sends. And the WebSocket refuses a request whose ``Origin`` is neither
the server itself nor in ``allowed_origins``. Non-browser clients send no Origin and are not affected by the second.

Abuse: only ``max_waiting`` connections (``max_waiting_per_address`` from one address) may wait to be let in at the same
time, and a ``Hub`` holds at most ``max_documents`` documents. Without these, a flood of unauthenticated sockets queues
behind the password hashing without end and anybody can fill the disk with documents.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import math
from collections.abc import Callable, Iterable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

from claudia_core import Import, LanguageError, Setup, normalize_language
from claudia_document_file import clean_details, is_uid
from claudia_fonts import DEFAULT_SUBSTITUTIONS

from ._version import __version__
from .admin_api import AdminContext, admin_router
from .auth import Account, AuthRefused, Credentials, RecoverableDirectory, UserDirectory
from .client_address import ClientAddress
from .fonts import FontService, font_router
from .formats import CLAUDIA, CLAUDIA_EXPORT, import_state
from .hosts import AllowedHosts, HostGuard
from .hub import Hub, HubError, same_document_message
from .hyphenation import HyphenationService, hyphenation_router
from .i18n import localized, message_of, msg
from .idle import IdleMiddleware, IdleWatch
from .login_throttle import LoginThrottle
from .protocol import DEFAULT_LOCALE, RequestError, normalize_locale, parse_request
from .security_headers import SecurityHeaders, WebScriptHashes
from .suite import Module, Suite
from .thing_names import naming_steps
from .throttle import Throttle
from .uploads import Upload, UploadDesk, UploadRefused, file_name, read_body

log = logging.getLogger("claudia_server")
HELLO_TIMEOUT = 10.0
OUTGOING_QUEUE = 1000  # frames waiting for a slow client before it is dropped
DEFAULT_MAX_WAITING = 256  # connections that have not been let in yet, all together ...
DEFAULT_MAX_WAITING_PER_ADDRESS = 64  # ... and from one address (a whole school may sit behind one)
MIN_ACCESS_SECRET = 16
_CLOSE = {"not_found": 4404, "bad_request": 4400, "unavailable": 1013, "internal": 1011, "sealed": 4423}


_REVALIDATE = "no-cache"
"""Keep a copy, but ask the server before every use (a cheap ``304`` when nothing changed)."""
_FOR_GOOD = "public, max-age=31536000, immutable"
"""For files whose name changes with their content: the copy can never be out of date."""
_HASHED_ASSETS = "_nuxt/"
"""Where the web build puts the files it names by content hash."""


class SinglePageApp(StaticFiles):
    """The built web app. A path that is neither a file nor under /api gets the start page (so a bookmark like
    /budget, or a reload on any address, still ends up on the welcome form); a missing file with an extension stays a
    404.

    Every answer says how long it may be kept (D248). Without that a client (a browser, the WebKit view of a desktop
    shell) decides for itself and may show the previous version of the app for a long time after the server was
    updated.
    Pages and any file not named by its content are revalidated on each load; the content-hashed files under
    ``_nuxt/`` are kept for good."""

    async def get_response(self, path, scope):
        """The file, or the start page for an address of the app."""
        path = path.replace("\\", "/")  # Starlette hands Windows the path with backslashes
        response = await self._found_or_start_page(path, scope)
        response.headers["Cache-Control"] = _FOR_GOOD if path.startswith(_HASHED_ASSETS) else _REVALIDATE
        return response

    async def _found_or_start_page(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            response = None
        if response is not None and response.status_code != 404:
            return response
        last = path.rsplit("/", 1)[-1]
        if path.startswith("api/") or path == "api" or "." in last:
            raise StarletteHTTPException(404)
        return await super().get_response("index.html", scope)


_LANDING = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claudia server</title>
<style>
 body{font:16px/1.5 system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem;color:#222}
 code,pre{background:#f1f1f1;border-radius:4px;padding:.1rem .3rem;font-size:.9em}
 pre{padding:.7rem;overflow:auto}
 @media (prefers-color-scheme:dark){body{background:#1d1d1f;color:#e8e8e8}code,pre{background:#2c2c2e}}
</style></head><body>
<h1>Claudia server</h1>
<p>This server is running and holds documents, but it was started without the web app, so there is no page to open
a document here.</p>
<h2>Use it from a browser</h2>
<p>Build the web app once, then start the server with it:</p>
<pre>python3 -m claudia_server --web web/.output/public</pre>
<p>Open this address again: it asks for the document and your name.</p>
<h2>Use it from the desktop app</h2>
<p>Connect to this address (HOST:PORT is what your browser's address bar shows) and give the document, your name and
your password.</p>
<p><a href="/api/health">/api/health</a><!--more-links--></p>
</body></html>
"""


API_DOCS = "/api/swagger"
"""Where the interactive API description is served, with ``api_docs`` only (SEC-14)."""

LOOPBACK_CLIENTS = frozenset({"127.0.0.1", "::1"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]"})


def health_answer(suite: Suite, request: Request) -> dict[str, object]:
    """``/api/health``: alive, and which apps this server serves (a shell checks that even when the document list is
    behind a secret, D444). The version is added only for a request from this computer to this computer's address —
    a desktop app that finds a running server must know whether it is its own (D445); nobody else needs it, and a
    reverse proxy on the same machine forwards from the loopback but with its public host name."""
    answer: dict[str, object] = {"ok": True, "apps": list(suite.apps)}
    client = request.client.host if request.client else ""
    host = urlsplit(f"//{request.headers.get('host', '')}").hostname or ""
    if client in LOOPBACK_CLIENTS and (host in LOOPBACK_HOSTS or f"[{host}]" in LOOPBACK_HOSTS):
        answer["version"] = __version__
    return answer


def origin_allowed(origin: str | None, host: str | None, allowed: set[str]) -> bool:
    """May a page with this ``Origin`` use the WebSocket? A client that is not a browser sends none."""
    if origin is None:
        return True
    if origin in allowed:
        return True
    return host is not None and urlsplit(origin).netloc == host  # the page came from this server


class _Waiting:
    """The connections that have not been let in yet, all together and per address (SEC-02).

    A person is let in within milliseconds. A socket that stays here is queued behind the password hashing or is doing
    nothing at all, so the number of them is bounded: past it, the newcomer is turned away and the ones that are in
    keep working."""

    def __init__(self, most: int, most_per_address: int):
        self._most = most
        self._most_per_address = most_per_address
        self._per_address: dict[str, int] = {}
        self._total = 0

    def enter(self, address: str) -> bool:
        """Take a place for a connection from ``address``; ``False`` if there is none for it."""
        here = self._per_address.get(address, 0)
        if self._total >= self._most or here >= self._most_per_address:
            return False
        self._per_address[address] = here + 1
        self._total += 1
        return True

    def leave(self, address: str) -> None:
        """Give the place of a connection from ``address`` back."""
        self._total -= 1
        if self._per_address[address] > 1:
            self._per_address[address] -= 1
        else:
            del self._per_address[address]


class Gateway:
    """What the WebSocket routes need: the apps of the server (``Suite``: each app's hub and the users of each of its
    documents), and the rule for making new documents.

    Checking a password and adding a person cost real work (the password hashing is meant to be slow), so they run in
    threads and never stop the event loop (SEC-03). At most ``max_hashing`` of them run at once, so a flood of logins
    cannot use up the memory of the machine (the hashing needs a lot of it).

    Nobody costs the server anything before they are let in beyond a place in the queue: at most ``max_waiting``
    connections (``max_waiting_per_address`` from one address) wait to be let in, and the others are turned away with
    1013 (SEC-02). With an ``access_secret`` only those who know it can make documents. It has at least
    ``MIN_ACCESS_SECRET`` characters, because it is the only thing between the network and the disk."""

    def __init__(
        self,
        suite: Suite,
        allowed: set[str],
        *,
        max_hashing: int = 2,
        access_secret: str | None = None,
        max_waiting: int = DEFAULT_MAX_WAITING,
        max_waiting_per_address: int = DEFAULT_MAX_WAITING_PER_ADDRESS,
        proxy_hops: int = 0,
        login_throttle: LoginThrottle | None = None,
    ):
        if access_secret is not None and len(access_secret) < MIN_ACCESS_SECRET:
            raise ValueError(f"the access secret needs at least {MIN_ACCESS_SECRET} characters")
        self.suite = suite
        self.allowed = allowed
        self.uploads = UploadDesk()  # files brought to become documents (D440)
        self._secret = None if access_secret is None else access_secret.encode()
        self._creating = asyncio.Lock()  # one new document at a time: the first person to ask becomes its owner
        self._hashing = asyncio.Semaphore(max_hashing)
        self._waiting = _Waiting(max_waiting, max_waiting_per_address)
        self.client_address = ClientAddress(proxy_hops)  # who a connection is, behind a proxy too (D1275)
        self.login_throttle = login_throttle or LoginThrottle()  # failed logins wait longer each time (D1266)

    async def prepare(self, connection, raw: str | bytes) -> None:
        """Do the slow hashing a request frame needs before ``connection.handle`` runs it (SEC-21).

        In a thread, behind the same cap as the logins (SEC-03): the event loop, and so every other window, goes on.
        Whatever goes wrong here is left to ``handle``, which hashes for itself and says what is wrong."""
        work = connection.hashing_for(raw)
        if work is None:
            return
        try:
            async with self._hashing:
                await asyncio.to_thread(work)
        except Exception:
            log.debug("could not hash ahead", exc_info=True)

    def accepts_secret(self, candidate: object) -> bool:
        """Did the person give the server's access secret? Always ``True`` for a server that has none."""
        if self._secret is None:
            return True
        if not isinstance(candidate, str):
            return False
        return hmac.compare_digest(candidate.encode(errors="surrogatepass"), self._secret)

    def set_secret(self, access_secret: str | None) -> None:
        """Change the access secret while the server runs (the settings pages, E3.1/admin). ``None`` removes it, so
        anyone may then make documents or read the list. Takes effect for the next request; nobody already let in
        is affected. ``ValueError`` for a secret shorter than ``MIN_ACCESS_SECRET``."""
        if access_secret is not None and len(access_secret) < MIN_ACCESS_SECRET:
            raise ValueError(f"the access secret needs at least {MIN_ACCESS_SECRET} characters")
        self._secret = None if access_secret is None else access_secret.encode()

    async def _verify(self, module: Module, doc_id: str, credentials: Credentials) -> Account | None:
        async with self._hashing:
            return await asyncio.to_thread(module.directory.verify, doc_id, credentials)

    def module_for(self, doc_id: str, app: str | None, asked_app: object = None) -> Module:
        """The module a connection to ``doc_id`` is for (D431). With ``app`` (from the address) that app's, and
        ``HubError('not_found')`` if the server does not host it. Without it (the old address): the first module that
        has the document, else the one ``asked_app`` (``hello.app``) names, else the first."""
        if app is not None:
            module = self.suite.module(app)
            if module is None:
                raise HubError("not_found", msg("this server does not host {app}", app=app))
            return module
        found = self.suite.locate(doc_id)
        if found is not None:
            return found
        return self.suite.for_new(asked_app if isinstance(asked_app, str) else None)

    async def admit(
        self, doc_id: str, credentials: Credentials, create: bool, access: object = None, *, app: str | None = None
    ) -> Account | None:
        """The account of the person, or ``None``. A new document is made for whoever asks first (its owner), if the
        server makes documents and the person knows its access secret (``access``), if it has one. ``app`` is the
        app of the document (default: as for the old address, see :meth:`module_for`).

        ``HubError('unavailable')`` if the server already holds as many documents as it may."""
        return (await self._admit(self.module_for(doc_id, app), doc_id, credentials, create, access))[0]

    async def _admit(
        self, module: Module, doc_id: str, credentials: Credentials, create: bool, access: object
    ) -> tuple[Account | None, bool]:
        """As :meth:`admit`, and whether the document was just made."""
        hub, directory = module.hub, module.directory
        if hub.exists(doc_id):
            return await self._verify(module, doc_id, credentials), False
        if not (create and hub.allow_create and self.accepts_secret(access)):
            await self._verify(module, doc_id, credentials)  # the same work as for a document that exists (SEC-04) ...
            return None, False  # ... and the same answer
        async with self._creating:
            if hub.exists(doc_id):  # somebody was faster
                return await self._verify(module, doc_id, credentials), False
            if not (isinstance(credentials.user, str) and isinstance(credentials.password, str)):
                return None, False
            await hub.ensure_room()  # before any hashing or disk: a refused document costs nothing
            # The same work as for a document that exists (SEC-04). It usually finds nobody, but not always: the user
            # directory is kept apart from the documents, so a creation that died between the two can leave this
            # person's account behind without a document. They then get that account back, not a second owner.
            if (reserved := await self._verify(module, doc_id, credentials)) is not None:
                return reserved, False
            async with self._hashing:
                account = await asyncio.to_thread(
                    directory.add_user, doc_id, credentials.user, credentials.password, "owner"
                )
            try:
                await hub.open(doc_id, create=True)
            except BaseException:
                directory.remove_user(doc_id, credentials.user)
                raise
            return account, True

    async def _recover(self, module: Module, doc_id: str, params: dict) -> Account | None:
        """The account of a person who came in with a recovery key and chose a new password (they are logged in)."""
        key, user, password = params.get("recovery_key"), params.get("user"), params.get("password")
        if not (isinstance(key, str) and isinstance(user, str) and isinstance(password, str)):
            raise HubError("bad_request", msg("a recovery key, a name and a new password are needed"))
        directory = module.directory
        if not isinstance(directory, RecoverableDirectory):
            raise HubError("unavailable", msg("this server does not keep recovery keys"))
        async with self._hashing:
            return await asyncio.to_thread(directory.recover, doc_id, key, user, password)

    async def serve(self, websocket: WebSocket, doc_id: str, app: str | None = None) -> None:
        """One connection from the handshake to its end; ``app`` is the app the address names (``None``: the old
        address without one, D431)."""
        if not origin_allowed(websocket.headers.get("origin"), websocket.headers.get("host"), self.allowed):
            await websocket.close(code=4403)  # refused during the handshake (HTTP 403)
            return
        address = self.client_address.of(websocket)
        if not self._waiting.enter(address):  # taken before the accept, so a client that was let on has its place
            await websocket.accept()  # (a refusal before the accept carries no close code)
            await websocket.close(code=1013)
            return
        try:
            await websocket.accept()
            admitted = await self._hello(websocket, doc_id, app, address)
        finally:
            self._waiting.leave(address)
        if admitted is not None:
            request_id, account, document, created, locale, imported = admitted
            await _Live(
                websocket,
                document,
                account,
                request_id,
                created=created,
                locale=locale,
                imported=imported,
                prepare=self.prepare,
            ).run()

    # -- a document made from a file (D438, D440) ------------------------------------------------------------------
    def _upload_for(self, params: dict) -> Upload | None:
        """The upload ``hello`` names, still held (it is taken only once the document exists)."""
        token = params.get("upload")
        if token is None:
            return None
        upload = self.uploads.peek(token)
        if upload is None:
            raise HubError("bad_request", msg("the file is no longer here: choose it again"))
        if upload.fmt == CLAUDIA:
            raise HubError("bad_request", msg("a Claudia file goes in as it is, not as a new document"))
        if params.get("create") is not True:
            raise HubError("bad_request", msg("a file becomes a new document: hello needs create"))
        return upload

    @staticmethod
    def _details_for(params: dict) -> tuple[str, tuple[str, ...]]:
        """The description and tags the person gave an import, tidied: checked before anything is made, so that a tag
        that does not fit costs nobody a half-made document."""
        description, tags = params.get("description", ""), params.get("tags", [])
        if not isinstance(description, str) or not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise HubError("bad_request", msg("description is text and tags are a list of words"))
        try:
            return clean_details(description, tags)
        except ValueError as error:
            raise HubError("bad_request", message_of(error)) from error

    async def _read_upload(
        self, module: Module, doc_id: str, upload: Upload, locale: str
    ) -> tuple[Upload, dict, list[dict]]:
        """The state the import makes, read in the worker pool before anything is created (D436): a file that cannot
        be read costs nobody a half-made document. Its things are named in ``locale``, the language of the importer."""
        if module.app != upload.app:
            raise HubError(
                "bad_request", msg("{name} cannot become a document of {app}", name=upload.name, app=module.app)
            )
        if module.hub.exists(doc_id):
            raise HubError("bad_request", msg("{id} is here already: give the new document another name", id=doc_id))
        try:
            state, losses = await module.hub.workers.submit(
                import_state, upload.fmt, upload.data, locale, state_schema=module.hub.state_schema
            )
        except Exception as exc:  # noqa: BLE001 - whatever a reader raises, the file is not one it can read
            log.info("cannot import %s: %s", upload.name, exc)
            raise HubError("bad_request", msg("{name} cannot be read", name=upload.name)) from exc
        return upload, state, losses

    async def _import(
        self,
        module: Module,
        doc_id: str,
        hosted,
        author: str,
        imported: tuple[Upload, dict, list[dict]],
        params: dict,
        details: tuple[str, tuple[str, ...]] = ("", ()),
    ) -> dict:
        """Make the new document what the file holds: one ``core.Import`` entry, the file itself kept in the document
        unless the person said not to (D439), and the description and tags the person chose in its plain manifest.
        Answers what the welcome says about it."""
        upload, state, losses = imported
        self.uploads.take(upload.token)
        keep = params.get("keep_original") is not False and upload.fmt != CLAUDIA_EXPORT  # an export is no original
        digest = hashlib.sha256(upload.data).hexdigest()
        kept = keep and await asyncio.to_thread(module.hub.keep_original, doc_id, upload.data)
        hosted.document.execute(Import(upload.name, upload.fmt, state, sha256=digest, kept=kept), author=author)
        described = details != ("", ()) and await asyncio.to_thread(module.hub.describe, doc_id, *details)
        return {"name": upload.name, "format": upload.fmt, "kept": kept, "losses": losses, "described": described}

    async def _read_hello(self, websocket: WebSocket) -> tuple[Any, dict] | None:
        """The first frame as ``(request id, params)``; the socket is closed with the reason if it is not a hello."""
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), HELLO_TIMEOUT)
        except TimeoutError:
            await websocket.close(code=4408)
            return None
        except WebSocketDisconnect:
            return None
        try:
            request_id, name, params = parse_request(raw, self.suite.first.hub.limits)
        except RequestError as exc:
            await _refuse(websocket, None, exc.code, exc.message, 4400)
            return None
        if name != "hello" or not isinstance(params, dict):
            await _refuse(
                websocket, request_id, "bad_request", msg("the first message must be hello with params"), 4400
            )
            return None
        return request_id, params

    async def _hello(self, websocket: WebSocket, doc_id: str, app: str | None, address: str):
        """The first frame: ``(request id, account, document)`` if the person may come in, else the socket is closed."""
        hello = await self._read_hello(websocket)
        if hello is None:
            return None
        request_id, params = hello
        locale = normalize_locale(params.get("locale"))
        if (wait := self.login_throttle.check(address, doc_id, params.get("user"))) > 0:
            await _refuse_for_now(websocket, request_id, wait, locale)  # before any hashing: it costs nothing (D1266)
            return None
        try:
            Hub.check_id(doc_id)
            upload = self._upload_for(params)
            details = self._details_for(params) if upload is not None else ("", ())
            module = self.module_for(doc_id, app, params.get("app") or (upload.app if upload else None))
            imported = None if upload is None else await self._read_upload(module, doc_id, upload, locale)
            if params.get("recovery_key") is not None:
                account, created = await self._recover(module, doc_id, params), False
            else:
                credentials = Credentials(params.get("user"), params.get("password"))
                account, created = await self._admit(
                    module, doc_id, credentials, params.get("create") is True, params.get("access")
                )
            if account is None:
                self.login_throttle.failed(address, doc_id, params.get("user"))
                await _refuse(websocket, request_id, "unauthorized", msg("missing or wrong credentials"), 4401, locale)
                return None
            self.login_throttle.succeeded(address)
            document = await module.hub.open(doc_id)
            if created and imported is not None:
                answer = await self._import(module, doc_id, document, account.user, imported, params, details)
                return request_id, account, document, created, locale, answer
            if created:
                _set_up(document.document, account.user, locale)
            return request_id, account, document, created, locale, None
        except HubError as exc:
            await _refuse(websocket, request_id, exc.code, exc.message, _CLOSE.get(exc.code, 4400), locale)
        except AuthRefused as exc:
            self.login_throttle.failed(address, doc_id, params.get("user"))
            await _refuse(websocket, request_id, "unauthorized", exc.args[0], 4401, locale)
        except ValueError as exc:  # the name or password of a new document is not acceptable
            await _refuse(websocket, request_id, "bad_request", message_of(exc), 4400, locale)
        return None


class _Presence:
    """``/api/presence``: a socket that a page with no document open keeps, so that the server knows it is in use
    (D434). It carries nothing and needs no login, so it says nothing to anybody; the same origin rule as every other
    socket applies, and at most ``most`` of them are open at once (SEC-02)."""

    def __init__(self, gateway: Gateway, most: int):
        self._gateway = gateway
        self._most = most
        self._open = 0

    async def serve(self, websocket: WebSocket) -> None:
        """Hold the socket until the page lets go of it; whatever the page sends is ignored."""
        if not origin_allowed(websocket.headers.get("origin"), websocket.headers.get("host"), self._gateway.allowed):
            await websocket.close(code=4403)
            return
        if self._open >= self._most:
            await websocket.accept()
            await websocket.close(code=1013)
            return
        self._open += 1
        try:
            await websocket.accept()
            while (await websocket.receive())["type"] != "websocket.disconnect":
                pass
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            self._open -= 1


def _set_up(document, author: str, locale: str) -> None:
    """What a new document starts with (``DocumentModel.setup_commands``: a workbook's first sheet, a text's language,
    D915), as one ``Setup`` entry by its maker that is nobody's undo step (UX-33). Before, her client did this as her
    own first steps, and her first Ctrl+Z took them back. A thing the empty document already holds (a presentation's
    first slide) is named in the same entry, in her language: every thing has a name (D550)."""
    try:
        language: str | None = normalize_language(locale)
    except LanguageError:
        language = None
    commands = [*type(document.model).setup_commands(language), *naming_steps(document.model, locale)]
    if commands:
        document.execute(Setup(tuple(commands)), author=author)


async def _refuse(
    websocket: WebSocket,
    request_id,
    code: str,
    message: str,
    close_code: int,
    locale: str = DEFAULT_LOCALE,
    **more: object,
) -> None:
    """Answer the first frame with an error (its message in ``locale``, once the person has said which) and close the
    socket with ``close_code``. ``more`` are further fields of the error (``retry_after``)."""
    error = {"code": code, "message": localized(message, locale), **more}
    await websocket.send_text(json.dumps({"id": request_id, "ok": False, "error": error}))
    await websocket.close(code=close_code)


async def _refuse_for_now(websocket: WebSocket, request_id, wait: float, locale: str) -> None:
    """The login came too soon after failed ones (D1266): refused before any hashing, with the whole seconds to wait
    (``retry_after``) and the close code 4429. Nothing is locked: the same login is looked at when the wait is over."""
    seconds = max(1, math.ceil(wait))
    message = (
        msg("Too many tries. Try again in 1 second.")
        if seconds == 1
        else msg("Too many tries. Try again in {seconds} seconds.", seconds=seconds)
    )
    await _refuse(websocket, request_id, "too_many_tries", message, 4429, locale, retry_after=seconds)


async def _nothing_to_prepare(connection, raw) -> None:
    """What a connection does before a request when nothing is to be hashed ahead (no gateway behind it)."""


class _Live:
    """A connection that has been let in: events go out through a bounded queue, requests come in through ``handle``."""

    def __init__(
        self,
        websocket: WebSocket,
        document,
        account: Account,
        request_id,
        *,
        created: bool = False,
        locale: str = DEFAULT_LOCALE,
        imported: dict | None = None,
        prepare=None,
    ):
        self.prepare = prepare or _nothing_to_prepare
        self.created = created
        self.imported = imported
        self.websocket = websocket
        self.document = document
        self.account = account
        self.request_id = request_id
        self.locale = locale
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=OUTGOING_QUEUE)
        self.background: set[asyncio.Task] = set()

    def send(self, text: str) -> None:
        """Queue a frame; a client that does not keep up is dropped (and the delivery fails, so the hub knows)."""
        try:
            self.queue.put_nowait(text)
        except asyncio.QueueFull:
            task = asyncio.get_running_loop().create_task(self.websocket.close(code=1013))
            self.background.add(task)
            task.add_done_callback(self.background.discard)
            raise

    async def _pump(self) -> None:
        try:
            while True:
                await self.websocket.send_text(await self.queue.get())
        except Exception:
            return  # the socket is gone; the receive loop notices too

    async def run(self) -> None:
        """Welcome the person, then serve requests until the socket ends."""
        try:
            connection = self.document.connect(self.account, self.send, locale=self.locale)
        except HubError as exc:
            await _refuse(
                self.websocket, self.request_id, exc.code, exc.message, _CLOSE.get(exc.code, 1013), self.locale
            )
            return
        result = {**connection.welcome(), "created": self.created}
        if self.imported is not None:
            result["imported"] = self.imported
        welcome = {"id": self.request_id, "ok": True, "result": result}
        self.send(json.dumps(welcome, separators=(",", ":")))
        pump = asyncio.create_task(self._pump())
        try:
            while not connection.broken:
                message = await self.websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                text = message.get("text")
                frame = text if text is not None else message.get("bytes", b"")
                await self.prepare(connection, frame)
                connection.handle(frame)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            pump.cancel()
            connection.close()
            for task in self.background:
                task.cancel()


def _bearer_token(authorization: str | None) -> str | None:
    """The token of an ``Authorization: Bearer <token>`` header, or ``None`` for any other header."""
    scheme, _, token = (authorization or "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else None


def create_app(
    hub: Hub | Suite,
    directory: UserDirectory | None = None,
    *,
    allowed_origins: Iterable[str] = (),
    allowed_hosts: Iterable[str] = (),
    access_secret: str | None = None,
    max_waiting: int = DEFAULT_MAX_WAITING,
    max_waiting_per_address: int = DEFAULT_MAX_WAITING_PER_ADDRESS,
    proxy_hops: int = 0,
    login_throttle: LoginThrottle | None = None,
    web_dir: str | Path | None = None,
    list_documents: bool = True,
    admin: AdminContext | None = None,
    fonts: FontService | None = None,
    hyphenation: HyphenationService | None = None,
    idle: IdleWatch | None = None,
    api_docs: bool = False,
) -> FastAPI:
    """The server for the apps of ``hub``: a ``Suite`` (one server, several apps, D430), or one ``Hub`` with the users
    of each of its documents in ``directory`` (a server of one app, as every server was before).

    Every app's documents are reached at ``/api/<app>/docs/<id>/ws`` and listed at ``/api/<app>/docs``;
    ``/api/docs`` lists the documents of all apps, and ``/api/docs/<id>/ws`` is the old address without the app
    (D431, see ``Gateway.module_for``). ``/api/presence`` is a socket that carries nothing: a page with no document
    open keeps it, so that the server knows it is in use (D434). With ``idle``, every request and socket is reported
    to that watch, which runs while the server does.

    The server answers only to ``localhost``, to IP addresses and to the host names in ``allowed_hosts`` (SEC-01, see
    ``claudia_server.hosts``); ``ValueError`` if one of them is not a host name. ``list_documents`` serves
    ``GET /api/docs`` (see ``Hub.listing``); switch it off on a shared server where the existence of a document should
    not be visible. ``api_docs`` serves the interactive API description at ``API_DOCS``; it is off by default because
    FastAPI's page loads its script from a CDN (SEC-14).

    With an ``access_secret`` (at least ``MIN_ACCESS_SECRET`` characters, ``ValueError`` otherwise) only those who know
    it can make documents or read the list. ``max_waiting`` and ``max_waiting_per_address`` bound the connections that
    wait to be let in (SEC-02).

    With ``proxy_hops`` reverse proxies in front of the server that set ``X-Forwarded-For``, a connection is counted
    by the address the nearest proxy appended, not by the proxy's own (D1275, ``client_address.py``); 0, the default,
    counts by the socket and ignores the header.

    Failed logins wait longer each time (D1266, ``login_throttle.py``), at the document's ``hello`` and at the
    administrator's sign-in alike, by the rules of ``login_throttle`` (a default one if none is given: a test passes
    its own for the clock). The login is refused with 4429 and ``retry_after`` before any hashing.

    With ``admin`` (``admin_api.AdminContext``), the server also serves ``/api/admin/*``: the settings pages, signed
    in to separately from any document (``admin.py``). Without it — the default, and every use before this existed
    — none of those routes exist at all, which keeps every other caller of this function unaffected."""
    suite = _as_suite(hub, directory)
    allowed = {o.rstrip("/") for o in allowed_origins}
    hosts = AllowedHosts(allowed_hosts)
    gateway = Gateway(
        suite,
        allowed,
        access_secret=access_secret,
        max_waiting=max_waiting,
        max_waiting_per_address=max_waiting_per_address,
        proxy_hops=proxy_hops,
        login_throttle=login_throttle,
    )

    presence = _Presence(gateway, max_waiting)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await suite.start()
        if idle is not None:
            await idle.start()
        try:
            yield
        finally:
            if idle is not None:
                await idle.stop()
            await suite.stop()

    # SEC-14: FastAPI's page loads its script from a CDN, so it is served only when the administrator asks for it.
    app = FastAPI(
        title="Claudia server",
        docs_url=API_DOCS if api_docs else None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    if allowed:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=sorted(allowed),
            allow_methods=["GET"],
            allow_headers=["Content-Type", "Authorization"],
        )
    # SEC-13: CSP, nosniff, referrer and permissions on every answer; the start page's inline scripts by hash.
    app.add_middleware(SecurityHeaders, script_hashes=WebScriptHashes(web_dir))
    if idle is not None:
        app.add_middleware(IdleMiddleware, watch=idle)
    app.add_middleware(HostGuard, hosts=hosts)  # added last, so it is the first to see a request (even a preflight)
    app.state.suite = suite
    app.state.gateway = gateway
    app.state.hub = suite.first.hub  # the first app's hub, for the callers that know one app

    @app.get("/api/health")
    async def health(request: Request):
        return health_answer(suite, request)

    _fixed_routes(app, suite, gateway, presence, list_documents)
    if admin is not None:
        app.include_router(
            admin_router(
                suite,
                gateway.set_secret,
                admin,
                throttle=gateway.login_throttle,
                address_of=gateway.client_address.of,
            )
        )
    if fonts is not None:
        app.include_router(font_router(fonts, DEFAULT_SUBSTITUTIONS, _people_of(gateway, admin)))
    if hyphenation is not None:
        app.include_router(hyphenation_router(hyphenation))
    # The addresses with the app (D431) come after every fixed /api/<word>/... route, so that none of those is read as
    # the name of an app.
    _app_routes(app, suite, gateway, list_documents)
    api_docs_link = f' &middot; <a href="{API_DOCS}">API description</a>' if api_docs else ""
    _web_routes(app, web_dir, more_links=api_docs_link)
    return app


def _as_suite(hub: Hub | Suite, directory: UserDirectory | None) -> Suite:
    """``hub`` as a suite (a single hub is a suite of one), every hub knowing where its documents' people are kept."""
    if isinstance(hub, Suite):
        suite = hub
    elif directory is None:
        raise TypeError("a single Hub needs the UserDirectory of its documents")
    else:
        suite = Suite.single(hub, directory)
    for module in suite:
        if module.hub.directory is None:
            module.hub.directory = module.directory  # owners add people to their documents through it
    return suite


def _may_list(gateway: Gateway, request: Request) -> None:
    """HTTP 401 unless the request carries the access secret (when the server has one)."""
    if not gateway.accepts_secret(_bearer_token(request.headers.get("authorization"))):
        raise HTTPException(401, "this server needs its access secret", headers={"WWW-Authenticate": "Bearer"})


def _fixed_routes(app: FastAPI, suite: Suite, gateway: Gateway, presence: _Presence, list_documents: bool) -> None:
    """The routes without an app in the address: the first app's protocol, every app's list, the old live address
    and the presence socket."""

    @app.get("/api/protocol")
    async def protocol():
        """The protocol of the first app (the address before D431; ``/api/<app>/protocol`` names the app)."""
        return suite.first.hub.methods.describe(suite.first.hub.limits)

    if list_documents:
        app.state.lookup_throttle = throttle = Throttle()

        @app.get("/api/docs")
        async def documents(request: Request):
            """Every app's documents. ``app`` is the one app of a server that hosts one, else ``null``."""
            _may_list(gateway, request)
            only = suite.apps[0] if len(suite.apps) == 1 else None
            return {"app": only, "apps": list(suite.apps), "documents": suite.listing()}

        @app.post("/api/docs/lookup")
        async def lookup(request: Request):
            """Find a document by its uid, an exact match (D533): ``{app, id, modified}``, or 404. Whoever may list the
            server may ask (so a server that does not list does not answer, and one with an access secret asks for
            it), a few times a minute from one address. A uid that is not one and a uid nobody here has get the same
            answer, and nothing about the document is told beyond what the list tells."""
            _may_list(gateway, request)
            address = gateway.client_address.of(request)
            if not throttle.allow(address):
                raise HTTPException(429, "too many questions; try again in a minute", headers={"Retry-After": "60"})
            try:
                uid = json.loads(await read_body(request, 1024))["uid"]
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(400, 'ask with {"uid": ...}') from exc
            found = await suite.find(uid) if is_uid(uid) else None
            if found is None:
                raise HTTPException(404, "no such document here")
            module, info = found
            return {"app": module.app, "id": info.id, "modified": info.modified}

    @app.websocket("/api/docs/{doc_id}/ws")
    async def live(websocket: WebSocket, doc_id: str):
        await gateway.serve(websocket, doc_id)

    @app.websocket("/api/presence")
    async def present(websocket: WebSocket):
        await presence.serve(websocket)

    _upload_routes(app, suite, gateway)


def _people_of(gateway: Gateway, admin: AdminContext | None) -> Callable[[Request], bool]:
    """Whether a request comes from this server's own people, who may have its fonts for this server only (D1041):
    it carries the access secret (any request does on a server without one), or an administrator's session."""

    def local(request: Request) -> bool:
        token = _bearer_token(request.headers.get("authorization"))
        if gateway.accepts_secret(token):
            return True
        return admin is not None and admin.sessions.resolve(token) is not None

    return local


def _upload_routes(app: FastAPI, suite: Suite, gateway: Gateway) -> None:
    """``POST /api/uploads`` holds a file a person brings, and ``POST /api/uploads/{token}/place`` takes a Claudia
    file in as it is (D440, D442). Whoever may make documents may upload: with an access secret, only those who know
    it."""

    def may_make(request: Request) -> None:
        if not gateway.accepts_secret(_bearer_token(request.headers.get("authorization"))):
            raise HTTPException(401, "this server needs its access secret", headers={"WWW-Authenticate": "Bearer"})

    @app.post("/api/uploads")
    async def upload(request: Request):
        may_make(request)
        address = gateway.client_address.of(request)
        try:
            gateway.uploads.room_for(address)
            data = await read_body(request, gateway.uploads.max_bytes)
            held = gateway.uploads.put(address, file_name(request.headers.get("x-claudia-name")), data)
        except UploadRefused as exc:
            raise HTTPException(exc.status, exc.message) from exc
        answer = held.describe()
        module = suite.module(held.app)
        answer["hosted"] = module is not None
        if held.fmt == CLAUDIA:
            answer["exists"] = module is not None and module.hub.exists(held.doc_id)
            twin = await suite.find(held.uid)
            answer["same_document"] = None if twin is None else twin[1].id  # a name, for the person; never the uid
        return answer

    @app.post("/api/uploads/{token}/place")
    async def place(token: str, request: Request):
        may_make(request)
        held = gateway.uploads.peek(token)
        if held is None or held.fmt != CLAUDIA:
            raise HTTPException(404, "the file is no longer here: choose it again")
        module = suite.module(held.app)
        if module is None:
            raise HTTPException(422, f"this server does not host {held.app}")
        twin = await suite.find(held.uid)
        if twin is not None:  # the same document is here, under whatever name and in whatever app (D533)
            raise HTTPException(409, str(same_document_message(twin[1].id)))
        try:
            await module.hub.place(held.doc_id, held.data)
        except HubError as exc:
            status = {"bad_request": 409, "unavailable": 503}.get(exc.code, 422)
            raise HTTPException(status, str(exc.message)) from exc
        gateway.uploads.take(token)
        return {"app": held.app, "id": held.doc_id}


def _app_routes(app: FastAPI, suite: Suite, gateway: Gateway, list_documents: bool) -> None:
    """The routes with the app in the address (D431): its protocol, its list and its documents' live address."""

    def module_of(app_name: str) -> Module:
        module = suite.module(app_name)
        if module is None:
            raise HTTPException(404, f"this server does not host {app_name}")
        return module

    @app.get("/api/{app_name}/protocol")
    async def app_protocol(app_name: str):
        return module_of(app_name).hub.methods.describe(suite.first.hub.limits)

    if list_documents:

        @app.get("/api/{app_name}/docs")
        async def app_documents(app_name: str, request: Request):
            _may_list(gateway, request)
            module = module_of(app_name)
            return {"app": module.app, "documents": module.hub.listing()}

    @app.websocket("/api/{app_name}/docs/{doc_id}/ws")
    async def app_live(websocket: WebSocket, app_name: str, doc_id: str):
        await gateway.serve(websocket, doc_id, app_name)


def _web_routes(app: FastAPI, web_dir: str | Path | None, *, more_links: str) -> None:
    """The web app, served from the same address: the page and the WebSocket then share an origin, so no allowed
    origin is needed. Mounted last so /api/... wins. Without one, / says what this server is, with ``more_links``
    (HTML) after its link to the health check."""
    if web_dir is not None:
        directory_path = Path(web_dir)
        if not (directory_path / "index.html").is_file():
            raise ValueError(
                f"{directory_path} does not contain a built web app (index.html); run `npm run build` in web/"
            )
        app.mount("/", SinglePageApp(directory=directory_path, html=True), name="web")
    else:
        landing_page = _LANDING.replace("<!--more-links-->", more_links)

        @app.get("/", include_in_schema=False, response_class=HTMLResponse)
        async def landing():
            return HTMLResponse(landing_page, headers={"Cache-Control": "no-store"})
