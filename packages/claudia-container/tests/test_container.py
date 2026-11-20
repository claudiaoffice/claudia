"""The document file (E2.1, E2.2, E2.3): one zip with a plain manifest, key slots and the sealed list of people."""

import io
import json
import os
import sys
import uuid
import zipfile

import pytest

from claudia_container import container
from claudia_container.container import (
    FORMAT_TEXT,
    MAX_DESCRIPTION,
    MAX_TAG,
    MAX_TAGS,
    ContainerError,
    NotAClaudiaDocument,
    OutdatedFormat,
    Person,
    ReaderLimitExceeded,
    UnsupportedFormat,
    add_user,
    change_password,
    clean_details,
    create_document,
    leave_document,
    read_manifest,
    read_people,
    remove_user,
    set_details,
    transfer_owner,
    unlock,
    unlock_with_recovery,
)
from claudia_container.crypto import KdfParams
from claudia_container.passwords import WeakPassword
from claudia_container.slots import Domain, Role, new_recovery_key

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
OWNER_PW, ED_PW, VIEW_PW = "Correct-Horse-9", "Battery-Staple-7", "Purple-Monkey-5"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "plan.claudia"


@pytest.fixture
def owner(path):
    return create_document(path, name="plan", app="computes", owner="Annabelle", password=OWNER_PW, kdf=CHEAP)


@pytest.fixture
def team(path, owner):
    add_user(path, owner.keys, "Bertram", ED_PW, Role.EDITOR)
    add_user(path, owner.keys, "Cornelia", VIEW_PW, Role.VIEWER)
    return owner


# --- the file ------------------------------------------------------------------------------------------------------


def test_the_document_is_one_zip_that_names_its_format_first(path, owner):
    assert zipfile.is_zipfile(path)
    with zipfile.ZipFile(path) as z:
        first = z.infolist()[0]
        assert first.filename == "format"
        assert first.compress_type == zipfile.ZIP_STORED
        assert z.read("format") == FORMAT_TEXT.encode()
        names = set(z.namelist())
        assert names >= {"format", "manifest.json", "slots.json", "people.bin"}
        assert {n.split("/")[0] for n in names} == {"format", "manifest.json", "slots.json", "people.bin", "private"}


def test_the_manifest_is_readable_without_a_password(path, owner):
    manifest = read_manifest(path)
    assert (manifest.name, manifest.app) == ("plan", "computes")
    assert manifest.unlisted is False
    assert manifest.kdf == CHEAP
    assert manifest.last_change.endswith("Z")


def test_the_file_shows_neither_names_nor_passwords_nor_keys(path, team):
    data = path.read_bytes()
    with zipfile.ZipFile(path) as z:
        data += b"".join(z.read(n) for n in z.namelist())
    secrets = [b"Annabelle", b"Bertram", b"Cornelia", OWNER_PW.encode(), ED_PW.encode(), b"owner", b"editor", b"viewer"]
    for secret in secrets:
        assert secret not in data
    for key in team.keys.values():
        assert key not in data


def test_creating_never_overwrites(path, owner):
    with pytest.raises(FileExistsError):
        create_document(path, name="plan", app="computes", owner="A", password=OWNER_PW, kdf=CHEAP)


@pytest.mark.parametrize("bad_id", ["", "../x", "a b", "x" * 65, "-lead"])
def test_a_document_id_must_be_safe(tmp_path, bad_id):
    with pytest.raises(ValueError, match="name"):
        create_document(tmp_path / "x.claudia", name=bad_id, app="computes", owner="A", password=OWNER_PW, kdf=CHEAP)


def test_a_weak_password_cannot_start_a_document(tmp_path):
    with pytest.raises(WeakPassword):
        create_document(tmp_path / "x.claudia", name="x", app="computes", owner="A", password="short", kdf=CHEAP)
    assert not (tmp_path / "x.claudia").exists()


# --- logging in ----------------------------------------------------------------------------------------------------


def test_the_owner_unlocks_everything(path, owner):
    unlocked = unlock(path, "annabelle", OWNER_PW)
    assert unlocked is not None
    assert (unlocked.name, unlocked.role) == ("Annabelle", Role.OWNER)
    assert unlocked.keys == owner.keys
    assert set(unlocked.keys) == set(Domain)


def test_a_viewer_unlocks_the_content_key_only(path, team):
    viewer = unlock(path, "Cornelia", VIEW_PW)
    assert viewer is not None
    assert viewer.role is Role.VIEWER
    assert set(viewer.keys) == {Domain.CONTENT}


@pytest.mark.parametrize(
    ("name", "password"), [("Annabelle", ED_PW), ("Nobody", OWNER_PW), ("Annabelle", "wrong-Pass-1")]
)
def test_a_wrong_name_and_a_wrong_password_are_the_same_refusal(path, team, name, password):
    assert unlock(path, name, password) is None


def test_a_file_that_asks_for_absurd_cost_is_refused_before_any_hashing(path, owner):
    with zipfile.ZipFile(path) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    manifest = json.loads(entries["manifest.json"])
    manifest["kdf"] = {"iterations": 20, "memory_kib": 2**30, "lanes": 16}
    entries["manifest.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(path, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    with pytest.raises(NotAClaudiaDocument):
        unlock(path, "Annabelle", OWNER_PW)


# --- people --------------------------------------------------------------------------------------------------------


def test_the_people_are_listed_for_everybody_who_may_read_the_content(path, team):
    viewer = unlock(path, "Cornelia", VIEW_PW)
    assert [(p.name, p.role) for p in read_people(path, viewer.keys)] == [
        ("Annabelle", Role.OWNER),
        ("Bertram", Role.EDITOR),
        ("Cornelia", Role.VIEWER),
    ]


def test_a_name_can_be_used_only_once_however_it_is_written(path, team):
    with pytest.raises(ValueError, match="already"):
        add_user(path, team.keys, "  BERTRAM ", "Another-Pass-1", Role.VIEWER)


def test_a_weak_password_cannot_be_given_to_a_new_person(path, team):
    with pytest.raises(WeakPassword):
        add_user(path, team.keys, "Dora", "weakweak", Role.EDITOR)
    assert [p.name for p in read_people(path, team.keys)] == ["Annabelle", "Bertram", "Cornelia"]


@pytest.mark.parametrize("name", ["", "   ", "x" * 81, "bad\x00name"])
def test_a_name_must_be_a_sensible_one(path, team, name):
    with pytest.raises(ValueError, match="name"):
        add_user(path, team.keys, name, "Another-Pass-1", Role.EDITOR)


def test_somebody_without_all_keys_cannot_add_people(path, team):
    viewer = unlock(path, "Cornelia", VIEW_PW)
    with pytest.raises(PermissionError):
        add_user(path, viewer.keys, "Dora", "Another-Pass-1", Role.VIEWER)


def test_a_removed_person_can_no_longer_log_in(path, team):
    remove_user(path, team.keys, "bertram")
    assert unlock(path, "Bertram", ED_PW) is None
    assert unlock(path, "Annabelle", OWNER_PW) is not None
    assert [p.name for p in read_people(path, team.keys)] == ["Annabelle", "Cornelia"]


def test_removing_somebody_who_is_not_there_is_a_key_error(path, team):
    with pytest.raises(KeyError):
        remove_user(path, team.keys, "Nobody")


def test_the_last_owner_cannot_be_removed(path, team):
    with pytest.raises(ValueError, match="owner"):
        remove_user(path, team.keys, "Annabelle")


def test_a_password_can_be_changed_by_its_owner(path, team):
    assert change_password(path, "Bertram", ED_PW, "Fresh-Secret-3") is True
    assert unlock(path, "Bertram", ED_PW) is None
    fresh = unlock(path, "Bertram", "Fresh-Secret-3")
    assert fresh is not None and fresh.keys == team.keys
    assert [p.name for p in read_people(path, team.keys)] == ["Annabelle", "Bertram", "Cornelia"]


def test_a_viewer_can_change_their_own_password_too(path, team):
    assert change_password(path, "Cornelia", VIEW_PW, "Fresh-Secret-3") is True
    assert unlock(path, "Cornelia", "Fresh-Secret-3").role is Role.VIEWER


def test_a_wrong_old_password_changes_nothing(path, team):
    assert change_password(path, "Bertram", "wrong-Pass-1", "Fresh-Secret-3") is False
    assert unlock(path, "Bertram", ED_PW) is not None


def test_a_weak_new_password_is_refused(path, team):
    with pytest.raises(WeakPassword):
        change_password(path, "Bertram", ED_PW, "weak")
    assert unlock(path, "Bertram", ED_PW) is not None


# --- leaving ---------------------------------------------------------------------------------------------------


def test_an_editor_can_leave(path, team):
    assert leave_document(path, "Bertram", ED_PW) is True
    assert unlock(path, "Bertram", ED_PW) is None
    assert [p.name for p in read_people(path, team.keys)] == ["Annabelle", "Cornelia"]


def test_a_viewer_can_leave_too_though_they_hold_only_the_content_key(path, team):
    viewer = unlock(path, "Cornelia", VIEW_PW)
    assert set(viewer.keys) == {Domain.CONTENT}
    assert leave_document(path, "Cornelia", VIEW_PW) is True
    assert unlock(path, "Cornelia", VIEW_PW) is None


def test_the_only_owner_cannot_leave(path, team):
    with pytest.raises(ValueError, match="owner"):
        leave_document(path, "Annabelle", OWNER_PW)
    assert unlock(path, "Annabelle", OWNER_PW) is not None


def test_an_owner_can_leave_once_another_owner_is_there(path, team):
    add_user(path, team.keys, "Dora", "Another-Pass-1", Role.OWNER)
    assert leave_document(path, "Annabelle", OWNER_PW) is True
    assert unlock(path, "Annabelle", OWNER_PW) is None
    assert unlock(path, "Dora", "Another-Pass-1") is not None


def test_a_wrong_password_leaves_nothing(path, team):
    assert leave_document(path, "Bertram", "wrong-Pass-1") is False
    assert unlock(path, "Bertram", ED_PW) is not None


def test_leaving_somebody_who_is_not_there_is_the_same_wrong_password_refusal(path, team):
    assert leave_document(path, "Nobody", "whatever-Pass-1") is False


# --- handing over ownership ------------------------------------------------------------------------------------


def test_the_owner_can_make_an_editor_the_new_owner(path, team):
    assert (
        transfer_owner(
            path, old_owner="Annabelle", old_owner_password=OWNER_PW, new_owner="Bertram", new_owner_password=ED_PW
        )
        is True
    )
    annabelle = unlock(path, "Annabelle", OWNER_PW)
    bertram = unlock(path, "Bertram", ED_PW)
    assert annabelle.role is Role.EDITOR
    assert bertram.role is Role.OWNER
    assert annabelle.keys == bertram.keys == team.keys
    assert [p.name for p in read_people(path, team.keys)] == ["Annabelle", "Bertram", "Cornelia"]


def test_a_wrong_old_owner_password_transfers_nothing(path, team):
    ok = transfer_owner(
        path, old_owner="Annabelle", old_owner_password="wrong-Pass-1", new_owner="Bertram", new_owner_password=ED_PW
    )
    assert ok is False
    assert unlock(path, "Annabelle", OWNER_PW).role is Role.OWNER
    assert unlock(path, "Bertram", ED_PW).role is Role.EDITOR


def test_a_wrong_new_owner_password_transfers_nothing(path, team):
    ok = transfer_owner(
        path, old_owner="Annabelle", old_owner_password=OWNER_PW, new_owner="Bertram", new_owner_password="wrong-Pass-1"
    )
    assert ok is False
    assert unlock(path, "Annabelle", OWNER_PW).role is Role.OWNER
    assert unlock(path, "Bertram", ED_PW).role is Role.EDITOR


def test_only_the_current_owner_can_be_replaced(path, team):
    with pytest.raises(ValueError, match="owner"):
        transfer_owner(
            path, old_owner="Bertram", old_owner_password=ED_PW, new_owner="Cornelia", new_owner_password=VIEW_PW
        )


def test_the_new_owner_must_already_be_an_editor(path, team):
    with pytest.raises(ValueError, match="editor"):
        transfer_owner(
            path, old_owner="Annabelle", old_owner_password=OWNER_PW, new_owner="Cornelia", new_owner_password=VIEW_PW
        )


def test_a_person_cannot_hand_the_document_to_themself(path, team):
    with pytest.raises(ValueError, match="else"):
        transfer_owner(
            path, old_owner="Annabelle", old_owner_password=OWNER_PW, new_owner="Annabelle", new_owner_password=OWNER_PW
        )


# --- the recovery key ----------------------------------------------------------------------------------------------


def test_the_recovery_key_opens_an_owner_slot_that_no_name_can_find(tmp_path):
    recovery = new_recovery_key()
    path = tmp_path / "r.claudia"
    created = create_document(
        path, name="r", app="computes", owner="Ann", password=OWNER_PW, kdf=CHEAP, recovery_key=recovery
    )
    opened = unlock_with_recovery(path, recovery)
    assert opened is not None
    assert opened.role is Role.OWNER
    assert opened.keys == created.keys
    assert unlock_with_recovery(path, new_recovery_key()) is None
    assert [p.name for p in read_people(path, created.keys)] == ["Ann"]  # the key is not a person


def test_a_document_without_a_recovery_key_has_no_way_in_but_a_password(path, owner):
    assert unlock_with_recovery(path, new_recovery_key()) is None


def test_somebody_holding_the_recovery_key_can_give_the_owner_a_new_password(tmp_path):
    recovery = new_recovery_key()
    path = tmp_path / "r.claudia"
    create_document(path, name="r", app="computes", owner="Ann", password=OWNER_PW, kdf=CHEAP, recovery_key=recovery)
    keys = unlock_with_recovery(path, recovery).keys
    remove_user(path, keys, "Ann", allow_last=True)
    add_user(path, keys, "Ann", "Brand-New-Pass-1", Role.OWNER)
    assert unlock(path, "Ann", "Brand-New-Pass-1").role is Role.OWNER
    assert unlock(path, "Ann", OWNER_PW) is None
    assert unlock_with_recovery(path, recovery) is not None  # still there for the next time


# --- writing is atomic -----------------------------------------------------------------------------------------------


def test_a_crash_while_replacing_leaves_the_old_file_whole(path, team, monkeypatch):
    before = path.read_bytes()

    def boom(*args, **kwargs):
        raise OSError("power cut")

    monkeypatch.setattr(container.os, "replace", boom)
    with pytest.raises(OSError, match="power cut"):
        add_user(path, team.keys, "Dora", "Another-Pass-1", Role.EDITOR)
    monkeypatch.undo()
    assert path.read_bytes() == before
    assert unlock(path, "Annabelle", OWNER_PW) is not None
    assert [f.name for f in path.parent.iterdir()] == [path.name]  # no temporary file left behind


# --- reading files from outside ---------------------------------------------------------------------------------


def zip_of(entries, compression=zipfile.ZIP_DEFLATED):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as z:
        for name, data in entries:
            z.writestr(name, data)
    return buffer.getvalue()


def good_entries(path):
    with zipfile.ZipFile(path) as z:
        return [(n, z.read(n)) for n in z.namelist()]


def test_something_that_is_not_a_zip_is_refused(tmp_path):
    bad = tmp_path / "bad.claudia"
    bad.write_bytes(b"this is not a document")
    with pytest.raises(NotAClaudiaDocument):
        read_manifest(bad)


def test_a_zip_that_is_not_a_claudia_document_is_refused(tmp_path):
    bad = tmp_path / "bad.claudia"
    bad.write_bytes(zip_of([("readme.txt", b"hello")]))
    with pytest.raises(NotAClaudiaDocument):
        read_manifest(bad)


def test_a_cut_off_file_is_refused(path, owner):
    path.write_bytes(path.read_bytes()[:-40])
    with pytest.raises(NotAClaudiaDocument):
        read_manifest(path)


def test_a_document_of_a_newer_format_says_so(path, owner):
    entries = [("format", b"claudia-document 3")] + [e for e in good_entries(path) if e[0] != "format"]
    path.write_bytes(zip_of(entries, zipfile.ZIP_STORED))
    with pytest.raises(UnsupportedFormat, match="newer"):
        read_manifest(path)


def test_a_document_of_the_first_format_is_refused_with_a_sentence_of_its_own(path, owner):
    entries = [("format", b"claudia-document 1")] + [e for e in good_entries(path) if e[0] != "format"]
    path.write_bytes(zip_of(entries, zipfile.ZIP_STORED))
    with pytest.raises(OutdatedFormat, match="older version"):
        read_manifest(path)
    assert issubclass(OutdatedFormat, UnsupportedFormat)


@pytest.mark.parametrize(
    "name",
    [
        "../evil",
        "/abs",
        "a/../b",
        "UPPER",
        pytest.param(
            "a\\b",
            marks=pytest.mark.skipif(
                sys.platform == "win32",
                reason="zipfile.ZipInfo replaces os.sep with '/' there, so this arrives as the harmless 'a/b'",
            ),
        ),
        "x" * 200,
    ],
)
def test_entry_names_that_could_leave_a_folder_are_refused(path, owner, name):
    path.write_bytes(zip_of([*good_entries(path), (name, b"x")]))
    with pytest.raises(ReaderLimitExceeded):
        read_manifest(path)


def test_duplicate_entry_names_are_refused(path, owner):
    entries = good_entries(path)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z, pytest.warns(UserWarning):
        for name, data in [*entries, entries[1]]:
            z.writestr(name, data)
    path.write_bytes(buffer.getvalue())
    with pytest.raises(ReaderLimitExceeded):
        read_manifest(path)


def test_a_zip_bomb_is_refused(path, owner):
    path.write_bytes(zip_of([*good_entries(path), ("padding.bin", b"\0" * (64 * 1024 * 1024))]))
    with pytest.raises(ReaderLimitExceeded):
        read_manifest(path)


def test_too_many_entries_are_refused(path, owner):
    many = [(f"history/{i:06d}.blk", b"x") for i in range(container.MAX_ENTRIES + 1)]
    path.write_bytes(zip_of([*good_entries(path), *many]))
    with pytest.raises(ReaderLimitExceeded):
        read_manifest(path)


def test_a_damaged_list_of_people_is_reported_not_guessed(path, team):
    entries = [(n, (bytes([d[0] ^ 1]) + d[1:]) if n == "people.bin" else d) for n, d in good_entries(path)]
    path.write_bytes(zip_of(entries, zipfile.ZIP_STORED))
    with pytest.raises(ContainerError, match="people"):
        read_people(path, team.keys)


def test_person_is_plain_data():
    assert Person("Ann", Role.OWNER, b"\x01" * 16).name == "Ann"


def test_the_journal_lives_next_to_the_file(path):
    assert container.journal_path(path) == path.with_name("plan.claudia.journal")


def test_nothing_is_left_over_after_all_this(path, team):
    assert sorted(os.listdir(path.parent)) == ["plan.claudia"]


# --- the original of an imported document (D439) -------------------------------------------------------------------
def test_the_original_of_an_import_is_kept_sealed_and_read_back_with_the_content_key(path, team):
    from claudia_container.container import read_original, write_original

    keys = unlock(path, "Annabelle", OWNER_PW).keys
    assert read_original(path, keys) is None
    secret = b"PK\x03\x04 a spreadsheet with the word Geheimnis in it"
    write_original(path, keys, secret)
    raw = path.read_bytes()
    assert b"Geheimnis" not in raw, "sealed, not stored in the clear"
    assert read_original(path, keys) == secret
    viewer = unlock(path, "Cornelia", VIEW_PW).keys
    assert read_original(path, viewer) == secret, "whoever may read the content may read the original"
    add_user(path, keys, "Ben", "Battery-Staple-8", Role.EDITOR)
    assert read_original(path, keys) == secret, "a change of the people carries it along"


def test_an_original_sealed_for_another_document_does_not_open(tmp_path, path, owner):
    from claudia_container.container import read_original, write_original

    other_path = tmp_path / "other.claudia"
    other = create_document(other_path, name="other", app="computes", owner="Annabelle", password=OWNER_PW, kdf=CHEAP)
    write_original(other_path, other.keys, b"the other one")
    with zipfile.ZipFile(other_path) as archive:
        stolen = archive.read("content/original.bin")
    keys = unlock(path, "Annabelle", OWNER_PW).keys
    write_original(path, keys, b"mine")
    entries = container._read_entries(path)
    entries["content/original.bin"] = stolen
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    with pytest.raises(container.TamperedDocument):
        read_original(path, keys)


# --- description and tags: a property of the document that anyone with the file may read (D103, D530) ---------------


def test_a_new_document_has_no_description_and_no_tags(path, owner):
    manifest = read_manifest(path)
    assert manifest.description == ""
    assert manifest.tags == ()


def test_a_document_can_be_made_with_a_description_and_tags(path):
    create_document(
        path,
        name="plan",
        app="computes",
        owner="Annabelle",
        password=OWNER_PW,
        kdf=CHEAP,
        description="Budget with **three** scenarios",
        tags=["Finance", "budget"],
    )
    manifest = read_manifest(path)
    assert manifest.description == "Budget with **three** scenarios"
    assert manifest.tags == ("finance", "budget")


def test_description_and_tags_are_readable_without_a_password_and_stored_in_the_clear(path, owner):
    set_details(path, owner.keys, "Cash-flow forecast, Q3", ["finance", "forecast"])
    with zipfile.ZipFile(path) as z:
        plain = json.loads(z.read("manifest.json"))
    assert plain["description"] == "Cash-flow forecast, Q3"
    assert plain["tags"] == ["finance", "forecast"]
    assert read_manifest(path).tags == ("finance", "forecast")


def test_only_the_owner_who_holds_all_keys_may_change_them(path, team):
    viewer = unlock(path, "Cornelia", VIEW_PW)
    with pytest.raises(PermissionError):
        set_details(path, viewer.keys, "mine now", [])
    assert read_manifest(path).description == ""


def test_changing_them_keeps_the_rest_of_the_document_whole(path, team):
    before = read_manifest(path)
    set_details(path, team.keys, "About the budget", ["finance"])
    after = read_manifest(path)
    assert (after.name, after.uid, after.app, after.created, after.salt) == (
        before.name,
        before.uid,
        before.app,
        before.created,
        before.salt,
    )
    assert after.last_change >= before.last_change
    assert [p.name for p in read_people(path, team.keys)] == ["Annabelle", "Bertram", "Cornelia"]
    assert unlock(path, "Bertram", ED_PW) is not None


def test_changing_the_people_keeps_the_description_and_tags(path, team):
    set_details(path, team.keys, "About the budget", ["finance"])
    add_user(path, team.keys, "Dorothea", "Silver-Fox-3-Run", Role.VIEWER)
    change_password(path, "Bertram", ED_PW, "New-Passw0rd-xx")
    manifest = read_manifest(path)
    assert (manifest.description, manifest.tags) == ("About the budget", ("finance",))


def test_a_document_written_before_description_and_tags_existed_still_reads(path, owner):
    with zipfile.ZipFile(path) as z:
        entries = {name: z.read(name) for name in z.namelist()}
    old = json.loads(entries["manifest.json"])
    del old["description"], old["tags"]
    entries["manifest.json"] = json.dumps(old).encode()
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("format", entries.pop("format"), compress_type=zipfile.ZIP_STORED)
        for name, data in entries.items():
            z.writestr(name, data)
    manifest = read_manifest(path)
    assert (manifest.description, manifest.tags) == ("", ())


def test_tags_are_tidied_lower_cased_and_counted_once():
    assert clean_details("  hello  ", ["  Finance ", "finance", "Year  9", "", "  "])[1] == ("finance", "year 9")


def test_a_tag_may_not_hold_a_comma_or_a_control_character():
    with pytest.raises(ValueError, match="comma"):
        clean_details("", ["a,b"])
    with pytest.raises(ValueError, match="control"):
        clean_details("", ["a\x00b"])


def test_the_limits_on_description_and_tags_are_kept():
    with pytest.raises(ValueError, match="description"):
        clean_details("x" * (MAX_DESCRIPTION + 1), [])
    with pytest.raises(ValueError, match="tag"):
        clean_details("", ["x" * (MAX_TAG + 1)])
    with pytest.raises(ValueError, match="tags"):
        clean_details("", [f"t{i}" for i in range(MAX_TAGS + 1)])


def test_a_description_keeps_its_line_breaks_but_loses_stray_control_characters():
    assert clean_details("one\ntwo\x07", [])[0] == "one\ntwo"


def test_a_manifest_with_a_description_or_tags_of_the_wrong_form_is_refused(path, owner):
    for broken in (
        {"description": 5},
        {"tags": "finance"},
        {"tags": [1]},
        {"description": "x" * (MAX_DESCRIPTION + 1)},
    ):
        with zipfile.ZipFile(path) as z:
            entries = {name: z.read(name) for name in z.namelist()}
        manifest = json.loads(entries["manifest.json"])
        manifest.update(broken)
        entries["manifest.json"] = json.dumps(manifest).encode()
        broken_path = path.with_name("broken.claudia")
        with zipfile.ZipFile(broken_path, "w") as z:
            z.writestr("format", entries.pop("format"), compress_type=zipfile.ZIP_STORED)
            for name, data in entries.items():
                z.writestr(name, data)
        with pytest.raises(NotAClaudiaDocument):
            read_manifest(broken_path)


# --- the random id (D533) ------------------------------------------------------------------------------------------


def _tamper(path, **changes):
    """Rewrite the plain manifest of the file with some fields changed, the way anybody with the file could."""
    with zipfile.ZipFile(path) as z:
        entries = {i.filename: z.read(i.filename) for i in z.infolist()}
    manifest = json.loads(entries["manifest.json"])
    manifest.update(changes)
    entries["manifest.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(path, "w") as z:
        for filename, data in entries.items():
            z.writestr(filename, data)


def test_every_new_document_gets_its_own_random_uuid(tmp_path):
    uids = set()
    for number in range(5):
        file = tmp_path / f"d{number}.claudia"
        create_document(file, name="same", app="computes", owner="A", password=OWNER_PW, kdf=CHEAP)
        uids.add(read_manifest(file).uid)
    assert len(uids) == 5
    for uid in uids:
        parsed = uuid.UUID(uid)
        assert (str(parsed), parsed.version) == (uid, 4)


def test_the_manifest_has_a_name_and_a_uid_but_no_id_or_title(path, owner):
    with zipfile.ZipFile(path) as z:
        plain = json.loads(z.read("manifest.json"))
    assert plain["name"] == "plan"
    assert plain["uid"] == read_manifest(path).uid
    assert "id" not in plain
    assert "title" not in plain


def test_the_uid_says_nothing_about_the_owner_or_the_content(path, owner):
    assert "Annabelle" not in read_manifest(path).uid
    assert "plan" not in read_manifest(path).uid


@pytest.mark.parametrize("bad", ["", "plan", "not-a-uuid", "00000000-0000-0000-0000-000000000000", 7, None])
def test_a_manifest_with_a_bad_uid_is_not_a_document(path, owner, bad):
    _tamper(path, uid=bad)
    with pytest.raises(NotAClaudiaDocument):
        read_manifest(path)


def test_a_uid_that_is_not_in_the_canonical_form_is_refused(path, owner):
    _tamper(path, uid=read_manifest(path).uid.upper())
    with pytest.raises(NotAClaudiaDocument):
        read_manifest(path)


def test_a_name_cannot_hold_a_colon_so_name_and_uid_stay_apart(tmp_path):
    with pytest.raises(ValueError, match="name"):
        create_document(tmp_path / "x.claudia", name="a:b", app="computes", owner="A", password=OWNER_PW, kdf=CHEAP)


def test_changing_the_uid_in_the_manifest_locks_everybody_out(path, team):
    _tamper(path, uid=str(uuid.uuid4()))
    assert unlock(path, "Annabelle", OWNER_PW) is None
    assert unlock(path, "Bertram", ED_PW) is None


def test_changing_the_name_in_the_manifest_locks_everybody_out(path, team):
    _tamper(path, name="other")
    assert unlock(path, "Annabelle", OWNER_PW) is None


def test_the_uid_stays_through_every_change_of_the_file(path, team):
    uid = read_manifest(path).uid
    set_details(path, team.keys, "About it", ["x"])
    add_user(path, team.keys, "Dora", "Tangerine-Dream-4", Role.EDITOR)
    change_password(path, "Bertram", ED_PW, "Another-Strong-8")
    assert read_manifest(path).uid == uid
    assert unlock(path, "Dora", "Tangerine-Dream-4") is not None
