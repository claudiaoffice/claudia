"""Rewriting a document for a redaction (D725, SEC-05): afterwards neither the file nor the journal holds what was
redacted, in the clear or sealed, in a block, the journal or the snapshot."""

import contextlib
import zipfile
from pathlib import Path

import pytest

from claudia_document_file import (
    begin,
    create_document,
    forget_original,
    journal_path,
    pack_journal,
    read_manifest,
    read_original,
    read_state,
    rewrite_journal,
    write_original,
)
from claudia_document_file.crypto import KdfParams
from claudia_document_file.journal import read_journal
from claudia_document_file.slots import Domain

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
SECRET = b"hunter2-4711"
BEFORE = [b'{"t":"entry","n":1}', b'{"t":"entry","secret":"' + SECRET + b'"}', b'{"t":"entry","n":3}']
AFTER = [b'{"t":"entry","n":1}', b'{"t":"entry","redacted":true}', b'{"t":"entry","n":3}']


@pytest.fixture
def path(tmp_path):
    return tmp_path / "plan.claudia"


@pytest.fixture
def owner(path):
    return create_document(path, name="plan", app="computes", owner="Annabelle", password="Correct-Horse-9", kdf=CHEAP)


@pytest.fixture
def writer(path, owner):
    w = begin(path, owner.keys)
    yield w
    with contextlib.suppress(ValueError):
        w.close()


def everything_opened(path: Path, keys) -> bytes:
    """Every byte the document folder holds, and every sealed entry and journal record opened with the keys."""
    folder = b"".join(p.read_bytes() for p in path.parent.iterdir() if p.is_file())
    state = read_state(path, keys)
    records = read_journal(journal_path(path), read_manifest(path).binding, keys)
    opened = [*state.history, *state.chat, state.snapshot or b"", *(r.payload for r in records)]
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    return folder + b"".join(opened) + "\n".join(names).encode()


def test_after_a_rewrite_nothing_of_the_old_content_is_left_anywhere(path, owner, writer):
    for payload in BEFORE[:2]:
        writer.append(Domain.HISTORY, payload)
    writer.append(Domain.CHAT, b'{"t":"chat","text":"' + SECRET + b'"}')
    writer = pack_journal(path, owner.keys, writer, snapshot=b'{"state":"' + SECRET + b'"}')  # into the blocks
    writer.append(Domain.HISTORY, BEFORE[2])  # and some still in the journal
    assert SECRET in everything_opened(path, owner.keys)

    fresh = rewrite_journal(path, owner.keys, writer, history=AFTER, chat=[b'{"t":"chat","text":""}'])
    state = read_state(path, owner.keys)
    assert state.history == AFTER and state.chat == [b'{"t":"chat","text":""}'] and state.snapshot is None
    assert SECRET not in everything_opened(path, owner.keys)
    assert fresh.generation == writer.generation + 1 and fresh.seq == 0
    fresh.append(Domain.HISTORY, b'{"t":"entry","n":4}')  # work goes on in the fresh journal
    assert read_state(path, owner.keys).history == [*AFTER, b'{"t":"entry","n":4}']
    fresh.close()


def test_a_rewrite_leaves_no_temporary_file(path, owner, writer):
    writer.append(Domain.HISTORY, BEFORE[1])
    rewrite_journal(path, owner.keys, writer, history=AFTER, chat=[]).close()
    assert sorted(p.name for p in path.parent.iterdir()) == ["plan.claudia", "plan.claudia.journal"]


def test_a_crash_between_the_file_and_the_journal_loses_nothing_and_shows_nothing_old(path, owner, writer, monkeypatch):
    writer.append(Domain.HISTORY, BEFORE[1])
    from claudia_document_file import journal

    def power_cut(*_args, **_kwargs):
        raise OSError("power cut")

    monkeypatch.setattr(journal.JournalWriter, "replace", classmethod(power_cut))
    with pytest.raises(OSError):
        rewrite_journal(path, owner.keys, writer, history=AFTER, chat=[])
    monkeypatch.undo()
    assert read_state(path, owner.keys).history == AFTER  # the old journal is behind the file now, so it is ignored
    begin(path, owner.keys).close()  # and the next opening replaces it
    assert SECRET not in journal_path(path).read_bytes()
    assert not read_journal(journal_path(path), read_manifest(path).binding, owner.keys)


def test_the_kept_original_of_an_import_can_be_forgotten(path, owner, writer):
    write_original(path, owner.keys, b"PK original file with " + SECRET)
    assert read_original(path, owner.keys) is not None
    forget_original(path, owner.keys)
    assert read_original(path, owner.keys) is None
    with zipfile.ZipFile(path) as z:
        assert "content/original.bin" not in z.namelist()
    forget_original(path, owner.keys)  # nothing kept: nothing to do


def test_the_blocks_are_sealed_anew_not_carried_over(path, owner, writer):
    writer.append(Domain.HISTORY, BEFORE[1])
    writer = pack_journal(path, owner.keys, writer)
    with zipfile.ZipFile(path) as z:
        old_block = z.read("history/000001.blk")
    rewrite_journal(path, owner.keys, writer, history=AFTER, chat=[]).close()
    with zipfile.ZipFile(path) as z:
        new_block = z.read("history/000001.blk")
    assert new_block != old_block
