"""The port of a person's private server (E8.5, D1621). No GTK in here.

Her own, the same at every start, so that what the page keeps for that address (Mine, collections, server bookmarks)
stays hers: ``20000 + uid % 10000``. Two accounts of one computer never get the same one (Linux's account numbers are
below 10000 apart). Below the ports the system hands out by itself (from 32768), and away from 8765, the port of every
shared Claudia server (D1621). The twin of ``clients/neutralino/src/private-port.ts``; both are held to
``clients/contract/private-port.vectors.json``.
"""

from __future__ import annotations

from collections.abc import Iterator

__all__ = ["PRIVATE_PORTS", "private_port", "walk_from"]

PRIVATE_PORTS = (20000, 29999)
"""The first and the last port a private server may have."""


def private_port(uid: int) -> int:
    """Her port, by her account number."""
    first, last = PRIVATE_PORTS
    return first + uid % (last - first + 1)


def walk_from(usual: int) -> Iterator[int]:
    """The other ports of her range, in the order her apps try them while hers is held: the ones after it, then from the
    first. Every window of hers walks the same order, so two that start at once try the same port, and one of them wins
    it (D435)."""
    first, last = PRIVATE_PORTS
    span = last - first + 1
    for step in range(1, span):
        yield first + (usual - first + step) % span
