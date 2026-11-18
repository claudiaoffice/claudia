"""``scripts/run_test_documents.py --corpus DIR``: a folder of the person's own documents, no catalogue, nothing copied
into ``test-documents/``. Run against copies of the library's own fixtures, so the files are real and the expected
outcome is known."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("run_test_documents", ROOT / "scripts" / "run_test_documents.py")
assert SPEC is not None and SPEC.loader is not None
run_test_documents = importlib.util.module_from_spec(SPEC)
sys.modules["run_test_documents"] = run_test_documents
SPEC.loader.exec_module(run_test_documents)

FIXTURES = ROOT / "test-documents"


def _corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "corpus"
    (corpus / "word").mkdir(parents=True)
    (corpus / "sheets").mkdir()
    shutil.copy(FIXTURES / "docx" / "heading-styles" / "source.docx", corpus / "word" / "headings.docx")
    shutil.copy(FIXTURES / "xlsx" / "cells-and-formulas" / "source.xlsx", corpus / "sheets" / "cells.xlsx")
    (corpus / "word" / "broken.docx").write_bytes(b"not a zip")  # a corpus is full of files like this on purpose
    (corpus / "readme.txt").write_text("not a document")
    return corpus


def _run(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["run_test_documents.py", *argv])
    return run_test_documents.main()


def test_a_corpus_run_checks_every_document_and_leaves_the_catalogue_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    catalogue = (FIXTURES / "catalogue.json").read_bytes()
    code = _run(monkeypatch, "--corpus", str(_corpus(tmp_path)))
    out = capsys.readouterr().out
    assert code == 0  # the broken file is rejected, which is correct behaviour and no failure
    assert "PASS" in out and "sheets/cells.xlsx" in out and "word/headings.docx" in out
    assert "REJECTED" in out and "word/broken.docx" in out
    assert "readme.txt" not in out
    assert "3 files: pass=2 fail=0 error=0 rejected=1" in out
    assert (FIXTURES / "catalogue.json").read_bytes() == catalogue


def test_format_narrows_the_corpus_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    assert _run(monkeypatch, "--corpus", str(_corpus(tmp_path)), "--format", "xlsx") == 0
    out = capsys.readouterr().out
    assert "cells.xlsx" in out and "headings.docx" not in out


def test_the_report_is_written_where_asked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    report = tmp_path / "reports" / "run.json"
    _run(monkeypatch, "--corpus", str(_corpus(tmp_path)), "--corpus-report", str(report))
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["summary"]["total"] == 3
    assert [f["path"] for f in data["files"]] == ["sheets/cells.xlsx", "word/broken.docx", "word/headings.docx"]


def test_a_folder_that_is_not_there_is_a_usage_error_not_a_clean_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    assert _run(monkeypatch, "--corpus", str(tmp_path / "missing")) == 2
    assert "not a directory" in capsys.readouterr().err


def test_a_folder_without_documents_is_not_a_clean_run_either(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    (tmp_path / "empty").mkdir()
    assert _run(monkeypatch, "--corpus", str(tmp_path / "empty")) == 1
    assert "no document of a supported format" in capsys.readouterr().err


@pytest.mark.parametrize(
    "flag", [["--id", "x"], ["--feature", "x"], ["--tag", "x"], ["--visual"], ["--report"], ["--no-write"]]
)
def test_catalogue_only_options_are_refused_with_a_corpus(
    flag: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    with pytest.raises(SystemExit) as exit_info:
        _run(monkeypatch, "--corpus", str(tmp_path), *flag)
    assert exit_info.value.code == 2
    assert "cannot be combined with --corpus" in capsys.readouterr().err


def test_a_report_path_without_a_corpus_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(SystemExit) as exit_info:
        _run(monkeypatch, "--corpus-report", str(tmp_path / "r.json"))
    assert exit_info.value.code == 2


def test_a_failure_makes_the_run_exit_non_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    from claudia_test_documents import CorpusResult

    failing = CorpusResult(
        "x.docx", "docx", "fail", {"import": "pass", "round_trip": "fail", "preserve": "skipped"}, 0.0, "d"
    )
    monkeypatch.setattr(run_test_documents, "run_corpus", lambda *a, **k: iter([failing]))
    assert _run(monkeypatch, "--corpus", str(tmp_path)) == 1
    assert "FAIL" in capsys.readouterr().out
