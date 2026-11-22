"""The document file (E2.1, E2.2, E2.3): one zip that holds the manifest, the key slots and the sealed list of people.

::

    format          "claudia-document 2", stored uncompressed and first, so tools can recognise the file
    manifest.json   readable by anyone: name, uid, description, tags, app, times, unlisted flag, the cost of the
                    password hashing, salt
    slots.json      the key slots (see :mod:`claudia_document_file.slots`): locators and sealed keys, no names
    people.bin      names, roles, slot locators and public keys of everybody; sealed with the content key (D102, D111)
    inbox/<l>.bin   new keys for the person whose slot locator is ``l``, sealed to her public key (D1274), until she
                    next logs in
    private/<id>/   a person's private notes: a chain of blocks and its head (D1265)

While a document is open its changes go to the journal next to the file (:mod:`claudia_document_file.journal`). Packing
the journal into encrypted blocks inside this zip is a later step. Every change of the file writes a new zip next to it
and replaces the old one atomically, so a crash leaves either the old or the new file, never a mixture.

A file may come from anybody. Before anything is read it is checked: format, number and names of entries, sizes and
compression ratios (:class:`ReaderLimitExceeded`), and the cost of the password hashing that it asks for.
"""

import base64
import binascii
import hmac
import io
import json
import os
import re
import threading
import unicodedata
import uuid
import zipfile
import zlib
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from claudia_file_writer import atomic_file

from . import blocks
from .audit import AuditRecord
from .blocks import (
    GENESIS,
    BlockError,
    Chain,
    Head,
    Place,
    block_hash,
    open_block,
    open_chain_head,
    open_head,
    seal_block,
    seal_chain_head,
    seal_head,
)
from .consent import ConsentRecord
from .crypto import (
    KEY_SIZE,
    DecryptionError,
    KdfParams,
    LoginMaterial,
    derive_login_material,
    derive_recovery_material,
    open_sealed,
    seal,
    warm_login_material,
)
from .inbox import PUBLIC_KEY_SIZE, new_key_pair, open_inbox, seal_to
from .journal import JournalWriter, journal_generation, read_journal
from .passwords import require_strong_password
from .slots import (
    ROLE_PARTS,
    KeySlot,
    Part,
    PrivateNotesKey,
    Role,
    Unlocked,
    make_slot,
    new_part_keys,
    new_private_notes_key,
    open_slot,
)

FORMAT_TEXT = "claudia-document 3"
FORMAT_VERSION = 3
"""Format 3 (E7.11): the file may hold the owners' consent (``consent/``). An older Claudia refuses a file of format 3
as a newer one; this one reads format 2 as it is (it has no consent) and writes 3 from the next change on."""
OLDEST_FORMAT = 2
"""The oldest format this version reads. A file of an older one is refused with a sentence (D1274: the slots and the
people list changed before there was a release, so nothing migrates them)."""
MAX_ENTRIES = 10_000
MAX_ENTRY_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_RATIO = 200
"""Largest allowed compression ratio of a larger entry. Encrypted data does not compress, so a high ratio is a bomb."""
_RATIO_FROM = 1024 * 1024

_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]*(/[a-z0-9][a-z0-9_.-]*)*")
_DOC_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_MAX_PERSON_NAME = 80
MAX_DESCRIPTION = 2000
"""Most characters of a document's description (Markdown, shown in the list to whoever may see the list)."""
MAX_TAGS = 10
"""Most tags a document has."""
MAX_TAG = 30
"""Most characters of one tag."""
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # all control characters but the line break and the tab
_CORE_ENTRIES = frozenset({"format", "manifest.json", "slots.json", "people.bin"})
_BLOCK_NAME = re.compile(r"(history|chat|audit)/(\d{6})\.blk")
_STREAMS = (Part.HISTORY.value, Part.CHAT.value, blocks.AUDIT)
"""The chains of blocks a file has: the history, the chat and the record of what left (D1271)."""
_HEAD = "head.bin"
_SNAPSHOT = "content/snapshot.bin"
_ORIGINAL = "content/original.bin"  # the file an imported document was made from, if it is kept (D439)
_RECOVERY_NAME = "(recovery)"
_INBOX = "inbox/"
_PRIVATE_ID = re.compile(r"[0-9a-f]{32}")
_WRITE_LOCK = threading.RLock()  # changes are rare; one at a time keeps read-modify-write simple and safe


class DocumentFileError(Exception):
    """The file cannot be used; the message says why."""


class NotAClaudiaDocument(DocumentFileError):
    """The file is not a Claudia document, or is damaged beyond reading."""


class UnsupportedFormat(DocumentFileError):
    """The file was written by a newer version of Claudia."""


class OutdatedFormat(UnsupportedFormat):
    """The file was written by an older version of Claudia than any that is read now."""


class TamperedDocument(DocumentFileError):
    """A block, the head or the journal does not fit the rest of the file: removed, changed, swapped, from another
    document or from another time."""


class ReaderLimitExceeded(DocumentFileError):
    """The file asks for more than a document may (too many entries, a zip bomb, names that leave a folder)."""


@dataclass(frozen=True)
class Manifest:
    """What anyone may read without a password (D103): enough to list the document, and to open it."""

    name: str
    uid: str
    app: str
    unlisted: bool
    created: str
    last_change: str
    kdf: KdfParams
    salt: bytes
    description: str = ""
    tags: tuple[str, ...] = ()

    @property
    def binding(self) -> str:
        """The name and the uid together, which the sealed parts of the document are bound to (D533). The manifest is
        plain, so anybody can change a field; with the binding a changed name or uid makes every slot, block and
        journal fail to open, and a file cannot be passed off under another uid."""
        return f"{self.name}:{self.uid}"

    def to_dict(self) -> dict[str, object]:
        """The manifest as plain data."""
        return {
            "format": FORMAT_VERSION,
            "name": self.name,
            "uid": self.uid,
            "app": self.app,
            "description": self.description,
            "tags": list(self.tags),
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
            known_format = data["format"] in range(OLDEST_FORMAT, FORMAT_VERSION + 1)  # type: ignore[index]
            if not known_format or data["ciphers"] != {"kdf": "argon2id", "aead": "aes-256-gcm"}:  # type: ignore[index]
                raise ValueError("unknown format or ciphers")
            manifest = cls(
                name=data["name"],  # type: ignore[index]
                uid=data["uid"],  # type: ignore[index]
                app=data["app"],  # type: ignore[index]
                unlisted=data["unlisted"],  # type: ignore[index]
                created=data["created"],  # type: ignore[index]
                last_change=data["last_change"],  # type: ignore[index]
                kdf=KdfParams.from_dict(data["kdf"]),  # type: ignore[index]
                salt=base64.b64decode(data["salt"], validate=True),  # type: ignore[index]
                description=data.get("description", ""),  # type: ignore[attr-defined]  # older files have none
                tags=_tuple_of(data.get("tags", [])),  # type: ignore[attr-defined]
            )
        except (KeyError, TypeError, AttributeError, binascii.Error) as error:
            raise ValueError(f"not a manifest: {error}") from error
        if not (
            isinstance(manifest.binding, str)
            and _DOC_ID.fullmatch(manifest.name)
            and is_uid(manifest.uid)
            and isinstance(manifest.app, str)
            and isinstance(manifest.description, str)
            and len(manifest.description) <= MAX_DESCRIPTION
            and _tags_fit(manifest.tags)
            and isinstance(manifest.unlisted, bool)
            and isinstance(manifest.created, str)
            and isinstance(manifest.last_change, str)
            and len(manifest.salt) >= 16
        ):
            raise ValueError("not a manifest: a field has the wrong form")
        return manifest


def is_uid(value: object) -> bool:
    """A uid as :func:`new_uid` makes it: a random (version 4) UUID in its canonical lower-case form."""
    if not isinstance(value, str):
        return False
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return str(parsed) == value and parsed.version == 4


def new_uid() -> str:
    """A new random document uid: a version 4 UUID from the system's random source, so it is not derived from the
    time, the name, the owner or the content (D533)."""
    return str(uuid.UUID(bytes=os.urandom(16), version=4))


def _tuple_of(value: object) -> tuple[str, ...]:
    """The tags of a manifest as a tuple; ``TypeError`` for anything but a list of strings."""
    if not isinstance(value, list) or not all(isinstance(tag, str) for tag in value):
        raise TypeError("the tags are not a list of strings")
    return tuple(value)


def _tags_fit(tags: tuple[str, ...]) -> bool:
    return len(tags) <= MAX_TAGS and all(len(tag) <= MAX_TAG for tag in tags)


def clean_details(description: str, tags: Sequence[str]) -> tuple[str, tuple[str, ...]]:
    """Tidy a description and tags before they go into a manifest, or ``ValueError`` with a sentence for the person.

    The description keeps its line breaks and loses other control characters; it is trimmed. A tag is trimmed, its
    inner white space becomes one space, and it is lower case, so "Finance" and "finance " are one tag; the same tag
    twice counts once and keeps its first place. A comma cannot be in a tag (it is what people type between tags), nor
    a control character."""
    text = _CONTROL.sub("", unicodedata.normalize("NFC", description).replace("\r\n", "\n").replace("\r", "\n")).strip()
    if len(text) > MAX_DESCRIPTION:
        raise ValueError(f"the description is longer than {MAX_DESCRIPTION} characters")
    cleaned: dict[str, None] = {}
    for raw in tags:
        if _CONTROL.search(raw) or "\n" in raw or "\t" in raw:
            raise ValueError("a tag cannot hold a control character")
        if "," in raw:
            raise ValueError("a tag cannot hold a comma: write each tag on its own")
        tag = " ".join(unicodedata.normalize("NFC", raw).split()).lower()
        if not tag:
            continue
        if len(tag) > MAX_TAG:
            raise ValueError(f"a tag has at most {MAX_TAG} characters")
        cleaned[tag] = None
    if len(cleaned) > MAX_TAGS:
        raise ValueError(f"a document has at most {MAX_TAGS} tags")
    return text, tuple(cleaned)


@dataclass(frozen=True)
class Person:
    """A user as the list of people shows it: name, role, the locator of the person's key slot, her public key (the
    inbox is sealed to it, D1274) and the id of her private notes (D1265), which only says that there are some."""

    name: str
    role: Role
    locator: bytes
    public_key: bytes = b""
    private_id: str | None = None


@dataclass(frozen=True)
class Recovery:
    """What the list of people knows of the recovery key: the locator of its slot and its public key (D105, D1274)."""

    locator: bytes
    public_key: bytes


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
    match = re.fullmatch(r"claudia-document (\d+)", declared)
    if match is None:
        raise NotAClaudiaDocument(f"{path.name} is not a Claudia document")
    version = int(match.group(1))
    if version > FORMAT_VERSION:
        raise UnsupportedFormat(f"{path.name} was written by a newer version of Claudia (format {version})")
    if version < OLDEST_FORMAT:
        raise OutdatedFormat(
            f"{path.name} was written by an older version of Claudia (format {version}), "
            "which this version cannot open: its keys are kept in another way"
        )
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
    """Log in. ``None`` for a wrong name or a wrong password: the same answer, whichever it was (D50, D102).

    A slot that is behind the document (keys were renewed, or the role changed, since the person was last here) is
    brought up to date from her inbox (D1274) and written, so she has the keys that the document has now."""
    entries = _read_entries(path)
    manifest = _manifest_of(entries, path)
    material = derive_login_material(password, name, manifest.salt, manifest.kdf)
    login = _resolve(entries, manifest, _slots_of(entries, path), material)
    if login is None:
        return None
    if login.slot is not None:
        _write_catch_up(path, material)
    return login.unlocked


def warm(path: Path, name: str, password: str) -> None:
    """Do the slow password hashing for ``name`` in this document now (SEC-21).

    Whatever ``unlock``, ``sealed_copy``, ``change_password``, ``add_user`` and the like do next with
    the same name and password takes the result instead of hashing again, once (see ``crypto.warm_login_material``). A
    server calls this in a worker thread and then runs the real call on its event loop, which must not stand still for
    the length of a hash. The file is only read; a file that cannot be read raises as ``read_manifest`` does.
    """
    manifest = read_manifest(path)
    warm_login_material(password, name, manifest.salt, manifest.kdf)


def sealed_copy(path: Path, name: str, password: str) -> bytes | None:
    """The document as a file for one person to keep (D110, D1270): the bytes of a complete, still sealed document.

    An owner gets the whole file. Anybody else gets the file with **only their own key slot** (and only their own
    private notes, and no inbox: new keys that are waiting for them are already in the slot), so nobody can attack the
    other people's passwords offline with it, and a viewer's file has only the parts the content key opens: the
    history, the chat and the head (sealed with keys a viewer does not hold) are left out; the snapshot stays. It opens
    with the same name and password, as a copy of its own and not as the live document.

    ``None`` for a wrong name or password, as :func:`unlock` (D50). The file at ``path`` is not changed. It holds what
    is in the blocks; a journal that has not been folded in yet is not part of it, so an open document is packed first.
    """
    entries = _read_entries(path)
    manifest = _manifest_of(entries, path)
    slots = _slots_of(entries, path)
    material = derive_login_material(password, name, manifest.salt, manifest.kdf)  # one hash: it is the slow part
    login = _resolve(entries, manifest, slots, material)
    if login is None:
        return None
    unlocked = login.unlocked
    kept = _with_login(slots, login, material.locator)
    others = _without_entry(_carried(entries), login.consumed)
    if unlocked.role is not Role.OWNER:
        kept = [slot for slot in kept if hmac.compare_digest(slot.locator, material.locator)]
        own = f"{blocks.PRIVATE}/{unlocked.private.id}/" if unlocked.private else None
        others = {
            n: data
            for n, data in others.items()
            if not n.startswith(_INBOX) and (not n.startswith(f"{blocks.PRIVATE}/") or (own and n.startswith(own)))
        }
    if Part.HISTORY not in unlocked.keys:
        others = {
            n: data for n, data in others.items() if n != _HEAD and not n.startswith(("history/", "chat/", "audit/"))
        }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        _fill_zip(archive, manifest, kept, entries["people.bin"], others)
    return buffer.getvalue()


def unlock_with_recovery(path: Path, recovery_key: bytes) -> Unlocked | None:
    """Open with the recovery key (D105): an owner with all keys, or ``None`` if it is not the document's key. A
    recovery slot that is behind the document is brought up to date from its inbox, as a person's is (D1274)."""
    entries = _read_entries(path)
    manifest = _manifest_of(entries, path)
    material = derive_recovery_material(recovery_key)
    login = _resolve(entries, manifest, _slots_of(entries, path), material)
    if login is None:
        return None
    if login.slot is not None:
        _write_catch_up(path, material)
    return login.unlocked


# --- logging in: a slot, and the letters waiting for it (D1274) ------------------------------------------------------


@dataclass(frozen=True)
class _Login:
    """A login: who got in, and, if her slot was behind the document, the slot as it should be and the inbox entry that
    it was made from."""

    unlocked: Unlocked
    slot: KeySlot | None = None
    consumed: str | None = None


def _inbox_name(locator: bytes) -> str:
    return f"{_INBOX}{locator.hex()}.bin"


def _inbox_aad(binding: str, locator: bytes) -> bytes:
    document = binding.encode()
    return b"claudia/inbox/1" + len(document).to_bytes(4, "big") + document + locator


def _letter(manifest: Manifest, locator: bytes, public_key: bytes, role: Role, keys: Mapping[Part, bytes]) -> bytes:
    """What the person with this slot locator and public key finds in her inbox: her role and the keys it holds."""
    held = {part.value: base64.b64encode(keys[part]).decode() for part in sorted(ROLE_PARTS[role])}
    payload = json.dumps({"role": role.value, "keys": held}).encode()
    return seal_to(public_key, payload, _inbox_aad(manifest.binding, locator))


def _resolve(
    entries: Mapping[str, bytes], manifest: Manifest, slots: Sequence[KeySlot], material: LoginMaterial
) -> _Login | None:
    """Open the slot of this login and, if there is a letter waiting for it that the document vouches for, take the
    keys and the role from the letter. ``None`` is a refusal, as in :func:`open_slot`.

    A letter that cannot be opened, was not written for this slot, does not agree with the list of people or has keys
    that open nothing is ignored: a forged letter must not be able to lock anybody out. The slot then stays as it is."""
    found = open_slot(slots, material, manifest.binding)
    if found is None:
        return None
    name = _inbox_name(material.locator)
    letter = entries.get(name)
    if letter is None or found.private_key is None:
        return _Login(found)
    try:
        data = json.loads(open_inbox(found.private_key, letter, _inbox_aad(manifest.binding, material.locator)))
        role = Role(data["role"])
        keys = {Part(part): base64.b64decode(key, validate=True) for part, key in data["keys"].items()}
    except (DecryptionError, ValueError, KeyError, TypeError, AttributeError):
        return _Login(found)
    if set(keys) != ROLE_PARTS[role] or any(len(key) != KEY_SIZE for key in keys.values()):
        return _Login(found)
    if not _document_vouches(entries, manifest, material.locator, role, keys):
        return _Login(found)
    slot = make_slot(
        material, manifest.binding, found.name, role, keys, private_key=found.private_key, private=found.private
    )
    return _Login(replace(found, role=role, keys=keys), slot, name)


def _document_vouches(
    entries: Mapping[str, bytes], manifest: Manifest, locator: bytes, role: Role, keys: Mapping[Part, bytes]
) -> bool:
    """Do these keys and this role fit the document? The content key opens the list of people, which has this slot with
    this role, and the history key opens the head."""
    try:
        people, recovery = _open_people_data(entries, manifest, keys)
    except (DocumentFileError, PermissionError):
        return False
    listed: Role | None
    if recovery is not None and recovery.locator == locator:
        listed = Role.OWNER
    else:
        listed = next((p.role for p in people if p.locator == locator), None)
    if listed is not role:
        return False
    if Part.HISTORY in keys:
        try:
            _head_of(entries, manifest, keys, blocks_exist=any(_block_names(entries).values()))
        except (TamperedDocument, PermissionError):
            return False
    return True


def _slot_for(
    material: LoginMaterial, manifest: Manifest, unlocked: Unlocked, role: Role, keys: Mapping[Part, bytes]
) -> KeySlot:
    """The slot of this person with ``role`` and ``keys``, keeping her own key pair and private notes."""
    return make_slot(
        material,
        manifest.binding,
        unlocked.name,
        role,
        keys,
        private_key=unlocked.private_key,
        private=unlocked.private,
    )


def _with_login(slots: Sequence[KeySlot], login: _Login, locator: bytes) -> list[KeySlot]:
    """``slots`` with the one at ``locator`` replaced by the caught-up slot of ``login``, if there is one."""
    if login.slot is None:
        return list(slots)
    return [login.slot if hmac.compare_digest(s.locator, locator) else s for s in slots]


def _without_entry(entries: Mapping[str, bytes], name: str | None) -> dict[str, bytes]:
    return {n: d for n, d in entries.items() if n != name}


def _write_catch_up(path: Path, material: LoginMaterial) -> None:
    """Write the slot of this login as it should be and delete the letter it was made from. The file is read again under
    the lock, so a change that came in between is not lost; if somebody else has caught the slot up meanwhile, nothing
    is written. The manifest stays as it is: this is not a change of the document."""
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        slots = _slots_of(entries, path)
        login = _resolve(entries, manifest, slots, material)
        if login is None or login.slot is None:
            return
        others = _without_entry(_carried(entries), login.consumed)
        _write_zip(
            path,
            manifest,
            _with_login(slots, login, material.locator),
            entries["people.bin"],
            others,
            exclusive=False,
        )


def _people_aad(binding: str) -> bytes:
    return b"claudia/people/1" + binding.encode()


def _open_people_data(
    entries: Mapping[str, bytes], manifest: Manifest, keys: Mapping[Part, bytes]
) -> tuple[list[Person], Recovery | None]:
    """The people and what is known of the recovery key (``None`` if there is none)."""
    key = keys.get(Part.CONTENT)
    if key is None:
        raise PermissionError("the list of people is sealed with the content key")
    try:
        data = json.loads(open_sealed(key, entries["people.bin"], _people_aad(manifest.binding)))
        people = [
            Person(
                item["name"],
                Role(item["role"]),
                base64.b64decode(item["locator"], validate=True),
                _public_key(item["public_key"]),
                _optional_private_id(item["private"]),
            )
            for item in data["people"]
        ]
        recovery = data["recovery"]
        found = None
        if recovery is not None:
            found = Recovery(base64.b64decode(recovery, validate=True), _public_key(data["recovery_public"]))
        return people, found
    except (DecryptionError, ValueError, KeyError, TypeError) as error:
        raise DocumentFileError("the list of people is damaged") from error


def _public_key(text: str) -> bytes:
    key = base64.b64decode(text, validate=True)
    if len(key) != PUBLIC_KEY_SIZE:
        raise ValueError("not a public key")
    return key


def _optional_private_id(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _PRIVATE_ID.fullmatch(value):
        raise ValueError("not the id of private notes")
    return value


def _open_people(entries: dict[str, bytes], manifest: Manifest, keys: Mapping[Part, bytes]) -> list[Person]:
    return _open_people_data(entries, manifest, keys)[0]


def read_people(path: Path, keys: Mapping[Part, bytes]) -> list[Person]:
    """Everybody who may log in, in the order they were added. Needs the content key (a viewer holds it, D111)."""
    entries = _read_entries(path)
    return _open_people(entries, _manifest_of(entries, path), keys)


# --- writing --------------------------------------------------------------------------------------------------------


def _people_blob(manifest: Manifest, content_key: bytes, people: list[Person], recovery: Recovery | None) -> bytes:
    data = {
        "people": [
            {
                "name": p.name,
                "role": p.role.value,
                "locator": base64.b64encode(p.locator).decode(),
                "public_key": base64.b64encode(p.public_key).decode(),
                "private": p.private_id,
            }
            for p in people
        ],
        "recovery": None if recovery is None else base64.b64encode(recovery.locator).decode(),
        "recovery_public": None if recovery is None else base64.b64encode(recovery.public_key).decode(),
    }
    return seal(content_key, json.dumps(data).encode(), _people_aad(manifest.binding))


def _carried(entries: Mapping[str, bytes]) -> dict[str, bytes]:
    """The entries that a change of the people leaves as they are: blocks, head and snapshot."""
    return {name: data for name, data in entries.items() if name not in _CORE_ENTRIES}


def _fill_zip(
    archive: zipfile.ZipFile,
    manifest: Manifest,
    slots: Sequence[KeySlot],
    people_blob: bytes,
    others: Mapping[str, bytes],
) -> None:
    """Put the entries of a document into ``archive``: the format name first, then the four that every document has,
    then ``others`` (the head, the blocks and the snapshot) in name order."""
    archive.writestr("format", FORMAT_TEXT, compress_type=zipfile.ZIP_STORED)
    archive.writestr("manifest.json", json.dumps(manifest.to_dict()), compress_type=zipfile.ZIP_DEFLATED)
    archive.writestr(
        "slots.json",
        json.dumps({"slots": [slot.to_dict() for slot in slots]}),
        compress_type=zipfile.ZIP_DEFLATED,
    )
    archive.writestr("people.bin", people_blob, compress_type=zipfile.ZIP_STORED)
    for name in sorted(others):
        archive.writestr(name, others[name], compress_type=zipfile.ZIP_STORED)


def _write_zip(
    path: Path,
    manifest: Manifest,
    slots: list[KeySlot],
    people_blob: bytes,
    others: Mapping[str, bytes],
    *,
    exclusive: bool,
) -> None:
    """Write the whole file next to the old one and replace it atomically. ``others`` are the entries besides the
    four that every document has: the head, the blocks and the snapshot."""
    if exclusive and path.exists():
        raise FileExistsError(path)
    with atomic_file(path, durable=True) as handle, zipfile.ZipFile(handle, "w") as archive:
        _fill_zip(archive, manifest, slots, people_blob, others)


def create_document(
    path: Path,
    *,
    name: str,
    app: str,
    owner: str,
    password: str,
    kdf: KdfParams | None = None,
    recovery_key: bytes | None = None,
    now: str | None = None,
    description: str = "",
    tags: Sequence[str] = (),
) -> Unlocked:
    """Make a new document file with one owner (and, if given, a recovery key). Returns the owner, unlocked.

    ``description`` and ``tags`` go into the manifest, which anyone may read
    (see :func:`~claudia_document_file.clean_details`).

    ``FileExistsError`` if the file exists, ``ValueError`` for an unacceptable id, name, description or tag,
    :class:`~claudia_document_file.passwords.WeakPassword` for a password that breaks the rules.
    """
    if not _DOC_ID.fullmatch(name):
        raise ValueError(f"{name!r} is not a valid document name")
    user = _check_name(owner)
    require_strong_password(password)
    params = kdf or KdfParams.default()
    stamp = now or _now()
    clean_description, clean_tags = clean_details(description, tags)
    manifest = Manifest(
        name,
        new_uid(),
        app,
        False,
        stamp,
        stamp,
        params,
        os.urandom(16),
        description=clean_description,
        tags=clean_tags,
    )
    keys = new_part_keys()
    material = derive_login_material(password, user, manifest.salt, params)
    pair, private = new_key_pair(), new_private_notes_key()
    slots = [make_slot(material, manifest.binding, user, Role.OWNER, keys, private_key=pair.private, private=private)]
    recovery = None
    if recovery_key is not None:
        recovery_material = derive_recovery_material(recovery_key)
        recovery_pair = new_key_pair()
        slots.append(
            make_slot(
                recovery_material, manifest.binding, _RECOVERY_NAME, Role.OWNER, keys, private_key=recovery_pair.private
            )
        )
        recovery = Recovery(recovery_material.locator, recovery_pair.public)
    person = Person(user, Role.OWNER, material.locator, pair.public, private.id)
    blob = _people_blob(manifest, keys[Part.CONTENT], [person], recovery)
    with _WRITE_LOCK:
        _write_zip(path, manifest, slots, blob, _private_entries(manifest.binding, private), exclusive=True)
    return Unlocked(user, Role.OWNER, keys, pair.private, private)


# --- a person's private notes (D1265) ---------------------------------------------------------------------------------


def _private_folder(private_id: str) -> str:
    return f"{blocks.PRIVATE}/{private_id}/"


def _private_entries(binding: str, private: PrivateNotesKey, payloads: Sequence[bytes] = ()) -> dict[str, bytes]:
    """The entries of private notes holding ``payloads``: their blocks and their head. Private notes that hold nothing
    still have one (empty) block, so that a file does not show who has something in it and who has not."""
    stream = f"{blocks.PRIVATE}/{private.id}"
    stored, end = _sealed_chain(private.key, binding, stream, [], payloads)
    if not stored:
        empty = seal_block(private.key, Place(binding, stream, 1, GENESIS), [])
        stored, end = {f"{stream}/000001.blk": empty}, Chain(1, block_hash(empty))
    stored[f"{stream}/head.bin"] = seal_chain_head(private.key, binding, stream, end)
    return stored


def _without_private(entries: Mapping[str, bytes], private_id: str | None) -> dict[str, bytes]:
    """``entries`` without the private notes with this id (they are gone from the file at the next write)."""
    if private_id is None:
        return dict(entries)
    folder = _private_folder(private_id)
    return {n: d for n, d in entries.items() if not n.startswith(folder)}


def _open_folder_chain(key: bytes, binding: str, stream: str, entries: Mapping[str, bytes]) -> list[bytes] | None:
    """The payloads of the chain ``stream`` that has a folder of its own and a head of its own (private notes, the
    consent), or ``None`` if the file has no head for it. :class:`TamperedDocument` if a block or the head does not
    fit."""
    folder = f"{stream}/"
    names = {n: d for n, d in entries.items() if n.startswith(folder)}
    head = names.get(f"{folder}head.bin")
    if head is None:
        if names:
            raise TamperedDocument(f"the {stream} has blocks but no head")
        return None
    try:
        end = open_chain_head(key, binding, stream, head)
        numbered = sorted(n for n in names if n != f"{folder}head.bin")
        if numbered != [f"{folder}{number:06d}.blk" for number in range(1, end.blocks + 1)]:
            raise BlockError(f"a block of the {stream} is missing or added")
        payloads, previous = [], GENESIS
        for number, name in enumerate(numbered, start=1):
            payloads.extend(open_block(key, Place(binding, stream, number, previous), names[name]))
            previous = block_hash(names[name])
        if previous != end.last:
            raise BlockError("the last block is not the one that the head names")
    except BlockError as error:
        raise TamperedDocument(f"the {stream} does not open: {error}") from error
    return payloads


def read_private(path: Path, private: PrivateNotesKey) -> list[bytes]:
    """What is in these private notes, in order. Whoever holds their key may read them, and nobody else: no role and no
    recovery key opens another person's private notes (D1265). :class:`TamperedDocument` if they are not in the file or
    a block or the head does not fit."""
    entries = _read_entries(path)
    binding = _manifest_of(entries, path).binding
    payloads = _open_folder_chain(private.key, binding, f"{blocks.PRIVATE}/{private.id}", entries)
    if payloads is None:
        raise TamperedDocument("these private notes are not in the file")
    return payloads


def write_private(path: Path, private: PrivateNotesKey, payloads: Sequence[bytes]) -> None:
    """Replace what is in these private notes by ``payloads``. The blocks and the head are made anew and the file is
    replaced atomically; nothing else in it changes, and no history and no journal is involved. What goes in is the
    business of E16.8; this round has the mechanism. :class:`TamperedDocument` if they are not in the file (private
    notes that were deleted cannot be written to again)."""
    with _WRITE_LOCK:
        read_private(path, private)  # it must be there, and must open
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        others = {
            **_without_private(_carried(entries), private.id),
            **_private_entries(manifest.binding, private, payloads),
        }
        _write_zip(path, manifest, _slots_of(entries, path), entries["people.bin"], others, exclusive=False)


def _changed(manifest: Manifest) -> Manifest:
    return replace(manifest, last_change=_now())


def _require_all_keys(keys: Mapping[Part, bytes]) -> None:
    if set(keys) != set(Part):
        raise PermissionError("only somebody who holds all the keys of the document may change who is in it")


def add_user(path: Path, keys: Mapping[Part, bytes], name: str, password: str, role: Role) -> Person:
    """Add a person, with a key pair and private notes of her own. ``keys`` are the document's keys (all three), so a
    viewer cannot do it (``PermissionError``).

    ``ValueError`` for a name that is unacceptable or already used (however it is written),
    :class:`~claudia_document_file.passwords.WeakPassword` for a weak password.
    """
    _require_all_keys(keys)
    clean = _check_name(name)
    require_strong_password(password)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        people, recovery = _open_people_data(entries, manifest, keys)
        if any(_normalised(p.name) == _normalised(clean) for p in people):
            raise ValueError(f"{clean!r} is already a person of this document")
        material = derive_login_material(password, clean, manifest.salt, manifest.kdf)
        pair, private = new_key_pair(), new_private_notes_key()
        person = Person(clean, role, material.locator, pair.public, private.id)
        slot = make_slot(material, manifest.binding, clean, role, keys, private_key=pair.private, private=private)
        blob = _people_blob(manifest, keys[Part.CONTENT], [*people, person], recovery)
        others = {**_carried(entries), **_private_entries(manifest.binding, private)}
        _write_zip(path, _changed(manifest), [*_slots_of(entries, path), slot], blob, others, exclusive=False)
    return person


def remove_user(path: Path, keys: Mapping[Part, bytes], name: str, *, allow_last: bool = False) -> None:
    """Remove a person from the list and the file, with her slot, her inbox and her private notes. **The keys she held
    are not renewed**: this is the plain removal; :func:`claudia_document_file.remove_person` renews them (D1263).
    ``KeyError`` if there is nobody of that name; ``ValueError`` for the last owner.

    ``allow_last`` is for somebody who holds the recovery key and replaces the owner.
    """
    _require_all_keys(keys)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        people, recovery = _open_people_data(entries, manifest, keys)
        target = next((p for p in people if _normalised(p.name) == _normalised(name)), None)
        if target is None:
            raise KeyError(name)
        others = [p for p in people if p is not target]
        if target.role is Role.OWNER and not allow_last and not any(p.role is Role.OWNER for p in others):
            raise ValueError("a document must keep at least one owner")
        slots = [s for s in _slots_of(entries, path) if s.locator != target.locator]
        blob = _people_blob(manifest, keys[Part.CONTENT], others, recovery)
        carried = _without_entry(_without_private(_carried(entries), target.private_id), _inbox_name(target.locator))
        _write_zip(path, _changed(manifest), slots, blob, carried, exclusive=False)


def change_password(path: Path, name: str, old_password: str, new_password: str) -> bool:
    """Give a person a new password. ``False`` if the old one is wrong; the keys, the key pair and the private notes
    stay the same, and what is waiting in her inbox is taken in first.

    :class:`~claudia_document_file.passwords.WeakPassword` if the new password breaks the rules.
    """
    require_strong_password(new_password)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        slots = _slots_of(entries, path)
        old = derive_login_material(old_password, name, manifest.salt, manifest.kdf)
        login = _resolve(entries, manifest, slots, old)
        if login is None:
            return False
        unlocked = login.unlocked
        fresh = derive_login_material(new_password, unlocked.name, manifest.salt, manifest.kdf)
        people, recovery = _open_people_data(entries, manifest, unlocked.keys)
        people = [replace(p, locator=fresh.locator) if p.locator == old.locator else p for p in people]
        replacement = make_slot(
            fresh,
            manifest.binding,
            unlocked.name,
            unlocked.role,
            unlocked.keys,
            private_key=unlocked.private_key,
            private=unlocked.private,
        )
        slots = [replacement if s.locator == old.locator else s for s in slots]
        blob = _people_blob(manifest, unlocked.keys[Part.CONTENT], people, recovery)
        others = _without_entry(_carried(entries), _inbox_name(old.locator))  # the letter was taken in, or is not one
        _write_zip(path, _changed(manifest), slots, blob, others, exclusive=False)
    return True


# --- leaving and handing over ownership (E2.3) -----------------------------------------------------------------


def leave_document(path: Path, name: str, password: str) -> bool:
    """``name`` removes themself, proving it with their own current password. Unlike :func:`remove_user` this
    needs none of the document's keys, so a viewer (who only ever holds the content key) can leave too. Her slot, her
    inbox and her private notes go with her. The keys are not renewed (she leaves of her own will, and holds what she
    has seen, D20).

    ``False`` if the password is wrong (or there is nobody of that name: the same refusal as elsewhere, D50).
    ``ValueError`` if ``name`` is the document's only owner: somebody else must become the owner first
    (:func:`transfer_owner`), or the document would be left without one.
    """
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        slots = _slots_of(entries, path)
        material = derive_login_material(password, name, manifest.salt, manifest.kdf)
        login = _resolve(entries, manifest, slots, material)
        if login is None:
            return False
        unlocked = login.unlocked
        people, recovery = _open_people_data(entries, manifest, unlocked.keys)
        target = next(p for p in people if p.locator == material.locator)
        others = [p for p in people if p is not target]
        if target.role is Role.OWNER and not any(p.role is Role.OWNER for p in others):
            raise ValueError("the document's only owner cannot leave; make somebody else the owner first")
        remaining_slots = [s for s in slots if s.locator != material.locator]
        blob = _people_blob(manifest, unlocked.keys[Part.CONTENT], others, recovery)
        carried = _without_entry(_without_private(_carried(entries), target.private_id), _inbox_name(target.locator))
        _write_zip(path, _changed(manifest), remaining_slots, blob, carried, exclusive=False)
    return True


def transfer_owner(
    path: Path, *, old_owner: str, old_owner_password: str, new_owner: str, new_owner_password: str
) -> bool:
    """Make ``new_owner`` (who must already be an editor) this document's owner, and ``old_owner`` an editor
    instead. Both must prove themselves with their own current password: a person's role lives inside their own
    password-sealed slot (D102), so changing it means resealing that slot, which takes the password that sealed
    it in the first place — nobody else's password will do, and the server never has either on its own. One
    atomic write, so the document is never left without an owner, or with ``new_owner`` as one before ``old_owner``
    has stopped being one. Each keeps her own key pair and private notes.

    ``False`` if either password is wrong — the same refusal whichever one it was, as elsewhere in this module.
    ``ValueError`` if ``old_owner`` is not currently the document's owner, ``new_owner`` is not currently an
    editor, or they are the same person; none of these depend on a password, so they are reported plainly.
    """
    if _normalised(old_owner) == _normalised(new_owner):
        raise ValueError("choose somebody else to become the new owner")
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        slots = _slots_of(entries, path)
        old_material = derive_login_material(old_owner_password, old_owner, manifest.salt, manifest.kdf)
        old_login = _resolve(entries, manifest, slots, old_material)
        if old_login is None:
            return False
        old_unlocked = old_login.unlocked
        if old_unlocked.role is not Role.OWNER:
            raise ValueError(f"{old_owner!r} is not the owner of this document")
        new_material = derive_login_material(new_owner_password, new_owner, manifest.salt, manifest.kdf)
        new_login = _resolve(entries, manifest, slots, new_material)
        if new_login is None:
            return False
        new_unlocked = new_login.unlocked
        if new_unlocked.role is not Role.EDITOR:
            raise ValueError(f"{new_owner!r} must already be an editor before becoming the owner")
        people, recovery = _open_people_data(entries, manifest, old_unlocked.keys)
        old_person = next(p for p in people if p.locator == old_material.locator)
        new_person = next(p for p in people if p.locator == new_material.locator)
        old_slot = _slot_for(old_material, manifest, old_unlocked, Role.EDITOR, old_unlocked.keys)
        new_slot = _slot_for(new_material, manifest, new_unlocked, Role.OWNER, old_unlocked.keys)
        slots = [
            old_slot if s.locator == old_material.locator else new_slot if s.locator == new_material.locator else s
            for s in slots
        ]
        people = [
            replace(old_person, role=Role.EDITOR)
            if p is old_person
            else replace(new_person, role=Role.OWNER)
            if p is new_person
            else p
            for p in people
        ]
        blob = _people_blob(manifest, old_unlocked.keys[Part.CONTENT], people, recovery)
        others = _without_entry(
            _without_entry(_carried(entries), _inbox_name(old_material.locator)), _inbox_name(new_material.locator)
        )
        _write_zip(path, _changed(manifest), slots, blob, others, exclusive=False)
    return True


def set_details(path: Path, keys: Mapping[Part, bytes], description: str, tags: Sequence[str]) -> None:
    """Give the document this description and these tags, which replace the ones it had. They are part of the
    manifest, which anyone who has the file may read without a password (D103): the owner chooses them knowing that.

    Needs all keys (``PermissionError``), as every change of the document itself does. ``ValueError`` for a description
    or tag that is not acceptable (see :func:`~claudia_document_file.clean_details`); nothing changes then."""
    _require_all_keys(keys)
    clean_description, clean_tags = clean_details(description, tags)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = replace(_manifest_of(entries, path), description=clean_description, tags=clean_tags)
        _write_zip(
            path,
            _changed(manifest),
            _slots_of(entries, path),
            entries["people.bin"],
            _carried(entries),
            exclusive=False,
        )


# --- the recovery key -----------------------------------------------------------------------------------------------


def has_recovery_key(path: Path, keys: Mapping[Part, bytes]) -> bool:
    """Does the document have a recovery slot? Needs the content key (the list of people says so)."""
    entries = _read_entries(path)
    return _open_people_data(entries, _manifest_of(entries, path), keys)[1] is not None


def set_recovery_key(path: Path, keys: Mapping[Part, bytes], recovery_key: bytes) -> None:
    """Give the document this recovery key, with a key pair of its own. A recovery key the document had before stops
    working (its slot and its inbox go).

    Needs all keys (``PermissionError``); ``ValueError`` if ``recovery_key`` is not 32 bytes."""
    _require_all_keys(keys)
    material = derive_recovery_material(recovery_key)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        people, old = _open_people_data(entries, manifest, keys)
        slots = [s for s in _slots_of(entries, path) if old is None or s.locator != old.locator]
        pair = new_key_pair()
        slots.append(make_slot(material, manifest.binding, _RECOVERY_NAME, Role.OWNER, keys, private_key=pair.private))
        blob = _people_blob(manifest, keys[Part.CONTENT], people, Recovery(material.locator, pair.public))
        carried = _carried(entries) if old is None else _without_entry(_carried(entries), _inbox_name(old.locator))
        _write_zip(path, _changed(manifest), slots, blob, carried, exclusive=False)


def recover_access(path: Path, recovery_key: bytes, name: str, new_password: str) -> Person | None:
    """Get back in with the recovery key: ``name`` gets ``new_password``, a **new key pair and new, empty private
    notes**. What was in her old private notes is gone with them: the recovery key never opened them (D1265).

    A person of the document keeps their role; somebody else becomes an owner. ``None`` if the key is not the document's
    recovery key (nothing changes); :class:`~claudia_document_file.passwords.WeakPassword` if the password breaks the
    rules (nothing changes)."""
    clean = _check_name(name)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        slots = _slots_of(entries, path)
        recovery_material = derive_recovery_material(recovery_key)
        login = _resolve(entries, manifest, slots, recovery_material)
        if login is None:
            return None
        opened = login.unlocked
        require_strong_password(new_password)
        people, recovery = _open_people_data(entries, manifest, opened.keys)
        target = next((p for p in people if _normalised(p.name) == _normalised(clean)), None)
        label = target.name if target else clean
        role = target.role if target else Role.OWNER
        material = derive_login_material(new_password, label, manifest.salt, manifest.kdf)
        pair, private = new_key_pair(), new_private_notes_key()
        fresh = make_slot(
            material, manifest.binding, label, role, opened.keys, private_key=pair.private, private=private
        )
        person = Person(label, role, material.locator, pair.public, private.id)
        slots = _with_login(slots, login, recovery_material.locator)
        if target is None:
            slots, people = [*slots, fresh], [*people, person]
            carried = _without_entry(_carried(entries), login.consumed)
        else:
            slots = [fresh if s.locator == target.locator else s for s in slots]
            people = [person if p is target else p for p in people]
            carried = _without_entry(
                _without_private(_without_entry(_carried(entries), login.consumed), target.private_id),
                _inbox_name(target.locator),
            )
        carried.update(_private_entries(manifest.binding, private))
        blob = _people_blob(manifest, opened.keys[Part.CONTENT], people, recovery)
        _write_zip(path, _changed(manifest), slots, blob, carried, exclusive=False)
    return person


# --- blocks, head and snapshot (E2.1, E2.5) -------------------------------------------------------------------------


@dataclass(frozen=True)
class State:
    """Everything an editor needs to bring a document up: the payloads of the history and the chat in order, the
    snapshot (a cache of the state, if there is one) and how many of the payloads are still only in the journal."""

    history: list[bytes]
    chat: list[bytes]
    snapshot: bytes | None
    pending: int


@dataclass(frozen=True)
class _Chains:
    head: Head
    stored: dict[str, list[bytes]]  # the blocks as they are in the file, per chain, in order
    opened: dict[str, list[list[bytes]]]  # their payloads


def _require_content_keys(keys: Mapping[Part, bytes]) -> None:
    if Part.HISTORY not in keys or Part.CHAT not in keys:
        raise PermissionError("the history and the chat are sealed with keys that this role does not hold")


def _block_names(entries: Mapping[str, bytes]) -> dict[str, dict[int, str]]:
    """The block entries of the file by chain and number. Anything else in the block folders is not ours."""
    found: dict[str, dict[int, str]] = {stream: {} for stream in _STREAMS}
    for name in entries:
        if not name.startswith(("history/", "chat/", "audit/")):
            continue
        match = _BLOCK_NAME.fullmatch(name)
        if match is None:
            raise TamperedDocument(f"{name} does not belong in the block folders")
        found[match.group(1)][int(match.group(2))] = name
    return found


def _head_of(
    entries: Mapping[str, bytes], manifest: Manifest, keys: Mapping[Part, bytes], *, blocks_exist: bool
) -> Head:
    stored = entries.get(_HEAD)
    if stored is None:
        if blocks_exist:
            raise TamperedDocument("the head of the document is missing although it has blocks")
        return Head.empty()
    history_key = keys.get(Part.HISTORY)
    if history_key is None:
        raise PermissionError("the head is sealed with the history key")
    try:
        return open_head(history_key, manifest.binding, stored)
    except BlockError as error:
        raise TamperedDocument(str(error)) from error


def _load_chains(entries: Mapping[str, bytes], manifest: Manifest, keys: Mapping[Part, bytes]) -> _Chains:
    """Open every block and check them against the head: count, order, chain and the hash of the last one."""
    _require_content_keys(keys)
    names = _block_names(entries)
    head = _head_of(entries, manifest, keys, blocks_exist=any(names.values()))
    stored: dict[str, list[bytes]] = {}
    opened: dict[str, list[list[bytes]]] = {}
    for stream in _STREAMS:
        key = keys[Part.HISTORY if stream == blocks.AUDIT else Part(stream)]
        numbers = sorted(names[stream])
        if numbers != list(range(1, len(numbers) + 1)):
            raise TamperedDocument(f"a block of the {stream} is missing")
        expected = head.chain(stream)
        if len(numbers) != expected.blocks:
            raise TamperedDocument(f"the file has {len(numbers)} {stream} blocks but its head says {expected.blocks}")
        previous, stored[stream], opened[stream] = GENESIS, [], []
        for number in numbers:
            data = entries[names[stream][number]]
            try:
                payloads = open_block(key, Place(manifest.binding, stream, number, previous), data)
            except BlockError as error:
                raise TamperedDocument(f"{names[stream][number]}: {error}") from error
            stored[stream].append(data)
            opened[stream].append(payloads)
            previous = block_hash(data)
        if previous != expected.last:
            raise TamperedDocument(f"the last {stream} block is not the one that the head names")
    return _Chains(head, stored, opened)


def _snapshot_of(entries: Mapping[str, bytes], manifest: Manifest, keys: Mapping[Part, bytes]) -> bytes | None:
    key, stored = keys.get(Part.CONTENT), entries.get(_SNAPSHOT)
    if key is None or stored is None:
        return None
    try:
        return open_sealed(key, stored, _snapshot_aad(manifest.binding))
    except DecryptionError:
        return None  # a cache that cannot be trusted is no cache; the history still has everything


def _snapshot_aad(binding: str) -> bytes:
    return b"claudia/snapshot/1" + binding.encode()


def read_snapshot(path: Path, keys: Mapping[Part, bytes]) -> bytes | None:
    """The snapshot, if the file has one that opens with the content key (a viewer holds it). ``None`` otherwise."""
    entries = _read_entries(path)
    return _snapshot_of(entries, _manifest_of(entries, path), keys)


# --- the record of what left the document (E2.9, D1271) ---------------------------------------------------------------


def read_audit(path: Path, keys: Mapping[Part, bytes]) -> list[AuditRecord]:
    """Everything that is recorded as having left the document, oldest first. Needs the history key
    (``PermissionError`` for a viewer, who does not see the record, D1261).

    :class:`TamperedDocument` if a block of the record is missing, changed or from elsewhere."""
    _require_content_keys(keys)
    entries = _read_entries(path)
    chains = _load_chains(entries, _manifest_of(entries, path), keys)
    return [AuditRecord.from_bytes(payload) for block in chains.opened[blocks.AUDIT] for payload in block]


def record_audit(path: Path, keys: Mapping[Part, bytes], record: AuditRecord) -> None:
    """Add ``record`` to the record of what left the document and write the file. It is not a command: no revision, no
    undo step, and the journal is not touched. Needs all keys (``PermissionError``): the server records for the person
    who acts, a viewer too, with the keys it holds for the open document.

    ``ValueError`` if the record is not a sound one (see :meth:`AuditRecord.check`); nothing changes then."""
    payload = record.to_bytes()
    _require_all_keys(keys)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        chains = _load_chains(entries, manifest, keys)
        audit_blocks, end = _extend(keys[Part.HISTORY], manifest.binding, blocks.AUDIT, chains, [payload])
        head = replace(chains.head, audit=end)
        replaced = {n for n in entries if n == _HEAD or n.startswith(f"{blocks.AUDIT}/")}
        others = {
            **{n: d for n, d in _carried(entries).items() if n not in replaced},
            **audit_blocks,
            _HEAD: seal_head(keys[Part.HISTORY], manifest.binding, head),
        }
        _write_zip(path, _changed(manifest), _slots_of(entries, path), entries["people.bin"], others, exclusive=False)


# --- the owners' consent to a remote AI provider (E7.11, D264) -----------------------------------------------------


def _consent_entries(key: bytes, binding: str, payloads: Sequence[bytes]) -> dict[str, bytes]:
    stored, end = _sealed_chain(key, binding, blocks.CONSENT, [], payloads)
    stored[f"{blocks.CONSENT}/head.bin"] = seal_chain_head(key, binding, blocks.CONSENT, end)
    return stored


def _consent_payloads(entries: Mapping[str, bytes], manifest: Manifest, keys: Mapping[Part, bytes]) -> list[bytes]:
    key = keys.get(Part.CONTENT)
    if key is None:
        raise PermissionError("the consent is sealed with the content key")
    return _open_folder_chain(key, manifest.binding, blocks.CONSENT, entries) or []


def read_consent(path: Path, keys: Mapping[Part, bytes]) -> list[ConsentRecord]:
    """Every decision of the owners about a remote AI provider, oldest first; none if nobody ever decided (which means
    *not allowed*). Needs the content key, so a viewer reads it too.

    :class:`TamperedDocument` if a block or the head of the list is missing, changed or from elsewhere."""
    entries = _read_entries(path)
    payloads = _consent_payloads(entries, _manifest_of(entries, path), keys)
    return [ConsentRecord.from_bytes(payload) for payload in payloads]


def record_consent(path: Path, keys: Mapping[Part, bytes], record: ConsentRecord) -> None:
    """Add ``record`` to the owners' consent and write the file. It is not a command: no revision, no undo step, and the
    journal is not touched. Needs the content key (``PermissionError``); that only an owner may do it is the server's
    rule (see :mod:`consent`).

    ``ValueError`` if the record is not a sound one; nothing changes then."""
    payload = record.to_bytes()
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        payloads = [*_consent_payloads(entries, manifest, keys), payload]
        others = {
            **{n: d for n, d in _carried(entries).items() if not n.startswith(f"{blocks.CONSENT}/")},
            **_consent_entries(keys[Part.CONTENT], manifest.binding, payloads),
        }
        _write_zip(path, _changed(manifest), _slots_of(entries, path), entries["people.bin"], others, exclusive=False)


# --- the original of an imported document (D439) ----------------------------------------------------------------------
def _original_aad(binding: str) -> bytes:
    return b"claudia/original/1" + binding.encode()


def write_original(path: Path, keys: Mapping[Part, bytes], data: bytes) -> None:
    """Keep ``data``, the file this document was imported from, sealed with the content key in the document file
    (``content/original.bin``), replacing one kept before. Every later change of the file carries it along. Needs all
    three keys, as every write of the file does."""
    _require_all_keys(keys)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        others = {**_carried(entries), _ORIGINAL: seal(keys[Part.CONTENT], data, _original_aad(manifest.binding))}
        _write_zip(path, _changed(manifest), _slots_of(entries, path), entries["people.bin"], others, exclusive=False)


def read_original(path: Path, keys: Mapping[Part, bytes]) -> bytes | None:
    """The file this document was imported from, if it is kept; ``None`` if not. Whoever holds the content key may
    read it (a viewer too). :class:`TamperedDocument` if the entry does not open: it was changed, or it belongs to
    another document."""
    key = keys.get(Part.CONTENT)
    if key is None:
        raise ValueError("reading the original needs the content key")
    entries = _read_entries(path)
    stored = entries.get(_ORIGINAL)
    if stored is None:
        return None
    try:
        return open_sealed(key, stored, _original_aad(_manifest_of(entries, path).binding))
    except DecryptionError as error:
        raise TamperedDocument("the kept original does not belong to this document or was changed") from error


def _journal_records(
    path: Path, manifest: Manifest, keys: Mapping[Part, bytes], head: Head
) -> tuple[list[bytes], list[bytes]]:
    """The history and chat payloads of the journal if it follows the file; none if the file has already taken them."""
    journal = journal_path(path)
    if not journal.exists():
        return [], []
    generation = journal_generation(journal)
    if generation <= head.generation:
        return [], []  # a crash came between the new file and the new journal: the file has these records already
    if generation > head.generation + 1:
        raise TamperedDocument("the journal does not follow the document file: blocks or the head were taken out")
    history, chat = [], []
    for record in read_journal(journal, manifest.binding, keys):
        if record.part is Part.HISTORY:
            history.append(record.payload)
        elif record.part is Part.CHAT:
            chat.append(record.payload)
    return history, chat


def read_state(path: Path, keys: Mapping[Part, bytes]) -> State:
    """The history, the chat and the snapshot of the document: the blocks of the file (checked against the head) and the
    journal that follows them. Needs all keys (``PermissionError``).

    :class:`TamperedDocument` if blocks, head or journal do not fit together,
    :class:`~claudia_document_file.journal.JournalError` if the journal is damaged."""
    entries = _read_entries(path)
    manifest = _manifest_of(entries, path)
    chains = _load_chains(entries, manifest, keys)
    history = [payload for block in chains.opened[Part.HISTORY] for payload in block]
    chat = [payload for block in chains.opened[Part.CHAT] for payload in block]
    more_history, more_chat = _journal_records(path, manifest, keys, chains.head)
    return State(
        [*history, *more_history],
        [*chat, *more_chat],
        _snapshot_of(entries, manifest, keys),
        len(more_history) + len(more_chat),
    )


def begin(path: Path, keys: Mapping[Part, bytes]) -> JournalWriter:
    """A writer for the journal of an open document: the existing one is continued (a cut-off last record is removed),
    one that the file has already taken in is replaced by the next, and a missing one is made."""
    _require_content_keys(keys)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        head = _head_of(entries, manifest, keys, blocks_exist=any(_block_names(entries).values()))
        journal, wanted = journal_path(path), head.generation + 1
        if not journal.exists():
            return JournalWriter.create(journal, manifest.binding, keys, wanted)
        generation = journal_generation(journal)
        if generation == wanted:
            return JournalWriter.open(journal, manifest.binding, keys)
        if generation < wanted:
            return JournalWriter.replace(journal, manifest.binding, keys, wanted)
        raise TamperedDocument("the journal does not follow the document file: blocks or the head were taken out")


def _chunks(payloads: Sequence[bytes]) -> Iterator[list[bytes]]:
    """The payloads in runs that each reach the block size (the last run may be smaller)."""
    run, size = [], 0
    for payload in payloads:
        run.append(payload)
        size += len(payload)
        if size >= blocks.BLOCK_TARGET_BYTES:
            yield run
            run, size = [], 0
    if run:
        yield run


def _extend(
    key: bytes, binding: str, stream: str, chains: _Chains, payloads: Sequence[bytes]
) -> tuple[dict[str, bytes], Chain]:
    """The blocks of ``stream`` after ``payloads`` were added: the last block is filled up if it is small, new blocks
    follow. Returns the block entries and the new end of the chain."""
    stored = list(chains.stored[stream])
    payloads = list(payloads)
    if payloads and stored:
        last = chains.opened[stream][-1]
        if sum(len(p) for p in last) < blocks.BLOCK_TARGET_BYTES:
            stored.pop()
            payloads = [*last, *payloads]
    return _sealed_chain(key, binding, stream, stored, payloads)


def _sealed_chain(
    key: bytes, binding: str, stream: str, stored: list[bytes], payloads: Sequence[bytes]
) -> tuple[dict[str, bytes], Chain]:
    """``stored`` blocks followed by new blocks sealed from ``payloads``: the block entries and the end of the chain."""
    previous = block_hash(stored[-1]) if stored else GENESIS
    for run in _chunks(payloads):
        data = seal_block(key, Place(binding, stream, len(stored) + 1, previous), run)
        stored.append(data)
        previous = block_hash(data)
    entries = {f"{stream}/{number:06d}.blk": data for number, data in enumerate(stored, start=1)}
    return entries, Chain(len(stored), previous)


type _Folding = Callable[[_Chains, Manifest, Part], tuple[dict[str, bytes], Chain]]
"""How the blocks of one part are made from the chains in the file: continued (packing) or made anew (rewriting).
The record of what left (D1271) is not folded: every write that makes the blocks carries it through unchanged."""


def _write_blocks(
    path: Path, keys: Mapping[Part, bytes], fold: _Folding, *, snapshot: bytes | None, generation: int
) -> None:
    """Make the blocks of both parts with ``fold``, write the new head and snapshot, and replace the file
    atomically. Every block entry of the old file is left behind. The journal is not touched."""
    _require_all_keys(keys)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        chains = _load_chains(entries, manifest, keys)
        if generation <= chains.head.generation:
            raise ValueError(f"journal generation {generation} is already in the file")
        history_blocks, history_end = fold(chains, manifest, Part.HISTORY)
        chat_blocks, chat_end = fold(chains, manifest, Part.CHAT)
        audit_blocks = {f"{blocks.AUDIT}/{n:06d}.blk": data for n, data in enumerate(chains.stored[blocks.AUDIT], 1)}
        head = Head(generation, history_end, chat_end, chains.head.audit)
        replaced = (_HEAD, _SNAPSHOT)
        kept = {n: d for n, d in _carried(entries).items() if n not in replaced and not _BLOCK_NAME.fullmatch(n)}
        packed = {
            **kept,
            **history_blocks,
            **chat_blocks,
            **audit_blocks,
            _HEAD: seal_head(keys[Part.HISTORY], manifest.binding, head),
        }
        if snapshot is not None:
            packed[_SNAPSHOT] = seal(keys[Part.CONTENT], snapshot, _snapshot_aad(manifest.binding))
        people_blob = entries["people.bin"]
        _write_zip(path, _changed(manifest), _slots_of(entries, path), people_blob, packed, exclusive=False)


def _pack_blocks(
    path: Path,
    keys: Mapping[Part, bytes],
    *,
    history: Sequence[bytes],
    chat: Sequence[bytes],
    snapshot: bytes | None,
    generation: int,
) -> None:
    """Fold the records of journal ``generation`` into the blocks, write the new head and snapshot, and replace the
    file atomically. The journal is not touched."""
    added = {Part.HISTORY: history, Part.CHAT: chat}

    def extend(chains: _Chains, manifest: Manifest, part: Part) -> tuple[dict[str, bytes], Chain]:
        return _extend(keys[part], manifest.binding, part, chains, added[part])

    _write_blocks(path, keys, extend, snapshot=snapshot, generation=generation)


def pack_journal(
    path: Path, keys: Mapping[Part, bytes], writer: JournalWriter, snapshot: bytes | None = None
) -> JournalWriter:
    """Fold the journal into the document file and go on with a fresh journal.

    Returns the writer of the fresh journal (``writer`` is closed).

    The file is replaced first and the journal second. A crash between the two leaves a journal whose records the file
    already holds; :func:`read_state` ignores it and :func:`begin` replaces it. ``snapshot`` becomes the snapshot of the
    file (``None`` removes it). If folding into the file fails, ``writer`` is still the open journal and nothing has
    changed. Once the file holds the records, ``writer`` is closed before the journal itself is replaced (on Windows,
    replacing a file that is still open is refused); if that replace then fails, the file already has the records, so
    the next :func:`begin` repeats it and nothing is lost."""
    journal = journal_path(path)
    manifest = read_manifest(path)
    history, chat = [], []
    for record in read_journal(journal, manifest.binding, keys):
        if record.part is Part.HISTORY:
            history.append(record.payload)
        elif record.part is Part.CHAT:
            chat.append(record.payload)
    _pack_blocks(path, keys, history=history, chat=chat, snapshot=snapshot, generation=writer.generation)
    generation = writer.generation
    writer.close()
    return JournalWriter.replace(journal, manifest.binding, keys, generation + 1)


def rewrite_journal(
    path: Path,
    keys: Mapping[Part, bytes],
    writer: JournalWriter,
    *,
    history: Sequence[bytes],
    chat: Sequence[bytes],
    snapshot: bytes | None = None,
) -> JournalWriter:
    """Replace everything the document has held so far by ``history`` and ``chat`` (redaction, D725, SEC-05).

    The blocks of the file are made anew from these payloads alone — none of the old blocks is carried over — and the
    journal, whose records ``history`` and ``chat`` supersede, is replaced by an empty one. Afterwards neither file
    holds a byte of what was there before: what was redacted is gone from the document folder (copies and backups made
    earlier keep it, D21). Same order and same crash safety as :func:`pack_journal`: the file first, then the journal; a
    crash in between leaves a journal the file has superseded, which :func:`read_state` ignores and :func:`begin`
    replaces. Returns the writer of the fresh journal (``writer`` is closed). ``snapshot`` becomes the snapshot of the
    file; ``None`` leaves it without one, since a snapshot taken before the redaction holds the content."""
    payloads = {Part.HISTORY: history, Part.CHAT: chat}

    def anew(_chains: _Chains, manifest: Manifest, part: Part) -> tuple[dict[str, bytes], Chain]:
        return _sealed_chain(keys[part], manifest.binding, part, [], payloads[part])

    _write_blocks(path, keys, anew, snapshot=snapshot, generation=writer.generation)
    generation = writer.generation
    writer.close()
    return JournalWriter.replace(journal_path(path), read_manifest(path).binding, keys, generation + 1)


def forget_original(path: Path, keys: Mapping[Part, bytes]) -> None:
    """Remove the kept original of an imported document (``content/original.bin``, D439), if there is one: its
    content was redacted (D723). Needs all three keys, as every write of the file does."""
    _require_all_keys(keys)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        if _ORIGINAL not in entries:
            return
        manifest = _manifest_of(entries, path)
        others = {name: data for name, data in _carried(entries).items() if name != _ORIGINAL}
        _write_zip(path, _changed(manifest), _slots_of(entries, path), entries["people.bin"], others, exclusive=False)
