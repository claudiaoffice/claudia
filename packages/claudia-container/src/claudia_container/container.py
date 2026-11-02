"""The document file (E2.1, E2.2, E2.3): one zip that holds the manifest, the key slots and the sealed list of people.

::

    format          "claudia-document 1", stored uncompressed and first, so tools can recognise the file
    manifest.json   readable by anyone: id, title, app, times, unlisted flag, the cost of the password hashing, salt
    slots.json      the key slots (see :mod:`claudia_container.slots`): locators and sealed keys, no names
    people.bin      names, roles and slot locators of everybody; sealed with the content key (D72, D81)

While a document is open its changes go to the journal next to the file (:mod:`claudia_container.journal`). Packing the
journal into encrypted blocks inside this zip is a later step. Every change of the file writes a new zip next to it and
replaces the old one atomically, so a crash leaves either the old or the new file, never a mixture.

A file may come from anybody. Before anything is read it is checked: format, number and names of entries, sizes and
compression ratios (:class:`ReaderLimitExceeded`), and the cost of the password hashing that it asks for.
"""

import base64
import binascii
import contextlib
import json
import os
import re
import threading
import unicodedata
import zipfile
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .crypto import DecryptionError, KdfParams, derive_login_material, derive_recovery_material, open_sealed, seal
from .journal import _fsync_directory
from .passwords import require_strong_password
from .slots import Domain, KeySlot, Role, Unlocked, make_slot, new_domain_keys, open_slot

FORMAT_TEXT = "claudia-document 1"
FORMAT_VERSION = 1
MAX_ENTRIES = 10_000
MAX_ENTRY_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_RATIO = 200
"""Largest allowed compression ratio of a larger entry. Encrypted data does not compress, so a high ratio is a bomb."""
_RATIO_FROM = 1024 * 1024

_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]*(/[a-z0-9][a-z0-9_.-]*)*")
_DOC_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_MAX_PERSON_NAME = 80
_WRITE_LOCK = threading.RLock()  # changes are rare; one at a time keeps read-modify-write simple and safe


class ContainerError(Exception):
    """The file cannot be used; the message says why."""


class NotAClaudiaDocument(ContainerError):
    """The file is not a Claudia document, or is damaged beyond reading."""


class UnsupportedFormat(ContainerError):
    """The file was written by a newer version of Claudia."""


class ReaderLimitExceeded(ContainerError):
    """The file asks for more than a document may (too many entries, a zip bomb, names that leave a folder)."""


@dataclass(frozen=True)
class Manifest:
    """What anyone may read without a password (D73): enough to list the document, and to open it."""

    id: str
    app: str
    title: str
    unlisted: bool
    created: str
    last_change: str
    kdf: KdfParams
    salt: bytes

    def to_dict(self) -> dict[str, object]:
        """The manifest as plain data."""
        return {
            "format": FORMAT_VERSION,
            "id": self.id,
            "app": self.app,
            "title": self.title,
            "unlisted": self.unlisted,
            "created": self.created,
            "last_change": self.last_change,
            "kdf": self.kdf.to_dict(),
            "salt": base64.b64encode(self.salt).decode(),
            "ciphers": {"kdf": "argon2id", "aead": "aes-256-gcm"},
        }

    @classmethod
    def from_dict(cls, data: object) -> Manifest:
        """Read a manifest; ``ValueError`` if it is not a sound one."""
        try:
            if data["format"] != FORMAT_VERSION or data["ciphers"] != {"kdf": "argon2id", "aead": "aes-256-gcm"}:  # type: ignore[index]
                raise ValueError("unknown format or ciphers")
            manifest = cls(
                id=data["id"],  # type: ignore[index]
                app=data["app"],  # type: ignore[index]
                title=data["title"],  # type: ignore[index]
                unlisted=data["unlisted"],  # type: ignore[index]
                created=data["created"],  # type: ignore[index]
                last_change=data["last_change"],  # type: ignore[index]
                kdf=KdfParams.from_dict(data["kdf"]),  # type: ignore[index]
                salt=base64.b64decode(data["salt"], validate=True),  # type: ignore[index]
            )
        except (KeyError, TypeError, binascii.Error) as error:
            raise ValueError(f"not a manifest: {error}") from error
        if not (
            isinstance(manifest.id, str)
            and _DOC_ID.fullmatch(manifest.id)
            and isinstance(manifest.app, str)
            and isinstance(manifest.title, str)
            and len(manifest.title) <= 200
            and isinstance(manifest.unlisted, bool)
            and isinstance(manifest.created, str)
            and isinstance(manifest.last_change, str)
            and len(manifest.salt) >= 16
        ):
            raise ValueError("not a manifest: a field has the wrong form")
        return manifest


@dataclass(frozen=True)
class Person:
    """A user as the list of people shows it: name, role, and the locator of the person's key slot."""

    name: str
    role: Role
    locator: bytes


def journal_path(path: Path) -> Path:
    """Where the journal of the document file at ``path`` lives."""
    return path.with_name(path.name + ".journal")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _normalised(name: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", name).casefold().split())


def _check_name(name: str) -> str:
    text = " ".join(unicodedata.normalize("NFKC", name).split())
    if not text or len(text) > _MAX_PERSON_NAME or any(unicodedata.category(c).startswith("C") for c in text):
        raise ValueError(f"a name has 1 to {_MAX_PERSON_NAME} characters and no control characters")
    return text


# --- reading ------------------------------------------------------------------------------------------------------


def _read_entries(path: Path) -> dict[str, bytes]:
    """Every entry of the zip, after all the checks of a file that may come from outside."""
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError, ValueError) as error:
        if isinstance(error, FileNotFoundError):
            raise
        raise NotAClaudiaDocument(f"{path.name} is not a Claudia document") from error
    with archive:
        infos = archive.infolist()
        _check_listing(path, infos)
        try:
            entries = {}
            for info in infos:
                with archive.open(info) as handle:
                    data = handle.read(info.file_size + 1)  # a lie about the size must not make us read on
                if len(data) != info.file_size:
                    raise ReaderLimitExceeded(f"the entry {info.filename} does not have the size it claims")
                entries[info.filename] = data
        except (zipfile.BadZipFile, OSError, EOFError, zlib.error) as error:
            raise NotAClaudiaDocument(f"{path.name} is damaged") from error
    _check_format(path, entries)
    return entries


def _check_listing(path: Path, infos: list[zipfile.ZipInfo]) -> None:
    """The limits that can be checked from the list of entries alone, before anything is read."""
    if len(infos) > MAX_ENTRIES:
        raise ReaderLimitExceeded(f"the file has more than {MAX_ENTRIES} entries")
    names = [info.filename for info in infos]
    if len(set(names)) != len(names):
        raise ReaderLimitExceeded("the file has entries with the same name")
    total = 0
    for info in infos:
        if len(info.filename) > 100 or not _NAME.fullmatch(info.filename):
            raise ReaderLimitExceeded(f"the file has an entry with an unacceptable name: {info.filename[:40]!r}")
        total += info.file_size
        too_big = info.file_size > MAX_ENTRY_BYTES or total > MAX_TOTAL_BYTES
        bomb = info.file_size > _RATIO_FROM and info.file_size > MAX_RATIO * max(info.compress_size, 1)
        if too_big or bomb:
            raise ReaderLimitExceeded(f"the entry {info.filename} is too large or compresses suspiciously well")
    if not infos or infos[0].filename != "format":
        raise NotAClaudiaDocument(f"{path.name} is not a Claudia document")


def _check_format(path: Path, entries: dict[str, bytes]) -> None:
    """The format line says this is a document of a version we can read, and the required entries are there."""
    declared = entries["format"].decode("utf-8", "replace")
    if declared != FORMAT_TEXT:
        match = re.fullmatch(r"claudia-document (\d+)", declared)
        if match and int(match.group(1)) > FORMAT_VERSION:
            raise UnsupportedFormat(f"{path.name} was written by a newer version of Claudia (format {match.group(1)})")
        raise NotAClaudiaDocument(f"{path.name} is not a Claudia document")
    for required in ("manifest.json", "slots.json", "people.bin"):
        if required not in entries:
            raise NotAClaudiaDocument(f"{path.name} is damaged: {required} is missing")


def _manifest_of(entries: dict[str, bytes], path: Path) -> Manifest:
    try:
        return Manifest.from_dict(json.loads(entries["manifest.json"]))
    except ValueError as error:  # (also json.JSONDecodeError)
        raise NotAClaudiaDocument(f"{path.name} has a damaged manifest: {error}") from error


def _slots_of(entries: dict[str, bytes], path: Path) -> list[KeySlot]:
    try:
        return [KeySlot.from_dict(item) for item in json.loads(entries["slots.json"])["slots"]]
    except (ValueError, KeyError, TypeError) as error:
        raise NotAClaudiaDocument(f"{path.name} has damaged key slots: {error}") from error


def read_manifest(path: Path) -> Manifest:
    """The manifest of the file: no password needed.

    Raises :class:`NotAClaudiaDocument`, :class:`UnsupportedFormat` or :class:`ReaderLimitExceeded`."""
    return _manifest_of(_read_entries(path), path)


def unlock(path: Path, name: str, password: str) -> Unlocked | None:
    """Log in. ``None`` for a wrong name or a wrong password: the same answer, whichever it was (D50, D72)."""
    entries = _read_entries(path)
    manifest = _manifest_of(entries, path)
    material = derive_login_material(password, name, manifest.salt, manifest.kdf)
    return open_slot(_slots_of(entries, path), material, manifest.id)


def unlock_with_recovery(path: Path, recovery_key: bytes) -> Unlocked | None:
    """Open with the recovery key (D75): an owner with all keys, or ``None`` if it is not the document's key."""
    entries = _read_entries(path)
    manifest = _manifest_of(entries, path)
    return open_slot(_slots_of(entries, path), derive_recovery_material(recovery_key), manifest.id)


def _people_aad(doc_id: str) -> bytes:
    return b"claudia/people/1" + doc_id.encode()


def _open_people(entries: dict[str, bytes], manifest: Manifest, keys: Mapping[Domain, bytes]) -> list[Person]:
    key = keys.get(Domain.CONTENT)
    if key is None:
        raise PermissionError("the list of people is sealed with the content key")
    try:
        data = json.loads(open_sealed(key, entries["people.bin"], _people_aad(manifest.id)))
        return [
            Person(item["name"], Role(item["role"]), base64.b64decode(item["locator"], validate=True))
            for item in data["people"]
        ]
    except (DecryptionError, ValueError, KeyError, TypeError) as error:
        raise ContainerError("the list of people is damaged") from error


def read_people(path: Path, keys: Mapping[Domain, bytes]) -> list[Person]:
    """Everybody who may log in, in the order they were added. Needs the content key (a viewer holds it, D81)."""
    entries = _read_entries(path)
    return _open_people(entries, _manifest_of(entries, path), keys)


# --- writing --------------------------------------------------------------------------------------------------------


def _people_blob(manifest: Manifest, content_key: bytes, people: list[Person]) -> bytes:
    data = {
        "people": [
            {"name": p.name, "role": p.role.value, "locator": base64.b64encode(p.locator).decode()} for p in people
        ]
    }
    return seal(content_key, json.dumps(data).encode(), _people_aad(manifest.id))


def _write_zip(path: Path, manifest: Manifest, slots: list[KeySlot], people_blob: bytes, *, exclusive: bool) -> None:
    """Write the whole file next to the old one and replace it atomically."""
    if exclusive and path.exists():
        raise FileExistsError(path)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            with zipfile.ZipFile(handle, "w") as archive:
                archive.writestr("format", FORMAT_TEXT, compress_type=zipfile.ZIP_STORED)
                archive.writestr("manifest.json", json.dumps(manifest.to_dict()), compress_type=zipfile.ZIP_DEFLATED)
                archive.writestr(
                    "slots.json",
                    json.dumps({"slots": [slot.to_dict() for slot in slots]}),
                    compress_type=zipfile.ZIP_DEFLATED,
                )
                archive.writestr("people.bin", people_blob, compress_type=zipfile.ZIP_STORED)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        _fsync_directory(path.parent)
    except BaseException:
        with contextlib.suppress(OSError):
            temp.unlink()
        raise


def create_document(
    path: Path,
    *,
    doc_id: str,
    app: str,
    title: str,
    owner: str,
    password: str,
    kdf: KdfParams | None = None,
    recovery_key: bytes | None = None,
    now: str | None = None,
) -> Unlocked:
    """Make a new document file with one owner (and, if given, a recovery key). Returns the owner, unlocked.

    ``FileExistsError`` if the file exists, ``ValueError`` for an unacceptable id or name,
    :class:`~claudia_container.passwords.WeakPassword` for a password that breaks the rules.
    """
    if not _DOC_ID.fullmatch(doc_id):
        raise ValueError(f"{doc_id!r} is not a valid document id")
    name = _check_name(owner)
    require_strong_password(password)
    params = kdf or KdfParams.default()
    stamp = now or _now()
    manifest = Manifest(doc_id, app, title, False, stamp, stamp, params, os.urandom(16))
    keys = new_domain_keys()
    material = derive_login_material(password, name, manifest.salt, params)
    slots = [make_slot(material, doc_id, name, Role.OWNER, keys)]
    if recovery_key is not None:
        slots.append(make_slot(derive_recovery_material(recovery_key), doc_id, "(recovery)", Role.OWNER, keys))
    person = Person(name, Role.OWNER, material.locator)
    with _WRITE_LOCK:
        _write_zip(path, manifest, slots, _people_blob(manifest, keys[Domain.CONTENT], [person]), exclusive=True)
    return Unlocked(name, Role.OWNER, keys)


def _changed(manifest: Manifest) -> Manifest:
    return Manifest(
        manifest.id,
        manifest.app,
        manifest.title,
        manifest.unlisted,
        manifest.created,
        _now(),
        manifest.kdf,
        manifest.salt,
    )


def _require_all_keys(keys: Mapping[Domain, bytes]) -> None:
    if set(keys) != set(Domain):
        raise PermissionError("only somebody who holds all the keys of the document may change who is in it")


def add_user(path: Path, keys: Mapping[Domain, bytes], name: str, password: str, role: Role) -> Person:
    """Add a person. ``keys`` are the document's keys (all three), so a viewer cannot do it (``PermissionError``).

    ``ValueError`` for a name that is unacceptable or already used (however it is written),
    :class:`~claudia_container.passwords.WeakPassword` for a weak password.
    """
    _require_all_keys(keys)
    clean = _check_name(name)
    require_strong_password(password)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        people = _open_people(entries, manifest, keys)
        if any(_normalised(p.name) == _normalised(clean) for p in people):
            raise ValueError(f"{clean!r} is already a person of this document")
        material = derive_login_material(password, clean, manifest.salt, manifest.kdf)
        person = Person(clean, role, material.locator)
        slots = [*_slots_of(entries, path), make_slot(material, manifest.id, clean, role, keys)]
        blob = _people_blob(manifest, keys[Domain.CONTENT], [*people, person])
        _write_zip(path, _changed(manifest), slots, blob, exclusive=False)
    return person


def remove_user(path: Path, keys: Mapping[Domain, bytes], name: str, *, allow_last: bool = False) -> None:
    """Remove a person. ``KeyError`` if there is nobody of that name; ``ValueError`` for the last owner.

    ``allow_last`` is for somebody who holds the recovery key and replaces the owner.
    """
    _require_all_keys(keys)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        people = _open_people(entries, manifest, keys)
        target = next((p for p in people if _normalised(p.name) == _normalised(name)), None)
        if target is None:
            raise KeyError(name)
        others = [p for p in people if p is not target]
        if target.role is Role.OWNER and not allow_last and not any(p.role is Role.OWNER for p in others):
            raise ValueError("a document must keep at least one owner")
        slots = [s for s in _slots_of(entries, path) if s.locator != target.locator]
        blob = _people_blob(manifest, keys[Domain.CONTENT], others)
        _write_zip(path, _changed(manifest), slots, blob, exclusive=False)


def change_password(path: Path, name: str, old_password: str, new_password: str) -> bool:
    """Give a person a new password. ``False`` if the old one is wrong; the keys stay the same.

    :class:`~claudia_container.passwords.WeakPassword` if the new password breaks the rules.
    """
    require_strong_password(new_password)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        slots = _slots_of(entries, path)
        old = derive_login_material(old_password, name, manifest.salt, manifest.kdf)
        unlocked = open_slot(slots, old, manifest.id)
        if unlocked is None:
            return False
        fresh = derive_login_material(new_password, unlocked.name, manifest.salt, manifest.kdf)
        people = _open_people(entries, manifest, unlocked.keys)
        people = [Person(p.name, p.role, fresh.locator) if p.locator == old.locator else p for p in people]
        replacement = make_slot(fresh, manifest.id, unlocked.name, unlocked.role, unlocked.keys)
        slots = [replacement if s.locator == old.locator else s for s in slots]
        blob = _people_blob(manifest, unlocked.keys[Domain.CONTENT], people)
        _write_zip(path, _changed(manifest), slots, blob, exclusive=False)
    return True
