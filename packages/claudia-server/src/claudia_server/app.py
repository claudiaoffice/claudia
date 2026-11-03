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

    {"id": 1, "method": "hello", "params": {"user": "ann", "password": "...", "create": false}}

The answer carries the welcome data (user, role, document, line, revision, people, limits). After that the connection
speaks the protocol of ``protocol.py`` and receives events. With ``create: true`` for a document that does not exist,
the document is made and the person becomes its owner. A wrong password, an unknown name and a document that does not
exist are the same answer. Failures to get that far close the socket with a code: 4400 bad request, 4401 unauthorized,
4404 no such document, 4408 no hello in time, 4403 foreign origin, 1013 too many connections or client too slow.

The root of the server is never a dead end. With a built web app (``web_dir``) every address that is not under /api
(and not a file) shows its start page; without one, / shows a short page that says what this server is and how to use
it.

Browsers: a page on another origin could try to use a user's localhost server, so the WebSocket refuses a request whose
``Origin`` is neither the server itself nor in ``allowed_origins``. Non-browser clients send no Origin and are not
affected.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

from .auth import Account, AuthRefused, Credentials, UserDirectory
from .hub import Hub, HubError
from .protocol import RequestError, parse_request

HELLO_TIMEOUT = 10.0
OUTGOING_QUEUE = 1000  # frames waiting for a slow client before it is dropped
_CLOSE = {"not_found": 4404, "bad_request": 4400, "unavailable": 1013, "internal": 1011}


class SinglePageApp(StaticFiles):
    """The built web app. A path that is neither a file nor under /api gets the start page (so a bookmark like
    /budget, or a reload on any address, still ends up on the welcome form); a missing file with an extension stays a
    404."""

    async def get_response(self, path, scope):
        """The file, or the start page for an address of the app."""
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


class Gateway:
    """What the WebSocket route needs: the hub, the users of each document, and the rule for making new documents.

    Checking a password and adding a person cost real work (the password hashing is meant to be slow), so they run in
    threads and never stop the event loop (SEC-03). At most ``max_hashing`` of them run at once, so a flood of logins
    cannot use up the memory of the machine (the hashing needs a lot of it)."""

    def __init__(self, hub: Hub, directory: UserDirectory, allowed: set[str], *, max_hashing: int = 2):
        self.hub = hub
        self.directory = directory
        self.allowed = allowed
        self._creating = asyncio.Lock()  # one new document at a time: the first person to ask becomes its owner
        self._hashing = asyncio.Semaphore(max_hashing)

    async def _verify(self, doc_id: str, credentials: Credentials) -> Account | None:
        async with self._hashing:
            return await asyncio.to_thread(self.directory.verify, doc_id, credentials)

    async def admit(self, doc_id: str, credentials: Credentials, create: bool) -> Account | None:
        """The account of the person, or ``None``. A new document is made for whoever asks first (its owner)."""
        hub, directory = self.hub, self.directory
        if hub.exists(doc_id):
            return await self._verify(doc_id, credentials)
        if not (create and hub.allow_create):
            await self._verify(doc_id, credentials)  # the same work as for a document that exists (SEC-04) ...
            return None  # ... and the same answer
        async with self._creating:
            if hub.exists(doc_id):  # somebody was faster
                return await self._verify(doc_id, credentials)
            if not (isinstance(credentials.user, str) and isinstance(credentials.password, str)):
                return None
            if (
                reserved := await self._verify(doc_id, credentials)
            ) is not None:  # (cannot happen; keeps verify's checks)
                return reserved
            async with self._hashing:
                account = await asyncio.to_thread(
                    directory.add_user, doc_id, credentials.user, credentials.password, "owner"
                )
            try:
                await hub.open(doc_id, create=True)
            except BaseException:
                directory.remove_user(doc_id, credentials.user)
                raise
            return account

    async def serve(self, websocket: WebSocket, doc_id: str) -> None:
        """One connection from the handshake to its end."""
        if not origin_allowed(websocket.headers.get("origin"), websocket.headers.get("host"), self.allowed):
            await websocket.close(code=4403)  # refused during the handshake (HTTP 403)
            return
        await websocket.accept()
        admitted = await self._hello(websocket, doc_id)
        if admitted is not None:
            request_id, account, document = admitted
            await _Live(websocket, document, account, request_id).run()

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
        try:
            Hub.check_id(doc_id)
            credentials = Credentials(params.get("user"), params.get("password"))
            account = await self.admit(doc_id, credentials, params.get("create") is True)
            if account is None:
                await _refuse(websocket, request_id, "unauthorized", "missing or wrong credentials", 4401)
                return None
            return request_id, account, await self.hub.open(doc_id)
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

    def __init__(self, websocket: WebSocket, document, account: Account, request_id):
        self.websocket = websocket
        self.document = document
        self.account = account
        self.request_id = request_id
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
            connection = self.document.connect(self.account, self.send)
        except HubError as exc:
            await _refuse(self.websocket, self.request_id, exc.code, exc.message, _CLOSE.get(exc.code, 1013))
            return
        welcome = {"id": self.request_id, "ok": True, "result": connection.welcome()}
        self.send(json.dumps(welcome, separators=(",", ":")))
        pump = asyncio.create_task(self._pump())
        try:
            while not connection.broken:
                message = await self.websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                text = message.get("text")
                connection.handle(text if text is not None else message.get("bytes", b""))
        except WebSocketDisconnect, RuntimeError:
            pass
        finally:
            pump.cancel()
            connection.close()
            for task in self.background:
                task.cancel()


def create_app(
    hub: Hub,
    directory: UserDirectory,
    *,
    allowed_origins: Iterable[str] = (),
    web_dir: str | Path | None = None,
    list_documents: bool = True,
) -> FastAPI:
    """The server for ``hub``, with the users of each document in ``directory``.

    ``list_documents`` serves ``GET /api/docs`` (see ``Hub.listing``); switch it off on a shared server where the
    existence of a document should not be visible."""
    allowed = {o.rstrip("/") for o in allowed_origins}
    gateway = Gateway(hub, directory, allowed)

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
            CORSMiddleware, allow_origins=sorted(allowed), allow_methods=["GET"], allow_headers=["Content-Type"]
        )
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
        async def documents():
            return {"app": hub.app, "documents": hub.listing()}

    @app.websocket("/api/docs/{doc_id}/ws")
    async def live(websocket: WebSocket, doc_id: str):
        await gateway.serve(websocket, doc_id)

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
