"""load/save round-trip, select's filters, and record_run's targeted update (D178)."""

from __future__ import annotations

from pathlib import Path

import pytest

from claudia_test_documents.catalogue import load, record_run, save, select


def _catalogue(tmp_path: Path) -> Path:
    path = tmp_path / "catalogue.json"
    save(
        path,
        [
            {"id": "a", "format": "docx", "feature": "bold", "enabled": True, "tags": ["tier1"]},
            {"id": "b", "format": "docx", "feature": "beyond-claudia/table", "enabled": True, "tags": ["tier2"]},
            {"id": "c", "format": "odt", "feature": "bold", "enabled": False, "tags": ["tier1"]},
        ],
    )
    return path


def test_save_then_load_round_trips_every_entry_in_order(tmp_path: Path):
    path = _catalogue(tmp_path)
    entries = load(path)
    assert [e["id"] for e in entries] == ["a", "b", "c"]


def test_select_defaults_to_enabled_entries_only(tmp_path: Path):
    entries = load(_catalogue(tmp_path))
    assert {e["id"] for e in select(entries)} == {"a", "b"}


def test_select_include_disabled_brings_back_everything(tmp_path: Path):
    entries = load(_catalogue(tmp_path))
    assert {e["id"] for e in select(entries, include_disabled=True)} == {"a", "b", "c"}


def test_select_narrows_by_format_feature_id_and_tag(tmp_path: Path):
    entries = load(_catalogue(tmp_path))
    assert {e["id"] for e in select(entries, formats={"docx"})} == {"a", "b"}
    assert {e["id"] for e in select(entries, features={"bold"})} == {"a"}
    assert {e["id"] for e in select(entries, ids={"b"})} == {"b"}
    assert {e["id"] for e in select(entries, tags={"tier2"})} == {"b"}


def test_select_filters_combine_with_and(tmp_path: Path):
    entries = load(_catalogue(tmp_path))
    assert [e["id"] for e in select(entries, formats={"docx"}, tags={"tier2"})] == ["b"]


def test_record_run_updates_only_the_named_entry(tmp_path: Path):
    path = _catalogue(tmp_path)
    entries = load(path)
    record_run(entries, "b", {"status": "pass"})
    assert entries[1]["last_run"] == {"status": "pass"}
    assert "last_run" not in entries[0]
    assert "last_run" not in entries[2]


def test_record_run_preserves_hand_written_fields(tmp_path: Path):
    path = _catalogue(tmp_path)
    entries = load(path)
    record_run(entries, "a", {"status": "fail"})
    save(path, entries)
    reloaded = load(path)
    assert reloaded[0]["feature"] == "bold"
    assert reloaded[0]["last_run"] == {"status": "fail"}
    assert "last_run" not in reloaded[1]


def test_record_run_raises_for_an_unknown_id(tmp_path: Path):
    entries = load(_catalogue(tmp_path))
    with pytest.raises(KeyError):
        record_run(entries, "no-such-id", {"status": "pass"})
