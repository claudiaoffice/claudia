"""Writing a file all at once: next to its place, then moved there in one step (CODE-34, D701).

Every writer of the server goes through here: the documents and their journal (``claudia_container``), the server's
state and certificate (``claudia_server.state``), and the files a server makes or fetches (fonts, web fonts, typeset
results, hyphenation patterns). Before, each did it its own way and only two retried on Windows.
"""

from __future__ import annotations

import contextlib
import gc
import io
import os
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

_PRIVATE = 0o600


def fsync_directory(directory: str | os.PathLike) -> None:
    """Make a folder's list of files durable, so that a file moved into it survives a crash. A system that cannot open
    a folder for this (Windows) is left alone."""
    with contextlib.suppress(OSError):
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


@dataclass(frozen=True)
class Replacer:
    """Moves a file just written into its place, and tries again on Windows while the system refuses.

    Windows refuses to replace a file that has an open handle anywhere, including the one antivirus scanning or
    indexing holds for a moment right after a file is written; POSIX does not. A refusal there is tried again after a
    wait that starts at ``first_wait`` seconds and doubles up to ``longest_wait``, ``attempts`` times in all (with the
    defaults a little under ten seconds). A handle of our own never goes away by waiting, so when the last attempt is
    refused too, the error names any file object of this process that still holds the file open.

    ``windows`` is whether to retry (``None``: on this system if it is Windows). ``replace`` and ``sleep`` are the
    system's unless given (``os.replace``, ``time.sleep``); a test gives its own."""

    windows: bool | None = None
    attempts: int = 10
    first_wait: float = 0.05
    longest_wait: float = 1.0
    replace: Callable[[Path, Path], None] | None = None
    sleep: Callable[[float], None] | None = None

    def __call__(self, temp: Path, path: Path) -> None:
        """Move ``temp`` to ``path``, replacing what is there."""
        retries = sys.platform == "win32" if self.windows is None else self.windows
        replace, sleep = self.replace or os.replace, self.sleep or time.sleep
        wait = self.first_wait
        for _ in range(self.attempts - 1 if retries else 0):
            try:
                replace(temp, path)
                return
            except PermissionError:
                sleep(wait)
                wait = min(wait * 2, self.longest_wait)
        try:
            replace(temp, path)
        except PermissionError as error:
            ours = _held_by_us(path, temp) if retries else []
            if ours:
                raise PermissionError(f"{error}; still open in this process: {ours}") from error
            raise


def _held_by_us(*paths: Path) -> list[str]:
    """The file objects of this process that still hold one of ``paths`` open. Best effort: whatever goes wrong while
    looking must not hide the refusal it is looked for."""
    try:
        return [handle for path in paths for handle in _open_in_this_process(path)]
    except Exception:
        return []


def _open_in_this_process(path: Path) -> list[str]:
    found = []
    for obj in gc.get_objects():
        if not isinstance(obj, (io.RawIOBase, io.BufferedIOBase)) or obj.closed:
            continue
        name = getattr(obj, "name", None)
        # A file opened from a bare descriptor (``os.fdopen``) reports the descriptor's number as its name, not a path.
        if not isinstance(name, (str, os.PathLike)):
            continue
        with contextlib.suppress(OSError):
            if Path(name).resolve() == path.resolve():
                found.append(repr(obj))
    return found


#: What moves a file just written into its place: a :class:`Replacer`, or any function of (temporary file, place).
Move = Callable[[Path, Path], None]


@contextlib.contextmanager
def atomic_file(
    path: str | os.PathLike, *, mode: int = _PRIVATE, durable: bool = False, replacer: Move | None = None
) -> Iterator[BinaryIO]:
    """A file opened for writing that takes the place of ``path`` when the ``with`` block ends without an error. Until
    then readers see the old file (or none); if the block fails, nothing is left behind.

    The file is private (0600) from its first byte; ``mode`` is what it gets before it is moved into place (0644 for a
    file that other users read). ``durable`` waits until the file and the folder's list of files are on disk: a
    document, a journal, a secret. A cache does not need it. ``replacer`` moves the file into place (default: a
    :class:`Replacer`)."""
    target = Path(path)
    handle, name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    temp = Path(name)
    try:
        with os.fdopen(handle, "wb") as out:
            yield out
            out.flush()
            if durable:
                os.fsync(out.fileno())
        if mode != _PRIVATE:
            os.chmod(temp, mode)
        (replacer or Replacer())(temp, target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    if durable:
        fsync_directory(target.parent)


def write_atomically(
    path: str | os.PathLike,
    data: bytes,
    *,
    mode: int = _PRIVATE,
    durable: bool = False,
    replacer: Move | None = None,
) -> None:
    """Write ``data`` to ``path`` all at once (see :func:`atomic_file` for ``mode`` and ``durable``)."""
    with atomic_file(path, mode=mode, durable=durable, replacer=replacer) as out:
        out.write(data)


def write_once(path: str | os.PathLike, data: bytes, *, mode: int = _PRIVATE, replacer: Replacer | None = None) -> bool:
    """Write ``data`` to ``path`` unless a file is there already; whether this call wrote it.

    For a file named by what is in it (a cache entry named by a hash): the file that is there has the same bytes. Two
    requests can make the same entry at once, and on Windows the one that comes second may be refused while the first
    one's file is being read; finding the file there then is success, without waiting."""
    target = Path(path)
    if target.exists():
        return False
    patient = replacer or Replacer()

    def unless_it_appeared(temp: Path, final: Path) -> None:
        try:
            (patient.replace or os.replace)(temp, final)
        except PermissionError:
            if final.exists():
                raise _AlreadyThere from None
            patient(temp, final)

    try:
        write_atomically(target, data, mode=mode, replacer=unless_it_appeared)
    except _AlreadyThere:
        return False
    return True


class _AlreadyThere(Exception):
    """Another writer put the file in place first."""
