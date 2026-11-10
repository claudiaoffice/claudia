"""run_case's own logic, against a fake format so these tests need no real office file (D218): a fake document
is just a zip of two text parts, ``doc.txt`` (what the fake model holds) and ``untouched.txt`` (what a
preserve check should catch going missing). Real formats are exercised by the real catalogue instead
(``tests/test_test_documents_catalogue.py`` at the repo root).
"""

from __future__ import annotations

from pathlib import Path

from claudia_opc_io import read_parts, write_parts
from claudia_test_documents.adapters import Adapter
from claudia_test_documents.runner import run_case

_SPEC_SOURCE = """
from claudia_test_documents.case import Case

def import_checks(model):
    assert model["text"] == "hello"

def modify(model):
    return {{"text": "edited"}}

def after_checks(model):
    assert model["text"] == "{after_text}"

CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks, preserve_parts={preserve!r})
"""


def _fake_import(file_bytes: bytes) -> dict:
    return {"text": read_parts(file_bytes)["doc.txt"].decode()}


def _fake_apply_edits(original_bytes: bytes, baseline: dict, current: dict) -> bytes:
    # `baseline` is unused here -- kept so the signature matches the real adapters'
    parts = read_parts(original_bytes)
    parts["doc.txt"] = current["text"].encode()
    return write_parts(parts)


def _fake_apply_edits_that_drops_untouched(original_bytes: bytes, baseline: dict, current: dict) -> bytes:
    parts = read_parts(original_bytes)
    parts["doc.txt"] = current["text"].encode()
    del parts["untouched.txt"]  # a stand-in for a library that silently drops what it did not touch
    return write_parts(parts)


def _source_bytes() -> bytes:
    return write_parts({"doc.txt": b"hello", "untouched.txt": b"keep me"})


def _entry(tmp_path: Path, spec_source: str, *, source_bytes: bytes | None = None) -> dict:
    (tmp_path / "source.bin").write_bytes(source_bytes if source_bytes is not None else _source_bytes())
    (tmp_path / "spec.py").write_text(spec_source, encoding="utf-8")
    return {"id": "fake-case", "format": "fake", "source": "source.bin", "spec": "spec.py"}


def test_a_passing_case_reports_pass_on_every_stage(tmp_path: Path):
    entry = _entry(tmp_path, _SPEC_SOURCE.format(after_text="edited", preserve=["untouched.txt"]))
    adapters = {"fake": Adapter(import_fn=_fake_import, apply_edits_fn=_fake_apply_edits)}
    result = run_case(entry, tmp_path, adapters=adapters)
    assert result.status == "pass"
    assert result.stages == {"import": "pass", "round_trip": "pass", "preserve": "pass", "visual": "not_run"}


def test_a_wrong_after_check_fails_the_round_trip_stage_only(tmp_path: Path):
    entry = _entry(tmp_path, _SPEC_SOURCE.format(after_text="not what it will actually be", preserve=["untouched.txt"]))
    adapters = {"fake": Adapter(import_fn=_fake_import, apply_edits_fn=_fake_apply_edits)}
    result = run_case(entry, tmp_path, adapters=adapters)
    assert result.status == "fail"
    assert result.stages["import"] == "pass"
    assert result.stages["round_trip"] == "fail"


def test_a_library_that_drops_an_untouched_part_fails_the_preserve_stage(tmp_path: Path):
    entry = _entry(tmp_path, _SPEC_SOURCE.format(after_text="edited", preserve=["untouched.txt"]))
    adapters = {"fake": Adapter(import_fn=_fake_import, apply_edits_fn=_fake_apply_edits_that_drops_untouched)}
    result = run_case(entry, tmp_path, adapters=adapters)
    assert result.status == "fail"
    assert result.stages["preserve"] == "fail"
    assert "untouched.txt" in (result.detail or "")


def test_a_format_with_no_apply_edits_adapter_skips_round_trip_and_preserve(tmp_path: Path):
    entry = _entry(tmp_path, _SPEC_SOURCE.format(after_text="edited", preserve=["untouched.txt"]))
    adapters = {"fake": Adapter(import_fn=_fake_import)}  # no apply_edits_fn yet, same as every non-docx format today
    result = run_case(entry, tmp_path, adapters=adapters)
    assert result.status == "pass"  # skipped is not a failure
    assert result.stages["import"] == "pass"
    assert result.stages["round_trip"] == "skipped"
    assert result.stages["preserve"] == "skipped"


def test_an_unregistered_format_fails_clearly_instead_of_crashing(tmp_path: Path):
    entry = _entry(tmp_path, _SPEC_SOURCE.format(after_text="edited", preserve=[]))
    entry["format"] = "no-such-format"
    result = run_case(entry, tmp_path, adapters={})
    assert result.status == "fail"
    assert "no-such-format" in (result.detail or "")


def test_a_case_with_no_checks_at_all_is_n_a_everywhere_and_still_passes(tmp_path: Path):
    spec_source = """
from claudia_test_documents.case import Case

CASE = Case()
"""
    (tmp_path / "source.bin").write_bytes(_source_bytes())
    (tmp_path / "spec.py").write_text(spec_source, encoding="utf-8")
    entry = {"id": "fake-empty", "format": "fake", "source": "source.bin", "spec": "spec.py"}
    adapters = {"fake": Adapter(import_fn=_fake_import, apply_edits_fn=_fake_apply_edits)}
    result = run_case(entry, tmp_path, adapters=adapters)
    assert result.status == "pass"
    assert result.stages == {"import": "n/a", "round_trip": "n/a", "preserve": "n/a", "visual": "not_run"}
