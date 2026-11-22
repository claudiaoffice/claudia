"""The cryptographic primitives of Claudia documents, behind a small interface (D104).

Nothing here is invented: passwords become keys with **Argon2id**, one secret becomes several unrelated keys with
**HKDF-SHA256**, and data is encrypted with **AES-256-GCM** (the `cryptography` package does the work). This module only
fixes the sizes, the labels and the rules around them, so the rest of Claudia never touches a primitive directly and an
algorithm can be replaced in one place.

A *login* is turned into two values (D102): a **locator**, which says which key slot belongs to this name and password
without the file ever containing the name, and a **key-encryption key**, which opens that slot. Both are derived from
the name *and* the password, so a wrong name and a wrong password are the same refusal.
"""

import hashlib
import hmac
import os
import threading
import time
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_SIZE = 32
"""Bytes in every key: AES-256."""
NONCE_SIZE = 12
"""Bytes of the random nonce put in front of every sealed value."""
TAG_SIZE = 16
"""Bytes of the authentication tag at the end of every sealed value."""
LOCATOR_SIZE = 16
"""Bytes of a slot locator."""

MAX_ITERATIONS = 20
MAX_LANES = 16
MAX_MEMORY_KIB = 1_048_576
"""Largest memory cost a file may ask for (1 GiB): a file from outside must not be able to exhaust the server."""

_MIN_SALT = 8  # Argon2's own minimum
_MIN_KIB_PER_LANE = 8  # Argon2's own minimum


class DecryptionError(Exception):
    """A sealed value could not be opened: wrong key, wrong authenticated data, or damaged bytes (never says which)."""


@dataclass(frozen=True)
class KdfParams:
    """The cost of turning a password into a key. They are written into the document's manifest (D103).

    A document keeps the cost it was made with. Every person's slot is sealed with a key derived from their own name and
    password, so raising the cost of an existing document would need each person's password, one at a time, and
    nothing does that: a new cost applies to the documents made after it (D1267). Values read from a file are checked
    against limits so that a hostile file cannot demand absurd amounts of memory or time.
    """

    iterations: int
    memory_kib: int
    lanes: int

    def __post_init__(self) -> None:
        for name in ("iterations", "memory_kib", "lanes"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"invalid KDF parameters: {name} must be a whole number")
        if not 1 <= self.iterations <= MAX_ITERATIONS:
            raise ValueError(f"invalid KDF parameters: iterations must be 1 to {MAX_ITERATIONS}")
        if not 1 <= self.lanes <= MAX_LANES:
            raise ValueError(f"invalid KDF parameters: lanes must be 1 to {MAX_LANES}")
        if not _MIN_KIB_PER_LANE * self.lanes <= self.memory_kib <= MAX_MEMORY_KIB:
            raise ValueError(
                f"invalid KDF parameters: memory_kib must be {_MIN_KIB_PER_LANE * self.lanes} to {MAX_MEMORY_KIB}"
            )

    @classmethod
    def default(cls) -> KdfParams:
        """The cost for new documents: 3 passes over 64 MiB with 4 lanes (about 0.4 seconds on a current laptop)."""
        return cls(iterations=3, memory_kib=65536, lanes=4)

    def to_dict(self) -> dict[str, int]:
        """The parameters as plain data for the manifest."""
        return {"iterations": self.iterations, "memory_kib": self.memory_kib, "lanes": self.lanes}

    @classmethod
    def from_dict(cls, data: object) -> KdfParams:
        """Read parameters from a manifest; raise ``ValueError`` if they are missing, mistyped or out of bounds."""
        try:
            return cls(iterations=data["iterations"], memory_kib=data["memory_kib"], lanes=data["lanes"])  # type: ignore[index]
        except (KeyError, TypeError) as error:
            raise ValueError("invalid KDF parameters: iterations, memory_kib and lanes are required") from error


@dataclass(frozen=True)
class LoginMaterial:
    """What a login or a recovery key yields: which slot to look at, and the key that opens it."""

    locator: bytes
    key: bytes = field(repr=False)  # a secret: never in a log line or a traceback


def random_key() -> bytes:
    """A fresh random 256-bit key."""
    return os.urandom(KEY_SIZE)


def hkdf_sha256(ikm: bytes, *, info: bytes, length: int, salt: bytes | None = None) -> bytes:
    """HKDF (RFC 5869) with SHA-256: ``length`` bytes derived from ``ikm``, separated by the label ``info``."""
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


# OpenSSL runs the lanes of an Argon2id call on a pool of worker threads that all callers in the process share. With
# more than one lane, two calls from different threads at once fail ("Not enough memory to derive key") or never
# return (seen with OpenSSL 4.0 through ``cryptography`` 50: two people logging in to a server together). So such calls
# take turns. One lane needs no pool and runs freely.
_POOL_LOCK = threading.Lock()


def argon2id(
    password: bytes,
    salt: bytes,
    params: KdfParams,
    length: int,
    *,
    secret: bytes | None = None,
    ad: bytes | None = None,
) -> bytes:
    """Argon2id (RFC 9106). ``secret`` and ``ad`` exist for the published test vectors; Claudia does not use them."""
    if len(salt) < _MIN_SALT:
        raise ValueError("the salt must be at least 8 bytes")
    kdf = Argon2id(
        salt=salt,
        length=length,
        iterations=params.iterations,
        lanes=params.lanes,
        memory_cost=params.memory_kib,
        ad=ad,
        secret=secret,
    )
    if params.lanes == 1:
        return kdf.derive(password)
    with _POOL_LOCK:
        return kdf.derive(password)


def _normalise_name(name: str) -> str:
    """The way names are compared: look-alike characters unified (NFKC), case ignored, outer spaces dropped."""
    return unicodedata.normalize("NFKC", name).casefold().strip()


WARM_SECONDS = 30.0
"""How long a login hashed ahead of time (:func:`warm_login_material`) waits to be used before it is forgotten."""
WARM_MOST = 64
"""Most logins kept hashed ahead of time at once: the oldest are forgotten first."""

_WARM_LOCK = threading.Lock()
_WARM_KEY = os.urandom(32)  # lives and dies with the process: nothing kept under it can be matched elsewhere
_warm: OrderedDict[bytes, tuple[float, LoginMaterial]] = OrderedDict()


def _now() -> float:
    return time.monotonic()


def _warm_key(password: str, name: str, doc_salt: bytes, params: KdfParams) -> bytes:
    """Names the inputs of a derivation without keeping them: a keyed hash, so neither password nor name is stored."""
    parts = (
        unicodedata.normalize("NFKC", password).encode(),
        _normalise_name(name).encode(),
        doc_salt,
        f"{params.iterations}/{params.memory_kib}/{params.lanes}".encode(),
    )
    mac = hmac.new(_WARM_KEY, digestmod=hashlib.sha256)
    for part in parts:
        mac.update(len(part).to_bytes(4, "big") + part)
    return mac.digest()


def _take_warm(key: bytes) -> LoginMaterial | None:
    with _WARM_LOCK:
        entry = _warm.pop(key, None)
    if entry is None or entry[0] < _now():
        return None
    return entry[1]


def warm_login_material(password: str, name: str, doc_salt: bytes, params: KdfParams) -> None:
    """Do the slow hashing of a login now, so that the next :func:`derive_login_material` for it is instant (SEC-21).

    A server hashes in a worker thread with this, then handles the request on its event loop, where hashing would
    stall every other window. The result is **one-shot** (the next derivation takes it away), expires after
    ``WARM_SECONDS``, is bounded to ``WARM_MOST`` entries, and is filed under a keyed hash, never under the
    password or the name.
    """
    material = _derive(password, name, doc_salt, params)
    key = _warm_key(password, name, doc_salt, params)
    with _WARM_LOCK:
        _warm[key] = (_now() + WARM_SECONDS, material)
        _warm.move_to_end(key)
        while len(_warm) > WARM_MOST:
            _warm.popitem(last=False)


def warm_material_count() -> int:
    """How many logins are waiting hashed (for tests and the threat model's bound)."""
    with _WARM_LOCK:
        return len(_warm)


def forget_warm_material() -> None:
    """Drop everything hashed ahead of time."""
    with _WARM_LOCK:
        _warm.clear()


def derive_login_material(password: str, name: str, doc_salt: bytes, params: KdfParams) -> LoginMaterial:
    """Turn a name and a password into the locator and the key-encryption key of that person's slot (D102).

    The Argon2id salt depends on the document's salt *and* the name, so the same password gives unrelated results for
    two people and for two documents. Whoever holds only the file must guess name and password together.

    If the very same login was hashed ahead of time with :func:`warm_login_material`, that result is taken (once).
    """
    warm = _take_warm(_warm_key(password, name, doc_salt, params))
    return warm if warm is not None else _derive(password, name, doc_salt, params)


def _derive(password: str, name: str, doc_salt: bytes, params: KdfParams) -> LoginMaterial:
    name_bytes = _normalise_name(name).encode()
    salt = hashlib.sha256(b"claudia/login-salt/1" + len(doc_salt).to_bytes(4, "big") + doc_salt + name_bytes).digest()
    secret = argon2id(unicodedata.normalize("NFKC", password).encode(), salt, params, KEY_SIZE)
    return LoginMaterial(
        locator=hkdf_sha256(secret, info=b"claudia/locator/1", length=LOCATOR_SIZE),
        key=hkdf_sha256(secret, info=b"claudia/slot-key/1", length=KEY_SIZE),
    )


def derive_recovery_material(recovery_key: bytes) -> LoginMaterial:
    """The locator and key of the recovery slot. A recovery key is random, so no Argon2id is needed.

    The labels differ from those of a login, so a recovery key can never be mistaken for a password's output.
    """
    _check_key(recovery_key)
    return LoginMaterial(
        locator=hkdf_sha256(recovery_key, info=b"claudia/recovery-locator/1", length=LOCATOR_SIZE),
        key=hkdf_sha256(recovery_key, info=b"claudia/recovery-slot-key/1", length=KEY_SIZE),
    )


def _check_key(key: bytes) -> None:
    if len(key) != KEY_SIZE:
        raise ValueError(f"a key must be {KEY_SIZE} bytes")


def _encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """AES-256-GCM with a given nonce: ciphertext followed by the tag. Private: a nonce must never be reused."""
    _check_key(key)
    return AESGCM(key).encrypt(nonce, plaintext, aad)


def seal(key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """Encrypt and authenticate ``plaintext``. The result is ``nonce + ciphertext + tag``.

    ``aad`` is authenticated but not stored: whoever opens the value must name the same context again (document,
    domain, position), so a value cannot be moved elsewhere unnoticed. A fresh random 96-bit nonce is used each time.
    """
    nonce = os.urandom(NONCE_SIZE)
    return nonce + _encrypt(key, nonce, plaintext, aad)


def open_sealed(key: bytes, sealed: bytes, aad: bytes) -> bytes:
    """Decrypt a value made by :func:`seal`; raise :class:`DecryptionError` for any failure, without saying which."""
    _check_key(key)
    if len(sealed) < NONCE_SIZE + TAG_SIZE:
        raise DecryptionError("the value cannot be opened")
    try:
        return AESGCM(key).decrypt(sealed[:NONCE_SIZE], sealed[NONCE_SIZE:], aad)
    except InvalidTag as error:
        raise DecryptionError("the value cannot be opened") from error
