"""Packing the journal into blocks, the head record and the snapshot (E2.1, E2.5).

Section 6 of the design: tests 4 (a changed, swapped, removed or foreign block is found), 5 (a crash loses nothing that
was acknowledged) and 6 (a viewer's key opens neither history nor chat)."""

import contextlib
import os
import zipfile
from pathlib import Path

import pytest

from claudia_container import blocks, container
from claudia_container.container import (
    TamperedDocument,
    add_user,
    begin,
    change_password,
    create_document,
    journal_path,
    pack_journal,
    read_snapshot,
    read_state,
    remove_user,
    unlock,
)
from claudia_container.crypto import KdfParams
from claudia_container.journal import JournalWriter, read_journal
from claudia_container.slots import Domain, Role

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
OWNER_PW, ED_PW, VIEW_PW = "Correct-Horse-9", "Battery-Staple-7", "Purple-Monkey-5"


def make(path: Path, doc_id="plan"):
    return create_document(
        path, doc_id=doc_id, app="computes", title="t", owner="Annabelle", password=OWNER_PW, kdf=CHEAP
    )


@pytest.fixture
def path(tmp_path):
    return tmp_path / "plan.claudia"


@pytest.fixture
def owner(path):
    return make(path)


@pytest.fixture
def writer(path, owner):
    w = begin(path, owner.keys)
    yield w
    with contextlib.suppress(ValueError):
        w.close()


def put(writer, history=(), chat=()):
    for payload in history:
        writer.append(Domain.HISTORY, payload)
    for payload in chat:
        writer.append(Domain.CHAT, payload)


def entries(path):
    with zipfile.ZipFile(path) as z:
        return {name: z.read(name) for name in z.namelist()}


def rewrite(path, entries_):
    """Write a zip from entries as an outsider with a zip tool would."""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("format", entries_["format"], compress_type=zipfile.ZIP_STORED)
        for name, data in entries_.items():
            if name != "format":
                z.writestr(name, data)


H = [b'{"t":"entry","n":1}', b'{"t":"entry","n":2}', b'{"t":"entry","n":3}']
C = [b'{"t":"chat","n":1}', b'{"t":"chat","n":2}']


# --- a new document, and the journal ----------------------------------------------------------------------------


def test_a_new_document_has_no_history_and_starts_its_journal_at_generation_zero(path, owner, writer):
    state = read_state(path, owner.keys)
    assert (state.history, state.chat, state.snapshot, state.pending) == ([], [], None, 0)
    assert journal_path(path).exists()
    assert writer.generation == 0


def test_what_is_written_to_the_journal_is_read_back_in_order(path, owner, writer):
    put(writer, H, C)
    state = read_state(path, owner.keys)
    assert (state.history, state.chat, state.pending) == (H, C, 5)


def test_begin_continues_an_existing_journal_and_repairs_a_cut_off_record(path, owner, writer):
    put(writer, H)
    writer.close()
    journal = journal_path(path)
    journal.write_bytes(journal.read_bytes()[:-5])  # the power went out while the last record was written
    again = begin(path, owner.keys)
    assert read_state(path, owner.keys).history == H[:2]
    again.append(Domain.HISTORY, b"after the crash")
    assert read_state(path, owner.keys).history == [*H[:2], b"after the crash"]
    again.close()


# --- packing -------------------------------------------------------------------------------------------------------


def test_packing_moves_the_journal_into_sealed_blocks_and_starts_the_next_generation(path, owner, writer):
    put(writer, H, C)
    fresh = pack_journal(path, owner.keys, writer)
    names = set(entries(path))
    assert {"head.bin", "history/000001.blk", "chat/000001.blk"} <= names
    assert fresh.generation == 1 and fresh.seq == 0
    assert read_journal(journal_path(path), "plan", owner.keys) == []
    state = read_state(path, owner.keys)
    assert (state.history, state.chat, state.pending) == (H, C, 0)
    fresh.close()


def test_a_packed_document_shows_nothing_readable(path, owner, writer):
    put(writer, [b"the-forecast-is-confidential-4711"], [b"whisper-4711"])
    pack_journal(path, owner.keys, writer, snapshot=b"snapshot-secret-4711").close()
    on_disk = b"".join(entries(path).values()) + journal_path(path).read_bytes() + path.read_bytes()
    for secret in (b"confidential", b"whisper", b"snapshot-secret", b"Annabelle", OWNER_PW.encode()):
        assert secret not in on_disk


def test_work_after_a_pack_goes_to_the_new_journal_and_a_second_pack_extends_the_chain(path, owner, writer):
    put(writer, H[:2], C[:1])
    fresh = pack_journal(path, owner.keys, writer)
    put(fresh, H[2:], C[1:])
    assert read_state(path, owner.keys).history == H
    last = pack_journal(path, owner.keys, fresh)
    state = read_state(path, owner.keys)
    assert (state.history, state.chat, state.pending) == (H, C, 0)
    assert last.generation == 2
    last.close()


def test_small_packs_are_merged_into_the_last_block_so_blocks_stay_few(path, owner, writer):
    for round_ in range(5):
        put(writer, [f"entry {round_}".encode()])
        writer = pack_journal(path, owner.keys, writer)
    assert [n for n in entries(path) if n.startswith("history/")] == ["history/000001.blk"]
    assert read_state(path, owner.keys).history == [f"entry {i}".encode() for i in range(5)]
    writer.close()


def test_big_histories_are_cut_into_blocks_that_stay_chained(path, owner, writer, monkeypatch):
    monkeypatch.setattr(blocks, "BLOCK_TARGET_BYTES", 100)
    payloads = [f"payload number {i:03d} ".encode() * 3 for i in range(30)]
    put(writer, payloads)
    pack_journal(path, owner.keys, writer).close()
    names = sorted(n for n in entries(path) if n.startswith("history/"))
    assert len(names) > 5
    assert names == [f"history/{i:06d}.blk" for i in range(1, len(names) + 1)]
    assert read_state(path, owner.keys).history == payloads


def test_the_manifest_notes_the_change(path, owner, writer):
    before = container.read_manifest(path).last_change
    put(writer, H)
    pack_journal(path, owner.keys, writer).close()
    assert container.read_manifest(path).last_change >= before


def test_a_failed_pack_changes_nothing_and_leaves_no_temporary_file(path, owner, writer, monkeypatch):
    put(writer, H, C)
    before = path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="disk full"):
        pack_journal(path, owner.keys, writer)
    monkeypatch.undo()
    assert path.read_bytes() == before
    assert sorted(p.name for p in path.parent.iterdir()) == ["plan.claudia", "plan.claudia.journal"]
    assert read_state(path, owner.keys).history == H


# --- a crash in the middle of packing (test 5) ----------------------------------------------------------------------


def test_a_crash_between_the_new_file_and_the_new_journal_loses_nothing_and_repeats_nothing(path, owner, writer):
    put(writer, H, C)
    writer.close()
    # the first half of a pack: the zip is replaced, the journal of generation 0 is still there
    container._pack_blocks(path, owner.keys, history=H, chat=C, snapshot=None, generation=0)
    assert read_journal(journal_path(path), "plan", owner.keys)  # still holds everything
    state = read_state(path, owner.keys)
    assert (state.history, state.chat, state.pending) == (H, C, 0)  # counted once
    resumed = begin(path, owner.keys)  # the next start replaces the old journal
    assert resumed.generation == 1
    put(resumed, [b"new"])
    assert read_state(path, owner.keys).history == [*H, b"new"]
    resumed.close()


def test_a_crash_before_the_new_file_leaves_the_old_state(path, owner, writer):
    put(writer, H)
    writer.close()
    (path.parent / f".{path.name}.{os.getpid()}.tmp").write_bytes(b"half a file")  # what a crash leaves behind
    assert read_state(path, owner.keys).history == H
    again = begin(path, owner.keys)
    pack_journal(path, owner.keys, again).close()
    assert read_state(path, owner.keys).history == H


def test_a_journal_that_does_not_follow_the_file_is_an_error(path, owner, writer):
    put(writer, H)
    pack_journal(path, owner.keys, writer).close()
    with zipfile.ZipFile(path) as z:
        stale = {n: z.read(n) for n in z.namelist() if not n.startswith(("history/", "head"))}
    rewrite(path, stale)  # somebody took the blocks and the head out: the journal is one generation ahead
    with pytest.raises(TamperedDocument, match="journal"):
        read_state(path, owner.keys)


# --- tampering (test 4) ---------------------------------------------------------------------------------------------


@pytest.fixture
def packed(path, owner, writer, monkeypatch):
    monkeypatch.setattr(blocks, "BLOCK_TARGET_BYTES", 60)
    put(writer, [f"history payload {i}".encode() * 2 for i in range(12)], [f"chat {i}".encode() * 3 for i in range(6)])
    pack_journal(path, owner.keys, writer).close()
    return entries(path)


def test_a_changed_block_is_found(path, owner, packed):
    data = bytearray(packed["history/000002.blk"])
    data[10] ^= 1
    rewrite(path, {**packed, "history/000002.blk": bytes(data)})
    with pytest.raises(TamperedDocument):
        read_state(path, owner.keys)


def test_two_swapped_blocks_are_found(path, owner, packed):
    first, second = packed["history/000001.blk"], packed["history/000002.blk"]
    swapped = {**packed, "history/000001.blk": second, "history/000002.blk": first}
    rewrite(path, swapped)
    with pytest.raises(TamperedDocument):
        read_state(path, owner.keys)


def test_a_removed_last_block_is_found_through_the_head(path, owner, packed):
    names = sorted(n for n in packed if n.startswith("history/"))
    rewrite(path, {n: d for n, d in packed.items() if n != names[-1]})
    with pytest.raises(TamperedDocument, match="head|block"):
        read_state(path, owner.keys)


def test_a_removed_chat_block_is_found(path, owner, packed):
    rewrite(path, {n: d for n, d in packed.items() if n != "chat/000001.blk"})
    with pytest.raises(TamperedDocument):
        read_state(path, owner.keys)


def test_a_removed_head_with_blocks_present_is_found(path, owner, packed):
    rewrite(path, {n: d for n, d in packed.items() if n != "head.bin"})
    with pytest.raises(TamperedDocument, match="head"):
        read_state(path, owner.keys)


def test_an_old_head_with_newer_blocks_is_found(path, owner, writer, packed):
    old_head = packed["head.bin"]
    fresh = begin(path, owner.keys)
    put(fresh, [b"more history"])
    pack_journal(path, owner.keys, fresh).close()
    rewrite(path, {**entries(path), "head.bin": old_head})
    with pytest.raises(TamperedDocument):
        read_state(path, owner.keys)


def test_a_block_from_another_document_is_found(tmp_path, path, owner, packed):
    other_path = tmp_path / "other.claudia"
    other = make(other_path, "other")
    w = begin(other_path, other.keys)
    put(w, [f"history payload {i}".encode() * 2 for i in range(12)])
    pack_journal(other_path, other.keys, w).close()
    foreign = entries(other_path)["history/000001.blk"]
    rewrite(path, {**packed, "history/000001.blk": foreign})
    with pytest.raises(TamperedDocument):
        read_state(path, owner.keys)


def test_unexpected_names_in_the_block_folders_are_refused(path, owner, packed):
    rewrite(path, {**packed, "history/extra.blk": b"x"})
    with pytest.raises(TamperedDocument):
        read_state(path, owner.keys)


def test_a_block_missing_in_the_middle_is_found(path, owner, packed):
    rewrite(path, {n: d for n, d in packed.items() if n != "history/000002.blk"})
    with pytest.raises(TamperedDocument):
        read_state(path, owner.keys)


# --- who can read what (test 6) -------------------------------------------------------------------------------------


def test_a_viewer_holds_no_key_for_history_or_chat(path, owner, writer):
    add_user(path, owner.keys, "Cornelia", VIEW_PW, Role.VIEWER)
    add_user(path, owner.keys, "Bertram", ED_PW, Role.EDITOR)
    put(writer, H, C)
    pack_journal(path, owner.keys, writer, snapshot=b"the state").close()
    viewer = unlock(path, "Cornelia", VIEW_PW)
    editor = unlock(path, "Bertram", ED_PW)
    assert set(viewer.keys) == {Domain.CONTENT}
    with pytest.raises(PermissionError):
        read_state(path, viewer.keys)
    assert read_state(path, editor.keys).history == H
    assert read_snapshot(path, viewer.keys) == b"the state"  # a viewer reads the content (D101)


# --- the snapshot ---------------------------------------------------------------------------------------------------


def test_the_snapshot_is_kept_until_it_is_replaced_or_dropped(path, owner, writer):
    assert read_snapshot(path, owner.keys) is None
    put(writer, H)
    w = pack_journal(path, owner.keys, writer, snapshot=b"state at 3")
    assert read_snapshot(path, owner.keys) == b"state at 3"
    assert read_state(path, owner.keys).snapshot == b"state at 3"
    w = pack_journal(path, owner.keys, w, snapshot=b"state at 4")
    assert read_snapshot(path, owner.keys) == b"state at 4"
    w = pack_journal(path, owner.keys, w, snapshot=None)
    assert read_snapshot(path, owner.keys) is None
    assert "content/snapshot.bin" not in entries(path)
    w.close()


def test_a_snapshot_that_cannot_be_opened_is_a_missing_cache_not_an_error(path, owner, writer):
    put(writer, H)
    pack_journal(path, owner.keys, writer, snapshot=b"state").close()
    data = bytearray(entries(path)["content/snapshot.bin"])
    data[-1] ^= 1
    rewrite(path, {**entries(path), "content/snapshot.bin": bytes(data)})
    assert read_snapshot(path, owner.keys) is None
    assert read_state(path, owner.keys).history == H


def test_a_snapshot_of_another_document_is_not_accepted(tmp_path, path, owner, writer):
    other_path = tmp_path / "other.claudia"
    other = make(other_path, "other")
    pack_journal(other_path, other.keys, begin(other_path, other.keys), snapshot=b"foreign").close()
    rewrite(path, {**entries(path), "content/snapshot.bin": entries(other_path)["content/snapshot.bin"]})
    assert read_snapshot(path, owner.keys) is None


# --- changing the people keeps the packed content -----------------------------------------------------------------


def test_adding_removing_and_changing_people_keeps_blocks_head_and_snapshot(path, owner, writer):
    put(writer, H, C)
    pack_journal(path, owner.keys, writer, snapshot=b"state").close()
    before = {n: d for n, d in entries(path).items() if n.startswith(("history/", "chat/", "head", "content/"))}
    add_user(path, owner.keys, "Bertram", ED_PW, Role.EDITOR)
    assert change_password(path, "Bertram", ED_PW, "New-Password-1")
    remove_user(path, owner.keys, "Bertram")
    after = {n: d for n, d in entries(path).items() if n.startswith(("history/", "chat/", "head", "content/"))}
    assert after == before
    state = read_state(path, owner.keys)
    assert (state.history, state.chat, state.snapshot) == (H, C, b"state")


# --- the journal itself ---------------------------------------------------------------------------------------------


def test_a_journal_can_be_replaced_by_the_next_generation_atomically(tmp_path, owner):
    from claudia_container.journal import journal_generation

    target = tmp_path / "x.journal"
    first = JournalWriter.create(target, "plan", owner.keys)
    first.append(Domain.HISTORY, b"old")
    first.close()
    assert journal_generation(target) == 0
    second = JournalWriter.replace(target, "plan", owner.keys, generation=1)
    assert (journal_generation(target), second.seq) == (1, 0)
    assert read_journal(target, "plan", owner.keys) == []
    assert target.stat().st_mode & 0o777 == 0o600
    second.append(Domain.HISTORY, b"new")
    second.close()
    assert [r.payload for r in read_journal(target, "plan", owner.keys)] == [b"new"]
    assert sorted(p.name for p in tmp_path.iterdir() if p.name.startswith(("x", "."))) == ["x.journal"]
