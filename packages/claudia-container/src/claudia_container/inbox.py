"""The inbox (E2.3, D1274): how new keys reach a person who is not there.

A key slot opens with a key derived from its person's password, so nobody else can write into it. To give somebody new
keys without her password the owner's server seals them to her **public key** and leaves the letter in the file; her
slot holds the matching **private key** and opens it at her next login. The primitives are the ones of D104 plus
X25519: an ephemeral key pair per letter, HKDF-SHA256 over the shared secret and both public keys, AES-256-GCM.

Nothing here knows about documents. The caller says in the authenticated data where the letter belongs (the document
and the person's locator), so a letter cannot be moved to another person or another document.
"""

from dataclasses import dataclass, field

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

from .crypto import KEY_SIZE, DecryptionError, hkdf_sha256, open_sealed, seal

PRIVATE_KEY_SIZE = 32
"""Bytes of an X25519 private key."""
PUBLIC_KEY_SIZE = 32
"""Bytes of an X25519 public key."""

_INFO = b"claudia/inbox/1"


@dataclass(frozen=True)
class KeyPair:
    """A person's key pair: the public key goes into the list of people, the private key into her key slot."""

    private: bytes = field(repr=False)  # a secret: never in a log line or a traceback
    public: bytes


def new_key_pair() -> KeyPair:
    """A fresh X25519 key pair."""
    private = X25519PrivateKey.generate()
    return KeyPair(
        private.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
        ),
        private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw),
    )


def _letter_key(shared: bytes, ephemeral: bytes, recipient: bytes) -> bytes:
    return hkdf_sha256(shared, info=_INFO + ephemeral + recipient, length=KEY_SIZE)


def seal_to(public: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """``plaintext`` sealed so that only the holder of the private key of ``public`` can open it.

    ``ValueError`` if ``public`` is not a usable public key (wrong size, or one that gives no shared secret)."""
    if len(public) != PUBLIC_KEY_SIZE:
        raise ValueError("not a public key: it has 32 bytes")
    ephemeral = X25519PrivateKey.generate()
    try:
        shared = ephemeral.exchange(X25519PublicKey.from_public_bytes(public))
    except ValueError as error:
        raise ValueError("not a usable public key") from error
    mine = ephemeral.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return mine + seal(_letter_key(shared, mine, public), plaintext, aad)


def open_inbox(private: bytes, letter: bytes, aad: bytes) -> bytes:
    """The plaintext of a letter sealed to the public key of ``private``. :class:`DecryptionError` for any other
    letter, one that was changed or cut off, or one that belongs elsewhere (``aad``); it never says which."""
    if len(letter) <= PUBLIC_KEY_SIZE or len(private) != PRIVATE_KEY_SIZE:
        raise DecryptionError("not a letter")
    ephemeral, sealed = letter[:PUBLIC_KEY_SIZE], letter[PUBLIC_KEY_SIZE:]
    try:
        key = X25519PrivateKey.from_private_bytes(private)
        shared = key.exchange(X25519PublicKey.from_public_bytes(ephemeral))
        mine = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    except ValueError as error:
        raise DecryptionError("not a letter for this key") from error
    return open_sealed(_letter_key(shared, ephemeral, mine), sealed, aad)
