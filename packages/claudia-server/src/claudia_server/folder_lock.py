"""One server per document folder (D435).

Two servers writing the same sealed files would interleave their journals, and an encrypted document that has been
written into by two processes cannot be repaired. A server therefore takes an exclusive lock on its folder before it
starts — the file ``.lock`` in it — and refuses to start when another process holds it.

The lock is the operating system's (``fcntl.flock`` on Linux and macOS, ``msvcrt.locking`` on Windows): it belongs to
the open file, so it goes away with the process however the process ends, and a lock file left behind by a crash
locks nothing. The file itself is never deleted.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

LOCK_FILE = ".lock"


class FolderLocked(Exception):
    """Another process uses the folder."""


class FolderLock:
    """The lock on one folder, held from :meth:`acquire` until :meth:`release` (or until the process ends)."""

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self._fd: int | None = None

    def acquire(self) -> None:
        """Take the lock, making the folder if need be. ``FolderLocked`` if another process holds it."""
        if self._fd is not None:
            return
        self.folder.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.folder / LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            _lock(fd)
        except OSError as exc:
            os.close(fd)
            raise FolderLocked(
                f"another Claudia server uses {self.folder}; stop it first, or give this one another folder"
            ) from exc
        self._fd = fd

    def release(self) -> None:
        """Let go of the lock. Safe to call when it is not held."""
        fd, self._fd = self._fd, None
        if fd is not None:
            _unlock(fd)
            os.close(fd)


if sys.platform == "win32":  # pragma: no cover - the Windows client's tests run this branch
    import msvcrt

    def _lock(fd: int) -> None:
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)
