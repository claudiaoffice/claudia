"""Key slots (E2.2, D101, D102, D105): one slot per user, found by a value that depends on name and password."""

import json
import os

import pytest

from claudia_container import crypto
from claudia_container.crypto import KdfParams
from claudia_container.slots import (
    Domain,
    InvalidRecoveryKey,
    KeySlot,
    Role,
    format_recovery_key,
    make_slot,
    new_domain_keys,
    new_recovery_key,
    open_slot,
    parse_recovery_key,
)

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
DOC = "doc-0001"
SALT = bytes(range(16))
ALL = {Domain.CONTENT, Domain.HISTORY, Domain.CHAT}


def login(name, password, salt=SALT, params=CHEAP):
    return crypto.derive_login_material(password, name, salt, params)


@pytest.fixture
def keys():
    return new_domain_keys()


@pytest.fixture
def slots(keys):
    return [
        make_slot(login("annabelle", "Correct-Horse-9"), DOC, "annabelle", Role.OWNER, keys),
        make_slot(login("bertram", "Battery-Staple-7"), DOC, "bertram", Role.EDITOR, keys),
        make_slot(login("cornelia", "Purple-Monkey-5"), DOC, "cornelia", Role.VIEWER, keys),
    ]


def test_new_domain_keys_are_three_different_random_keys():
    keys = new_domain_keys()
    assert set(keys) == ALL
    assert len(set(keys.values())) == 3
    assert all(len(key) == 32 for key in keys.values())


def test_the_owner_and_the_editor_open_all_three_domains(slots, keys):
    people = [("annabelle", "Correct-Horse-9", Role.OWNER), ("bertram", "Battery-Staple-7", Role.EDITOR)]
    for name, password, role in people:
        unlocked = open_slot(slots, login(name, password), DOC)
        assert unlocked is not None
        assert unlocked.role is role
        assert unlocked.name == name
        assert unlocked.keys == keys


def test_a_viewer_gets_the_content_key_and_nothing_else(slots, keys):
    unlocked = open_slot(slots, login("cornelia", "Purple-Monkey-5"), DOC)
    assert unlocked is not None
    assert unlocked.role is Role.VIEWER
    assert unlocked.keys == {Domain.CONTENT: keys[Domain.CONTENT]}


@pytest.mark.parametrize(
    ("name", "password"),
    [
        ("annabelle", "Correct-Horse-8"),  # wrong password
        ("annabell", "Correct-Horse-9"),  # wrong name
        ("bertram", "Correct-Horse-9"),  # right password, but of somebody else
        ("nobody", "Whatever-1234"),
    ],
)
def test_a_wrong_name_and_a_wrong_password_give_the_same_refusal(slots, name, password):
    assert open_slot(slots, login(name, password), DOC) is None


def test_names_are_compared_the_way_people_type_them(slots):
    assert open_slot(slots, login("  Annabelle ", "Correct-Horse-9"), DOC) is not None
    assert open_slot(slots, login("ANNABELLE", "Correct-Horse-9"), DOC) is not None


def test_look_alike_forms_of_the_same_characters_are_the_same_name_and_password():
    assert login("Ａｎｎａ", "Pass-wörd-1") == login("anna", "Pass-wörd-1")  # full-width letters (NFKC)
    assert login("anna", "\u00c9xample-1") == login("anna", "E\u0301xample-1")  # composed or decomposed accent


def test_the_file_part_of_a_slot_shows_no_name_no_role_and_no_password(slots):
    text = json.dumps([slot.to_dict() for slot in slots])
    for secret in ["annabelle", "bertram", "cornelia", "owner", "editor", "viewer", "Correct-Horse", "Battery-Staple"]:
        assert secret not in text


def test_the_same_password_for_two_users_gives_two_unrelated_locators():
    a, b = login("annabelle", "Same-Password-1"), login("bertram", "Same-Password-1")
    assert a.locator != b.locator
    assert a.key != b.key


def test_the_same_name_and_password_in_two_documents_gives_unrelated_material():
    a = login("annabelle", "Same-Password-1", salt=bytes(16))
    b = login("annabelle", "Same-Password-1", salt=bytes(range(1, 17)))
    assert a.locator != b.locator
    assert a.key != b.key


def test_the_cost_parameters_are_part_of_the_derivation():
    other = KdfParams(iterations=2, memory_kib=64, lanes=1)
    assert login("a", "Pass-word-1").key != login("a", "Pass-word-1", params=other).key


def test_login_material_is_repeatable_and_sized():
    a, b = login("annabelle", "Correct-Horse-9"), login("annabelle", "Correct-Horse-9")
    assert a == b
    assert len(a.locator) == 16
    assert len(a.key) == 32


def test_the_representation_of_login_material_does_not_leak_the_key():
    material = login("annabelle", "Correct-Horse-9")
    assert material.key.hex() not in repr(material)
    assert str(material.key) not in repr(material)


def test_a_slot_moved_to_another_document_does_not_open(slots):
    assert open_slot(slots, login("annabelle", "Correct-Horse-9"), "doc-0002") is None


def test_a_damaged_slot_is_refused_not_misread(slots):
    damaged = bytearray(slots[0].sealed)
    damaged[20] ^= 1
    broken = [KeySlot(slots[0].locator, bytes(damaged)), *slots[1:]]
    assert open_slot(broken, login("annabelle", "Correct-Horse-9"), DOC) is None


def test_two_slots_cannot_be_swapped_to_change_somebodys_role(slots):
    owner, editor, _ = slots
    swapped = [KeySlot(owner.locator, editor.sealed), KeySlot(editor.locator, owner.sealed)]
    assert open_slot(swapped, login("annabelle", "Correct-Horse-9"), DOC) is None  # bound to its locator
    assert open_slot(swapped, login("bertram", "Battery-Staple-7"), DOC) is None


def test_an_empty_list_of_slots_opens_nothing():
    assert open_slot([], login("annabelle", "Correct-Horse-9"), DOC) is None


def test_slots_survive_the_trip_through_json(slots):
    again = [KeySlot.from_dict(json.loads(json.dumps(slot.to_dict()))) for slot in slots]
    assert again == slots


@pytest.mark.parametrize(
    "bad", [{}, {"locator": "zz", "sealed": "AAAA"}, {"locator": "AAAA", "sealed": 5}, "text", None]
)
def test_a_slot_made_from_rubbish_is_refused(bad):
    with pytest.raises(ValueError, match="slot"):
        KeySlot.from_dict(bad)


def test_the_unlocked_keys_are_not_printed_by_accident(slots, keys):
    unlocked = open_slot(slots, login("annabelle", "Correct-Horse-9"), DOC)
    assert unlocked is not None
    assert keys[Domain.CONTENT].hex() not in repr(unlocked)
    assert str(keys[Domain.CONTENT]) not in repr(unlocked)


# --- the recovery key (D105) -------------------------------------------------------------------------------------


def test_the_recovery_key_is_256_random_bits_shown_in_groups():
    key = new_recovery_key()
    assert len(key) == 32
    assert new_recovery_key() != key
    text = format_recovery_key(key)
    groups = text.split("-")
    assert len(groups) == 13
    assert all(len(group) == 4 for group in groups)
    assert text == text.upper()


def test_the_written_down_key_can_be_typed_back_in_any_style():
    key = new_recovery_key()
    text = format_recovery_key(key)
    assert parse_recovery_key(text) == key
    assert parse_recovery_key(text.lower()) == key
    assert parse_recovery_key(text.replace("-", " ")) == key
    assert parse_recovery_key("  " + text.replace("-", "") + "\n") == key


@pytest.mark.parametrize("bad", ["", "ABCD-EFGH", "!" * 52, "A" * 51, "A" * 53])
def test_a_mistyped_recovery_key_is_reported_as_such(bad):
    with pytest.raises(InvalidRecoveryKey):
        parse_recovery_key(bad)


def test_the_recovery_key_opens_an_owner_slot_with_everything(keys):
    recovery = new_recovery_key()
    slot = make_slot(crypto.derive_recovery_material(recovery), DOC, "(recovery)", Role.OWNER, keys)
    unlocked = open_slot([slot], crypto.derive_recovery_material(recovery), DOC)
    assert unlocked is not None
    assert unlocked.role is Role.OWNER
    assert unlocked.keys == keys


def test_a_wrong_recovery_key_opens_nothing(keys):
    slot = make_slot(crypto.derive_recovery_material(new_recovery_key()), DOC, "(recovery)", Role.OWNER, keys)
    assert open_slot([slot], crypto.derive_recovery_material(new_recovery_key()), DOC) is None


def test_a_recovery_key_is_not_a_password_for_a_user_slot(slots):
    """Recovery material and login material come from different labels: the recovery key cannot open a login slot."""
    key = os.urandom(32)
    assert crypto.derive_recovery_material(key).locator not in {slot.locator for slot in slots}


def test_a_role_that_may_not_hold_a_key_cannot_be_given_it(keys):
    with pytest.raises(ValueError, match="key"):
        only_history = {Domain.HISTORY: keys[Domain.HISTORY]}  # the content key is missing
        make_slot(login("c", "Pass-word-1"), DOC, "c", Role.VIEWER, only_history)


def test_a_wrong_size_key_is_a_programming_error():
    with pytest.raises(ValueError, match="32"):
        make_slot(login("c", "Pass-word-1"), DOC, "c", Role.OWNER, dict.fromkeys(Domain, b"short"))
