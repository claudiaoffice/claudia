"""The FastAPI application (E3.1).

    WebSocket  /api/docs/{doc}/ws    the live connection (see protocol.py)
    GET        /api/health           liveness
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
request, 4401 unauthorized, 4404 no such document, 4408 no hello in time, 4403 foreign origin or host, 4423 the
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
import hmac
import json
from collections.abc import Iterable
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

from .admin_api import AdminContext, admin_router
from .auth import Account, AuthRefused, Credentials, RecoverableDirectory, UserDirectory
from .hosts import AllowedHosts, HostGuard
from .hub import Hub, HubError
from .protocol import DEFAULT_LOCALE, RequestError, normalize_locale, parse_request

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
<p><a href="/api/health">/api/health</a> &middot; <a href="/api/swagger">API description</a></p>
</body></html>
"""


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
    """What the WebSocket route needs: the hub, the users of each document, and the rule for making new documents.

    Checking a password and adding a person cost real work (the password hashing is meant to be slow), so they run in
    threads and never stop the event loop (SEC-03). At most ``max_hashing`` of them run at once, so a flood of logins
    cannot use up the memory of the machine (the hashing needs a lot of it).

    Nobody costs the server anything before they are let in beyond a place in the queue: at most ``max_waiting``
    connections (``max_waiting_per_address`` from one address) wait to be let in, and the others are turned away with
    1013 (SEC-02). With an ``access_secret`` only those who know it can make documents. It has at least
    ``MIN_ACCESS_SECRET`` characters, because it is the only thing between the network and the disk."""

    def __init__(
        self,
        hub: Hub,
        directory: UserDirectory,
        allowed: set[str],
        *,
        max_hashing: int = 2,
        access_secret: str | None = None,
        max_waiting: int = DEFAULT_MAX_WAITING,
        max_waiting_per_address: int = DEFAULT_MAX_WAITING_PER_ADDRESS,
    ):
        if access_secret is not None and len(access_secret) < MIN_ACCESS_SECRET:
            raise ValueError(f"the access secret needs at least {MIN_ACCESS_SECRET} characters")
        self.hub = hub
        self.directory = directory
        self.allowed = allowed
        self._secret = None if access_secret is None else access_secret.encode()
        self._creating = asyncio.Lock()  # one new document at a time: the first person to ask becomes its owner
        self._hashing = asyncio.Semaphore(max_hashing)
        self._waiting = _Waiting(max_waiting, max_waiting_per_address)

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

    async def _verify(self, doc_id: str, credentials: Credentials) -> Account | None:
        async with self._hashing:
            return await asyncio.to_thread(self.directory.verify, doc_id, credentials)

    async def admit(self, doc_id: str, credentials: Credentials, create: bool, access: object = None) -> Account | None:
        """The account of the person, or ``None``. A new document is made for whoever asks first (its owner), if the
        server makes documents and the person knows its access secret (``access``), if it has one.

        ``HubError('unavailable')`` if the server already holds as many documents as it may."""
        return (await self._admit(doc_id, credentials, create, access))[0]

    async def _admit(
        self, doc_id: str, credentials: Credentials, create: bool, access: object
    ) -> tuple[Account | None, bool]:
        """As :meth:`admit`, and whether the document was just made."""
        hub, directory = self.hub, self.directory
        if hub.exists(doc_id):
            return await self._verify(doc_id, credentials), False
        if not (create and hub.allow_create and self.accepts_secret(access)):
            await self._verify(doc_id, credentials)  # the same work as for a document that exists (SEC-04) ...
            return None, False  # ... and the same answer
        async with self._creating:
            if hub.exists(doc_id):  # somebody was faster
                return await self._verify(doc_id, credentials), False
            if not (isinstance(credentials.user, str) and isinstance(credentials.password, str)):
                return None, False
            await hub.ensure_room()  # before any hashing or disk: a refused document costs nothing
            # The same work as for a document that exists (SEC-04). It usually finds nobody, but not always: the user
            # directory is kept apart from the documents, so a creation that died between the two can leave this
            # person's account behind without a document. They then get that account back, not a second owner.
            if (reserved := await self._verify(doc_id, credentials)) is not None:
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

    async def _recover(self, doc_id: str, params: dict) -> Account | None:
        """The account of a person who came in with a recovery key and chose a new password (they are logged in)."""
        key, user, password = params.get("recovery_key"), params.get("user"), params.get("password")
        if not (isinstance(key, str) and isinstance(user, str) and isinstance(password, str)):
            raise HubError("bad_request", "a recovery key, a name and a new password are needed")
        directory = self.directory
        if not isinstance(directory, RecoverableDirectory):
            raise HubError("unavailable", "this server does not keep recovery keys")
        async with self._hashing:
            return await asyncio.to_thread(directory.recover, doc_id, key, user, password)

    async def serve(self, websocket: WebSocket, doc_id: str) -> None:
        """One connection from the handshake to its end."""
        if not origin_allowed(websocket.headers.get("origin"), websocket.headers.get("host"), self.allowed):
            await websocket.close(code=4403)  # refused during the handshake (HTTP 403)
            return
        address = websocket.client.host if websocket.client else ""
        if not self._waiting.enter(address):  # taken before the accept, so a client that was let on has its place
            await websocket.accept()  # (a refusal before the accept carries no close code)
            await websocket.close(code=1013)
            return
        try:
            await websocket.accept()
            admitted = await self._hello(websocket, doc_id)
        finally:
            self._waiting.leave(address)
        if admitted is not None:
            request_id, account, document, created, locale = admitted
            await _Live(websocket, document, account, request_id, created=created, locale=locale).run()

    async def _hello(self, websocket: WebSocket, doc_id: str):
        """The first frame: ``(request id, account, document)`` if the person may come in, else the socket is closed."""
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), HELLO_TIMEOUT)
        except TimeoutError:
            await websocket.close(code=4408)
            return None
        except WebSocketDisconnect:
            return None
        try:
            request_id, name, params = parse_request(raw, self.hub.limits)
        except RequestError as exc:
            await _refuse(websocket, None, exc.code, exc.message, 4400)
            return None
        if name != "hello" or not isinstance(params, dict):
            await _refuse(websocket, request_id, "bad_request", "the first message must be hello with params", 4400)
            return None
        locale = normalize_locale(params.get("locale"))
        try:
            Hub.check_id(doc_id)
            if params.get("recovery_key") is not None:
                account, created = await self._recover(doc_id, params), False
            else:
                credentials = Credentials(params.get("user"), params.get("password"))
                account, created = await self._admit(
                    doc_id, credentials, params.get("create") is True, params.get("access")
                )
            if account is None:
                await _refuse(websocket, request_id, "unauthorized", "missing or wrong credentials", 4401)
                return None
            return request_id, account, await self.hub.open(doc_id), created, locale
        except HubError as exc:
            await _refuse(websocket, request_id, exc.code, exc.message, _CLOSE.get(exc.code, 4400))
        except AuthRefused as exc:
            await _refuse(websocket, request_id, "unauthorized", str(exc), 4401)
        except ValueError as exc:  # the name or password of a new document is not acceptable
            await _refuse(websocket, request_id, "bad_request", str(exc), 4400)
        return None


async def _refuse(websocket: WebSocket, request_id, code: str, message: str, close_code: int) -> None:
    """Answer the first frame with an error and close the socket with ``close_code``."""
    frame = {"id": request_id, "ok": False, "error": {"code": code, "message": message}}
    await websocket.send_text(json.dumps(frame))
    await websocket.close(code=close_code)


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
    ):
        self.created = created
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
            await _refuse(self.websocket, self.request_id, exc.code, exc.message, _CLOSE.get(exc.code, 1013))
            return
        welcome = {"id": self.request_id, "ok": True, "result": {**connection.welcome(), "created": self.created}}
        self.send(json.dumps(welcome, separators=(",", ":")))
        pump = asyncio.create_task(self._pump())
        try:
            while not connection.broken:
                message = await self.websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                text = message.get("text")
                connection.handle(text if text is not None else message.get("bytes", b""))
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
    hub: Hub,
    directory: UserDirectory,
    *,
    allowed_origins: Iterable[str] = (),
    allowed_hosts: Iterable[str] = (),
    access_secret: str | None = None,
    max_waiting: int = DEFAULT_MAX_WAITING,
    max_waiting_per_address: int = DEFAULT_MAX_WAITING_PER_ADDRESS,
    web_dir: str | Path | None = None,
    list_documents: bool = True,
    admin: AdminContext | None = None,
) -> FastAPI:
    """The server for ``hub``, with the users of each document in ``directory``.

    The server answers only to ``localhost``, to IP addresses and to the host names in ``allowed_hosts`` (SEC-01, see
    ``claudia_server.hosts``); ``ValueError`` if one of them is not a host name. ``list_documents`` serves
    ``GET /api/docs`` (see ``Hub.listing``); switch it off on a shared server where the existence of a document should
    not be visible.

    With an ``access_secret`` (at least ``MIN_ACCESS_SECRET`` characters, ``ValueError`` otherwise) only those who know
    it can make documents or read the list. ``max_waiting`` and ``max_waiting_per_address`` bound the connections that
    wait to be let in (SEC-02).

    With ``admin`` (``admin_api.AdminContext``), the server also serves ``/api/admin/*``: the settings pages, signed
    in to separately from any document (``admin.py``). Without it — the default, and every use before this existed
    — none of those routes exist at all, which keeps every other caller of this function unaffected."""
    allowed = {o.rstrip("/") for o in allowed_origins}
    hosts = AllowedHosts(allowed_hosts)
    gateway = Gateway(
        hub,
        directory,
        allowed,
        access_secret=access_secret,
        max_waiting=max_waiting,
        max_waiting_per_address=max_waiting_per_address,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await hub.start()
        try:
            yield
        finally:
            await hub.stop()

    app = FastAPI(title="Claudia server", docs_url="/api/swagger", openapi_url="/api/openapi.json", lifespan=lifespan)
    if allowed:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=sorted(allowed),
            allow_methods=["GET"],
            allow_headers=["Content-Type", "Authorization"],
        )
    app.add_middleware(HostGuard, hosts=hosts)  # added last, so it is the first to see a request (even a preflight)
    if hub.directory is None:
        hub.directory = directory  # owners add people to their documents through it
    app.state.hub = hub

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    @app.get("/api/protocol")
    async def protocol():
        return hub.methods.describe(hub.limits)

    if list_documents:

        @app.get("/api/docs")
        async def documents(request: Request):
            if not gateway.accepts_secret(_bearer_token(request.headers.get("authorization"))):
                raise HTTPException(401, "this server needs its access secret", headers={"WWW-Authenticate": "Bearer"})
            return {"app": hub.app, "documents": hub.listing()}

    @app.websocket("/api/docs/{doc_id}/ws")
    async def live(websocket: WebSocket, doc_id: str):
        await gateway.serve(websocket, doc_id)

    if admin is not None:
        app.include_router(admin_router(hub, gateway.set_secret, admin))

    # The web app, served from the same address: the page and the WebSocket then share an origin, so no allowed origin
    # is needed. Mounted last so /api/... wins.
    if web_dir is not None:
        directory_path = Path(web_dir)
        if not (directory_path / "index.html").is_file():
            raise ValueError(
                f"{directory_path} does not contain a built web app (index.html); run `npm run build` in web/"
            )
        app.mount("/", SinglePageApp(directory=directory_path, html=True), name="web")
    else:

        @app.get("/", include_in_schema=False, response_class=HTMLResponse)
        async def landing():
            return HTMLResponse(_LANDING, headers={"Cache-Control": "no-store"})

    return app
