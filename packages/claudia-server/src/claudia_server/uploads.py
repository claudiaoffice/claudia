"""Files a person brings, held for a moment until they become a document (D440).

The live connection carries JSON frames only, so a file comes in over HTTP first: ``POST /api/uploads`` with the
bytes as the body and the file's name in ``X-Claudia-Name`` (percent-encoded). The server looks at the bytes
(``formats.sniff``), keeps them here under a random token and answers what the file is. Nothing else happens: an
upload is not a document and changes nothing on disk.

What makes it a document is the usual way in: ``hello`` with ``create: true`` and ``upload: <token>`` (an Office or
OpenDocument file becomes a new document of its app, D438), or ``POST /api/uploads/<token>/place`` (a Claudia file
goes in as it is, D442). Either takes the upload away.

An upload is held for ``ttl`` seconds at most. ``most`` uploads wait at once (``most_per_address`` from one address),
each at most ``max_bytes``: someone who may reach the server cannot fill its memory with files that never become
anything (SEC-02).
"""

from __future__ import annotations

import re
import secrets
import tempfile
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import unquote

from fastapi import HTTPException, Request

from claudia_document_file import DocumentFileError, read_manifest

from .formats import CLAUDIA, CLAUDIA_EXPORT, FORMATS, export_made, file_details, sniff

MAX_UPLOAD_BYTES = 64 * 1024 * 1024
DEFAULT_MOST = 16
DEFAULT_MOST_PER_ADDRESS = 4
DEFAULT_TTL = 300.0
_ID_CHARS = re.compile(r"[^A-Za-z0-9_-]+")


class UploadRefused(Exception):
    """The upload cannot be taken: ``status`` is the HTTP status to answer with, ``message`` English for people."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class Upload:
    """One file, held: what it is and where it came from."""

    token: str
    name: str  # the file's own name, as the person's computer called it
    data: bytes = field(repr=False)
    fmt: str  # a key of ``formats.FORMATS``, or ``"claudia"``
    app: str  # the app its document belongs to
    address: str
    expires: float
    doc_id: str  # a Claudia file: its own name; any other: a name made from the file's, which the person may change
    uid: str = ""  # a Claudia file: its random id (D533); held for the check when it is placed, never shown
    description: str = ""  # what the file says about itself: its manifest, or the properties of an office file
    tags: tuple[str, ...] = ()
    made_by: str = ""  # an export: who made it, as the file says (D1272)
    made_at: str = ""  # an export: when

    def describe(self) -> dict:
        """What the person is told about it: never the bytes."""
        answer = {"upload": self.token, "name": self.name, "format": self.fmt, "app": self.app, "size": len(self.data)}
        answer["id" if self.fmt == CLAUDIA else "suggested_id"] = self.doc_id
        answer["description"] = self.description
        answer["tags"] = list(self.tags)
        if self.fmt == CLAUDIA_EXPORT:
            answer["kind"] = EXPORT_KIND
            answer["made_by"], answer["made_at"] = self.made_by, self.made_at
        elif self.fmt != CLAUDIA:
            answer["kind"] = FORMATS[self.fmt][1]
        return answer


async def read_body(request: Request, most: int) -> bytes:
    """The request's body, refused with 413 past ``most`` bytes (before reading it, when it says how long it is)."""
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > most:
        raise HTTPException(413, f"the file is larger than {most // (1024 * 1024)} MB")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > most:
            raise HTTPException(413, f"the file is larger than {most // (1024 * 1024)} MB")
        chunks.append(chunk)
    return b"".join(chunks)


def file_name(header: str | None) -> str:
    """The file's own name from ``X-Claudia-Name``: percent-decoded, without folders, at most 120 characters."""
    raw = unquote(header or "", errors="replace").strip()
    name = PureWindowsPath(PurePosixPath(raw).name).name
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    return name[:120] or "document"


def id_from_name(name: str) -> str:
    """A document id made from a file's name: ``Budget 2026 (final).xlsx`` gives ``Budget-2026-final``."""
    stem = name.rsplit(".", 1)[0] if "." in name.strip(".") else name
    plain = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    made = _ID_CHARS.sub("-", plain).strip("-_")[:64].rstrip("-_")
    return made or "imported"


EXPORT_KIND = "Claudia export"
"""What the import dialog calls an unencrypted export (D1272)."""


class UploadDesk:
    """The uploads waiting to become a document."""

    def __init__(
        self,
        *,
        max_bytes: int = MAX_UPLOAD_BYTES,
        most: int = DEFAULT_MOST,
        most_per_address: int = DEFAULT_MOST_PER_ADDRESS,
        ttl: float = DEFAULT_TTL,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.max_bytes = max_bytes
        self._most = most
        self._most_per_address = most_per_address
        self._ttl = ttl
        self._clock = clock
        self._held: dict[str, Upload] = {}

    def _expire(self) -> None:
        now = self._clock()
        for token in [t for t, upload in self._held.items() if upload.expires <= now]:
            del self._held[token]

    def room_for(self, address: str) -> None:
        """``UploadRefused(503)`` if no more uploads may wait now, all together or from ``address``."""
        self._expire()
        if len(self._held) >= self._most or sum(u.address == address for u in self._held.values()) >= (
            self._most_per_address
        ):
            raise UploadRefused(503, "too many files are waiting to be opened; try again in a few minutes")

    def put(self, address: str, name: str, data: bytes) -> Upload:
        """Hold ``data``. ``UploadRefused`` for a file that is too large, of no kind Claudia opens, or a full desk."""
        if len(data) > self.max_bytes:
            raise UploadRefused(413, f"the file is larger than {self.max_bytes // (1024 * 1024)} MB")
        self.room_for(address)
        try:
            kind = sniff(data)
        except ValueError as error:
            raise UploadRefused(415, "this is not a file Claudia can open") from error
        uid = ""
        details: tuple[str, tuple[str, ...]] = ("", ())
        if kind.fmt == CLAUDIA:
            app, doc_id, uid, details = _claudia_manifest(data)
        elif kind.fmt == CLAUDIA_EXPORT:
            if kind.app is None:
                raise UploadRefused(415, "this Claudia export is damaged or from a newer version")
            app, doc_id = kind.app, id_from_name(name.removesuffix(".zip").removesuffix(".claudia-export"))
        else:
            app, doc_id, details = FORMATS[kind.fmt][0], id_from_name(name), file_details(kind.fmt, data)
        upload = Upload(
            secrets.token_urlsafe(24), name, data, kind.fmt, app, address, self._clock() + self._ttl, doc_id
        )
        upload.uid = uid
        upload.description, upload.tags = details
        if kind.fmt == CLAUDIA_EXPORT:
            upload.made_by, upload.made_at = export_made(data)
        self._held[upload.token] = upload
        return upload

    def peek(self, token: object) -> Upload | None:
        """The upload of ``token``, still held; ``None`` if there is none (or it expired)."""
        self._expire()
        return self._held.get(token) if isinstance(token, str) else None

    def take(self, token: object) -> Upload | None:
        """The upload of ``token``, no longer held."""
        upload = self.peek(token)
        if upload is not None:
            del self._held[upload.token]
        return upload


def _claudia_manifest(data: bytes) -> tuple[str, str, str, tuple[str, tuple[str, ...]]]:
    """The app, name, uid, and (description, tags) a Claudia file's manifest gives (read from a private temporary
    file)."""
    with tempfile.TemporaryDirectory(prefix="claudia-upload-") as folder:
        path = Path(folder) / "upload.claudia"
        path.write_bytes(data)
        try:
            manifest = read_manifest(path)
        except DocumentFileError as error:
            raise UploadRefused(415, "this Claudia file is damaged or from a newer version") from error
    return manifest.app, manifest.name, manifest.uid, (manifest.description, manifest.tags)
