"""The key that makes a person's private server hers (E8.5, D1620; CODE-99). No GTK in here.

Her apps keep it in the server's state folder (hers alone), start the server with it (``--owner-key-file``), and use a
server they find on her port only when it answers a fresh challenge with it (``GET /api/owner``, the server's
``owner_proof.py``). The answer covers the port the server listens on, so a program on her usual address cannot pass
the challenge on to her real server elsewhere. The twin of ``clients/neutralino/src/owner-key.ts``; both are held to
``clients/contract/private-port.vectors.json``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

__all__ = ["OWNER_KEY_FILE", "OwnerKey", "is_owned_by", "owner_answer", "owner_key", "proves"]

OWNER_KEY_FILE = "owner.key"
_KEY_BYTES = 32
_HEX_KEY = re.compile(r"[0-9a-fA-F]{64}")


@dataclass(frozen=True)
class OwnerKey:
    file: Path
    """Where it is kept, for ``--owner-key-file``."""
    key: bytes


def owner_key(state: Path, *, make: Callable[[], bytes] = lambda: secrets.token_bytes(_KEY_BYTES)) -> OwnerKey:
    """The key in ``state``, made the first time (readable by this person only). It is written whole under another name
    and linked into place, so another of her windows never reads half of it; when another window was first, its key is
    the one (§13). A file that holds no key is replaced: a server started with the old one then no longer proves to be
    hers, and her apps start their own next to it. ``make`` is for the tests."""
    file = state / OWNER_KEY_FILE
    found = _read_key(file)
    if found is not None:
        return OwnerKey(file, found)
    state.mkdir(parents=True, exist_ok=True)
    temporary = file.with_name(f"{file.name}.{os.getpid()}")
    made = make()
    handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        out.write(made.hex() + "\n")
    try:
        os.link(temporary, file)  # only when there is no file yet
    except OSError:
        if _read_key(file) is None:
            temporary.replace(file)  # a file that holds no key: replaced
    finally:
        temporary.unlink(missing_ok=True)
    return OwnerKey(file, _read_key(file) or made)  # the key in the file, whoever wrote it


def _read_key(file: Path) -> bytes | None:
    try:
        text = file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    return bytes.fromhex(text) if _HEX_KEY.fullmatch(text) else None


def owner_answer(key: bytes, port: int, challenge: str) -> str:
    """What a server that listens on ``port`` with ``key`` answers to ``challenge``."""
    return hmac.new(key, f"claudia owner proof\n{port}\n{challenge}".encode(), hashlib.sha256).hexdigest()


def proves(key: bytes, port: int, challenge: str, answer: object) -> bool:
    """Is ``answer`` the one a server with ``key`` on ``port`` gives to ``challenge``? Compared in constant time."""
    expected = owner_answer(key, port, challenge).encode()
    return isinstance(answer, str) and hmac.compare_digest(answer.encode(), expected)


def is_owned_by(port: int, key: bytes, timeout: float = 1.0) -> bool:
    """Does the server on ``port`` of this computer prove that it is the one with ``key``? Any failure to ask is a
    no."""
    challenge = secrets.token_hex(32)  # fresh, 64 lower-case hex digits
    url = f"http://127.0.0.1:{port}/api/owner?challenge={challenge}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as answer:  # noqa: S310 (our own http URL)
            body = json.loads(answer.read())
    except (urllib.error.URLError, OSError, ValueError):
        return False
    return isinstance(body, dict) and proves(key, port, challenge, body.get("answer"))
