"""Changing roles and removing people (E2.3, D1263, D1274): keys are renewed for what somebody loses, and everybody who
stays catches up from her inbox at her next login."""

import contextlib
import io
import zipfile

import pytest

from claudia_document_file import (
    TamperedDocument,
    add_user,
    begin,
    change_password,
    create_document,
    journal_path,
    read_audit,
    read_manifest,
    read_original,
    read_people,
    read_snapshot,
    read_state,
    unlock,
    unlock_with_recovery,
)
from claudia_document_file.audit import AuditRecord
from claudia_document_file.crypto import KdfParams
from claudia_document_file.file import record_audit, write_original
from claudia_document_file.journal import JournalError, read_journal
from claudia_document_file.renewal import RenewalInterrupted, change_role, remove_person
from claudia_document_file.slots import Part, Role, new_recovery_key

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
ANNA, BERT, CORA = ("Annabelle", "Correct-Horse-9"), ("Bertram", "Battery-Staple-7"), ("Cornelia", "Purple-Monkey-5")
DAVE = ("Dagobert", "Orange-Walrus-3")
HISTORY = [b'{"t":"entry","n":1}', b'{"t":"entry","n":2}']
CHAT = [b'{"t":"chat","text":"hello"}']


@pytest.fixture
def path(tmp_path):
    return tmp_path / "plan.claudia"


@pytest.fixture
def recovery():
    return new_recovery_key()


@pytest.fixture
def owner(path, recovery):
    first = create_document(
        path, name="plan", app="computes", owner=ANNA[0], password=ANNA[1], kdf=CHEAP, recovery_key=recovery
    )
    add_user(path, first.keys, BERT[0], BERT[1], Role.EDITOR)
    add_user(path, first.keys, CORA[0], CORA[1], Role.VIEWER)
    return first


@pytest.fixture
def writer(path, owner):
    w = begin(path, owner.keys)
    for payload in HISTORY:
        w.append(Part.HISTORY, payload)
    w.append(Part.CHAT, CHAT[0])
    yield w
    with contextlib.suppress(ValueError):
        w.close()


def zip_names(path) -> set[str]:
    with zipfile.ZipFile(path) as z:
        return set(z.namelist())


def inbox_of(path) -> set[str]:
    return {n for n in zip_names(path) if n.startswith("inbox/")}


def people_of(path, keys) -> dict[str, Role]:
    return {p.name: p.role for p in read_people(path, keys)}


# --- removing a person ---------------------------------------------------------------------------------------------


def test_removing_an_editor_renews_all_three_keys(path, owner, writer):
    done = remove_person(path, owner.keys, writer, BERT[0])
    assert done.renewed == frozenset(Part)
    assert all(done.keys[part] != owner.keys[part] for part in Part)


def test_removing_a_viewer_renews_the_content_key_only(path, owner, writer):
    done = remove_person(path, owner.keys, writer, CORA[0])
    assert done.renewed == frozenset({Part.CONTENT})
    assert done.keys[Part.HISTORY] == owner.keys[Part.HISTORY]
    assert done.keys[Part.CHAT] == owner.keys[Part.CHAT]
    assert done.keys[Part.CONTENT] != owner.keys[Part.CONTENT]


def test_the_list_and_the_slot_of_a_removed_person_are_gone(path, owner, writer):
    done = remove_person(path, owner.keys, writer, BERT[0])
    assert people_of(path, done.keys) == {ANNA[0]: Role.OWNER, CORA[0]: Role.VIEWER}
    assert unlock(path, *BERT) is None


def test_the_removed_person_cannot_open_anything_with_the_old_keys(path, owner, writer):
    remove_person(path, owner.keys, writer, BERT[0])
    with pytest.raises(TamperedDocument):
        read_state(path, owner.keys)
    with pytest.raises(Exception, match="damaged"):
        read_people(path, owner.keys)


def test_the_new_keys_read_the_whole_history_and_chat(path, owner, writer):
    done = remove_person(path, owner.keys, writer, BERT[0])
    state = read_state(path, done.keys)
    assert state.history == HISTORY and state.chat == CHAT


def test_records_still_in_the_journal_are_folded_in_and_the_journal_starts_again(path, owner, writer):
    before = writer.generation
    done = remove_person(path, owner.keys, writer, BERT[0])
    assert done.writer.generation == before + 1
    assert read_state(path, done.keys).pending == 0
    done.writer.append(Part.HISTORY, b'{"t":"entry","n":3}')
    assert read_state(path, done.keys).history == [*HISTORY, b'{"t":"entry","n":3}']
    done.writer.close()


def test_the_journal_is_sealed_under_the_new_keys(path, owner, writer):
    done = remove_person(path, owner.keys, writer, BERT[0])
    done.writer.append(Part.HISTORY, b'{"t":"entry","n":3}')
    manifest_binding = read_manifest(path).binding
    assert [r.payload for r in read_journal(journal_path(path), manifest_binding, done.keys)] == [
        b'{"t":"entry","n":3}'
    ]
    with pytest.raises(JournalError):
        read_journal(journal_path(path), manifest_binding, owner.keys)
    done.writer.close()


def test_the_record_of_what_left_is_sealed_again_and_kept(path, owner, writer):
    record_audit(path, owner.keys, AuditRecord("export", ANNA[0], "2026-11-19T10:00:00Z", "docx", ("content",), None))
    done = remove_person(path, owner.keys, writer, BERT[0])
    assert [r.who for r in read_audit(path, done.keys)] == [ANNA[0]]
    done.writer.close()


def test_the_kept_original_is_sealed_again(path, owner, writer):
    write_original(path, owner.keys, b"the imported file")
    done = remove_person(path, owner.keys, writer, CORA[0])  # a viewer: the content key is renewed
    assert read_original(path, done.keys) == b"the imported file"
    with pytest.raises(TamperedDocument):
        read_original(path, owner.keys)
    done.writer.close()


def test_the_snapshot_is_given_with_the_new_keys_or_left_out(path, owner, writer):
    done = remove_person(path, owner.keys, writer, CORA[0], snapshot=b"state")
    assert read_snapshot(path, done.keys) == b"state"
    again = remove_person(path, done.keys, done.writer, BERT[0])
    assert read_snapshot(path, again.keys) is None
    again.writer.close()


def test_the_last_owner_cannot_be_removed(path, owner, writer):
    with pytest.raises(ValueError, match="at least one owner"):
        remove_person(path, owner.keys, writer, ANNA[0])
    assert read_state(path, owner.keys).history == HISTORY  # nothing changed


def test_somebody_who_is_not_there_is_a_key_error(path, owner, writer):
    with pytest.raises(KeyError):
        remove_person(path, owner.keys, writer, "Nobody")


def test_only_somebody_with_all_the_keys_can_do_it(path, owner, writer):
    viewer = unlock(path, *CORA)
    with pytest.raises(PermissionError):
        remove_person(path, viewer.keys, writer, BERT[0])
    with pytest.raises(PermissionError):
        change_role(path, viewer.keys, writer, BERT[0], Role.VIEWER)


# --- everybody who stays catches up at the next login --------------------------------------------------------------


def test_everybody_who_stays_and_the_recovery_key_have_a_letter(path, owner, writer):
    remove_person(path, owner.keys, writer, BERT[0])
    assert len(inbox_of(path)) == 3  # Annabelle, Cornelia and the recovery key


def test_a_person_who_stays_gets_the_new_keys_at_her_next_login_and_the_letter_goes(path, owner, writer):
    done = remove_person(path, owner.keys, writer, BERT[0])
    cora = unlock(path, *CORA)
    assert cora.role is Role.VIEWER and cora.keys == {Part.CONTENT: done.keys[Part.CONTENT]}
    assert len(inbox_of(path)) == 2
    assert unlock(path, *CORA).keys == cora.keys  # and again: the slot itself is up to date now


def test_an_owner_who_was_away_logs_in_with_the_new_keys(path, owner, writer):
    done = remove_person(path, owner.keys, writer, BERT[0])
    anna = unlock(path, *ANNA)
    assert anna.keys == done.keys and anna.private_key == owner.private_key and anna.private == owner.private
    done.writer.close()
    assert read_state(path, anna.keys).history == HISTORY


def test_somebody_who_was_away_for_two_renewals_needs_only_the_newest_letter(path, owner, writer):
    first = remove_person(path, owner.keys, writer, BERT[0])
    add_user(path, first.keys, *DAVE, Role.EDITOR)
    second = remove_person(path, first.keys, first.writer, DAVE[0])
    assert len(inbox_of(path)) == 3  # one each, not one per renewal
    anna = unlock(path, *ANNA)
    assert anna.keys == second.keys
    second.writer.close()


def test_the_recovery_key_opens_with_the_new_keys(path, owner, writer, recovery):
    done = remove_person(path, owner.keys, writer, BERT[0])
    opened = unlock_with_recovery(path, recovery)
    assert opened.keys == done.keys and opened.role is Role.OWNER
    assert len(inbox_of(path)) == 2


def test_a_password_change_takes_in_the_letter_first(path, owner, writer):
    done = remove_person(path, owner.keys, writer, BERT[0])
    assert change_password(path, CORA[0], CORA[1], "Fresh-Walnut-8")
    assert unlock(path, CORA[0], "Fresh-Walnut-8").keys == {Part.CONTENT: done.keys[Part.CONTENT]}
    assert len(inbox_of(path)) == 2


# --- a forged letter locks nobody out ------------------------------------------------------------------------------


def rewritten(path, change) -> None:
    """Rewrite the zip of ``path`` with ``change`` applied to its entries (what a file from outside can do)."""
    with zipfile.ZipFile(path) as z:
        entries = {i.filename: z.read(i.filename) for i in z.infolist()}
    change(entries)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data, compress_type=zipfile.ZIP_STORED)
    path.write_bytes(buffer.getvalue())


def letter_name_of(path, who) -> str:
    from claudia_document_file.crypto import derive_login_material
    from claudia_document_file.file import _inbox_name, _manifest_of, _read_entries

    entries = _read_entries(path)
    manifest = _manifest_of(entries, path)
    return _inbox_name(derive_login_material(who[1], who[0], manifest.salt, manifest.kdf).locator)


def test_a_letter_of_noise_is_ignored(path, owner, writer):
    done = remove_person(path, owner.keys, writer, CORA[0])
    name = letter_name_of(path, BERT)
    rewritten(path, lambda e: e.__setitem__(name, b"x" * 200))
    bert = unlock(path, *BERT)
    assert bert is not None and bert.keys[Part.HISTORY] == owner.keys[Part.HISTORY]
    done.writer.close()


def test_a_letter_that_was_swapped_to_another_person_is_ignored(path, owner, writer):
    done = remove_person(path, owner.keys, writer, CORA[0])
    anna_name, bert_name = letter_name_of(path, ANNA), letter_name_of(path, BERT)

    def swap(e):
        e[anna_name], e[bert_name] = e[bert_name], e[anna_name]

    rewritten(path, swap)
    # neither can open the other's letter; both stay as they were, which still opens their slot
    assert unlock(path, *ANNA).keys == owner.keys
    assert unlock(path, *BERT).keys == owner.keys
    done.writer.close()


def test_a_letter_with_keys_that_open_nothing_is_ignored(path, owner, writer):
    from claudia_document_file.crypto import random_key
    from claudia_document_file.file import _inbox_name, _letter, _manifest_of, _open_people_data, _read_entries

    done = remove_person(path, owner.keys, writer, CORA[0])
    entries = _read_entries(path)
    manifest = _manifest_of(entries, path)
    people, _ = _open_people_data(entries, manifest, done.keys)
    bert = next(p for p in people if p.name == BERT[0])
    forged = _letter(manifest, bert.locator, bert.public_key, Role.EDITOR, {part: random_key() for part in Part})
    rewritten(path, lambda e: e.__setitem__(_inbox_name(bert.locator), forged))
    assert unlock(path, *BERT).keys == owner.keys  # not locked out: the slot is as it was
    done.writer.close()


# --- changing a role -----------------------------------------------------------------------------------------------


def test_raising_a_viewer_to_editor_renews_nothing_and_the_letter_gives_her_the_keys(path, owner, writer):
    done = change_role(path, owner.keys, writer, CORA[0], Role.EDITOR)
    assert done.renewed == frozenset() and done.keys == owner.keys and done.writer is writer
    assert people_of(path, owner.keys)[CORA[0]] is Role.EDITOR
    cora = unlock(path, *CORA)
    assert cora.role is Role.EDITOR and cora.keys == owner.keys
    assert len(inbox_of(path)) == 0


def test_moving_between_editor_and_owner_renews_nothing(path, owner, writer):
    change_role(path, owner.keys, writer, BERT[0], Role.OWNER)
    assert unlock(path, *BERT).role is Role.OWNER
    change_role(path, owner.keys, writer, BERT[0], Role.EDITOR)
    assert unlock(path, *BERT).role is Role.EDITOR


def test_lowering_an_editor_renews_the_history_and_the_chat_key_not_the_content_key(path, owner, writer):
    done = change_role(path, owner.keys, writer, BERT[0], Role.VIEWER)
    assert done.renewed == frozenset({Part.HISTORY, Part.CHAT})
    assert done.keys[Part.CONTENT] == owner.keys[Part.CONTENT]
    bert = unlock(path, *BERT)
    assert bert.role is Role.VIEWER and bert.keys == {Part.CONTENT: owner.keys[Part.CONTENT]}
    assert people_of(path, bert.keys)[BERT[0]] is Role.VIEWER
    with pytest.raises(TamperedDocument):
        read_state(path, owner.keys)  # what he held opens nothing new
    assert read_state(path, done.keys).history == HISTORY
    done.writer.close()


def test_a_lowered_person_who_was_never_asked_again_still_gets_only_what_a_viewer_gets(path, owner, writer):
    done = change_role(path, owner.keys, writer, BERT[0], Role.VIEWER)
    # his slot still says editor, with keys of before: he logs in and is a viewer, whatever the slot says
    bert = unlock(path, *BERT)
    assert Part.HISTORY not in bert.keys and Part.CHAT not in bert.keys
    done.writer.close()


def test_the_same_role_changes_nothing(path, owner, writer):
    before = path.read_bytes()
    done = change_role(path, owner.keys, writer, BERT[0], Role.EDITOR)
    assert done.renewed == frozenset() and path.read_bytes() == before


def test_the_last_owner_cannot_be_lowered(path, owner, writer):
    with pytest.raises(ValueError, match="at least one owner"):
        change_role(path, owner.keys, writer, ANNA[0], Role.EDITOR)


def test_an_owner_can_be_lowered_when_there_is_another(path, owner, writer):
    change_role(path, owner.keys, writer, BERT[0], Role.OWNER)
    done = change_role(path, owner.keys, writer, ANNA[0], Role.VIEWER)
    assert done.renewed == frozenset({Part.HISTORY, Part.CHAT})
    done.writer.close()


# --- crash safety ----------------------------------------------------------------------------------------------------


def test_a_crash_while_the_file_is_written_changes_nothing(path, owner, writer, monkeypatch):
    before = path.read_bytes()

    def crash(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("claudia_document_file.renewal._write_zip", crash)
    with pytest.raises(OSError):
        remove_person(path, owner.keys, writer, BERT[0])
    assert path.read_bytes() == before
    assert read_state(path, owner.keys).history == HISTORY
    writer.append(Part.HISTORY, b'{"t":"entry","n":3}')  # the journal is still the open one


def test_a_crash_between_the_file_and_the_journal_loses_nothing(path, owner, writer, monkeypatch):
    def crash(*args, **kwargs):
        raise OSError("power out")

    monkeypatch.setattr("claudia_document_file.renewal.JournalWriter.replace", crash)
    with pytest.raises(RenewalInterrupted) as stopped:
        remove_person(path, owner.keys, writer, BERT[0])
    monkeypatch.undo()
    anna = unlock(path, *ANNA)  # the file is the new one; the journal is the old one, which it has taken in
    assert anna.keys == stopped.value.keys  # the error carries the new keys, so an open document can go on
    state = read_state(path, anna.keys)
    assert state.history == HISTORY and state.chat == CHAT and state.pending == 0
    resumed = begin(path, anna.keys)
    assert resumed.generation == writer.generation + 1
    resumed.close()


# --- nothing in the file tells --------------------------------------------------------------------------------------


def test_the_file_shows_no_name_no_password_and_no_text_after_a_renewal(path, owner, writer):
    done = remove_person(path, owner.keys, writer, BERT[0])
    done.writer.close()
    blob = b"".join(
        zipfile.ZipFile(path).read(n) for n in zipfile.ZipFile(path).namelist() if n not in ("manifest.json",)
    )
    for secret in (ANNA[0], BERT[0], CORA[0], ANNA[1], BERT[1], CORA[1], b"hello".decode()):
        assert secret.encode() not in blob
    assert b"hello" not in journal_path(path).read_bytes()
    assert b"Bertram" not in path.read_bytes()


def test_a_removed_person_leaves_nothing_of_her_own_behind(path, owner, writer):
    bert = unlock(path, *BERT)
    done = remove_person(path, owner.keys, writer, BERT[0])
    assert not any(n.startswith(f"private/{bert.private.id}/") for n in zip_names(path))
    done.writer.close()


def test_the_other_peoples_private_notes_are_not_touched_by_a_renewal(path, owner, writer):
    def private_bytes():
        with zipfile.ZipFile(path) as z:
            return {n: z.read(n) for n in z.namelist() if n.startswith(f"private/{owner.private.id}/")}

    before = private_bytes()
    done = remove_person(path, owner.keys, writer, BERT[0])
    assert before and private_bytes() == before
    done.writer.close()
