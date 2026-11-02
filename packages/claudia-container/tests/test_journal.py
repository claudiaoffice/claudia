"""The encrypted journal (E2.1, D76): every change is appended as a sealed record before it is acknowledged."""

import os
import struct
import zlib

import pytest

from claudia_container import journal as journal_module
from claudia_container.crypto import random_key
from claudia_container.journal import MAX_RECORD_BYTES, JournalError, JournalWriter, read_journal
from claudia_container.slots import Domain

DOC = "plan"


@pytest.fixture
def keys():
    return {Domain.CONTENT: random_key(), Domain.HISTORY: random_key(), Domain.CHAT: random_key()}


@pytest.fixture
def path(tmp_path):
    return tmp_path / "plan.claudia.journal"


def written(path, keys, items):
    writer = JournalWriter.create(path, DOC, keys)
    for domain, payload in items:
        writer.append(domain, payload)
    writer.close()


ITEMS = [
    (Domain.HISTORY, b'{"t":"entry","d":1}'),
    (Domain.CHAT, b'{"t":"chat","d":"hello"}'),
    (Domain.HISTORY, b'{"t":"entry","d":2}'),
    (Domain.HISTORY, b'{"t":"entry","d":3}'),
]


def test_records_come_back_in_order_with_their_domain(path, keys):
    written(path, keys, ITEMS)
    records = read_journal(path, DOC, keys)
    assert [(r.seq, r.domain, r.payload) for r in records] == [(i + 1, d, p) for i, (d, p) in enumerate(ITEMS)]


def test_an_empty_journal_has_no_records(path, keys):
    written(path, keys, [])
    assert read_journal(path, DOC, keys) == []


def test_append_returns_the_sequence_number(path, keys):
    writer = JournalWriter.create(path, DOC, keys)
    assert [writer.append(Domain.HISTORY, b"x") for _ in range(3)] == [1, 2, 3]
    writer.close()


def test_the_file_shows_no_content(path, keys):
    secret = b"quarterly-forecast-4711"
    written(path, keys, [(Domain.HISTORY, b'{"cell":"' + secret + b'"}'), (Domain.CHAT, b"chat " + secret)])
    assert secret not in path.read_bytes()


def test_sealing_the_same_payload_twice_looks_different(path, keys):
    written(path, keys, [(Domain.HISTORY, b"same"), (Domain.HISTORY, b"same")])
    frames = journal_module._split(path.read_bytes())
    assert frames[0] != frames[1]


def test_a_reopened_journal_continues_the_numbering(path, keys):
    written(path, keys, ITEMS)
    writer = JournalWriter.open(path, DOC, keys)
    assert writer.append(Domain.HISTORY, b"later") == len(ITEMS) + 1
    writer.close()
    assert read_journal(path, DOC, keys)[-1].payload == b"later"


def test_creating_never_overwrites(path, keys):
    written(path, keys, ITEMS)
    with pytest.raises(FileExistsError):
        JournalWriter.create(path, DOC, keys)


def test_every_append_is_synced_to_disk_before_it_returns(path, keys, monkeypatch):
    calls = []
    real = os.fsync
    monkeypatch.setattr(journal_module.os, "fsync", lambda fd: (calls.append(fd), real(fd))[1])
    writer = JournalWriter.create(path, DOC, keys)
    before = len(calls)
    writer.append(Domain.HISTORY, b"x")
    assert len(calls) > before
    writer.close()


# --- crashes: a half-written last record never happened ------------------------------------------------------------


@pytest.mark.parametrize("cut", [1, 5, 30])
def test_a_cut_off_last_record_is_ignored(path, keys, cut):
    written(path, keys, ITEMS)
    data = path.read_bytes()
    path.write_bytes(data[:-cut])
    assert [r.seq for r in read_journal(path, DOC, keys)] == [1, 2, 3]


def test_a_garbled_last_record_counts_as_cut_off(path, keys):
    written(path, keys, ITEMS)
    data = bytearray(path.read_bytes())
    data[-3] ^= 0xFF  # the check value of the last record no longer fits
    path.write_bytes(bytes(data))
    assert [r.seq for r in read_journal(path, DOC, keys)] == [1, 2, 3]


def test_the_writer_repairs_the_tail_and_reuses_the_lost_number(path, keys):
    written(path, keys, ITEMS)
    path.write_bytes(path.read_bytes()[:-7])
    writer = JournalWriter.open(path, DOC, keys)
    assert writer.append(Domain.HISTORY, b"again") == 4
    writer.close()
    records = read_journal(path, DOC, keys)
    assert [(r.seq, r.payload) for r in records][-1] == (4, b"again")
    assert len(records) == 4


# --- damage and tampering: an error, never a guess --------------------------------------------------------------


def frames_of(path):
    return journal_module._split(path.read_bytes())


def rebuilt(path, header, frames):
    path.write_bytes(header + b"".join(frames))


def header_of(path):
    return path.read_bytes()[: len(path.read_bytes()) - sum(len(f) for f in frames_of(path))]


def test_damage_in_the_middle_is_an_error(path, keys):
    written(path, keys, ITEMS)
    data = bytearray(path.read_bytes())
    first = frames_of(path)[0]
    data[len(data) - sum(len(f) for f in frames_of(path)) + len(first) + 12] ^= 1  # inside record 2
    path.write_bytes(bytes(data))
    with pytest.raises(JournalError):
        read_journal(path, DOC, keys)


def test_a_forged_change_with_a_repaired_check_value_is_still_refused(path, keys):
    """The check value only finds accidents. The encryption finds tampering, also in the last record."""
    written(path, keys, ITEMS)
    header, frames = header_of(path), frames_of(path)
    body = bytearray(frames[-1][4:-4])
    body[-1] ^= 1  # a flipped bit in the tag
    body = bytes(body)
    frames[-1] = struct.pack(">I", len(body)) + body + struct.pack(">I", zlib.crc32(body))
    rebuilt(path, header, frames)
    with pytest.raises(JournalError):
        read_journal(path, DOC, keys)


def test_swapped_records_are_refused(path, keys):
    written(path, keys, ITEMS)
    header, frames = header_of(path), frames_of(path)
    frames[2], frames[3] = frames[3], frames[2]
    rebuilt(path, header, frames)
    with pytest.raises(JournalError):
        read_journal(path, DOC, keys)


def test_a_removed_record_leaves_a_gap_that_is_noticed(path, keys):
    written(path, keys, ITEMS)
    header, frames = header_of(path), frames_of(path)
    del frames[1]
    rebuilt(path, header, frames)
    with pytest.raises(JournalError):
        read_journal(path, DOC, keys)


def test_a_repeated_record_is_refused(path, keys):
    written(path, keys, ITEMS)
    header, frames = header_of(path), frames_of(path)
    frames.insert(2, frames[1])
    rebuilt(path, header, frames)
    with pytest.raises(JournalError):
        read_journal(path, DOC, keys)


def test_the_wrong_key_is_refused(path, keys):
    written(path, keys, ITEMS)
    with pytest.raises(JournalError):
        read_journal(path, DOC, {**keys, Domain.HISTORY: random_key()})


def test_a_key_that_is_missing_is_refused(path, keys):
    written(path, keys, ITEMS)
    with pytest.raises(JournalError):
        read_journal(path, DOC, {Domain.CONTENT: keys[Domain.CONTENT]})  # a viewer's key opens no history


def test_a_journal_of_another_document_is_refused(path, keys):
    written(path, keys, ITEMS)
    with pytest.raises(JournalError):
        read_journal(path, "other", keys)


@pytest.mark.parametrize("damage", ["magic", "short", "empty"])
def test_a_file_that_is_not_a_journal_is_refused(path, keys, damage):
    written(path, keys, ITEMS)
    data = path.read_bytes()
    path.write_bytes({"magic": b"X" + data[1:], "short": data[:5], "empty": b""}[damage])
    with pytest.raises(JournalError):
        read_journal(path, DOC, keys)


def test_a_record_cannot_ask_for_gigabytes(path, keys):
    written(path, keys, ITEMS)
    data = path.read_bytes()
    start = len(data) - sum(len(f) for f in frames_of(path))
    path.write_bytes(data[:start] + struct.pack(">I", 0xFFFFFFF0) + b"junk")
    with pytest.raises(JournalError):
        read_journal(path, DOC, keys)


def test_an_oversized_payload_is_refused_when_written(path, keys):
    writer = JournalWriter.create(path, DOC, keys)
    with pytest.raises(ValueError, match="too large"):
        writer.append(Domain.HISTORY, b"x" * (MAX_RECORD_BYTES + 1))
    writer.close()


def test_a_domain_without_a_key_cannot_be_written(path):
    writer = JournalWriter.create(path, DOC, {Domain.HISTORY: random_key()})
    with pytest.raises(ValueError, match="chat"):
        writer.append(Domain.CHAT, b"x")
    writer.close()
