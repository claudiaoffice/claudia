"""Hyphenation patterns for the clients' layout (D913): which languages a server can hyphenate, and the files.

Pages are laid out in the client (D901), and a client hyphenates a word where the TeX patterns of its language allow
(D912). Every client must use the same patterns, so the server hands them out by SHA-256, the way it hands out fonts
(D905):

* ``GET /api/hyphenation`` - the languages: BCP 47 tag, other tags they stand for, name, licence, and the hash and
  size of the pattern file and of the list of exceptions.
* ``GET /api/hyphenation/{sha256}`` - one file, as UTF-8 text. Its address never changes its meaning.

The patterns are the plain-text files of hyph-utf8 (github.com/hyphenation/tex-hyphen), pinned at one commit with
every file's SHA-256 in ``hyphenation.lock.json``. ``python -m claudia_server.hyphenation fetch DIR`` fetches them
(the demo start script and the Docker image do it); the server is given the folder with ``--hyphenation DIR``
(default ``STATE_DIR/hyphenation``) and reads every file it lists into memory at start, checking each hash. A file
that is missing or differs is left out, with its language, and named in the start-up banner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response

from claudia_file_writer import FetchError, PinnedFile, fetch_pinned
from claudia_file_writer import download as https_download

#: The format of ``GET /api/hyphenation``; it rises when a field changes meaning or goes away.
HYPHENATION_FORMAT = 1
LOCK_FORMAT = 1
#: The largest pattern file a fetch accepts (the largest pinned one is under 300 kB).
MAX_FILE_BYTES = 4 * 1024 * 1024
_HASH = re.compile(r"[0-9a-f]{64}")
_FOREVER = "public, max-age=31536000, immutable"


@dataclass(frozen=True)
class PatternFile(PinnedFile):
    """One file of the lock: its name in the folder, where it comes from, its SHA-256 and size."""

    def to_data(self) -> dict:
        """What a client is told of the file."""
        return {"sha256": self.sha256, "size": self.size}


@dataclass(frozen=True)
class Language:
    """The patterns of one language: its tag, the tags it also stands for, a name, the licence, and the files."""

    tag: str
    aliases: tuple[str, ...]
    name: str
    licence: str
    patterns: PatternFile
    exceptions: PatternFile | None

    def files(self) -> list[PatternFile]:
        """The pattern file, and the exceptions if the language has some."""
        return [self.patterns, *([self.exceptions] if self.exceptions else [])]

    def to_data(self) -> dict:
        """The language as ``GET /api/hyphenation`` lists it."""
        return {
            "tag": self.tag,
            "aliases": list(self.aliases),
            "name": self.name,
            "licence": self.licence,
            "patterns": self.patterns.to_data(),
            "exceptions": self.exceptions.to_data() if self.exceptions else None,
        }


def read_lock(text: str | None = None) -> tuple[Language, ...]:
    """The languages of a lock file (by default the packaged ``hyphenation.lock.json``); ``ValueError`` if malformed."""
    if text is None:
        text = resources.files("claudia_server").joinpath("hyphenation.lock.json").read_text(encoding="utf-8")
    data = json.loads(text)
    if data.get("format") != LOCK_FORMAT:
        raise ValueError(f"lock format {data.get('format')!r} is not known (this version reads {LOCK_FORMAT})")
    return tuple(
        Language(
            str(entry["tag"]),
            tuple(str(a) for a in entry.get("aliases", [])),
            str(entry["name"]),
            str(entry["licence"]),
            PatternFile.from_lock(entry["patterns"]),
            PatternFile.from_lock(entry["exceptions"]) if entry.get("exceptions") else None,
        )
        for entry in data["languages"]
    )


@dataclass
class HyphenationService:
    """The patterns a server hands out: the languages whose files are all present with the pinned bytes."""

    languages: tuple[Language, ...]
    files: dict[str, bytes]
    #: what was left out, and why
    problems: tuple[str, ...] = ()

    @classmethod
    def from_folder(cls, folder: str | Path, languages: tuple[Language, ...] | None = None) -> HyphenationService:
        """Read the files of ``languages`` (default: the lock's) from ``folder``, checking each one's hash."""
        root = Path(folder)
        usable: list[Language] = []
        files: dict[str, bytes] = {}
        problems: list[str] = []
        for language in read_lock() if languages is None else languages:
            got: dict[str, bytes] = {}
            for f in language.files():
                path = root / f.name
                if not path.is_file():
                    problems.append(f"{language.tag}: {f.name} is missing")
                    break
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != f.sha256:
                    problems.append(f"{language.tag}: {f.name} is not the pinned file")
                    break
                got[f.sha256] = data
            else:
                usable.append(language)
                files.update(got)
        return cls(tuple(usable), files, tuple(problems))

    def listing(self) -> dict:
        """The body of ``GET /api/hyphenation``."""
        return {"format": HYPHENATION_FORMAT, "languages": [language.to_data() for language in self.languages]}

    def summary(self) -> str:
        """One line for the start-up banner."""
        if not self.languages:
            return (
                "no hyphenation patterns: pages are not hyphenated "
                "(python -m claudia_server.hyphenation fetch DIR, then --hyphenation DIR)"
            )
        return f"hyphenation: {', '.join(language.tag for language in self.languages)} (/api/hyphenation)"


def hyphenation_router(service: HyphenationService) -> APIRouter:
    """The ``/api/hyphenation`` routes of a server."""
    router = APIRouter(prefix="/api/hyphenation")

    @router.get("")
    async def hyphenation_listing() -> JSONResponse:
        return JSONResponse(service.listing(), headers={"Cache-Control": "no-cache"})

    @router.get("/{sha256}")
    async def hyphenation_file(sha256: str) -> Response:
        data = service.files.get(sha256) if _HASH.fullmatch(sha256) else None
        if data is None:
            raise HTTPException(404, "no such pattern file")
        return Response(data, media_type="text/plain; charset=utf-8", headers={"Cache-Control": _FOREVER})

    return router


# ---------------------------------------------------------------------------------------------------- fetching
def _download(url: str) -> bytes:
    return https_download(url, max_bytes=MAX_FILE_BYTES)


def fetch(
    target: str | Path,
    languages: tuple[Language, ...] | None = None,
    *,
    download: Callable[[str], bytes] | None = None,
    report: Callable[[str], None] = lambda _line: None,
) -> list[Path]:
    """Fetch the files of ``languages`` (default: the lock's) into ``target``; files already there with the right
    bytes are kept. The files, in order. ``download`` gives the bytes of a URL (default: an HTTPS request).

    :class:`claudia_file_writer.FetchError` names the first file that could not be fetched or whose bytes differ
    from the lock."""
    files = [f for language in (read_lock() if languages is None else languages) for f in language.files()]
    return fetch_pinned(files, target, download=download or _download, report=report, label="hyphenation patterns")


def main(argv: list[str] | None = None) -> int:
    """``python -m claudia_server.hyphenation fetch DIR``; the exit status."""
    parser = argparse.ArgumentParser(
        prog="python -m claudia_server.hyphenation", description="The hyphenation patterns of a Claudia server."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    get = commands.add_parser("fetch", help="fetch the pinned hyphenation patterns into a folder")
    get.add_argument("folder", help="where the files go; give it to the server with --hyphenation")
    args = parser.parse_args(argv)
    try:
        files = fetch(args.folder, report=lambda line: print(line, flush=True))
    except FetchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"{len(files)} pattern files in {args.folder}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
