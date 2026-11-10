"""Every enabled entry in the test-document library (``test-documents/``, D218) runs clean as part of the
normal gate -- Tiers 1-2 only (no ``soffice``, no network, no catalogue write-back: that is
``scripts/run_test_documents.py``'s job, run on purpose, not a side effect of ``pytest``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from claudia_test_documents import load_catalogue, run_case, select

ROOT = Path(__file__).resolve().parent.parent
LIBRARY_ROOT = ROOT / "test-documents"


def _enabled_entries() -> list[dict]:
    return select(load_catalogue(LIBRARY_ROOT / "catalogue.json"))


@pytest.mark.parametrize("entry", _enabled_entries(), ids=lambda e: e["id"])
def test_catalogue_entry_passes(entry: dict):
    result = run_case(entry, LIBRARY_ROOT, visual=False)
    assert result.status == "pass", f"{entry['id']}: {result.stages} -- {result.detail}"
