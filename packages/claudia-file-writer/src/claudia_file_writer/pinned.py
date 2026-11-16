"""Files fetched by URL and checked against the SHA-256 a lock file gives (CODE-34, D701).

The fonts every server has (``claudia_fonts.starter``) and the hyphenation patterns (``claudia_server.hyphenation``)
are pinned this way: each lock names a file, where it comes from and its hash, and nothing else is accepted. A fetch
runs only when an operator asks for it (or the Docker image is built); a running server never fetches.
"""

from __future__ import annotations

import hashlib
import re
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from .atomic import write_atomically

_HASH = re.compile(r"[0-9a-f]{64}")
# A name stays in its folder on every system: no separators, no drive letter or stream (":"), not hidden; the brackets
# and commas are those of variable font files (``Inter[opsz,wght].ttf``).
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._,+\[\]-]*")
_PUBLIC = 0o644


class FetchError(Exception):
    """A pinned file could not be fetched, or its bytes are not the pinned ones."""


@dataclass(frozen=True)
class PinnedFile:
    """One file of a lock: its name in its folder, where it comes from, its SHA-256 (lower case) and its size."""

    name: str
    url: str
    sha256: str
    size: int

    @classmethod
    def from_lock(cls, entry: Mapping) -> Self:
        """The file a lock entry (``name``, ``url``, ``sha256``, ``size``) names; ``ValueError`` if its name could leave
        its folder, it is not fetched over https or it has no SHA-256."""
        name = str(entry["name"])
        if not _NAME.fullmatch(name):
            raise ValueError(f"lock: bad file name {name!r}")
        url = str(entry["url"])
        if not url.startswith("https://"):
            raise ValueError(f"lock: {name} is not fetched over https")
        sha256 = str(entry["sha256"]).lower()
        if not _HASH.fullmatch(sha256):
            raise ValueError(f"lock: {name} has no SHA-256")
        return cls(name, url, sha256, int(entry["size"]))

    def is_at(self, path: Path) -> bool:
        """Whether ``path`` is a file with exactly the pinned bytes."""
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == self.sha256


def download(url: str, *, max_bytes: int, timeout: float = 60) -> bytes:
    """The bytes at ``url`` (https only); :class:`FetchError` if there are more than ``max_bytes``."""
    if not url.startswith("https://"):
        raise FetchError(f"{url} is not fetched over https")
    with urllib.request.urlopen(url, timeout=timeout) as answer:  # noqa: S310 - https only, checked above
        data = answer.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise FetchError(f"{url} is larger than {max_bytes} bytes")
    return data


def fetch_pinned(
    files: Iterable[PinnedFile],
    folder: str | Path,
    *,
    download: Callable[[str], bytes],
    report: Callable[[str], None] = lambda _line: None,
    label: str = "pinned files",
) -> list[Path]:
    """Fetch every one of ``files`` into ``folder`` (made if need be); a file already there with the pinned bytes is
    kept. The files' paths, in order. ``download`` gives the bytes of a URL; ``report`` is told of every file fetched
    (``"fetching <label>: <name>"``). Fetched files are readable by everyone (0644): the Docker image fetches as root
    for a server that runs as another user.

    :class:`FetchError` names the first file that could not be fetched or whose bytes are not the pinned ones; that
    file is not written."""
    root = Path(folder)
    root.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for f in files:
        path = root / f.name
        paths.append(path)
        if f.is_at(path):
            continue
        report(f"fetching {label}: {f.name}")
        try:
            data = download(f.url)
        except OSError as error:
            raise FetchError(f"{f.url}: {error}") from error
        got = hashlib.sha256(data).hexdigest()
        if got != f.sha256:
            raise FetchError(f"{f.name}: SHA-256 {got}, the lock says {f.sha256}")
        write_atomically(path, data, mode=_PUBLIC)
    return paths
