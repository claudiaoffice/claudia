"""The encrypted journal of an open document (E2.1, D106).

While somebody has a document open, every change is appended here as one sealed record and is on disk before the
server answers (``fsync``). Nothing about the content is visible: a record shows only its domain, a sequence number and
its size. File layout::

    header   b"CLAUDIA-J1\\n", generation (4 bytes), length of the document id (2 bytes), the document id
    record   length of body (4 bytes), body, CRC-32 of body (4 bytes)
    body     domain (1 byte), sequence number (8 bytes), sealed payload (nonce, ciphertext, tag)

The CRC finds accidents. The encryption (AES-GCM, with the document id, generation, domain and sequence number as
authenticated data) finds everything else: a record cannot be altered, moved to another place or another document,
swapped with another, repeated or left out without being noticed.

A crash can leave the last record cut off or garbled. Such a record was never acknowledged, so it is dropped (and the
writer repairs the file). Damage anywhere else is an error, never a guess. Not detected in this version: an outsider
who cuts records off the end of the file; that needs the head record of the packed file (design, section 3).
"""

import contextlib
import gc
import io
import os
import struct
import sys
import time
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Self

from .crypto import NONCE_SIZE, TAG_SIZE, DecryptionError, open_sealed, seal
from .slots import Domain

MAGIC = b"CLAUDIA-J1\n"
MAX_RECORD_BYTES = 16 * 1024 * 1024
"""Largest payload of one record; a file cannot make the reader allocate more than this."""

_DOMAIN_BYTE = {Domain.CONTENT: 1, Domain.HISTORY: 2, Domain.CHAT: 3}
_BYTE_DOMAIN = {value: domain for domain, value in _DOMAIN_BYTE.items()}
_BODY_FIXED = 1 + 8 + NONCE_SIZE + TAG_SIZE
_MIN_BODY = _BODY_FIXED
_MAX_BODY = _BODY_FIXED + MAX_RECORD_BYTES


class JournalError(Exception):
    """The journal is damaged, was tampered with, belongs to another document or cannot be opened with these keys."""


@dataclass(frozen=True)
class JournalRecord:
    """One opened record: its number (from 1), its domain and what was written."""

    seq: int
    domain: Domain
    payload: bytes


def _header(doc_id: str, generation: int) -> bytes:
    name = doc_id.encode()
    return MAGIC + struct.pack(">IH", generation, len(name)) + name


def _header_end(data: bytes) -> tuple[int, int, str]:
    """``(end of header, generation, document id)``; ``JournalError`` if there is no header."""
    fixed = len(MAGIC) + 6
    if len(data) < fixed or data[: len(MAGIC)] != MAGIC:
        raise JournalError("this is not a Claudia journal")
    generation, length = struct.unpack(">IH", data[len(MAGIC) : fixed])
    if len(data) < fixed + length:
        raise JournalError("the journal header is cut off")
    try:
        doc_id = data[fixed : fixed + length].decode()
    except UnicodeDecodeError as error:
        raise JournalError("the journal header is damaged") from error
    return fixed + length, generation, doc_id


@dataclass(frozen=True)
class _Parsed:
    generation: int
    doc_id: str
    bodies: list[bytes]
    valid_end: int  # the file is sound up to here; anything after it is a cut-off last record


def _parse(data: bytes) -> _Parsed:
    pos, generation, doc_id = _header_end(data)
    bodies: list[bytes] = []
    while pos < len(data):
        if len(data) - pos < 4:
            break  # the length itself was cut off
        (size,) = struct.unpack(">I", data[pos : pos + 4])
        if not _MIN_BODY <= size <= _MAX_BODY:
            if not any(data[pos:]):
                break  # a tail of zeros: the file system had grown the file when the power went out
            raise JournalError("a record has an impossible size")
        end = pos + 4 + size + 4
        if end > len(data):
            break  # the last record is cut off
        body = data[pos + 4 : pos + 4 + size]
        (check,) = struct.unpack(">I", data[end - 4 : end])
        if check != zlib.crc32(body):
            if end == len(data):
                break  # the last record is garbled: it was being written
            raise JournalError("a record in the middle of the journal is damaged")
        bodies.append(body)
        pos = end
    return _Parsed(generation, doc_id, bodies, pos)


def _split(data: bytes) -> list[bytes]:
    """The complete records as they are in the file (length, body, check value). For tests and tools."""
    start, _, _ = _header_end(data)
    parsed = _parse(data)
    frames, pos = [], start
    for body in parsed.bodies:
        frames.append(data[pos : pos + 4 + len(body) + 4])
        pos += 4 + len(body) + 4
    return frames


def _aad(doc_id: str, generation: int, domain_byte: int, seq: int) -> bytes:
    name = doc_id.encode()
    fixed = struct.pack(">IBQ", generation, domain_byte, seq)
    return b"claudia/journal/1" + struct.pack(">H", len(name)) + name + fixed


def _fsync_directory(directory: Path) -> None:
    with contextlib.suppress(OSError):  # (some systems cannot open a directory)
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


_REPLACE_RETRIES = 10
_REPLACE_DELAY = 0.05  # seconds, doubled each retry up to _REPLACE_MAX_DELAY
_REPLACE_MAX_DELAY = 1.0


def _open_in_this_process(path: Path) -> list[str]:
    """Every file object this process still has open against ``path`` (best effort; for the diagnostic below).

    Retrying and excluding the directory from Windows Defender have both failed to explain a replace that keeps
    being refused, every attempt, every time -- behaviour more consistent with a handle of our own we never
    closed than with an outside program's transient lock. This answers that directly instead of guessing again:
    if nothing of ours shows up here, the lock really is somebody else's."""
    found = []
    for obj in gc.get_objects():
        if not isinstance(obj, (io.RawIOBase, io.BufferedIOBase)):
            continue
        name = getattr(obj, "name", None)
        # A file opened from a bare descriptor (as every writer here is, via `os.fdopen`) reports that
        # descriptor's *number* as `.name`, not a path, until something re-opens it by path instead -- that
        # int is not a path and must be skipped before it ever reaches `Path(...)`, rather than caught after.
        if not isinstance(name, (str, os.PathLike)) or obj.closed:
            continue
        try:
            same = Path(name).resolve() == path.resolve()
        except OSError:
            continue
        if same:
            found.append(repr(obj))
    return found


def _replace(temp: Path, path: Path) -> None:
    """``os.replace(temp, path)``, retried briefly on Windows.

    Windows refuses to replace a file that still has an open handle anywhere, including a transient one held
    for a moment by real-time antivirus scanning or file-system indexing right after the file is written --
    something POSIX simply does not have. A handle of our own must still be closed before calling this (that
    failure is deterministic and retrying it would only waste time); this is for the transient kind.

    ``pack_journal`` can land here twice in a row for the same file -- once to rotate the journal, and again
    (via ``begin``'s own recovery) if that rotation's replace is what failed -- so the lock this is waiting out
    may already have been outstanding for a while by the second attempt. The backoff is capped rather than left
    to double forever, so repeated contention still clears within a bounded total wait (worst case, with 10
    retries capped at 1s: a bit under 10s) instead of either giving up too soon or stalling indefinitely.
    """
    if sys.platform != "win32":
        os.replace(temp, path)
        return
    delay = _REPLACE_DELAY
    for attempt in range(_REPLACE_RETRIES):
        try:
            os.replace(temp, path)
            return
        except PermissionError as error:
            if attempt == _REPLACE_RETRIES - 1:
                # Best-effort diagnostic only: whatever goes wrong while looking must never stand in for the
                # real failure above, so a second bug here cannot hide the first one the way it just did.
                try:
                    ours = _open_in_this_process(path) + _open_in_this_process(temp)
                except Exception:
                    ours = []
                if ours:
                    raise PermissionError(f"{error}; still open in this process: {ours}") from error
                raise
            time.sleep(delay)
            delay = min(delay * 2, _REPLACE_MAX_DELAY)


class JournalWriter:
    """Appends sealed records to a journal. One writer per open document."""

    def __init__(
        self, handle: BinaryIO, doc_id: str, keys: Mapping[Domain, bytes], generation: int, last_seq: int
    ) -> None:
        self._handle = handle
        self._doc_id = doc_id
        self._keys = dict(keys)
        self._generation = generation
        self.seq = last_seq
        """The number of the last record written (0 for none)."""

    @property
    def generation(self) -> int:
        """The generation of this journal. It grows by one every time the journal is folded into the document file."""
        return self._generation

    @classmethod
    def create(cls, path: Path, doc_id: str, keys: Mapping[Domain, bytes], generation: int = 0) -> Self:
        """Start a new journal; ``FileExistsError`` if there is one."""
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        handle = os.fdopen(fd, "wb")
        handle.write(_header(doc_id, generation))
        handle.flush()
        os.fsync(handle.fileno())
        _fsync_directory(path.parent)
        return cls(handle, doc_id, keys, generation, 0)

    @classmethod
    def replace(cls, path: Path, doc_id: str, keys: Mapping[Domain, bytes], generation: int) -> Self:
        """Put an empty journal of ``generation`` in place of the one at ``path``, all at once: a crash leaves the old
        journal or the new one, never a mixture. Returns a writer on the new journal."""
        temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(_header(doc_id, generation))
                handle.flush()
                os.fsync(handle.fileno())
            _replace(temp, path)
            _fsync_directory(path.parent)
        except BaseException:
            with contextlib.suppress(OSError):
                temp.unlink()
            raise
        return cls(path.open("ab"), doc_id, keys, generation, 0)

    @classmethod
    def open(cls, path: Path, doc_id: str, keys: Mapping[Domain, bytes]) -> Self:
        """Continue an existing journal. A cut-off last record is removed first; its number is used again."""
        data = path.read_bytes()
        parsed = _parse(data)
        if parsed.doc_id != doc_id:
            raise JournalError("this journal belongs to another document")
        if parsed.valid_end < len(data):
            with path.open("r+b") as repair:
                repair.truncate(parsed.valid_end)
                repair.flush()
                os.fsync(repair.fileno())
        last = struct.unpack(">Q", parsed.bodies[-1][1:9])[0] if parsed.bodies else 0
        return cls(path.open("ab"), doc_id, keys, parsed.generation, last)

    def append(self, domain: Domain, payload: bytes) -> int:
        """Seal and write one record, and return only when it is on disk. Returns its number."""
        if len(payload) > MAX_RECORD_BYTES:
            raise ValueError(f"the record is too large ({len(payload)} bytes, at most {MAX_RECORD_BYTES})")
        key = self._keys.get(domain)
        if key is None:
            raise ValueError(f"this writer holds no key for the {domain} records")
        seq = self.seq + 1
        domain_byte = _DOMAIN_BYTE[domain]
        sealed = seal(key, payload, _aad(self._doc_id, self._generation, domain_byte, seq))
        body = bytes([domain_byte]) + struct.pack(">Q", seq) + sealed
        self._handle.write(struct.pack(">I", len(body)) + body + struct.pack(">I", zlib.crc32(body)))
        self._handle.flush()
        os.fsync(self._handle.fileno())  # the change did not happen unless it is on disk
        self.seq = seq
        return seq

    def close(self) -> None:
        """Let go of the file."""
        self._handle.close()


def journal_generation(path: Path) -> int:
    """The generation in the header of the journal at ``path`` (no key needed). :class:`JournalError` if it has none."""
    with path.open("rb") as handle:
        data = handle.read(len(MAGIC) + 6 + 2048)
    return _header_end(data)[1]


def read_journal(path: Path, doc_id: str, keys: Mapping[Domain, bytes]) -> list[JournalRecord]:
    """Open every record of the journal. ``JournalError`` for damage, tampering, a foreign journal or a missing key."""
    parsed = _parse(path.read_bytes())
    if parsed.doc_id != doc_id:
        raise JournalError("this journal belongs to another document")
    records = []
    expected = 1
    for body in parsed.bodies:
        domain_byte = body[0]
        (seq,) = struct.unpack(">Q", body[1:9])
        if seq != expected:
            raise JournalError(f"record {expected} is missing, repeated or out of place (found {seq})")
        domain = _BYTE_DOMAIN.get(domain_byte)
        if domain is None:
            raise JournalError(f"record {seq} has an unknown domain")
        key = keys.get(domain)
        if key is None:
            raise JournalError(f"no key for the {domain} records")
        try:
            payload = open_sealed(key, body[9:], _aad(doc_id, parsed.generation, domain_byte, seq))
        except DecryptionError as error:
            raise JournalError(f"record {seq} cannot be opened: wrong key, or it was changed") from error
        records.append(JournalRecord(seq, domain, payload))
        expected += 1
    return records
