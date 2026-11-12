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

``/api/swagger`` is the one exception: FastAPI's page loads its script from a CDN (SEC-14, open), so it only gets
the framing rule, not the script rule, until that page is served from the package or switched off.
"""

from __future__ import annotations

import base64
import hashlib
import re
from collections.abc import Iterable
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

    def __init__(self, app: ASGIApp, *, script_hashes: Iterable[str] = ()) -> None:
        self.app = app
        self.script_hashes = tuple(script_hashes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        host = _host(scope)
        loose = scope.get("path", "").startswith(_LOOSE)
        policy = f"frame-ancestors {FRAME_ANCESTORS}" if loose else content_security_policy(host, self.script_hashes)

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
