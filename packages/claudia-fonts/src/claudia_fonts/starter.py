"""The starter set: open fonts a server can fetch so that it has something to lay out and print with (D93, D905).

The set is pinned in ``starter.lock.json``: every file by URL (a fixed commit of github.com/google/fonts) and SHA-256.
:func:`fetch` downloads what is missing into one folder per collection, each with its ``collection.json``, and
refuses a file whose bytes are not the pinned ones. It is the only part of this package that uses the network, and it
runs only when an operator asks for it (``python -m claudia_fonts fetch DIR``) or the demo start script does.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from .collection import COLLECTION_FILE, RECORD_FORMAT

LOCK_FORMAT = 1
#: The largest file the fetch accepts (the largest pinned file is about 1 MB).
MAX_FILE_BYTES = 16 * 1024 * 1024


class FetchError(Exception):
    """A pinned file could not be fetched, or its bytes are not the pinned ones."""


@dataclass(frozen=True)
class LockedFile:
    """One file of the lock: its name in the collection folder, where it comes from and its SHA-256."""

    name: str
    url: str
    sha256: str
    size: int


@dataclass(frozen=True)
class LockedCollection:
    """A collection of the lock: its folder name, licence record and files."""

    name: str
    folder: str
    licence: str
    redistributable: bool
    source: str
    version: str
    files: tuple[LockedFile, ...]


def read_lock(text: str | None = None) -> tuple[LockedCollection, ...]:
    """The collections of a lock file (by default the packaged ``starter.lock.json``); ``ValueError`` if malformed."""
    if text is None:
        text = resources.files("claudia_fonts").joinpath("starter.lock.json").read_text(encoding="utf-8")
    data = json.loads(text)
    if data.get("format") != LOCK_FORMAT:
        raise ValueError(f"lock format {data.get('format')!r} is not known (this version reads {LOCK_FORMAT})")
    out: list[LockedCollection] = []
    for c in data["collections"]:
        folder = str(c["folder"])
        if not folder or "/" in folder or "\\" in folder or folder.startswith("."):
            raise ValueError(f"lock: bad folder name {folder!r}")
        files = []
        for f in c["files"]:
            name = str(f["name"])
            if not name or "/" in name or "\\" in name or name.startswith("."):
                raise ValueError(f"lock: bad file name {name!r}")
            if not str(f["url"]).startswith("https://"):
                raise ValueError(f"lock: {name} is not fetched over https")
            files.append(LockedFile(name, str(f["url"]), str(f["sha256"]).lower(), int(f["size"])))
        out.append(
            LockedCollection(
                str(c["name"]),
                folder,
                str(c["licence"]),
                bool(c["redistributable"]),
                str(c.get("source", "")),
                str(c.get("version", "")),
                tuple(files),
            )
        )
    return tuple(out)


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as answer:  # noqa: S310 - https only, checked in read_lock
        data = answer.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise FetchError(f"{url} is larger than {MAX_FILE_BYTES} bytes")
    return data


def _write(target: Path, data: bytes) -> None:
    handle, temporary = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _matches(path: Path, sha256: str) -> bool:
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha256


def fetch(
    target: str | Path,
    collections: Iterable[LockedCollection] | None = None,
    *,
    download: Callable[[str], bytes] | None = None,
    report: Callable[[str], None] = lambda _line: None,
) -> list[Path]:
    """Fetch every file of ``collections`` (default: the starter set) into ``target``, one folder per collection with
    its ``collection.json``; files already there with the right bytes are kept. The collection folders, in order.
    ``download`` gives the bytes of a URL (default: an HTTPS request).

    :class:`FetchError` names the first file that could not be fetched or whose bytes differ from the lock."""
    root = Path(target)
    get = download or _download
    folders: list[Path] = []
    for collection in read_lock() if collections is None else collections:
        folder = root / collection.folder
        folder.mkdir(parents=True, exist_ok=True)
        for f in collection.files:
            path = folder / f.name
            if _matches(path, f.sha256):
                continue
            report(f"fetching {collection.name}: {f.name}")
            try:
                data = get(f.url)
            except OSError as error:
                raise FetchError(f"{f.url}: {error}") from error
            got = hashlib.sha256(data).hexdigest()
            if got != f.sha256:
                raise FetchError(f"{f.name}: SHA-256 {got}, the lock says {f.sha256}")
            _write(path, data)
        record = {
            "format": RECORD_FORMAT,
            "name": collection.name,
            "licence": collection.licence,
            "redistributable": collection.redistributable,
            "source": collection.source,
            "version": collection.version,
        }
        _write(folder / COLLECTION_FILE, (json.dumps(record, indent=2) + "\n").encode("utf-8"))
        folders.append(folder)
    return folders


def collection_folders(path: str | Path) -> list[Path]:
    """The collection folders under ``path``: ``path`` itself if it has a ``collection.json``, else each of its
    subfolders that has one, sorted by name. Empty if ``path`` is not a folder."""
    root = Path(path)
    if (root / COLLECTION_FILE).is_file():
        return [root]
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / COLLECTION_FILE).is_file())
