"""The unencrypted export (E2.9, D1270, D1272): one documented zip, no keys, no passwords, no people; read back with
the container's limits and a check of every part against ``export.json``."""

import io
import json
import zipfile

import pytest

from claudia_container import ExportRefused, is_export, read_export, write_export

STATE = {"sheets": [{"name": "Plan", "cells": {"A1": 1}}]}
HISTORY = [b'{"t":"entry","d":{"n":1}}', b'{"t":"entry","d":{"n":2}}']
CHAT = [b'{"t":"chat","d":{"text":"hi"}}']


def made(**more):
    return write_export("computes", 3, STATE, exporter="Annabelle", exported_at="2026-11-19T10:00:00Z", **more)


def rebuilt(entries: dict[str, bytes], *, order=None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name in order or list(entries):
            z.writestr(name, entries[name], compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def entries_of(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


def test_the_first_entry_names_the_format_so_tools_can_recognise_it():
    with zipfile.ZipFile(io.BytesIO(made())) as z:
        assert z.namelist()[0] == "format"
        assert z.read("format") == b"claudia-export 2"
        assert z.infolist()[0].compress_type == zipfile.ZIP_STORED


def test_content_only_has_three_entries_and_nothing_else():
    assert sorted(entries_of(made())) == ["content.json", "export.json", "format"]


def test_an_export_with_history_and_chat_has_them_as_lines():
    entries = entries_of(made(history=HISTORY, chat=CHAT))
    assert sorted(entries) == ["chat.jsonl", "content.json", "export.json", "format", "history.jsonl"]
    assert entries["history.jsonl"].decode().splitlines() == [h.decode() for h in HISTORY]


def test_the_round_trip_gives_back_what_was_written():
    read = read_export(made(history=HISTORY, chat=CHAT))
    assert (read.app, read.state_schema, read.state) == ("computes", 3, STATE)
    assert (read.exporter, read.exported_at) == ("Annabelle", "2026-11-19T10:00:00Z")
    assert read.history == HISTORY and read.chat == CHAT


def test_content_only_reads_as_none_for_history_and_chat():
    read = read_export(made())
    assert read.history is None and read.chat is None


def test_export_json_names_every_part_with_a_hash():
    info = json.loads(entries_of(made(history=HISTORY))["export.json"])
    assert set(info["parts"]) == {"content.json", "history.jsonl"}
    assert all(len(part["sha256"]) == 64 for part in info["parts"].values())
    assert info["format"] == "claudia-export 2" and info["app"] == "computes"


def test_it_holds_no_key_no_slot_no_people_and_no_password_hash():
    data = made(history=HISTORY, chat=CHAT)
    names = entries_of(data)
    assert not {"slots.json", "people.bin", "manifest.json", "head.bin"} & set(names)


def test_it_is_recognised_by_its_first_entry_alone():
    assert is_export(made())
    assert not is_export(b"not a zip")
    assert not is_export(rebuilt({"format": b"claudia-document 1", "manifest.json": b"{}"}))


def test_a_changed_part_is_refused():
    entries = entries_of(made())
    entries["content.json"] = json.dumps({"sheets": []}).encode()
    with pytest.raises(ExportRefused, match="content.json"):
        read_export(rebuilt(entries, order=["format", "export.json", "content.json"]))


def test_a_part_that_export_json_does_not_name_is_refused():
    entries = entries_of(made())
    entries["history.jsonl"] = b"{}\n"
    with pytest.raises(ExportRefused, match="history.jsonl"):
        read_export(rebuilt(entries, order=["format", "export.json", "content.json", "history.jsonl"]))


def test_a_part_that_export_json_names_but_is_missing_is_refused():
    entries = entries_of(made(history=HISTORY))
    del entries["history.jsonl"]
    with pytest.raises(ExportRefused, match="history.jsonl"):
        read_export(rebuilt(entries, order=["format", "export.json", "content.json"]))


def test_an_entry_with_another_name_or_a_path_is_refused():
    entries = entries_of(made())
    entries["../evil.json"] = b"{}"
    with pytest.raises(ExportRefused):
        read_export(rebuilt(entries, order=["format", "export.json", "content.json", "../evil.json"]))


def test_a_format_of_a_newer_version_is_refused_with_a_sentence():
    entries = entries_of(made())
    entries["format"] = b"claudia-export 3"
    with pytest.raises(ExportRefused, match="newer"):
        read_export(rebuilt(entries, order=["format", "export.json", "content.json"]))


def test_a_file_that_is_not_an_export_is_refused():
    with pytest.raises(ExportRefused, match="not a Claudia export"):
        read_export(b"PK\x03\x04 nonsense")
    with pytest.raises(ExportRefused, match="not a Claudia export"):
        read_export(rebuilt({"format": b"claudia-document 1"}))


def test_content_that_is_not_json_is_refused():
    entries = entries_of(made())
    import hashlib

    bad = b"{not json"
    info = json.loads(entries["export.json"])
    info["parts"]["content.json"] = {"sha256": hashlib.sha256(bad).hexdigest(), "bytes": len(bad)}
    entries["content.json"], entries["export.json"] = bad, json.dumps(info).encode()
    with pytest.raises(ExportRefused, match="content.json"):
        read_export(rebuilt(entries, order=["format", "export.json", "content.json"]))


def test_a_zip_bomb_is_refused_before_it_is_inflated(monkeypatch):
    import claudia_container.export_file as module

    monkeypatch.setattr(module, "MAX_PART_BYTES", 1000)
    big = write_export("computes", 3, {"x": "a" * 5000}, exporter="A", exported_at="2026-11-19T10:00:00Z")
    with pytest.raises(ExportRefused, match="too large"):
        read_export(big)


def test_a_history_line_that_is_not_json_is_refused():
    with pytest.raises(ValueError, match="history"):
        made(history=[b"not json"])


def test_the_exporter_and_time_are_checked():
    with pytest.raises(ValueError):
        write_export("computes", 3, STATE, exporter="", exported_at="2026-11-19T10:00:00Z")


ORDER = ["format", "export.json", "content.json"]


def test_a_history_payload_with_a_line_break_cannot_be_written():
    with pytest.raises(ValueError, match="line break"):
        made(history=[b'{"t":"entry",\n"d":1}'])


def test_a_part_that_is_not_json_cannot_be_written():
    with pytest.raises(ValueError):
        made(chat=[b"not json"])


def test_a_part_that_claims_a_wrong_size_is_refused(monkeypatch):
    monkeypatch.setattr("claudia_container.export_file._MAX_INFO_BYTES", 5)
    with pytest.raises(ExportRefused, match="too large"):
        read_export(made())


def test_an_export_without_export_json_is_refused():
    entries = entries_of(made())
    del entries["export.json"]
    with pytest.raises(ExportRefused, match="damaged"):
        read_export(rebuilt(entries, order=["format", "content.json"]))


def test_two_entries_with_one_name_are_refused():
    buffer = io.BytesIO()
    with pytest.warns(UserWarning), zipfile.ZipFile(buffer, "w") as z:
        z.writestr("format", b"claudia-export 2")
        z.writestr("export.json", b"{}")
        z.writestr("export.json", b"{}")
    with pytest.raises(ExportRefused):
        read_export(buffer.getvalue())


def test_an_export_json_that_is_not_what_an_export_has_is_refused():
    entries = entries_of(made())
    for broken in (b"[]", b"not json", b'{"format":"claudia-export 2"}'):
        entries["export.json"] = broken
        with pytest.raises(ExportRefused, match="export.json"):
            read_export(rebuilt(entries, order=ORDER))
    info = json.loads(entries_of(made())["export.json"])
    info["parts"] = {"history.jsonl": info["parts"]["content.json"]}
    entries["export.json"] = json.dumps(info).encode()
    with pytest.raises(ExportRefused, match="not what an export has"):
        read_export(rebuilt(entries, order=ORDER))


def test_content_that_is_json_but_not_a_state_is_refused():
    entries = entries_of(made())
    entries["content.json"] = b"[1, 2]"
    info = json.loads(entries["export.json"])
    import hashlib

    info["parts"]["content.json"] = {"sha256": hashlib.sha256(entries["content.json"]).hexdigest(), "bytes": 6}
    entries["export.json"] = json.dumps(info).encode()
    with pytest.raises(ExportRefused, match="not a state"):
        read_export(rebuilt(entries, order=ORDER))
