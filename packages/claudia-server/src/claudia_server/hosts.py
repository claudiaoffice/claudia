"""The names a server answers to (SEC-01, DNS rebinding).

A web page may only talk to a server under the page's *own* name. DNS rebinding gets around that: the page's name
(``evil.example``) first points at the attacker's server, and once the page has loaded it is pointed at ``127.0.0.1``.
The browser now sends requests to the server on the visitor's computer as if it were the page's own origin, with
``Host: evil.example`` and ``Origin: http://evil.example``. The two match, so an Origin check that trusts the ``Host``
header cannot tell the difference.

What a rebound request cannot do is carry a ``Host`` that the server knows as its own. So the server answers only to

* ``localhost``,
* every IP address (an address is not a name: a page has nothing to rebind), except the unspecified ones
  (``0.0.0.0``, ``::``), which some browsers accept as "this computer", and
* the names it was configured with (``--allow-host``, ``--tls-name``, the name it listens on).

``AllowedHosts`` is the rule and ``HostGuard`` applies it to every HTTP request and WebSocket before anything else
sees them.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from collections.abc import Iterable

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

log = logging.getLogger("claudia_server")

LOCALHOST = "localhost"
CLOSE_FOREIGN_HOST = 4403  # the code of a refused handshake, shared with a foreign Origin (see ``app``)
_REPORTED_AT_MOST = 100  # different refused names put in the log, so that a flood of them cannot fill it

# What browsers and HTTP clients write in a Host header: a name or an address with an optional port. Anything else
# (user info, a path, spaces, a second port) is not a host.
# ASCII only: with Unicode case folding the Kelvin sign would match ``k`` and lower-case to it.
_HOST = re.compile(r"(?P<name>\[[0-9a-f:.]+\]|[a-z0-9._-]+)(?::[0-9]{1,5})?", re.IGNORECASE | re.ASCII)
_REFUSAL = (
    "This server does not answer to the name you used. If the server is yours, start it with --allow-host NAME "
    "(the name people type in the address bar)."
)


def host_name(header: str | None) -> str | None:
    """The name or address in a ``Host`` header: lower case, without port, brackets or final dot.

    ``None`` for a missing header and for anything that is not a plain host."""
    match = _HOST.fullmatch(header or "")
    if match is None:
        return None
    return match["name"].strip("[]").rstrip(".").lower() or None


def _address(name: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(name)
    except ValueError:
        return None


def is_loopback(host: str) -> bool:
    """Does ``host`` (a name or an address to listen on) mean this computer only?"""
    address = _address(host.strip("[]"))
    return address.is_loopback if address is not None else host.lower().rstrip(".") == LOCALHOST


def machine_names() -> list[str]:
    """The name this computer goes by on its network, if it is a plain host name (so ``http://nas:8765`` works).

    Not its fully qualified name: finding that out can wait for a DNS server for seconds at every start."""
    name = socket.gethostname()
    return [name] if host_name(name) else []


class AllowedHosts:
    """Which ``Host`` headers a server answers to: this computer, any IP address, and the names it was given."""

    def __init__(self, names: Iterable[str] = ()):
        """``ValueError`` if a name is not a host name. A port in a name is ignored; an IP address is allowed anyway."""
        self._names = frozenset({LOCALHOST, *filter(None, map(self._configured, names))})

    @staticmethod
    def _configured(candidate: str) -> str | None:
        if _address(candidate.strip("[]")) is not None:
            return None
        name = host_name(candidate)
        if name is None:
            raise ValueError(f"{candidate!r} is not a host name")
        return name

    @property
    def names(self) -> list[str]:
        """The names (not the addresses) the server answers to, ``localhost`` first."""
        return [LOCALHOST, *sorted(self._names - {LOCALHOST})]

    def allows(self, header: str | None) -> bool:
        """Is this ``Host`` header one of the server's own?"""
        name = host_name(header)
        if name is None:
            return False
        address = _address(name)
        if address is not None:
            return not address.is_unspecified
        return name in self._names


class HostGuard:
    """ASGI middleware: HTTP requests and WebSockets for a host that is not the server's own are refused (403, or a
    WebSocket closed with 4403) before any other part of the application sees them."""

    def __init__(self, app: ASGIApp, hosts: AllowedHosts):
        self.app = app
        self.hosts = hosts
        self._reported: set[str] = set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request on if its host is ours, else refuse it."""
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)  # the lifespan has no host
            return
        given = Headers(scope=scope).getlist("host")
        header = given[0] if len(given) == 1 else None  # two Host headers are one too many: nobody knows which counts
        if self.hosts.allows(header):
            await self.app(scope, receive, send)
            return
        self._report(header)
        if scope["type"] == "websocket":
            await receive()  # the handshake; closing in answer to it is refused with HTTP 403
            await send({"type": "websocket.close", "code": CLOSE_FOREIGN_HOST})
        else:
            await PlainTextResponse(_REFUSAL, status_code=403)(scope, receive, send)

    def _report(self, header: str | None) -> None:
        """Tell the operator once per name that a name was refused, so that a missing ``--allow-host`` is found."""
        shown = repr(header)
        if shown in self._reported or len(self._reported) >= _REPORTED_AT_MOST:
            return
        self._reported.add(shown)
        log.warning("refused a request for the host %s; if it names this server, add it with --allow-host", shown)
