"""The recovery key (E2.2, D105): made at creation or later, replaced by a new one, and a way back in."""

import pytest

from claudia_container.container import (
    add_user,
    create_document,
    has_recovery_key,
    read_people,
    recover_access,
    set_recovery_key,
    unlock,
    unlock_with_recovery,
)
from claudia_container.crypto import KdfParams
from claudia_container.passwords import WeakPassword
from claudia_container.slots import Domain, Role, new_recovery_key

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
OWNER_PW, ED_PW, VIEW_PW, NEW_PW = "Correct-Horse-9", "Battery-Staple-7", "Purple-Monkey-5", "Fresh-Start-42"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "plan.claudia"


@pytest.fixture
def owner(path):
    return create_document(
        path, doc_id="plan", app="computes", title="t", owner="Annabelle", password=OWNER_PW, kdf=CHEAP
    )


@pytest.fixture
def team(path, owner):
    add_user(path, owner.keys, "Bertram", ED_PW, Role.EDITOR)
    add_user(path, owner.keys, "Cornelia", VIEW_PW, Role.VIEWER)
    return owner


def test_a_document_made_without_a_recovery_key_has_none(path, owner):
    assert has_recovery_key(path, owner.keys) is False


def test_a_document_made_with_a_recovery_key_has_one(path):
    key = new_recovery_key()
    owner = create_document(
        path, doc_id="plan", app="computes", title="t", owner="Ann", password=OWNER_PW, kdf=CHEAP, recovery_key=key
    )
    assert has_recovery_key(path, owner.keys) is True
    assert unlock_with_recovery(path, key) is not None


def test_a_recovery_key_can_be_added_later_and_opens_with_all_keys(path, team):
    key = new_recovery_key()
    set_recovery_key(path, team.keys, key)
    assert has_recovery_key(path, team.keys) is True
    opened = unlock_with_recovery(path, key)
    assert opened is not None and opened.role is Role.OWNER and set(opened.keys) == set(Domain)


def test_a_new_recovery_key_makes_the_old_one_useless(path, team):
    old, new = new_recovery_key(), new_recovery_key()
    set_recovery_key(path, team.keys, old)
    set_recovery_key(path, team.keys, new)
    assert unlock_with_recovery(path, old) is None
    assert unlock_with_recovery(path, new) is not None


def test_the_recovery_key_is_not_a_person(path, team):
    set_recovery_key(path, team.keys, new_recovery_key())
    assert [p.name for p in read_people(path, team.keys)] == ["Annabelle", "Bertram", "Cornelia"]
    assert unlock(path, "Annabelle", OWNER_PW) is not None  # nobody lost access by it


def test_only_somebody_with_all_keys_may_set_the_recovery_key(path, team):
    viewer = unlock(path, "Cornelia", VIEW_PW)
    with pytest.raises(PermissionError):
        set_recovery_key(path, viewer.keys, new_recovery_key())


def test_a_recovery_key_must_be_a_key(path, team):
    with pytest.raises(ValueError):
        set_recovery_key(path, team.keys, b"short")


# --- getting back in ------------------------------------------------------------------------------------------------


def test_the_recovery_key_gives_a_person_a_new_password_and_keeps_their_role(path, team):
    key = new_recovery_key()
    set_recovery_key(path, team.keys, key)
    person = recover_access(path, key, "bertram", NEW_PW)
    assert (person.name, person.role) == ("Bertram", Role.EDITOR)
    assert unlock(path, "Bertram", ED_PW) is None
    editor = unlock(path, "Bertram", NEW_PW)
    assert editor.role is Role.EDITOR and set(editor.keys) == set(Domain)
    assert [p.name for p in read_people(path, team.keys)] == ["Annabelle", "Bertram", "Cornelia"]


def test_a_viewer_who_is_recovered_stays_a_viewer(path, team):
    key = new_recovery_key()
    set_recovery_key(path, team.keys, key)
    recover_access(path, key, "Cornelia", NEW_PW)
    assert set(unlock(path, "Cornelia", NEW_PW).keys) == {Domain.CONTENT}


def test_somebody_unknown_who_has_the_key_becomes_an_owner(path, team):
    key = new_recovery_key()
    set_recovery_key(path, team.keys, key)
    person = recover_access(path, key, "Dora", NEW_PW)
    assert (person.name, person.role) == ("Dora", Role.OWNER)
    assert unlock(path, "Dora", NEW_PW).role is Role.OWNER


def test_a_wrong_recovery_key_changes_nothing(path, team):
    set_recovery_key(path, team.keys, new_recovery_key())
    before = path.read_bytes()
    assert recover_access(path, new_recovery_key(), "Annabelle", NEW_PW) is None
    assert path.read_bytes() == before


def test_a_weak_new_password_is_refused_and_nothing_changes(path, team):
    key = new_recovery_key()
    set_recovery_key(path, team.keys, key)
    before = path.read_bytes()
    with pytest.raises(WeakPassword):
        recover_access(path, key, "Annabelle", "weak")
    assert path.read_bytes() == before
    assert unlock(path, "Annabelle", OWNER_PW) is not None
