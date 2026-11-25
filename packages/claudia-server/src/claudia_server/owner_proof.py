"""A person's private server proves to her own apps that it is hers (E8.5, D1620; CODE-99).

Her apps start the server with a key from her own state folder (``--owner-key-file``: 32 random bytes as 64 hex
digits) and, before they use a server they find on her port, send it a fresh challenge. The server answers with
HMAC-SHA256 of the challenge and **the port it listens on** (from its socket, not from the request): a program that
holds her usual address cannot pass her challenge on to her real server on another port and pretend to be it. A server
started without a key (every shared server) has no ``/api/owner`` at all.

Only a request from this computer is answered, as with the version in ``/api/health``; nobody else needs it. The
answers are pinned by ``clients/contract/private-port.vectors.json``, which the clients' tests read too.
"""

import hashlib
import hmac
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

KEY_BYTES = 32
_HEX_KEY = re.compile(rf"[0-9a-fA-F]{{{2 * KEY_BYTES}}}")
_CHALLENGE = re.compile(r"[0-9a-f]{64}")


def load_key(path: str | Path) -> bytes:
    """The key in ``path``; ``ValueError`` unless the file holds 64 hex digits (and white space around them)."""
    text = Path(path).read_text(encoding="utf-8").strip()
    if not _HEX_KEY.fullmatch(text):
        raise ValueError(f"{path} does not hold a key of {KEY_BYTES} bytes as {2 * KEY_BYTES} hex digits")
    return bytes.fromhex(text)


def answer(key: bytes, port: int, challenge: str) -> str:
    """The proof for ``challenge`` from a server that listens on ``port`` with ``key``."""
    message = f"claudia owner proof\n{port}\n{challenge}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def owner_router(key: bytes, this_computer: frozenset[str]) -> APIRouter:
    """``GET /api/owner?challenge=<64 lower-case hex digits>`` → ``{"answer": …}``, only to a client whose address is
    in ``this_computer`` (the loopback addresses ``app.py`` knows)."""
    router = APIRouter()

    @router.get("/api/owner")
    async def owner(request: Request, challenge: str = ""):
        client = request.client.host if request.client else ""
        listening = request.scope.get("server")
        if client not in this_computer or not listening:
            raise HTTPException(status_code=404)
        if not _CHALLENGE.fullmatch(challenge):
            raise HTTPException(status_code=400, detail="the challenge is 64 lower-case hex digits")
        return {"answer": answer(key, int(listening[1]), challenge)}

    return router
