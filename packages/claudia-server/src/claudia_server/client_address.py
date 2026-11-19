"""Who a connection is: the address the server counts it by (D1275, SEC-02, SEC-11).

Straight from the socket, a connection's address is the one it comes from. Behind a reverse proxy that is the proxy's,
for everybody, so a per-address cap or wait would be one cap or one wait for the whole server. A proxy says whom it
serves in the ``X-Forwarded-For`` header, and appends the address it saw to the right of what is there. Everything left
of that was written by whoever sent the request and is not to be believed, so with ``trusted_hops`` proxies in front of
the server the client is the entry that many places from the right, and nothing else is read.
"""

from __future__ import annotations

import ipaddress
import logging
import threading

from starlette.requests import HTTPConnection

log = logging.getLogger("claudia_server")


def _entry(header: str | None, trusted_hops: int) -> str | None:
    """The entry ``trusted_hops`` places from the right of ``header``, if it is there and is an IP address."""
    if trusted_hops < 1 or not header:
        return None
    entries = [entry.strip() for entry in header.split(",")]
    if len(entries) < trusted_hops:
        return None
    try:
        return str(ipaddress.ip_address(entries[-trusted_hops]))
    except ValueError:
        return None


def forwarded_address(peer: str, header: str | None, trusted_hops: int) -> str:
    """The client's address: the entry ``trusted_hops`` places from the right of ``header`` (an ``X-Forwarded-For``
    value), or ``peer`` (the socket's address) if there are no trusted proxies, the header is missing, has fewer
    entries than there are proxies, or the entry is not an IP address (a client could put anything there)."""
    return _entry(header, trusted_hops) or peer


class ClientAddress:
    """Reads the address of a connection (an HTTP request or a WebSocket) for the whole server. ``trusted_hops`` is how
    many proxies stand in front of it and set ``X-Forwarded-For`` (0: none, the header is ignored)."""

    def __init__(self, trusted_hops: int = 0):
        if trusted_hops < 0:
            raise ValueError("the number of trusted proxies cannot be negative")
        self.trusted_hops = trusted_hops
        self._said = False
        self._lock = threading.Lock()

    def of(self, connection: HTTPConnection) -> str:
        """The address of ``connection``: ``""`` if it has none (a test client, a unix socket)."""
        peer = connection.client.host if connection.client else ""
        if not peer or self.trusted_hops < 1:
            return peer
        address = _entry(connection.headers.get("x-forwarded-for"), self.trusted_hops)
        if address is None:
            self._say_once(peer)
            return peer
        return address

    def _say_once(self, peer: str) -> None:
        """Say once, in the log, that a proxy did not send what was expected: without it every client is counted as the
        proxy and nobody sees why a cap or a wait hits everybody."""
        with self._lock:
            if self._said:
                return
            self._said = True
        log.warning(
            "no usable X-Forwarded-For entry from %s although %d proxy(ies) are trusted: its clients are counted as "
            "that one address. Set the header in the proxy, or give --proxy-hops 0.",
            peer,
            self.trusted_hops,
        )
