"""E3.1: name + password against the users of the document (replaces the demo's token table).

The directory used here is a stand-in for the users inside the document file (E2.3): the server only asks
``verify(doc_id, credentials)`` and never knows where users live. There is no central user database.
"""

import pytest

from claudia_server.auth import (
    AI_USER,
    Account,
    AuthRefused,
    Credentials,
    ScryptDirectory,
    is_reserved,
)


@pytest.fixture
def users():
    directory = ScryptDirectory(cost=2**4)  # cheap parameters: the tests check logic, not hardness
    directory.add_user("plan", "Ann", "correct horse battery", "owner")
    directory.add_user("plan", "Ben", "tr0ub4dor&3 is okay", "editor")
    directory.add_user("plan", "Vera", "just looking around", "viewer")
    directory.add_user("other", "Ann", "a different password", "editor")
    return directory


def test_the_right_password_gives_the_account_with_its_role(users):
    account = users.verify("plan", Credentials("Ann", "correct horse battery"))
    assert account == Account("Ann", "owner")
    assert users.verify("plan", Credentials("Vera", "just looking around")).role == "viewer"


def test_wrong_password_unknown_user_and_missing_credentials_are_all_the_same_answer(users):
    assert users.verify("plan", Credentials("Ann", "wrong")) is None
    assert users.verify("plan", Credentials("Nobody", "correct horse battery")) is None
    assert users.verify("plan", Credentials("Ann", None)) is None
    assert users.verify("plan", Credentials(None, None)) is None
    assert users.verify("no-such-document", Credentials("Ann", "correct horse battery")) is None


def test_users_belong_to_one_document(users):
    assert users.verify("other", Credentials("Ann", "correct horse battery")) is None
    assert users.verify("other", Credentials("Ann", "a different password")).role == "editor"


def test_the_name_is_matched_ignoring_case_and_spacing_and_keeps_its_spelling(users):
    account = users.verify("plan", Credentials("  ann ", "correct horse battery"))
    assert account is not None and account.user == "Ann"


def test_a_password_is_never_stored_as_it_is(users):
    assert "correct horse battery" not in repr(vars(users))


def test_the_name_ai_belongs_to_the_assistant(users):
    assert is_reserved("ai") and is_reserved(" AI ") and is_reserved("ａｉ")  # case, spacing, full-width letters
    with pytest.raises(ValueError, match="reserved"):
        users.add_user("plan", "AI", "whatever it is", "editor")
    with pytest.raises(AuthRefused, match="AI assistant"):
        users.verify("plan", Credentials("ai", "anything"))
    with pytest.raises(ValueError, match="reserved"):
        Account("ai", "editor")
    assert Account.assistant().system and Account.assistant().user == AI_USER


def test_accounts_are_validated():
    with pytest.raises(ValueError, match="role"):
        Account("Ann", "boss")
    with pytest.raises(ValueError, match="invalid user name"):
        Account("Ann\nBen", "editor")
    assert (
        Account("Ann", "owner").can_write
        and Account("Ann", "editor").can_write
        and not Account("Ann", "viewer").can_write
    )


def test_passwords_must_be_long_enough_and_names_unique_per_document(users):
    with pytest.raises(ValueError, match="at least 8"):
        users.add_user("plan", "Cleo", "short", "editor")
    with pytest.raises(ValueError, match="already"):
        users.add_user("plan", "ann", "another password", "editor")


def test_removing_a_user_locks_them_out(users):
    users.remove_user("plan", "Ben")
    assert users.verify("plan", Credentials("Ben", "tr0ub4dor&3 is okay")) is None
    with pytest.raises(KeyError):
        users.remove_user("plan", "Ben")


def test_checking_an_unknown_user_costs_a_hash_too(users, monkeypatch):
    """No quick answer for a name that does not exist: the time must not tell which names are users."""
    import hashlib

    calls = []
    real = hashlib.scrypt
    monkeypatch.setattr(hashlib, "scrypt", lambda *a, **k: calls.append(1) or real(*a, **k))
    users.verify("plan", Credentials("Nobody", "whatever"))
    users.verify("plan", Credentials("Ann", "whatever"))
    assert len(calls) == 2
