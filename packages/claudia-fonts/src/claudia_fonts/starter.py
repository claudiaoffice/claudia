"""The starter set: open fonts every server has, so that it can always lay out and print (D93, D905, D500).

The set is pinned in ``starter.lock.json``: every file by URL (a fixed commit of github.com/google/fonts) and SHA-256.
Since D500 the set ships inside this package (:func:`builtin_folder`), so a server has it without the network — the
desktop apps' local server above all, which nobody sets fonts up for. :func:`fetch` downloads what is missing into one
folder per collection, each with its ``collection.json``, and refuses a file whose bytes are not the pinned ones; it is
the only part of this package that uses the network, and it runs only when an operator asks for it
(``python -m claudia_fonts fetch DIR``). The test suite checks that the shipped files are the pinned ones.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from claudia_file_writer import PinnedFile, fetch_pinned, write_atomically
from claudia_file_writer import download as https_download

from .collection import COLLECTION_FILE, RECORD_FORMAT

LOCK_FORMAT = 1
#: The largest file the fetch accepts (the largest pinned file is about 1 MB).
MAX_FILE_BYTES = 16 * 1024 * 1024


#: One file of the lock: its name in the collection folder, where it comes from and its SHA-256 (D701: the pinned files
#: of fonts and hyphenation patterns are one kind of thing).
LockedFile = PinnedFile
_PUBLIC = 0o644


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
        files = [LockedFile.from_lock(f) for f in c["files"]]
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
    return https_download(url, max_bytes=MAX_FILE_BYTES)


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

    ``FetchError`` (:class:`claudia_file_writer.FetchError`) names the first file that could not be fetched or whose
    bytes differ from the lock."""
    root = Path(target)
    folders: list[Path] = []
    for collection in read_lock() if collections is None else collections:
        folder = root / collection.folder
        fetch_pinned(collection.files, folder, download=download or _download, report=report, label=collection.name)
        record = {
            "format": RECORD_FORMAT,
            "name": collection.name,
            "licence": collection.licence,
            "redistributable": collection.redistributable,
            "source": collection.source,
            "version": collection.version,
        }
        write_atomically(folder / COLLECTION_FILE, (json.dumps(record, indent=2) + "\n").encode("utf-8"), mode=_PUBLIC)
        folders.append(folder)
    return folders


def builtin_folder() -> Path:
    """The starter set as this package ships it: a folder of collection folders (D500). Every server reads it first;
    the fonts an operator adds come after it and win for the same family and style."""
    return Path(str(resources.files("claudia_fonts").joinpath("builtin")))


def collection_folders(path: str | Path) -> list[Path]:
    """The collection folders under ``path``: ``path`` itself if it has a ``collection.json``, else each of its
    subfolders that has one, sorted by name. Empty if ``path`` is not a folder."""
    root = Path(path)
    if (root / COLLECTION_FILE).is_file():
        return [root]
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / COLLECTION_FILE).is_file())
