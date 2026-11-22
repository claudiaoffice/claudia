"""Running a folder of documents nobody wrote a spec for (an external corpus), against a fake format so these tests
need no real office file: a fake document is a zip of ``doc.txt`` (what the fake model holds) and ``extra.txt``
(a part the fake export may keep, rewrite or drop). Real formats are exercised by the real catalogue and by the
person's own corpus, not here."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claudia_opc_io import read_parts, write_parts
from claudia_test_documents.adapters import Adapter
from claudia_test_documents.corpus import CorpusResult, discover, run_corpus, run_file, summarize, write_report


class FakeModel:
    def __init__(self, text: str) -> None:
        self.text = text

    def serialize(self) -> dict:
        return {"paragraphs": [{"text": self.text}]}


def _import(data: bytes) -> FakeModel:
    return FakeModel(read_parts(data)["doc.txt"].decode())


def _keep(original: bytes, baseline: FakeModel, current: FakeModel) -> bytes:
    return original


def _rewrite_extra(original: bytes, baseline: FakeModel, current: FakeModel) -> bytes:
    parts = read_parts(original)
    parts["extra.txt"] = b"rewritten"
    return write_parts(parts)


def _drop_extra(original: bytes, baseline: FakeModel, current: FakeModel) -> bytes:
    parts = read_parts(original)
    del parts["extra.txt"]
    return write_parts(parts)


def _garble_text(original: bytes, baseline: FakeModel, current: FakeModel) -> bytes:
    parts = read_parts(original)
    parts["doc.txt"] = b"garbled"
    return write_parts(parts)


def _adapters(apply=_keep) -> dict[str, Adapter]:
    return {"fake": Adapter(import_fn=_import, apply_edits_fn=apply)}


def _doc(text: str = "hello") -> bytes:
    return write_parts({"doc.txt": text.encode(), "extra.txt": b"keep me"})


def _write(root: Path, name: str, data: bytes) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


# --- discover -------------------------------------------------------------------------------------------------


def test_discover_finds_supported_files_in_nested_folders_in_a_stable_order(tmp_path: Path):
    _write(tmp_path, "b/two.fake", _doc())
    _write(tmp_path, "a/deep/one.FAKE", _doc())  # the suffix is matched case-insensitively
    _write(tmp_path, "a/notes.txt", b"not a document")
    assert [p.relative_to(tmp_path).as_posix() for p in discover(tmp_path, adapters=_adapters())] == [
        "a/deep/one.FAKE",
        "b/two.fake",
    ]


def test_discover_skips_hidden_folders_and_office_lock_files(tmp_path: Path):
    _write(tmp_path, "keep.fake", _doc())
    _write(tmp_path, ".git/objects/x.fake", _doc())
    _write(tmp_path, "sub/.cache/y.fake", _doc())
    _write(tmp_path, "sub/~$lock.fake", _doc())
    assert [p.name for p in discover(tmp_path, adapters=_adapters())] == ["keep.fake"]


def test_discover_can_be_narrowed_to_some_formats(tmp_path: Path):
    _write(tmp_path, "a.fake", _doc())
    _write(tmp_path, "b.other", _doc())
    adapters = {**_adapters(), "other": Adapter(import_fn=_import, apply_edits_fn=_keep)}
    assert [p.name for p in discover(tmp_path, formats={"other"}, adapters=adapters)] == ["b.other"]


def test_discover_refuses_a_folder_that_is_not_there(tmp_path: Path):
    with pytest.raises(NotADirectoryError):
        discover(tmp_path / "missing", adapters=_adapters())


# --- run_file -------------------------------------------------------------------------------------------------


def test_a_file_that_survives_a_no_op_round_trip_passes_every_stage(tmp_path: Path):
    path = _write(tmp_path, "ok.fake", _doc())
    result = run_file(path, tmp_path, adapters=_adapters())
    assert result.status == "pass"
    assert result.stages == {"import": "pass", "round_trip": "pass", "preserve": "pass"}
    assert result.path == "ok.fake"
    assert result.format == "fake"
    assert result.changed_parts == [] and result.dropped_parts == []


def test_a_rewritten_part_is_reported_but_is_not_a_failure(tmp_path: Path):
    path = _write(tmp_path, "ok.fake", _doc())
    result = run_file(path, tmp_path, adapters=_adapters(_rewrite_extra))
    assert result.status == "pass"
    assert result.changed_parts == ["extra.txt"]


def test_a_dropped_part_fails_the_preserve_stage_and_names_the_part(tmp_path: Path):
    path = _write(tmp_path, "lossy.fake", _doc())
    result = run_file(path, tmp_path, adapters=_adapters(_drop_extra))
    assert result.status == "fail"
    assert result.stages["preserve"] == "fail"
    assert result.stages["round_trip"] == "pass"
    assert result.dropped_parts == ["extra.txt"]
    assert "extra.txt" in (result.detail or "")


def test_a_model_that_changes_through_a_no_op_edit_fails_the_round_trip_and_says_where(tmp_path: Path):
    path = _write(tmp_path, "drift.fake", _doc())
    result = run_file(path, tmp_path, adapters=_adapters(_garble_text))
    assert result.status == "fail"
    assert result.stages["round_trip"] == "fail"
    assert "paragraphs[0].text" in (result.detail or "")


def test_a_file_that_is_not_a_package_is_rejected_not_failed(tmp_path: Path):
    path = _write(tmp_path, "broken.fake", b"this is not a zip file at all")
    result = run_file(path, tmp_path, adapters={"fake": Adapter(import_fn=_raise_bad_zip, apply_edits_fn=_keep)})
    assert result.status == "rejected"
    assert result.stages == {"import": "rejected", "round_trip": "skipped", "preserve": "skipped"}


def test_a_package_over_the_limits_is_rejected_not_failed(tmp_path: Path):
    from claudia_opc_io import PackageRefused

    def refuse(data: bytes) -> FakeModel:
        raise PackageRefused("too many parts")

    path = _write(tmp_path, "bomb.fake", _doc())
    result = run_file(path, tmp_path, adapters={"fake": Adapter(import_fn=refuse, apply_edits_fn=_keep)})
    assert result.status == "rejected"
    assert "too many parts" in (result.detail or "")


def _raise_bad_zip(data: bytes) -> FakeModel:
    from zipfile import BadZipFile

    raise BadZipFile("File is not a zip file")


def test_an_importer_that_crashes_on_a_readable_file_is_an_error_with_the_exception_named(tmp_path: Path):
    def crash(data: bytes) -> FakeModel:
        raise KeyError("word/styles.xml")

    path = _write(tmp_path, "crash.fake", _doc())
    result = run_file(path, tmp_path, adapters={"fake": Adapter(import_fn=crash, apply_edits_fn=_keep)})
    assert result.status == "error"
    assert result.stages["import"] == "error"
    assert "KeyError" in (result.detail or "") and "styles.xml" in (result.detail or "")


def test_an_exporter_that_crashes_is_an_error_on_the_round_trip_stage(tmp_path: Path):
    def crash(original: bytes, baseline: FakeModel, current: FakeModel) -> bytes:
        raise ValueError("cannot patch")

    path = _write(tmp_path, "x.fake", _doc())
    result = run_file(path, tmp_path, adapters=_adapters(crash))
    assert result.status == "error"
    assert result.stages["import"] == "pass"
    assert result.stages["round_trip"] == "error"
    assert result.stages["preserve"] == "skipped"


def test_a_format_without_an_export_path_checks_import_only(tmp_path: Path):
    path = _write(tmp_path, "i.fake", _doc())
    result = run_file(path, tmp_path, adapters={"fake": Adapter(import_fn=_import)})
    assert result.status == "pass"
    assert result.stages == {"import": "pass", "round_trip": "skipped", "preserve": "skipped"}


def test_a_model_without_serialize_is_compared_as_it_is(tmp_path: Path):
    adapters = {"fake": Adapter(import_fn=lambda data: {"text": "same"}, apply_edits_fn=_keep)}
    path = _write(tmp_path, "d.fake", _doc())
    assert run_file(path, tmp_path, adapters=adapters).status == "pass"


# --- run_corpus, summarize, write_report -----------------------------------------------------------------------


def _corpus(tmp_path: Path) -> Path:
    _write(tmp_path, "a.fake", _doc())
    _write(tmp_path, "b.fake", _doc("other"))
    _write(tmp_path, "readme.txt", b"ignored")
    return tmp_path


def test_run_corpus_yields_one_result_per_supported_file_in_order(tmp_path: Path):
    results = list(run_corpus(_corpus(tmp_path), adapters=_adapters()))
    assert [r.path for r in results] == ["a.fake", "b.fake"]


def test_run_corpus_can_stop_after_the_first_problem(tmp_path: Path):
    root = _corpus(tmp_path)
    results = list(run_corpus(root, adapters=_adapters(_drop_extra), fail_fast=True))
    assert [r.path for r in results] == ["a.fake"]


def test_run_corpus_does_not_stop_on_a_rejected_file_when_failing_fast(tmp_path: Path):
    root = _corpus(tmp_path)
    adapters = {"fake": Adapter(import_fn=_raise_bad_zip, apply_edits_fn=_keep)}
    assert len(list(run_corpus(root, adapters=adapters, fail_fast=True))) == 2


def test_summarize_counts_every_status_and_lists_the_files_that_need_a_look():
    results = [
        CorpusResult("a", "fake", "pass", {}, 0.0, None),
        CorpusResult("b", "fake", "fail", {}, 0.0, "x"),
        CorpusResult("c", "fake", "error", {}, 0.0, "y"),
        CorpusResult("d", "fake", "rejected", {}, 0.0, "z"),
        CorpusResult("e", "fake", "pass", {}, 0.0, None),
    ]
    summary = summarize(results)
    assert summary["counts"] == {"pass": 2, "fail": 1, "error": 1, "rejected": 1}
    assert summary["total"] == 5
    assert summary["needs_attention"] == ["b", "c"]


def test_write_report_is_json_a_person_can_diff_between_runs(tmp_path: Path):
    root = _corpus(tmp_path / "corpus")
    results = list(run_corpus(root, adapters=_adapters()))
    report = tmp_path / "out" / "report.json"
    write_report(report, root, results)
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["root"] == str(root)
    assert data["summary"]["total"] == 2
    assert [f["path"] for f in data["files"]] == ["a.fake", "b.fake"]
    assert "duration_s" not in data["files"][0]  # timings differ on every run; a report is meant to be diffed
    assert report.read_text(encoding="utf-8").endswith("\n")


def test_a_format_whose_files_are_not_zip_packages_has_no_parts_to_compare(tmp_path: Path):
    adapters = {"fake": Adapter(import_fn=lambda data: {"n": len(data)}, apply_edits_fn=_keep)}
    path = _write(tmp_path, "flat.fake", b"plain bytes, no archive")
    result = run_file(path, tmp_path, adapters=adapters)
    assert result.status == "pass"
    assert result.stages["preserve"] == "skipped"


def test_a_file_whose_suffix_has_no_adapter_is_an_error_not_a_crash(tmp_path: Path):
    path = _write(tmp_path, "x.unknown", b"?")
    result = run_file(path, tmp_path, adapters=_adapters())
    assert result.status == "error"
    assert "no adapter" in (result.detail or "")


def test_a_list_that_gains_an_item_through_a_no_op_edit_is_a_round_trip_failure(tmp_path: Path):
    calls = iter([["a"], ["a"], ["a", "b"]])  # baseline, the independent second import, the re-import
    adapters = {"fake": Adapter(import_fn=lambda data: {"items": next(calls)}, apply_edits_fn=_keep)}
    path = _write(tmp_path, "grow.fake", _doc())
    result = run_file(path, tmp_path, adapters=adapters)
    assert result.status == "fail"
    assert "items[1]" in (result.detail or "")
