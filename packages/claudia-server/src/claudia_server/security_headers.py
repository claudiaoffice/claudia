"""The headers that tell a browser what a page of this server may do (SEC-13).

Every HTTP answer gets

* ``Content-Security-Policy``: scripts only from this server (and the start page's own inline scripts, by hash),
  WebAssembly compiled from bytes the page fetched from this server (``'wasm-unsafe-eval'``: the layout library's
  HarfBuzz, D903; it allows no JavaScript ``eval``), frames only of this server's pages and of ``blob:`` documents
  the page made itself (the PDF handed to the browser's print dialog, D906),
  connections only to this server and its WebSocket, no plugins, no ``<base>``, and **framing** only by this server
  itself or by a page on this computer (``http://127.0.0.1:*``, ``http://localhost:*``): the Windows and macOS
  desktop clients show the web app in a frame of their own local shell page (D251), and any other site that frames a
  document or the server settings to trick a click is refused;
* ``X-Content-Type-Options: nosniff``, ``Referrer-Policy: no-referrer`` (a document's address never travels to
  another site) and a ``Permissions-Policy`` that switches off the camera, microphone and location, which no part of
  Claudia uses.

The start page of the web build has two inline scripts (Nuxt's import map and its runtime configuration); their
SHA-256 hashes are read from the built HTML once, at start, so a new build needs no change here and no
``'unsafe-inline'`` is ever needed for scripts. Styles keep ``'unsafe-inline'``: Vue's style bindings and the chart
library set them, and a style cannot run code.

The connection rule names the host the request came in under. ``HostGuard`` has already refused every host the server
does not answer to, so the value echoed here is one of the server's own names.

``/api/swagger`` is the one exception: FastAPI's page loads its script from a CDN, so it only gets the framing rule,
not the script rule. It is served only when the administrator starts the server with ``--api-docs`` (SEC-14).
"""

from __future__ import annotations

import base64
import hashlib
import re
from collections.abc import Callable, Iterable
from pathlib import Path

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

#: Pages that may show this server's pages in a frame: itself, and the desktop shells' local pages (D251).
FRAME_ANCESTORS = "'self' http://127.0.0.1:* http://localhost:*"
#: Paths that keep only the framing rule (SEC-14).
_LOOSE = ("/api/swagger",)
#: An inline script that a browser runs: no ``src``, and either no type or a JavaScript / module / import-map type.
_INLINE_SCRIPT = re.compile(r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>", re.DOTALL | re.IGNORECASE)
_RUNNABLE_TYPES = {"", "text/javascript", "application/javascript", "module", "importmap"}

_FIXED = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}


def inline_script_hashes(pages: Iterable[str]) -> tuple[str, ...]:
    """The CSP sources (``'sha256-…'``) of the inline scripts a browser would run in ``pages`` (HTML text), sorted and
    without repeats. A ``<script src>`` and a data block (``type="application/json"``) are not inline scripts."""
    found: set[str] = set()
    for page in pages:
        for match in _INLINE_SCRIPT.finditer(page):
            attrs = match["attrs"]
            if re.search(r"\bsrc\s*=", attrs, re.IGNORECASE):
                continue
            kind = re.search(r"""\btype\s*=\s*["']?([^"'\s>]+)""", attrs, re.IGNORECASE)
            if (kind[1].lower() if kind else "") not in _RUNNABLE_TYPES:
                continue
            digest = hashlib.sha256(match["body"].encode("utf-8")).digest()
            found.add(f"'sha256-{base64.b64encode(digest).decode('ascii')}'")
    return tuple(sorted(found))


def web_script_hashes(web_dir: str | Path | None) -> tuple[str, ...]:
    """The hashes of the inline scripts of every HTML page at the top of the built web app (``index.html`` and the
    pages Nuxt writes beside it); none without a web app."""
    if web_dir is None:
        return ()
    return inline_script_hashes(p.read_text(encoding="utf-8") for p in sorted(Path(web_dir).glob("*.html")))


class WebScriptHashes:
    """:func:`web_script_hashes` that follows the web app when it is built again while the server runs.

    Every build of the web app writes a new inline script (its build id is in it), and a policy with the hashes of the
    build the server started with blocks it: the page stays blank. That happened to the desktop apps (2026-11-15):
    their server outlives its windows (D445), and the start scripts build the web app again before each window. So
    the pages are looked at again (their size and time, which is cheap) before each answer, and read again only when
    one changed."""

    def __init__(self, web_dir: str | Path | None) -> None:
        self._dir = Path(web_dir) if web_dir is not None else None
        self._seen: tuple[tuple[str, int, int], ...] | None = None
        self._hashes: tuple[str, ...] = ()

    @staticmethod
    def _stamp(folder: Path) -> tuple[tuple[str, int, int], ...]:
        stamp = []
        for page in sorted(folder.glob("*.html")):
            try:
                info = page.stat()
            except OSError:  # being written again right now
                continue
            stamp.append((page.name, info.st_mtime_ns, info.st_size))
        return tuple(stamp)

    def __call__(self) -> tuple[str, ...]:
        if self._dir is None:
            return ()
        stamp = self._stamp(self._dir)
        if stamp != self._seen:
            try:
                self._hashes = web_script_hashes(self._dir)
            except OSError:  # a page went away in between: keep the last hashes, look again next time
                return self._hashes
            self._seen = stamp
        return self._hashes


def content_security_policy(host: str, script_hashes: Iterable[str] = ()) -> str:
    """The policy for a page that was asked for under ``host`` (``name`` or ``name:port``). Anything in ``host`` that
    is not part of a host name, an IPv6 literal or a port is dropped, so it cannot add a directive."""
    host = re.sub(r"[^A-Za-z0-9.\-:\[\]]", "", host)
    scripts = " ".join(("'self'", "'wasm-unsafe-eval'", *script_hashes))
    return "; ".join(
        (
            "default-src 'self'",
            f"script-src {scripts}",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob:",
            "font-src 'self' data:",
            f"connect-src 'self' ws://{host} wss://{host}" if host else "connect-src 'self'",
            "worker-src 'self' blob:",
            "frame-src 'self' blob:",
            "object-src 'none'",
            "base-uri 'none'",
            "form-action 'self'",
            f"frame-ancestors {FRAME_ANCESTORS}",
        )
    )


class SecurityHeaders:
    """ASGI middleware: the headers above on every HTTP answer (a WebSocket has none to set). A header the
    application set itself is left as it is."""

    def __init__(self, app: ASGIApp, *, script_hashes: Iterable[str] | Callable[[], Iterable[str]] = ()) -> None:
        self.app = app
        self.script_hashes = script_hashes if callable(script_hashes) else tuple(script_hashes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        host = _host(scope)
        loose = scope.get("path", "").startswith(_LOOSE)
        hashes = self.script_hashes() if callable(self.script_hashes) else self.script_hashes
        policy = f"frame-ancestors {FRAME_ANCESTORS}" if loose else content_security_policy(host, hashes)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in (("content-security-policy", policy), *_FIXED.items()):
                    if name not in headers:
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _host(scope: Scope) -> str:
    """The Host header as sent (``HostGuard`` has vetted it; ``content_security_policy`` cleans it again)."""
    for name, value in scope.get("headers", ()):
        if name == b"host":
            return value.decode("latin-1")
    return ""
