"""Known-answer tests for the wrappers (test 12 of the Epic 2 design) and the rules of the wrappers themselves.

The reference values are published: RFC 5869 (HKDF), the argon2 reference test suite and RFC 9106 (Argon2id), and the
GCM test cases 13 and 14 for AES-256 (McGrew and Viega). If a library update changes one of them, something is wrong.
"""

import pytest

from claudia_container import crypto
from claudia_container.crypto import (
    MAX_ITERATIONS,
    MAX_LANES,
    MAX_MEMORY_KIB,
    DecryptionError,
    KdfParams,
    open_sealed,
    random_key,
    seal,
)

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)  # for tests that do not test the cost


def test_hkdf_matches_rfc_5869_test_case_1():
    okm = crypto.hkdf_sha256(b"\x0b" * 22, info=bytes(range(0xF0, 0xFA)), length=42, salt=bytes(range(13)))
    assert okm.hex() == "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"


def test_argon2id_matches_the_reference_suite():
    params = KdfParams(iterations=2, memory_kib=65536, lanes=1)
    out = crypto.argon2id(b"password", b"somesalt", params, length=32)
    assert out.hex() == "09316115d5cf24ed5a15a31a3ba326e5cf32edc24702987c02b6566f61913cf7"


def test_argon2id_matches_rfc_9106():
    params = KdfParams(iterations=3, memory_kib=32, lanes=4)
    out = crypto.argon2id(b"\x01" * 32, b"\x02" * 16, params, length=32, secret=b"\x03" * 8, ad=b"\x04" * 12)
    assert out.hex() == "0d640df58d78766c08c037a34a8b53c9d01ef0452d75b65eb52520e96b01e659"


@pytest.mark.parametrize(
    ("plain", "expected"),
    [
        (b"", "530f8afbc74536b9a963b4f1c4cb738b"),  # test case 13: only the tag
        (bytes(16), "cea7403d4d606b6e074ec5d3baf39d18d0d1c8a799996bf0265b98b5d48ab919"),  # test case 14
    ],
)
def test_aes_256_gcm_matches_the_published_test_cases(plain, expected):
    assert crypto._encrypt(bytes(32), bytes(12), plain, b"").hex() == expected


def test_seal_and_open_round_trip():
    key = random_key()
    sealed = seal(key, b"the quarterly numbers", b"doc-1")
    assert open_sealed(key, sealed, b"doc-1") == b"the quarterly numbers"


def test_a_random_key_is_32_bytes_and_never_repeats():
    assert len(random_key()) == 32
    assert len({random_key() for _ in range(50)}) == 50


def test_sealing_twice_gives_different_bytes():
    key = random_key()
    assert seal(key, b"same", b"") != seal(key, b"same", b"")  # fresh nonce each time


def test_sealed_bytes_do_not_contain_the_plaintext():
    assert b"secret-budget" not in seal(random_key(), b"secret-budget", b"")


@pytest.mark.parametrize("damage", ["flip_nonce", "flip_body", "flip_tag", "cut", "empty"])
def test_any_damage_is_refused_with_one_error(damage):
    key = random_key()
    sealed = bytearray(seal(key, b"content of the cell", b"aad"))
    if damage == "flip_nonce":
        sealed[0] ^= 1
    elif damage == "flip_body":
        sealed[14] ^= 1
    elif damage == "flip_tag":
        sealed[-1] ^= 1
    elif damage == "cut":
        sealed = sealed[:-3]
    else:
        sealed = bytearray()
    with pytest.raises(DecryptionError):
        open_sealed(key, bytes(sealed), b"aad")


def test_the_wrong_key_or_the_wrong_authenticated_data_is_refused():
    key = random_key()
    sealed = seal(key, b"x", b"history|block-3")
    with pytest.raises(DecryptionError):
        open_sealed(random_key(), sealed, b"history|block-3")
    with pytest.raises(DecryptionError):
        open_sealed(key, sealed, b"history|block-4")  # a block moved to another place


def test_a_key_of_the_wrong_size_is_a_programming_error():
    with pytest.raises(ValueError, match="32"):
        seal(b"short", b"x", b"")


def test_kdf_parameters_round_trip_through_the_manifest():
    params = KdfParams(iterations=3, memory_kib=65536, lanes=4)
    assert KdfParams.from_dict(params.to_dict()) == params


@pytest.mark.parametrize(
    "bad",
    [
        {"iterations": 0, "memory_kib": 64, "lanes": 1},
        {"iterations": MAX_ITERATIONS + 1, "memory_kib": 64, "lanes": 1},
        {"iterations": 1, "memory_kib": 64, "lanes": 0},
        {"iterations": 1, "memory_kib": 64 * 1024, "lanes": MAX_LANES + 1},
        {"iterations": 1, "memory_kib": 4, "lanes": 1},  # Argon2 needs at least 8 KiB per lane
        {"iterations": 1, "memory_kib": MAX_MEMORY_KIB + 1, "lanes": 1},  # a file must not be able to demand gigabytes
        {"iterations": "3", "memory_kib": 64, "lanes": 1},
        {"memory_kib": 64, "lanes": 1},
    ],
)
def test_a_file_cannot_demand_absurd_or_broken_kdf_parameters(bad):
    with pytest.raises(ValueError, match="KDF"):
        KdfParams.from_dict(bad)


def test_the_default_parameters_are_allowed_by_the_limits():
    assert KdfParams.default() == KdfParams.from_dict(KdfParams.default().to_dict())
