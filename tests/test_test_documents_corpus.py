"""Your own folder of documents, run through the generic import/export checks -- when you point at one.

``CLAUDIA_TEST_CORPUS=/path/to/docs uv run pytest tests/test_test_documents_corpus.py`` runs one test per document of a
supported format under that folder; without the variable there is nothing to run and the test is skipped, so the normal
gate never depends on a corpus being present. (``scripts/run_test_documents.py --corpus DIR`` does the same with a
summary and a JSON report -- see ``test-documents/README.md``.)

A file that is not a readable package is "rejected" and passes here: refusing it is correct. A "fail" or "error" is a
finding about claudia's own import or export of a real-world file.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from claudia_test_documents import discover_corpus, run_corpus_file

_CORPUS = os.environ.get("CLAUDIA_TEST_CORPUS")
_ROOT = Path(_CORPUS).expanduser().resolve() if _CORPUS else None
_FILES = discover_corpus(_ROOT) if _ROOT is not None else []


@pytest.mark.skipif(_ROOT is None, reason="set CLAUDIA_TEST_CORPUS to a folder of documents to run them")
@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.relative_to(_ROOT).as_posix() if _ROOT else str(p))
def test_corpus_file_imports_and_round_trips(path: Path):
    assert _ROOT is not None
    result = run_corpus_file(path, _ROOT)
    assert result.status in {"pass", "rejected"}, f"{result.path}: {result.stages} -- {result.detail}"
