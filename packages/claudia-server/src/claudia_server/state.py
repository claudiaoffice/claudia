"""Where the server keeps what is not a document: its encryption key and its TLS certificate.

Deliberately *not* the documents folder: a copy or backup of the documents must not carry the key that opens
them. The folder is ``--state-dir``, else ``$CLAUDIA_STATE_DIR``, else a per-user place (``~/.local/share/claudia``,
``~/Library/Application Support/claudia`` or ``%APPDATA%\\claudia``). In a container it is a volume of its own.
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path


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
    """Write a secret: readable by its owner only from the first byte on, and replaced atomically."""
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
