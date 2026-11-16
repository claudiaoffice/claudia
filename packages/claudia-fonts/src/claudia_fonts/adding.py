"""Adding fonts to a server through its settings (E3.13 f, D1041): check first, then add.

Server settings ▸ Fonts ▸ Add fonts… is two steps, and nothing on the server changes before the second:

1. :func:`~claudia_fonts.check_files` says what each file would become: ``added`` (with ``replaces`` when the server
   has a font of that family and style already, which the new one then replaces for every document), or ``left-out``
   with a code that says why (``forbids-embedding``, ``not-a-font``, ``duplicate``...). A ``.zip`` is opened and its
   fonts are checked one by one; its other files and its folders are ignored.
2. :func:`~claudia_fonts.add_collection` writes the files that would be added into a new collection folder under the
   server's own root of added collections, with the record (who may receive the fonts, the licence in words, who
   added them and when). It refuses a collection with no usable font, no name or no licence.

A collection is answered for as a whole: :func:`~claudia_fonts.rename_collection` changes the name in its record, and
:func:`~claudia_fonts.remove_collection` takes the folder away with its files, but only a folder under that root, so
the shipped set (D500) and an operator's ``--fonts`` folders can never be removed from a page.

The codes are for a page that says them in its own words; the messages of :class:`AddRefused` are English, for a
log or an API error.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import tempfile
import unicodedata
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from fontTools.ttLib import TTFont

from .catalogue import Catalogue
from .collection import COLLECTION_FILE, Collection, CollectionRecord
from .font import FONT_SUFFIXES, FontProblem, read_font
from .starter import (
    _write as write_public,
)  # the starter set's own writer: a file readable by everyone, whole or not at all

#: At most this many fonts in one collection added at once (a zip counts by its fonts).
MAX_FILES = 64
#: At most this many bytes of fonts in one collection added at once.
MAX_BYTES = 128 * 1024 * 1024

Verdict = Literal["added", "left-out"]

#: Licences a font names in its name table (ID 13), as the record's licence: the first that matches.
_LICENCES = (
    (re.compile(r"open font licen[cs]e|\bOFL\b", re.IGNORECASE), "OFL-1.1"),
    (re.compile(r"apache licen[cs]e", re.IGNORECASE), "Apache-2.0"),
    (re.compile(r"ubuntu font licen[cs]e", re.IGNORECASE), "Ubuntu-font-1.0"),
    (re.compile(r"GUST font licen[cs]e", re.IGNORECASE), "LPPL-1.3c"),
)


class AddRefused(ValueError):
    """Fonts that cannot be added (or a collection that cannot be renamed or removed), and why."""


@dataclass(frozen=True)
class FileCheck:
    """What one file of an upload would become. ``code`` is empty for a plain addition; ``detail`` is what the words
    for the code need (the collection a font replaces, the fsType of one that forbids embedding)."""

    name: str
    verdict: Verdict
    code: str = ""
    detail: str = ""
    family: str | None = None
    style: str | None = None
    outlines: str | None = None
    licence: str = ""
    """The licence the font names (as an SPDX identifier), or empty."""
    data: bytes = b""

    def to_data(self) -> dict:
        """The line as plain data for a page, without the bytes."""
        return {
            "name": self.name,
            "verdict": self.verdict,
            "code": self.code,
            "detail": self.detail,
            "family": self.family,
            "style": self.style,
            "outlines": self.outlines,
            "licence": self.licence,
        }


def _base_name(name: str) -> str:
    """A file's own name without any folder, whichever separators its system used."""
    return PureWindowsPath(PurePosixPath(name).name).name


def _expanded(files: Iterable[tuple[str, bytes]]) -> list[tuple[str, bytes] | FileCheck]:
    """The files with every zip opened into its fonts; a zip that cannot be read is a line of its own."""
    out: list[tuple[str, bytes] | FileCheck] = []
    for raw_name, data in files:
        name = _base_name(raw_name)
        if not name.lower().endswith(".zip"):
            out.append((name, data))
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for member in archive.infolist():
                    inner = _base_name(member.filename)
                    if not member.is_dir() and Path(inner).suffix.lower() in FONT_SUFFIXES:
                        if member.file_size > MAX_BYTES:
                            raise AddRefused(f"{inner} in {name} is too large")
                        out.append((inner, archive.read(member)))
        except (zipfile.BadZipFile, EOFError, OSError) as error:
            out.append(FileCheck(name, "left-out", "not-a-zip", str(error)))
    return out


def _licence(data: bytes) -> str:
    try:
        text = TTFont(io.BytesIO(data), lazy=True)["name"].getDebugName(13) or ""
    except Exception:  # noqa: BLE001  # pragma: no cover - only a hint; read_font has read the font already
        return ""
    return next((spdx for pattern, spdx in _LICENCES if pattern.search(text)), "")


def _check_one(name: str, data: bytes, work: Path, catalogue: Catalogue, seen: dict[str, str]) -> FileCheck:
    if Path(name).suffix.lower() not in FONT_SUFFIXES:
        return FileCheck(name, "left-out", "not-a-font-file")
    path = work / f"{len(list(work.iterdir()))}{Path(name).suffix.lower()}"
    path.write_bytes(data)
    try:
        font = read_font(path, Collection(work, CollectionRecord("check", "check", redistributable=True)))
    except FontProblem as problem:
        return FileCheck(name, "left-out", problem.code, problem.detail, problem.family, problem.style)
    key = f"{font.family.casefold()}\n{font.style.casefold()}"
    if key in seen:
        return FileCheck(name, "left-out", "duplicate", seen[key], font.family, font.style, font.outlines)
    seen[key] = name
    found = [f for f in catalogue.fonts_of(font.family) if f.style.casefold() == font.style.casefold()]
    code, detail = ("replaces", found[0].collection) if found else ("", "")
    return FileCheck(name, "added", code, detail, font.family, font.style, font.outlines, _licence(data), data)


def check_files(files: Sequence[tuple[str, bytes]], catalogue: Catalogue) -> tuple[FileCheck, ...]:
    """A line for each font of ``files`` (``(name, bytes)``, a zip opened into its fonts), in order: what adding them
    to a server whose fonts are ``catalogue`` would do. Changes nothing. :class:`AddRefused` for more than
    :data:`~claudia_fonts.adding.MAX_FILES` fonts or :data:`~claudia_fonts.adding.MAX_BYTES` bytes."""
    expanded = _expanded(files)
    if len(expanded) > MAX_FILES:
        raise AddRefused(f"at most {MAX_FILES} fonts can be added at once")
    if sum(len(item[1]) for item in expanded if isinstance(item, tuple)) > MAX_BYTES:
        raise AddRefused(f"at most {MAX_BYTES // (1024 * 1024)} MB of fonts can be added at once")
    seen: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="claudia-fonts-check-") as work:
        return tuple(
            item if isinstance(item, FileCheck) else _check_one(*item, Path(work), catalogue, seen) for item in expanded
        )


def _slug(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:48] or "fonts"


def _free_folder(root: Path, name: str) -> Path:
    base = _slug(name)
    candidate, number = root / base, 1
    while candidate.exists():
        number += 1
        candidate = root / f"{base}-{number}"
    return candidate


def _required(value: str, what: str) -> str:
    if not value.strip():
        raise AddRefused(f"a collection needs a {what}")
    return value.strip()


def add_collection(
    root: str | Path,
    files: Sequence[tuple[str, bytes]],
    catalogue: Catalogue,
    *,
    name: str,
    licence: str,
    redistributable: bool,
    added_by: str,
    added: str,
) -> Path:
    """Add the fonts of ``files`` that :func:`~claudia_fonts.check_files` would add as a new collection under ``root``;
    its folder. :class:`AddRefused` if none would be added, or the name or the licence is blank."""
    record = CollectionRecord(
        name=_required(name, "name"),
        licence=_required(licence, "licence"),
        redistributable=redistributable,
        added_by=added_by,
        added=added,
    )
    usable = [check for check in check_files(files, catalogue) if check.verdict == "added"]
    if not usable:
        raise AddRefused("none of these files is a font this server can use")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    folder = _free_folder(root, record.name)
    staging = Path(tempfile.mkdtemp(prefix=f".{folder.name}-", dir=root))
    try:
        names: set[str] = set()
        for check in usable:
            stem, suffix = Path(check.name).stem, Path(check.name).suffix.lower()
            file_name, number = f"{stem}{suffix}", 1
            while file_name.casefold() in names or any(c in file_name for c in "*?"):
                number += 1
                file_name = f"{stem.replace('*', '_').replace('?', '_')}-{number}{suffix}"
            names.add(file_name.casefold())
            write_public(staging / file_name, check.data)
        record_bytes = (json.dumps(record.to_data(), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        write_public(staging / COLLECTION_FILE, record_bytes)
        staging.chmod(0o755)
        staging.rename(folder)  # the collection appears whole or not at all
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return folder


def rename_collection(folder: str | Path, name: str) -> None:
    """Give the collection in ``folder`` another name; its folder and everything else in its record stay."""
    folder = Path(folder)
    record = Collection.from_folder(folder).record
    renamed = CollectionRecord(
        name=_required(name, "name"),
        licence=record.licence,
        redistributable=record.redistributable,
        source=record.source,
        version=record.version,
        added_by=record.added_by,
        added=record.added,
    )
    text = json.dumps(renamed.to_data(), indent=2, ensure_ascii=False) + "\n"
    write_public(folder / COLLECTION_FILE, text.encode("utf-8"))


def remove_collection(root: str | Path, folder: str | Path) -> None:
    """Remove the collection in ``folder`` with its files. :class:`AddRefused` unless it is a collection directly
    under ``root`` (the server's own added collections)."""
    root, folder = Path(root).resolve(), Path(folder).resolve()
    if folder.parent != root or not (folder / COLLECTION_FILE).is_file():
        raise AddRefused("only a collection added through the server settings can be removed there")
    shutil.rmtree(folder)
