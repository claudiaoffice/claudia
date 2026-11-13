"""What may be asked of the typesetting service, checked before anything runs (E3.4, E3.10).

A job comes from a document, which can come from anyone who may edit it, so every field is
validated here: names that could leave the job folder, files that bring code for the engine,
font names that could carry TeX, sizes that could exhaust the machine.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

MAX_SOURCE_CHARS = 200_000
MAX_FILES = 100
MAX_FILES_BYTES = 25_000_000
MAX_NAME_CHARS = 100
MAX_PASSES = 3
MIN_WIDTH_MM = 20.0
MAX_WIDTH_MM = 400.0

#: What a document may bring besides its source: data for the engine, never code for it (D38).
ALLOWED_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".pdf", ".bib", ".tex", ".csv", ".txt"})

_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*(/[A-Za-z0-9_][A-Za-z0-9_.\-]*)*")
_FONT = re.compile(r"[^\W_](?:[^\W_]|[ .\-]){0,63}")  # letters and digits of any script


class BadJob(ValueError):
    """The job was refused before anything ran; the message says why, for the person who asked."""


class Mode(StrEnum):
    """How much of a page the source is."""

    MATH = "math"  # a formula, shown inline in a cell or a text
    PAGE = "page"  # a block of text and formulas of a given width
    DOCUMENT = "document"  # a whole document with its own class, figures and bibliography


@dataclass(frozen=True)
class Limits:
    """What one job may use. The sandbox enforces every one of them."""

    seconds: float = 20.0
    memory_mb: int = 2048
    output_mb: int = 16
    pages: int = 200
    #: Whether ``memory_mb`` also limits the *address space* of the process (Linux). Turn it off for a tool built on
    #: V8 or Chromium, which reserve far more address space than they use and are stopped by any such limit; the
    #: server's own memory limit (a container, a cgroup) is then what holds. Windows' Job Object limits committed
    #: memory, which these tools respect, so nothing changes there.
    address_space: bool = True

    def __post_init__(self) -> None:
        for name in ("seconds", "memory_mb", "output_mb", "pages"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")


def is_plain_family(name: str) -> bool:
    """Whether a font family name is safe to write into TeX: letters, digits, spaces, dots and hyphens only."""
    return _FONT.fullmatch(name) is not None


def _check_name(name: str, what: str) -> None:
    if not name or len(name) > MAX_NAME_CHARS or not _NAME.fullmatch(name):
        raise BadJob(f"{what} {name[:40]!r}: not a plain relative name")
    if "." + name.rsplit(".", 1)[-1].lower() not in ALLOWED_SUFFIXES or "." not in name.rsplit("/", 1)[-1]:
        raise BadJob(f"{what} {name[:40]!r}: this kind of file is not allowed")


@dataclass(frozen=True)
class Job:
    """One request to typeset: a mode, a source, and for a document the files it brings."""

    mode: Mode
    source: str
    files: Mapping[str, bytes] = field(default_factory=dict)
    main: str = "main.tex"
    passes: int = 1
    font: str | None = None
    width_mm: float = 150.0

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise BadJob("the source is empty")
        if len(self.source) > MAX_SOURCE_CHARS:
            raise BadJob(f"the source is too long ({len(self.source)} characters, at most {MAX_SOURCE_CHARS})")
        if self.files and self.mode is not Mode.DOCUMENT:
            raise BadJob("only a document can bring files")
        if len(self.files) > MAX_FILES:
            raise BadJob(f"too many files ({len(self.files)}, at most {MAX_FILES})")
        for name in self.files:
            _check_name(name, "file name")
        if sum(len(data) for data in self.files.values()) > MAX_FILES_BYTES:
            raise BadJob(f"the files are too big together (at most {MAX_FILES_BYTES // 1_000_000} MB)")
        try:
            _check_name(self.main, "file name")
        except BadJob as error:
            raise BadJob(f"main file: {error}") from error
        if self.main.lower() in {name.lower() for name in self.files}:
            raise BadJob("the main file cannot also be one of the other files")
        if not 1 <= self.passes <= MAX_PASSES:
            raise BadJob(f"passes must be between 1 and {MAX_PASSES}")
        if self.font is not None and not is_plain_family(self.font):
            raise BadJob(f"font {self.font[:40]!r}: not a plain family name")
        if not MIN_WIDTH_MM <= self.width_mm <= MAX_WIDTH_MM:
            raise BadJob(f"width must be between {MIN_WIDTH_MM:g} and {MAX_WIDTH_MM:g} mm")
        object.__setattr__(self, "files", MappingProxyType(dict(self.files)))
