"""Key slots (E2.2, D101, D102, D105): who may open which part of a document.

A document has three **domain keys** (content, history, chat). Every user has one **slot**: the domain keys that the
user's role may hold, encrypted with a key derived from that user's name and password. The slot is found by its
**locator**, a value derived from the same name and password, so the file shows neither names nor roles.

* owner and editor hold all three keys; a viewer holds the content key only (D101);
* a slot is bound to its document and to its own locator, so it cannot be moved to another document or swapped with
  another slot to change somebody's role;
* a wrong name and a wrong password are the same refusal (``None``), as D50 demands.
"""

import base64
import binascii
import hmac
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from .crypto import (
    KEY_SIZE,
    LOCATOR_SIZE,
    NONCE_SIZE,
    TAG_SIZE,
    DecryptionError,
    LoginMaterial,
    open_sealed,
    random_key,
    seal,
)


class Role(StrEnum):
    """What a person may do in a document (D35). The role decides which domain keys the person's slot holds."""

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class Domain(StrEnum):
    """The separately encrypted parts of a document: the current content, the command history and the chat."""

    CONTENT = "content"
    HISTORY = "history"
    CHAT = "chat"


ROLE_DOMAINS: Mapping[Role, frozenset[Domain]] = MappingProxyType(
    {
        Role.OWNER: frozenset(Domain),
        Role.EDITOR: frozenset(Domain),
        Role.VIEWER: frozenset({Domain.CONTENT}),
    }
)
"""Which domain keys each role holds."""


class InvalidRecoveryKey(ValueError):
    """A typed recovery key is not a valid one (wrong length or characters)."""


@dataclass(frozen=True)
class KeySlot:
    """One slot as stored in the file: a locator and the sealed payload. No name and no role appear in the clear."""

    locator: bytes
    sealed: bytes

    def to_dict(self) -> dict[str, str]:
        """The slot as plain data (base64) for the file."""
        return {"locator": base64.b64encode(self.locator).decode(), "sealed": base64.b64encode(self.sealed).decode()}

    @classmethod
    def from_dict(cls, data: object) -> KeySlot:
        """Read a slot from the file; raise ``ValueError`` if it is not one."""
        try:
            locator = base64.b64decode(data["locator"], validate=True)  # type: ignore[index]
            sealed = base64.b64decode(data["sealed"], validate=True)  # type: ignore[index]
        except (KeyError, TypeError, binascii.Error) as error:
            raise ValueError(f"not a key slot: {error}") from error
        if len(locator) != LOCATOR_SIZE or len(sealed) < NONCE_SIZE + TAG_SIZE:
            raise ValueError("not a key slot: wrong sizes")
        return cls(locator, sealed)


@dataclass(frozen=True)
class Unlocked:
    """What a successful login yields: who it is, the role, and the domain keys that role holds."""

    name: str
    role: Role
    keys: dict[Domain, bytes] = field(repr=False)  # secrets: never in a log line or a traceback


def new_domain_keys() -> dict[Domain, bytes]:
    """Fresh random keys for a new document, one per domain."""
    return {domain: random_key() for domain in Domain}


def _slot_aad(doc_id: str, locator: bytes) -> bytes:
    document = doc_id.encode()
    return b"claudia/slot/1" + len(document).to_bytes(4, "big") + document + locator


def make_slot(material: LoginMaterial, doc_id: str, name: str, role: Role, keys: Mapping[Domain, bytes]) -> KeySlot:
    """Make the slot for ``name`` with ``role``. Only the domain keys of that role are put into it."""
    allowed = ROLE_DOMAINS[role]
    for domain in sorted(allowed):
        if domain not in keys:
            raise ValueError(f"the {role} role needs the {domain} key")
        if len(keys[domain]) != KEY_SIZE:
            raise ValueError(f"a key must be {KEY_SIZE} bytes")
    payload = {
        "name": name,
        "role": role.value,
        "keys": {domain.value: base64.b64encode(keys[domain]).decode() for domain in sorted(allowed)},
    }
    sealed = seal(material.key, json.dumps(payload).encode(), _slot_aad(doc_id, material.locator))
    return KeySlot(material.locator, sealed)


def open_slot(slots: Sequence[KeySlot], material: LoginMaterial, doc_id: str) -> Unlocked | None:
    """Find and open the slot that belongs to this login. ``None`` means refused, whatever the reason.

    Every locator is compared in constant time and the whole list is always walked, so the answer takes the same
    time whichever slot matches or none does.
    """
    found: KeySlot | None = None
    for slot in slots:
        if hmac.compare_digest(slot.locator, material.locator):
            found = slot
    if found is None:
        return None
    try:
        payload = json.loads(open_sealed(material.key, found.sealed, _slot_aad(doc_id, found.locator)))
    except DecryptionError:
        return None
    try:
        return Unlocked(
            name=payload["name"],
            role=Role(payload["role"]),
            keys={Domain(domain): base64.b64decode(key, validate=True) for domain, key in payload["keys"].items()},
        )
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        # Authentic but malformed: not a wrong password. Whoever wrote it knew the key, so this is a bug, not an attack.
        raise ValueError(f"the key slot is authentic but malformed: {error}") from error


# --- the recovery key (D105) -------------------------------------------------------------------------------------

_RECOVERY_CHARS = 52  # 256 bits in base32
_GROUP = 4


def new_recovery_key() -> bytes:
    """A fresh recovery key: 256 random bits. It is shown to the owner once and never stored."""
    return random_key()


def format_recovery_key(key: bytes) -> str:
    """The key as it is written down: 13 groups of 4 capital letters and digits, separated by dashes."""
    if len(key) != KEY_SIZE:
        raise ValueError(f"a key must be {KEY_SIZE} bytes")
    text = base64.b32encode(key).decode().rstrip("=")
    return "-".join(text[i : i + _GROUP] for i in range(0, len(text), _GROUP))


def parse_recovery_key(text: str) -> bytes:
    """Read a typed recovery key in any style; raise :class:`InvalidRecoveryKey` if it is not one.

    Small letters, spaces instead of dashes and surrounding blanks are fine.
    """
    cleaned = "".join(text.split()).replace("-", "").upper()
    if len(cleaned) != _RECOVERY_CHARS:
        raise InvalidRecoveryKey("a recovery key has 52 letters and digits")
    try:
        key = base64.b32decode(cleaned + "====")
    except binascii.Error as error:
        raise InvalidRecoveryKey("a recovery key has only the letters A to Z and the digits 2 to 7") from error
    if base64.b32encode(key).decode().rstrip("=") != cleaned:  # the last character must be exactly what we would write
        raise InvalidRecoveryKey("this is not a valid recovery key")
    return key
