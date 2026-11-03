"""Keeping typeset results by what they were made from (E3.4).

The key is a digest of everything that changes the picture: the job, the engine's version and
the font catalogue's digest (coarse in v1: a new font anywhere makes every result stale).
"""

import contextlib
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from .job import Job

#: Bumped when the way a source is built changes, so that old results are not reused.
BUILD_VERSION = 1

_KEY = re.compile(r"[0-9a-f]{64}")


def cache_key(job: Job, *, engine: str, fonts: str) -> str:
    """The key under which the result of ``job`` is kept."""
    identity = {
        "build": BUILD_VERSION,
        "mode": job.mode.value,
        "source": job.source,
        "font": job.font,
        "width_mm": job.width_mm,
        "engine": engine,
        "fonts": fonts,
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()


class ResultCache:
    """SVG results in a folder, one file per key, written atomically."""

    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)

    def _path(self, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise ValueError("a cache key is a lower-case sha256 digest")
        return self._directory / f"{key}.svg"

    def get(self, key: str) -> str | None:
        """The result kept under ``key``, or None."""
        path = self._path(key)
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError, UnicodeDecodeError:
            return None

    def put(self, key: str, svg: str) -> None:
        """Keep ``svg`` under ``key``."""
        path = self._path(key)
        self._directory.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=self._directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(svg)
            os.replace(temporary, path)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary)
            raise
