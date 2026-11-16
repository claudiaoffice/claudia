"""Where the server keeps what is not a document: its TLS certificate and its administration.

::

    tls/cert.pem, tls/key.pem     the certificate the server made for itself (:mod:`claudia_server.certs`)
    admin/settings.json           the server settings an administrator chose (:mod:`claudia_server.server_settings`)
    admin/admins.json             who may change them

Deliberately *not* the documents folder: a copy or backup of the documents must not carry the server's private key or
who administers it. No document key is kept here or anywhere else on disk -- a document is opened by its people's
passwords, and its keys live in memory only while it is open (:mod:`claudia_server.sealed`).

The folder is ``--state-dir``, else ``$CLAUDIA_STATE_DIR``, else a per-user place (``~/.local/share/claudia``,
``~/Library/Application Support/claudia`` or ``%APPDATA%\\claudia``). In a container it is a volume of its own.
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

from claudia_file_writer import write_atomically


def default_state_dir() -> Path:
    env = os.environ.get("CLAUDIA_STATE_DIR")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "claudia"


def private_dir(path: Path) -> Path:
    """Make the folder (and its parents) if need be; only its owner may enter it (where the system knows that)."""
    path.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):  # (a system without such permissions)
        path.chmod(0o700)
    return path


def write_private(path: Path, data: bytes) -> None:
    """Write a secret: readable by its owner only from the first byte on, replaced atomically and on disk before this
    returns (:func:`claudia_file_writer.write_atomically`)."""
    write_atomically(path, data, durable=True)
