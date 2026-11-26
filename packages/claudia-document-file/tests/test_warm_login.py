"""Hashing a password ahead of time, so that a request that needs it does not hash on the server's event loop
(SEC-21): ``warm_login_material`` does the slow work, the next ``derive_login_material`` for the same inputs takes the
result, once.
"""

import pytest

from claudia_document_file import KdfParams, crypto

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
SALT = b"s" * 16


@pytest.fixture
def hashed(monkeypatch):
    """Counts the Argon2 runs."""
    runs = []
    real = crypto.argon2id

    def counting(password, salt, params, length, **more):
        runs.append(password)
        return real(password, salt, params, length, **more)

    monkeypatch.setattr(crypto, "argon2id", counting)
    return runs


@pytest.fixture(autouse=True)
def _empty_cache():
    crypto.forget_warm_material()
    yield
    crypto.forget_warm_material()


def test_a_warmed_login_is_not_hashed_again(hashed):
    crypto.warm_login_material("Correct-Horse-9", "ann", SALT, CHEAP)
    assert len(hashed) == 1
    warm = crypto.derive_login_material("Correct-Horse-9", "ann", SALT, CHEAP)
    assert len(hashed) == 1, "taken from what was warmed"
    assert warm == crypto.derive_login_material("Correct-Horse-9", "ann", SALT, CHEAP), "and the same as hashing it"
    assert len(hashed) == 2


def test_what_was_warmed_is_used_once(hashed):
    crypto.warm_login_material("Correct-Horse-9", "ann", SALT, CHEAP)
    crypto.derive_login_material("Correct-Horse-9", "ann", SALT, CHEAP)
    crypto.derive_login_material("Correct-Horse-9", "ann", SALT, CHEAP)
    assert len(hashed) == 2


@pytest.mark.parametrize(
    "other",
    [
        ("Correct-Horse-8", "ann", SALT, CHEAP),
        ("Correct-Horse-9", "ben", SALT, CHEAP),
        ("Correct-Horse-9", "ann", b"t" * 16, CHEAP),
        ("Correct-Horse-9", "ann", SALT, KdfParams(iterations=2, memory_kib=64, lanes=1)),
    ],
)
def test_only_the_very_same_inputs_take_what_was_warmed(hashed, other):
    crypto.warm_login_material("Correct-Horse-9", "ann", SALT, CHEAP)
    crypto.derive_login_material(*other)
    assert len(hashed) == 2
    crypto.derive_login_material("Correct-Horse-9", "ann", SALT, CHEAP)
    assert len(hashed) == 2, "and it is still there for them"


def test_a_name_is_taken_the_way_names_are_compared(hashed):
    crypto.warm_login_material("Correct-Horse-9", "Ann ", SALT, CHEAP)
    crypto.derive_login_material("Correct-Horse-9", "ann", SALT, CHEAP)
    assert len(hashed) == 1


def test_what_was_warmed_expires(hashed, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(crypto, "warm_clock", lambda: now[0])
    crypto.warm_login_material("Correct-Horse-9", "ann", SALT, CHEAP)
    now[0] += crypto.WARM_SECONDS + 1
    crypto.derive_login_material("Correct-Horse-9", "ann", SALT, CHEAP)
    assert len(hashed) == 2


def test_what_is_kept_is_bounded(hashed):
    for n in range(crypto.WARM_MOST + 20):
        crypto.warm_login_material(f"Correct-Horse-{n}", "ann", SALT, CHEAP)
    assert crypto.warm_material_count() <= crypto.WARM_MOST


def test_the_password_is_not_kept_in_the_clear():
    crypto.warm_login_material("Correct-Horse-9", "ann", SALT, CHEAP)
    for key in crypto.warm_material_names():
        assert b"Correct-Horse-9" not in key and b"ann" not in key


def test_a_document_warms_the_login_of_its_own_file(tmp_path, hashed):
    from claudia_document_file import Role, create_document, unlock, warm

    path = tmp_path / "a.claudia"
    create_document(path, name="a", app="claudia-writer", owner="Ann", password="Correct-Horse-9", kdf=CHEAP)
    del hashed[:]
    warm(path, "Ann", "Correct-Horse-9")
    assert len(hashed) == 1
    unlocked = unlock(path, "Ann", "Correct-Horse-9")
    assert unlocked is not None and unlocked.role is Role.OWNER
    assert len(hashed) == 1, "unlocking took what warm had hashed"


def test_warming_does_not_open_anything_for_a_wrong_password(tmp_path):
    from claudia_document_file import create_document, unlock, warm

    path = tmp_path / "a.claudia"
    create_document(path, name="a", app="claudia-writer", owner="Ann", password="Correct-Horse-9", kdf=CHEAP)
    warm(path, "Ann", "Wrong-Horse-9")
    assert unlock(path, "Ann", "Wrong-Horse-9") is None
