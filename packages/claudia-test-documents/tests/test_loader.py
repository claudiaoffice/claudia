"""load_case loads each spec.py by its own path -- every one is named the same, so this is the one thing that
must not get confused by Python's own module cache (D178)."""

from __future__ import annotations

from pathlib import Path

import pytest

from claudia_test_documents.loader import load_case

_SPEC_SOURCE = """
from claudia_test_documents.case import Case

def import_checks(model):
    pass

CASE = Case(import_checks=import_checks)
"""


def _write_spec(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    spec_path = directory / "spec.py"
    spec_path.write_text(_SPEC_SOURCE, encoding="utf-8")
    return spec_path


def test_two_entries_each_named_spec_py_do_not_collide(tmp_path: Path):
    case_a = load_case(_write_spec(tmp_path / "a"), "entry-a")
    case_b = load_case(_write_spec(tmp_path / "b"), "entry-b")
    assert case_a is not case_b
    assert case_a.import_checks is not case_b.import_checks  # distinct function objects, not one cached module


def test_a_spec_with_no_case_raises_import_error(tmp_path: Path):
    spec_path = tmp_path / "spec.py"
    spec_path.write_text("# no CASE here\n", encoding="utf-8")
    with pytest.raises(ImportError):
        load_case(spec_path, "entry-without-case")


def test_a_missing_spec_file_raises_import_error(tmp_path: Path):
    with pytest.raises(ImportError):
        load_case(tmp_path / "does-not-exist" / "spec.py", "entry-missing")
