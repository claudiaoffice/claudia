"""The owners' consent (E7.11, D264): a sealed list of its own, beside the record of what left the document.

A consent is a permission that can be withdrawn, so it is not the record of what left (which nothing removes an entry
from) and not history. It is sealed with the *content* key, so a viewer can read whether Claude is allowed; only the
server's method, not the cryptography, keeps editors from writing it (they hold the content key too). What the seal
guarantees is that whoever administers the server, and holds no key, cannot give the owners' consent."""

import contextlib
import json
import zipfile

import pytest

from claudia_document_file import (
    FORMAT_TEXT,
    ConsentRecord,
    TamperedDocument,
    add_user,
    begin,
    blocks,
    create_document,
    pack_journal,
    read_audit,
    read_consent,
    read_state,
    record_consent,
    rewrite_journal,
    sealed_copy,
)
from claudia_document_file.crypto import KdfParams
from claudia_document_file.renewal import remove_person
from claudia_document_file.slots import Part, Role

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
PASSWORD = "Correct-Horse-9"
VERA = ("Vera", "Another-Pass-7!")


@pytest.fixture
def path(tmp_path):
    return tmp_path / "budget.claudia"


@pytest.fixture
def owner(path):
    return create_document(path, name="budget", app="computes", owner="Anna", password=PASSWORD, kdf=CHEAP)


@pytest.fixture
def writer(path, owner):
    w = begin(path, owner.keys)
    yield w
    with contextlib.suppress(ValueError):
        w.close()


def allow(who="Anna", when="2026-11-22T10:00:00Z", allowed=True, provider="claude"):
    return ConsentRecord(provider=provider, allowed=allowed, who=who, when=when)


def consent_entries(path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist() if n.startswith("consent/")}


def test_a_document_nobody_allowed_anything_in_has_an_empty_list(path, owner):
    assert read_consent(path, owner.keys) == []


def test_a_consent_is_written_and_read_back_in_order_with_who_and_when(path, owner):
    record_consent(path, owner.keys, allow())
    record_consent(path, owner.keys, allow(who="Jonas", when="2026-11-22T11:00:00Z", allowed=False))
    rows = read_consent(path, owner.keys)
    assert [(r.provider, r.allowed, r.who, r.when) for r in rows] == [
        ("claude", True, "Anna", "2026-11-22T10:00:00Z"),
        ("claude", False, "Jonas", "2026-11-22T11:00:00Z"),
    ]


def test_the_consent_holds_no_text_in_the_clear(path, owner):
    record_consent(path, owner.keys, allow(who="Annabelle-the-owner"))
    assert all(b"Annabelle" not in data and b"claude" not in data for data in consent_entries(path).values())


def test_a_viewer_can_read_whether_claude_is_allowed(path, owner):
    record_consent(path, owner.keys, allow())
    viewer_keys = {Part.CONTENT: owner.keys[Part.CONTENT]}
    assert [r.allowed for r in read_consent(path, viewer_keys)] == [True]


def test_a_consent_adds_no_revision_no_history_and_is_not_in_the_record_of_what_left(path, owner, writer):
    before = read_state(path, owner.keys)
    record_consent(path, owner.keys, allow())
    assert read_state(path, owner.keys).history == before.history
    assert read_audit(path, owner.keys) == []


def test_packing_carries_the_consent_through_byte_for_byte(path, owner, writer):
    record_consent(path, owner.keys, allow())
    before = consent_entries(path)
    writer.append(Part.HISTORY, b'{"t":"entry","n":1}')
    pack_journal(path, owner.keys, writer)
    assert consent_entries(path) == before


def test_a_redaction_does_not_change_one_byte_of_the_consent(path, owner, writer):
    record_consent(path, owner.keys, allow())
    before = consent_entries(path)
    writer.append(Part.HISTORY, b'{"secret":"hunter2"}')
    rewrite_journal(path, owner.keys, writer, history=[b'{"redacted":true}'], chat=[], snapshot=None)
    assert consent_entries(path) == before
    assert [r.allowed for r in read_consent(path, owner.keys)] == [True]


def test_a_block_that_is_removed_or_changed_is_noticed(path, owner, tmp_path):
    record_consent(path, owner.keys, allow())
    damaged = tmp_path / "damaged.claudia"
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(damaged, "w") as target:
        for name in source.namelist():
            if name != f"{blocks.CONSENT}/000001.blk":
                target.writestr(name, source.read(name))
    with pytest.raises(TamperedDocument):
        read_consent(damaged, owner.keys)


def test_a_consent_of_another_document_does_not_open_here(tmp_path, owner, path):
    record_consent(path, owner.keys, allow())
    other_path = tmp_path / "other.claudia"
    other = create_document(other_path, name="other", app="computes", owner="Anna", password=PASSWORD, kdf=CHEAP)
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(other_path) as target:
        entries = {n: target.read(n) for n in target.namelist() if not n.startswith("consent/")}
        entries |= {n: source.read(n) for n in source.namelist() if n.startswith("consent/")}
    with zipfile.ZipFile(other_path, "w") as rewritten:
        for name, data in entries.items():
            rewritten.writestr(name, data)
    with pytest.raises(TamperedDocument):
        read_consent(other_path, other.keys)


def test_a_viewers_copy_carries_the_consent_and_an_owners_copy_too(path, owner):
    add_user(path, owner.keys, *VERA, Role.VIEWER)
    record_consent(path, owner.keys, allow())
    for name, password in (VERA, ("Anna", PASSWORD)):
        copy = path.with_name(f"{name}.claudia")
        copy.write_bytes(sealed_copy(path, name, password))
        assert [r.allowed for r in read_consent(copy, {Part.CONTENT: owner.keys[Part.CONTENT]})] == [True]


def test_the_consent_is_sealed_again_when_the_content_key_is_renewed(path, owner, writer):
    add_user(path, owner.keys, *VERA, Role.VIEWER)
    record_consent(path, owner.keys, allow())
    done = remove_person(path, owner.keys, writer, "Vera")  # a viewer leaves: the content key is renewed
    assert [r.allowed for r in read_consent(path, done.keys)] == [True]
    with pytest.raises(TamperedDocument):
        read_consent(path, owner.keys)
    done.writer.close()


def test_the_format_is_raised_and_the_older_one_is_still_read():
    assert FORMAT_TEXT == "claudia-document 3"


def test_a_file_of_the_older_format_opens_and_has_no_consent(path, owner):
    with zipfile.ZipFile(path) as source:
        entries = {n: source.read(n) for n in source.namelist()}
    manifest = json.loads(entries["manifest.json"])
    manifest["format"] = 2
    entries["manifest.json"] = json.dumps(manifest).encode()
    entries["format"] = b"claudia-document 2"
    old = path.with_name("old.claudia")
    with zipfile.ZipFile(old, "w") as target:
        for name, data in entries.items():
            target.writestr(name, data)
    assert read_consent(old, owner.keys) == []


@pytest.mark.parametrize("bad", [{"provider": ""}, {"who": ""}, {"when": ""}, {"provider": "x" * 201}])
def test_a_consent_needs_a_provider_a_name_and_a_time(path, owner, bad):
    with pytest.raises(ValueError, match="consent"):
        record_consent(
            path, owner.keys, ConsentRecord(**{"provider": "claude", "allowed": True, "who": "A", "when": "t", **bad})
        )
    assert read_consent(path, owner.keys) == []


def test_allowed_is_yes_or_no(path, owner):
    with pytest.raises(ValueError, match="consent"):
        record_consent(path, owner.keys, ConsentRecord("claude", "yes", "Anna", "t"))  # type: ignore[arg-type]
