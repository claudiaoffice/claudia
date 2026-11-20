"""The sealed copy of a document for one person (D110, D1270, E2.12).

Owners get the whole file. Editors and viewers get a file with only their own key slot, and a viewer's file has only
the parts the content key opens: no history, no chat, no head."""

import io
import json
import zipfile
from pathlib import Path

import pytest

from claudia_container import container
from claudia_container.container import (
    add_user,
    begin,
    create_document,
    pack_journal,
    read_snapshot,
    read_state,
    sealed_copy,
    set_recovery_key,
    unlock,
)
from claudia_container.crypto import KdfParams
from claudia_container.slots import Domain, Role, new_recovery_key

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
OWNER, EDITOR, VIEWER = ("Annabelle", "Correct-Horse-9"), ("Bertram", "Battery-Staple-7"), ("Carla", "Purple-Monkey-5")


@pytest.fixture
def path(tmp_path):
    return tmp_path / "plan.claudia"


@pytest.fixture
def team(path):
    """A document with an owner, an editor and a viewer, a recovery key, two changes and a chat line, packed with a
    snapshot (the server does that before it makes a copy)."""
    owner = create_document(path, name="plan", app="computes", owner=OWNER[0], password=OWNER[1], kdf=CHEAP)
    add_user(path, owner.keys, EDITOR[0], EDITOR[1], Role.EDITOR)
    add_user(path, owner.keys, VIEWER[0], VIEWER[1], Role.VIEWER)
    set_recovery_key(path, owner.keys, new_recovery_key())
    writer = begin(path, owner.keys)
    writer.append(Domain.HISTORY, b"first change")
    writer.append(Domain.HISTORY, b"second change")
    writer.append(Domain.CHAT, b"hello")
    pack_journal(path, owner.keys, writer, snapshot=b'{"cells": 2}').close()
    return owner


def copy_of(path: Path, who, tmp_path: Path) -> Path:
    data = sealed_copy(path, *who)
    assert data is not None
    target = tmp_path / "copy" / "plan.claudia"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(data)
    return target


def names(data: bytes) -> set[str]:
    return set(zipfile.ZipFile(io.BytesIO(data)).namelist())


def slot_count(data: bytes) -> int:
    return len(json.loads(zipfile.ZipFile(io.BytesIO(data)).read("slots.json"))["slots"])


def test_an_owner_gets_the_whole_file(path, team, tmp_path):
    data = sealed_copy(path, *OWNER)
    assert names(data) == names(path.read_bytes())
    assert slot_count(data) == 4  # owner, editor, viewer and the recovery key's slot
    copy = copy_of(path, OWNER, tmp_path)
    assert read_state(copy, unlock(copy, *OWNER).keys).history == [b"first change", b"second change"]


def test_an_editor_gets_the_file_with_only_her_own_slot(path, team, tmp_path):
    data = sealed_copy(path, *EDITOR)
    assert slot_count(data) == 1
    whole = names(path.read_bytes())
    assert {n for n in names(data) if not n.startswith("private/")} == {
        n for n in whole if not n.startswith("private/")
    }
    assert (
        len({n.split("/")[1] for n in names(data) if n.startswith("private/")}) == 1
    )  # her own domain, not the others'
    assert len({n.split("/")[1] for n in whole if n.startswith("private/")}) == 3
    copy = copy_of(path, EDITOR, tmp_path)
    keys = unlock(copy, *EDITOR).keys
    assert read_state(copy, keys).history == [b"first change", b"second change"]
    assert read_state(copy, keys).chat == [b"hello"]


@pytest.mark.parametrize("other", [OWNER, VIEWER])
def test_nobody_else_gets_in_to_an_editors_copy(path, team, tmp_path, other):
    copy = copy_of(path, EDITOR, tmp_path)
    assert unlock(copy, other[0], other[1]) is None


def test_a_recovery_key_does_not_open_a_non_owners_copy(path, team, tmp_path):
    copy = copy_of(path, EDITOR, tmp_path)
    assert container.unlock_with_recovery(copy, new_recovery_key()) is None
    assert slot_count(copy.read_bytes()) == 1


def test_a_viewer_gets_the_parts_the_content_key_opens_and_no_more(path, team, tmp_path):
    data = sealed_copy(path, *VIEWER)
    assert slot_count(data) == 1
    held = names(data)
    assert not any(name.startswith(("history/", "chat/")) for name in held)
    assert "head.bin" not in held
    assert {"format", "manifest.json", "slots.json", "people.bin", "content/snapshot.bin"} <= held
    copy = copy_of(path, VIEWER, tmp_path)
    unlocked = unlock(copy, *VIEWER)
    assert set(unlocked.keys) == {Domain.CONTENT}
    assert read_snapshot(copy, unlocked.keys) == b'{"cells": 2}'


def test_a_viewers_copy_holds_none_of_the_history_even_sealed(path, team):
    history_blocks = [n for n in names(path.read_bytes()) if n.startswith(("history/", "chat/"))]
    assert history_blocks  # the source has them, so the absence above means something
    data = sealed_copy(path, *VIEWER)
    for name in history_blocks:
        assert zipfile.ZipFile(path).read(name) not in data


@pytest.mark.parametrize("who", [("Annabelle", "wrong-one-1A"), ("Nobody", "Correct-Horse-9")])
def test_a_wrong_name_or_password_gets_nothing(path, team, who):
    assert sealed_copy(path, *who) is None


def test_the_source_file_is_not_changed(path, team):
    before = path.read_bytes()
    sealed_copy(path, *VIEWER)
    assert path.read_bytes() == before


def test_the_copy_is_a_complete_document_of_its_own(path, team, tmp_path):
    copy = copy_of(path, VIEWER, tmp_path)
    original = container.read_manifest(path)
    assert container.read_manifest(copy).uid == original.uid
