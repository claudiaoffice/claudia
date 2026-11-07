"""Who may configure the server (separate from any document's users, D20/D35)."""

import pytest

from claudia_server.admin import AdminDirectory, needs_administrator, normalized

PASSWORD = "correct horse battery"


@pytest.fixture
def admins():
    directory = AdminDirectory(cost=2**4)  # cheap parameters: the tests check logic, not hardness
    directory.add("tobi", PASSWORD, added="2026-01-01T00:00:00.000Z")
    return directory


def test_the_right_password_gives_the_account(admins):
    account = admins.verify("tobi", PASSWORD)
    assert account is not None and account.name == "tobi" and account.added == "2026-01-01T00:00:00.000Z"


def test_wrong_password_unknown_name_and_missing_credentials_are_all_the_same_answer(admins):
    assert admins.verify("tobi", "wrong") is None
    assert admins.verify("nobody", PASSWORD) is None
    assert admins.verify("tobi", None) is None
    assert admins.verify(None, None) is None


def test_the_name_is_matched_ignoring_case_and_spacing_and_keeps_its_spelling(admins):
    account = admins.verify("  Tobi ", PASSWORD)
    assert account is not None and account.name == "tobi"
    assert normalized("  Tobi ") == normalized("TOBI")


def test_a_password_is_never_stored_as_it_is(admins):
    assert PASSWORD not in repr(vars(admins))


def test_checking_an_unknown_name_costs_a_hash_too(admins, monkeypatch):
    """No quick answer for a name that does not exist: the time must not tell which names are administrators."""
    import hashlib

    calls = []
    real = hashlib.scrypt
    monkeypatch.setattr(hashlib, "scrypt", lambda *a, **k: calls.append(1) or real(*a, **k))
    admins.verify("nobody", "whatever")
    admins.verify("tobi", "whatever")
    assert len(calls) == 2


def test_names_and_passwords_are_validated(admins):
    with pytest.raises(ValueError, match="at least 8"):
        admins.add("anna", "short", added="2026-01-01T00:00:00.000Z")
    with pytest.raises(ValueError, match="already"):
        admins.add("tobi", "another password", added="2026-01-01T00:00:00.000Z")
    with pytest.raises(ValueError, match="invalid administrator name"):
        admins.add("tobi\nben", "another password", added="2026-01-01T00:00:00.000Z")


def test_removing_an_administrator_locks_them_out(admins):
    admins.add("anna", "another good password", added="2026-01-01T00:00:00.000Z")
    admins.remove("tobi")
    assert admins.verify("tobi", PASSWORD) is None
    with pytest.raises(KeyError):
        admins.remove("tobi")


def test_the_last_administrator_cannot_be_removed(admins):
    with pytest.raises(ValueError, match="last administrator"):
        admins.remove("tobi")
    assert len(admins) == 1


def test_changing_a_password(admins):
    admins.change_password("tobi", "a brand new password")
    assert admins.verify("tobi", PASSWORD) is None
    assert admins.verify("tobi", "a brand new password") is not None
    with pytest.raises(KeyError):
        admins.change_password("nobody", "a brand new password")
    with pytest.raises(ValueError, match="at least 8"):
        admins.change_password("tobi", "short")


def test_dump_and_load_round_trip(admins):
    admins.add("anna", "another good password", added="2026-01-02T00:00:00.000Z")
    restored = AdminDirectory()
    restored.load(admins.dump())
    assert {a.name for a in restored.list_admins()} == {"tobi", "anna"}
    assert restored.verify("tobi", PASSWORD) is not None
    assert restored.verify("anna", "another good password") is not None
    assert restored.verify("anna", "wrong") is None


def test_needs_administrator_only_when_exposed_and_nobody_is_one_yet():
    assert needs_administrator(True, 0) is True
    assert needs_administrator(False, 0) is False  # loopback: the mechanism stays dormant
    assert needs_administrator(True, 1) is False  # never recurs once there is one
    assert needs_administrator(False, 1) is False
