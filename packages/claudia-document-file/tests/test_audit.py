"""The audit chain (E2.9, D1271): what leaves the document is recorded in blocks of their own, under the history key.

The chain is not part of the command log, so it adds no revision; it is not redactable, not by anybody; a viewer's
sealed copy has none of it; a removed or swapped block is noticed like any other block."""

import contextlib
import zipfile
from dataclasses import replace

import pytest

from claudia_document_file import (
    AuditRecord,
    TamperedDocument,
    add_user,
    begin,
    blocks,
    create_document,
    pack_journal,
    read_audit,
    read_state,
    record_audit,
    rewrite_journal,
    sealed_copy,
)
from claudia_document_file.crypto import KdfParams
from claudia_document_file.slots import Domain, Role

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
PASSWORD = "Correct-Horse-9"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "plan.claudia"


@pytest.fixture
def owner(path):
    return create_document(path, name="plan", app="computes", owner="Annabelle", password=PASSWORD, kdf=CHEAP)


@pytest.fixture
def writer(path, owner):
    w = begin(path, owner.keys)
    yield w
    with contextlib.suppress(ValueError):
        w.close()


def export(who="Annabelle", when="2026-11-19T10:00:00Z", fmt="docx", parts=("content",)):
    return AuditRecord(kind="export", who=who, when=when, format=fmt, parts=parts, pages=None)


def audit_bytes(path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist() if n.startswith("audit/")}


def test_a_new_document_has_an_empty_record(path, owner):
    assert read_audit(path, owner.keys) == []


def test_a_record_is_written_and_read_back_in_order(path, owner):
    record_audit(path, owner.keys, export(fmt="docx"))
    record_audit(path, owner.keys, AuditRecord("pdf", "Ben", "2026-11-19T11:00:00Z", "pdf", ("content",), 12))
    rows = read_audit(path, owner.keys)
    assert [r.kind for r in rows] == ["export", "pdf"]
    assert rows[0].who == "Annabelle" and rows[0].format == "docx" and rows[0].pages is None
    assert rows[1].who == "Ben" and rows[1].pages == 12 and rows[1].parts == ("content",)


def test_the_record_holds_no_text_in_the_clear(path, owner):
    record_audit(path, owner.keys, export(who="Annabelle-Unique"))
    with zipfile.ZipFile(path) as z:
        assert b"Annabelle-Unique" not in b"".join(z.read(n) for n in z.namelist())


def test_a_record_adds_no_revision_and_no_history(path, owner, writer):
    record_audit(path, owner.keys, export())
    assert read_state(path, owner.keys).history == []
    assert read_state(path, owner.keys).pending == 0


def test_a_record_leaves_the_journal_in_place(path, owner, writer):
    writer.append(Domain.HISTORY, b'{"t":"x"}')
    record_audit(path, owner.keys, export())
    assert read_state(path, owner.keys).history == [b'{"t":"x"}']
    writer = pack_journal(path, owner.keys, writer)
    assert read_state(path, owner.keys).history == [b'{"t":"x"}']
    assert len(read_audit(path, owner.keys)) == 1
    writer.close()


def test_packing_carries_the_chain_through_byte_for_byte(path, owner, writer):
    record_audit(path, owner.keys, export())
    before = audit_bytes(path)
    writer.append(Domain.HISTORY, b'{"t":"x"}')
    pack_journal(path, owner.keys, writer)
    assert audit_bytes(path) == before


def test_a_redaction_does_not_change_one_byte_of_the_chain(path, owner, writer):
    record_audit(path, owner.keys, export())
    record_audit(path, owner.keys, export(fmt="xlsx"))
    before = audit_bytes(path)
    writer.append(Domain.HISTORY, b'{"secret":"hunter2"}')
    rewrite_journal(path, owner.keys, writer, history=[b'{"redacted":true}'], chat=[], snapshot=None)
    assert audit_bytes(path) == before
    assert [r.format for r in read_audit(path, owner.keys)] == ["docx", "xlsx"]


def test_a_block_that_is_removed_is_noticed(path, owner, monkeypatch):
    monkeypatch.setattr(blocks, "BLOCK_TARGET_BYTES", 50)
    record_audit(path, owner.keys, export())
    record_audit(path, owner.keys, export())
    names = sorted(audit_bytes(path))
    assert len(names) == 2
    with zipfile.ZipFile(path) as source:
        kept = {n: source.read(n) for n in source.namelist() if n != names[-1]}
    damaged = path.with_name("damaged.claudia")
    with zipfile.ZipFile(damaged, "w") as target:
        for name, data in kept.items():
            target.writestr(name, data, compress_type=zipfile.ZIP_STORED)
    with pytest.raises(TamperedDocument):
        read_audit(damaged, owner.keys)


def test_a_viewer_cannot_read_or_write_the_record(path, owner):
    viewer_keys = {Domain.CONTENT: owner.keys[Domain.CONTENT]}
    with pytest.raises(PermissionError):
        read_audit(path, viewer_keys)
    with pytest.raises(PermissionError):
        record_audit(path, viewer_keys, export())


def test_a_viewers_copy_of_the_file_has_no_record(path, owner):
    add_user(path, owner.keys, "Vera", "Another-Pass-7!", Role.VIEWER)
    record_audit(path, owner.keys, export())
    data = sealed_copy(path, "Vera", "Another-Pass-7!")
    copy = path.with_name("vera.claudia")
    copy.write_bytes(data)
    with zipfile.ZipFile(copy) as z:
        assert not [n for n in z.namelist() if n.startswith("audit/")]


def test_an_editors_or_owners_copy_has_the_record(path, owner):
    record_audit(path, owner.keys, export())
    copy = path.with_name("copy.claudia")
    copy.write_bytes(sealed_copy(path, "Annabelle", PASSWORD))
    assert len(read_audit(copy, owner.keys)) == 1


def test_a_long_record_makes_more_blocks_and_stays_readable(path, owner, monkeypatch):
    monkeypatch.setattr(blocks, "BLOCK_TARGET_BYTES", 200)
    for number in range(30):
        record_audit(path, owner.keys, export(fmt=f"f{number}"))
    assert [r.format for r in read_audit(path, owner.keys)] == [f"f{n}" for n in range(30)]


def test_a_record_of_another_document_does_not_open_here(tmp_path):
    first = create_document(tmp_path / "a.claudia", name="a", app="computes", owner="A", password=PASSWORD, kdf=CHEAP)
    second = create_document(tmp_path / "b.claudia", name="b", app="computes", owner="A", password=PASSWORD, kdf=CHEAP)
    record_audit(tmp_path / "a.claudia", first.keys, export())
    with zipfile.ZipFile(tmp_path / "a.claudia") as z:
        stolen = {n: z.read(n) for n in z.namelist() if n.startswith("audit/")}
    with zipfile.ZipFile(tmp_path / "b.claudia") as z:
        rest = {n: z.read(n) for n in z.namelist()}
    swapped = tmp_path / "swapped.claudia"
    with zipfile.ZipFile(swapped, "w") as target:
        for name, data in {**rest, **stolen}.items():
            target.writestr(name, data, compress_type=zipfile.ZIP_STORED)
    with pytest.raises(TamperedDocument):
        read_audit(swapped, second.keys)


@pytest.mark.parametrize("kind", ["export", "print", "pdf"])
def test_the_kinds_of_the_record(path, owner, kind):
    record_audit(path, owner.keys, AuditRecord(kind, "A", "2026-11-19T10:00:00Z", "pdf", ("content",), 3))
    assert read_audit(path, owner.keys)[0].kind == kind


def test_an_unknown_kind_is_refused(path, owner):
    with pytest.raises(ValueError, match="kind"):
        record_audit(path, owner.keys, AuditRecord("copy", "A", "2026-11-19T10:00:00Z", "pdf", ("content",), 3))


def test_the_parts_are_content_history_or_chat_only(path, owner):
    with pytest.raises(ValueError, match="parts"):
        record_audit(path, owner.keys, export(parts=("content", "passwords")))


def test_a_record_needs_a_name_a_time_and_a_format():
    with pytest.raises(ValueError, match="200 characters"):
        export(who="").check()
    with pytest.raises(ValueError, match="200 characters"):
        export(fmt="x" * 201).check()


def test_pages_is_a_number_of_pages_or_nothing():
    for bad in (-1, True, "3"):
        with pytest.raises(ValueError, match="pages"):
            replace(export(), pages=bad).check()


def test_a_payload_that_is_not_a_record_is_refused():
    with pytest.raises(ValueError, match="not an audit record"):
        AuditRecord.from_bytes(b'{"kind":"export"}')
    with pytest.raises(ValueError, match="not an audit record"):
        AuditRecord.from_bytes(b"[1]")
