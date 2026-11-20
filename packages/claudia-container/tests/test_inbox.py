"""The inbox (E2.3, D1274): a letter sealed to a public key that only the holder of the private key can open."""

import pytest

from claudia_container.crypto import DecryptionError
from claudia_container.inbox import PRIVATE_KEY_SIZE, PUBLIC_KEY_SIZE, new_key_pair, open_inbox, seal_to

AAD = b"claudia/inbox/test"


def test_a_key_pair_has_two_keys_of_32_bytes_and_every_pair_is_new():
    first, second = new_key_pair(), new_key_pair()
    assert len(first.private) == PRIVATE_KEY_SIZE and len(first.public) == PUBLIC_KEY_SIZE
    assert first.private != second.private and first.public != second.public


def test_what_is_sealed_to_a_public_key_opens_with_its_private_key():
    pair = new_key_pair()
    assert open_inbox(pair.private, seal_to(pair.public, b"new keys", AAD), AAD) == b"new keys"


def test_the_same_letter_sealed_twice_is_never_the_same_bytes():
    pair = new_key_pair()
    assert seal_to(pair.public, b"x", AAD) != seal_to(pair.public, b"x", AAD)


def test_another_private_key_does_not_open_it():
    pair, other = new_key_pair(), new_key_pair()
    with pytest.raises(DecryptionError):
        open_inbox(other.private, seal_to(pair.public, b"x", AAD), AAD)


def test_the_authenticated_data_must_be_the_same():
    pair = new_key_pair()
    with pytest.raises(DecryptionError):
        open_inbox(pair.private, seal_to(pair.public, b"x", AAD), b"another place")


def test_a_changed_or_cut_off_letter_is_refused():
    pair = new_key_pair()
    sealed = seal_to(pair.public, b"x", AAD)
    for bad in (
        sealed[:-1],
        sealed[:20],
        sealed[:-1] + bytes([sealed[-1] ^ 1]),
        bytes([sealed[0] ^ 1]) + sealed[1:],
        b"",
    ):
        with pytest.raises(DecryptionError):
            open_inbox(pair.private, bad, AAD)


def test_a_public_key_that_gives_no_shared_secret_is_refused():
    with pytest.raises(ValueError, match="public key"):
        seal_to(bytes(PUBLIC_KEY_SIZE), b"x", AAD)
    with pytest.raises(ValueError, match="public key"):
        seal_to(b"short", b"x", AAD)
