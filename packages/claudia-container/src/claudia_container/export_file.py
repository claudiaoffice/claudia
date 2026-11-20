"""The unencrypted export (E2.9, D1270, D1272): a documented zip anybody can read, which comes back in as a document.

::

    format        "claudia-export 2", stored uncompressed and first, so tools can recognise the file
    export.json   what the file is: the app, the schema of the state, who exported it and when, and the SHA-256 and
                  size of every other part (integrity of the file, not its authenticity: anybody can write one)
    content.json  the state of the document, as the app's own ``serialize()`` gives it
    history.jsonl the history, one change per line, hidden side lines included      } only if an owner exported them
    chat.jsonl    the chat, one message per line                                    }

There are no key slots, no password hashes, no list of people and no manifest: whoever has the file can read what it
holds and nothing else. The reader is for a file from anybody: it checks the listing before it inflates anything and
refuses names, sizes and compression ratios that no export has (:class:`ExportRefused`).
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
import zlib
from dataclasses import dataclass

from .container import ContainerError

FORMAT_TEXT = "claudia-export 2"
FORMAT_VERSION = 2
MAX_PART_BYTES = 256 * 1024 * 1024
"""Largest a part may be once inflated. A hostile file cannot make the reader hold more than this per part."""
MAX_RATIO = 200
_RATIO_FROM = 1024 * 1024
_PARTS = ("content.json", "history.jsonl", "chat.jsonl")
_MAX_INFO_BYTES = 64 * 1024


class ExportRefused(ContainerError):
    """The file is not an export this version reads; the message is a sentence for the person."""


@dataclass(frozen=True)
class ExportFile:
    """What an export holds. ``history`` and ``chat`` are ``None`` when the exporter did not include them."""

    app: str
    state_schema: int
    state: dict
    exporter: str
    exported_at: str
    history: list[bytes] | None = None
    chat: list[bytes] | None = None


def _lines(payloads: list[bytes], what: str) -> bytes:
    for number, payload in enumerate(payloads, start=1):
        if b"\n" in payload or b"\r" in payload:
            raise ValueError(f"{what} {number} has a line break, so it cannot be one line")
        try:
            json.loads(payload)
        except ValueError as error:
            raise ValueError(f"{what} {number} is not JSON") from error
    return b"".join(payload + b"\n" for payload in payloads)


def write_export(
    app: str,
    state_schema: int,
    state: dict,
    *,
    exporter: str,
    exported_at: str,
    history: list[bytes] | None = None,
    chat: list[bytes] | None = None,
) -> bytes:
    """The bytes of an export. ``ValueError`` for a history or chat entry that is not one line of JSON, or an empty
    exporter or time."""
    if not exporter or not exported_at:
        raise ValueError("an export says who made it and when")
    parts = {"content.json": json.dumps(state, separators=(",", ":"), ensure_ascii=False).encode()}
    if history is not None:
        parts["history.jsonl"] = _lines(history, "history")
    if chat is not None:
        parts["chat.jsonl"] = _lines(chat, "chat")
    info = {
        "format": FORMAT_TEXT,
        "app": app,
        "state_schema": state_schema,
        "exporter": exporter,
        "exported_at": exported_at,
        "parts": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)} for name, data in parts.items()
        },
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("format", FORMAT_TEXT, compress_type=zipfile.ZIP_STORED)
        header = json.dumps(info, indent=2, ensure_ascii=False)
        archive.writestr("export.json", header, compress_type=zipfile.ZIP_DEFLATED)
        for name, data in parts.items():
            archive.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def is_export(data: bytes) -> bool:
    """Does ``data`` look like an export? By its first entry alone, the way a Claudia document is recognised."""
    if not data.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if not infos or infos[0].filename != "format" or infos[0].file_size > 64:
                return False
            return archive.read(infos[0]).startswith(b"claudia-export ")
    except (zipfile.BadZipFile, OSError, ValueError, EOFError):
        return False


def _inflate(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int) -> bytes:
    with archive.open(info) as handle:
        data = handle.read(limit + 1)
    if len(data) > limit or len(data) != info.file_size:
        raise ExportRefused(f"{info.filename} is too large or does not have the size it claims")
    return data


def _check_listing(infos: list[zipfile.ZipInfo]) -> None:
    if not infos or infos[0].filename != "format":
        raise ExportRefused("this is not a Claudia export")
    allowed = {"format", "export.json", *_PARTS}
    names = [info.filename for info in infos]
    if len(set(names)) != len(names):
        raise ExportRefused("the file has entries with the same name")
    for info in infos:
        if info.filename not in allowed:
            raise ExportRefused(f"the file has an entry that no export has: {info.filename[:40]!r}")
        bomb = info.file_size > _RATIO_FROM and info.file_size > MAX_RATIO * max(info.compress_size, 1)
        if info.file_size > MAX_PART_BYTES or bomb:
            raise ExportRefused(f"{info.filename} is too large or compresses suspiciously well")


def read_export(data: bytes) -> ExportFile:
    """Read an export. :class:`ExportRefused` with a sentence for anything that is not a sound one: another kind of
    file, a newer version, a part that does not fit ``export.json``, a part that is too large, a state that is not
    JSON."""
    if not is_export(data):
        raise ExportRefused("this is not a Claudia export")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError, ValueError) as error:  # pragma: no cover - is_export opened it already
        raise ExportRefused("this is not a Claudia export") from error
    with archive:
        infos = archive.infolist()
        try:
            _check_listing(infos)
            declared = archive.read(infos[0]).decode("utf-8", "replace")
            if declared != FORMAT_TEXT:
                match = re.fullmatch(r"claudia-export (\d+)", declared)
                if match and int(match.group(1)) > FORMAT_VERSION:
                    raise ExportRefused("this export was written by a newer version of Claudia")
                raise ExportRefused("this is not a Claudia export this version can read")
            by_name = {info.filename: info for info in infos}
            if "export.json" not in by_name or "content.json" not in by_name:
                raise ExportRefused("the export is damaged: export.json or content.json is missing")
            info = _info(_inflate(archive, by_name["export.json"], _MAX_INFO_BYTES))
            return _assemble(archive, by_name, info)
        except (zipfile.BadZipFile, OSError, EOFError, zlib.error) as error:
            raise ExportRefused("the export is damaged") from error


def _info(raw: bytes) -> dict:
    try:
        info = json.loads(raw)
        parts = info["parts"]
        valid = (
            info["format"] == FORMAT_TEXT
            and isinstance(info["app"], str)
            and isinstance(info["state_schema"], int)
            and isinstance(info["exporter"], str)
            and isinstance(info["exported_at"], str)
            and isinstance(parts, dict)
            and set(parts) <= set(_PARTS)
            and all(isinstance(p, dict) and isinstance(p.get("sha256"), str) for p in parts.values())
        )
    except (ValueError, KeyError, TypeError) as error:
        raise ExportRefused(f"export.json cannot be read: {error}") from error
    if not valid or "content.json" not in parts:
        raise ExportRefused("export.json is not what an export has")
    return info


def _assemble(archive: zipfile.ZipFile, by_name: dict[str, zipfile.ZipInfo], info: dict) -> ExportFile:
    named, present = set(info["parts"]), {name for name in by_name if name in _PARTS}
    if named != present:
        odd = sorted(named ^ present)[0]
        raise ExportRefused(f"{odd} is not in the file and in export.json alike")
    raw: dict[str, bytes] = {}
    for name in _PARTS:
        if name in by_name:
            raw[name] = _inflate(archive, by_name[name], MAX_PART_BYTES)
            if hashlib.sha256(raw[name]).hexdigest() != info["parts"][name]["sha256"]:
                raise ExportRefused(f"{name} is not what export.json says: it was changed")
    try:
        state = json.loads(raw["content.json"])
    except ValueError as error:
        raise ExportRefused("content.json is not JSON") from error
    if not isinstance(state, dict):
        raise ExportRefused("content.json is not a state")
    return ExportFile(
        info["app"],
        info["state_schema"],
        state,
        info["exporter"],
        info["exported_at"],
        _split(raw.get("history.jsonl"), "history.jsonl"),
        _split(raw.get("chat.jsonl"), "chat.jsonl"),
    )


def _split(raw: bytes | None, name: str) -> list[bytes] | None:
    if raw is None:
        return None
    lines = raw.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    for number, line in enumerate(lines, start=1):
        try:
            json.loads(line)
        except ValueError as error:
            raise ExportRefused(f"line {number} of {name} is not JSON") from error
    return lines
