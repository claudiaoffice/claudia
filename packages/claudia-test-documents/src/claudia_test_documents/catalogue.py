"""The catalogue: the single file deciding which test documents exist and get run, plus the status of their last
run (D218). A ``source.docx``/``spec.py`` pair sitting on disk with no entry here is not part of the library --
staged, not wired in.

Two writers share one file: a person hand-edits every field except ``last_run``, which only
:func:`record_run` ever touches, and only for the entries a run actually covered -- a filtered run (``--format
docx``) leaves every other entry's ``last_run`` exactly as it was, not overwritten with "not run this time".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

Entry = dict[str, Any]


def load(path: Path) -> list[Entry]:
    """The catalogue's entries, in file order. ``FileNotFoundError``/``json.JSONDecodeError`` propagate as-is --
    a missing or broken catalogue is a setup error worth seeing in full, not one to paper over."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entries: list[Entry] = data["documents"]
    return entries


def save(path: Path, entries: list[Entry]) -> None:
    """The inverse of :func:`load`: entries, in the order given, with a trailing newline (consistent with every
    other formatted file in this repo). Always writes the whole document back -- ``record_run`` is what keeps a
    save from clobbering fields a run did not touch, not this function."""
    data = {"schema_version": 1, "documents": entries}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def select(
    entries: list[Entry],
    *,
    formats: set[str] | None = None,
    features: set[str] | None = None,
    ids: set[str] | None = None,
    tags: set[str] | None = None,
    include_disabled: bool = False,
) -> list[Entry]:
    """The entries matching every filter given (all optional, and all narrowing -- passing several ANDs them
    together); disabled entries are left out unless ``include_disabled``."""
    selected = entries
    if not include_disabled:
        selected = [e for e in selected if e.get("enabled", True)]
    if formats is not None:
        selected = [e for e in selected if e["format"] in formats]
    if features is not None:
        selected = [e for e in selected if e["feature"] in features]
    if ids is not None:
        selected = [e for e in selected if e["id"] in ids]
    if tags is not None:
        selected = [e for e in selected if tags & set(e.get("tags", []))]
    return selected


def record_run(entries: list[Entry], entry_id: str, last_run: dict) -> None:
    """Attach ``last_run`` to the one entry with this id, in place. ``KeyError`` if no entry has it -- a result
    for an id the catalogue does not list would otherwise vanish silently."""
    for entry in entries:
        if entry["id"] == entry_id:
            entry["last_run"] = last_run
            return
    raise KeyError(f"no catalogue entry {entry_id!r}")
