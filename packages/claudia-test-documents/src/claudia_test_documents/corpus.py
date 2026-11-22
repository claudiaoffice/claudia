"""Running a folder of documents nobody wrote a spec for -- an external corpus (D218's library, extended).

The catalogue (:mod:`claudia_test_documents.catalogue`) tests the few files that were chosen, checked in and given
a hand-written ``spec.py``. A corpus is the opposite: a directory of real-world files a person downloaded (Apache
POI's or LibreOffice's own test documents, say), far too many to catalogue and not ours to check in. Nothing is
known about what such a file *should* contain, so the checks here are the ones that hold for any document:

1. **import** -- the file reads into claudia's model without crashing.
2. **round trip** -- an edit that changes nothing, applied through the format's own edit-and-reexport path and read
   back, leaves the model exactly as it was.
3. **preserve** -- no package part of the original file is missing from the re-exported one. Parts that were
   rewritten are *listed* (``changed_parts``) but are not a failure: a library's own ``save()`` rewrites things
   claudia never touched, for reasons that have nothing to do with correctness (see ``test-documents/README.md``).

A file that is not a readable package at all -- a fuzzer's truncated zip, a package over the safety limits (SEC-15)
-- is **rejected**, not failed: refusing it is correct behaviour, and a corpus of real-world test files is full of
them on purpose. Any other exception while importing a file that *is* a package is an **error**: that is a bug in
claudia's own reader, which is what running a corpus is for.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

from claudia_opc_io import PackageRefused, read_parts

from .adapters import ADAPTERS, Adapter

#: What a file's result can be: "pass", "fail" (a check ran and said so), "error" (claudia's own code crashed on a
#: readable file) or "rejected" (not a readable package, or over the safety limits -- correct, not a finding).
Status = str

#: A person's own notes of how a corpus went. Bumped only if the shape of the JSON a report holds changes.
REPORT_SCHEMA_VERSION = 1

_STAGES = ("import", "round_trip", "preserve")


@dataclass
class CorpusResult:
    """How one corpus file went through the three generic checks."""

    path: str  # relative to the corpus root, with "/" on every platform, so a report reads the same everywhere
    format: str
    status: Status
    stages: dict[str, Status]
    duration_s: float
    detail: str | None = None
    changed_parts: list[str] = field(default_factory=list)
    dropped_parts: list[str] = field(default_factory=list)

    def as_report_entry(self) -> dict[str, Any]:
        """This result as one entry of a report: everything but the duration, which differs on every run and would
        make two reports of the same corpus differ for no reason."""
        entry = asdict(self)
        del entry["duration_s"]
        return entry


def discover(root: Path, *, formats: set[str] | None = None, adapters: dict[str, Adapter] | None = None) -> list[Path]:
    """Every file under ``root`` whose suffix names a format with an adapter, sorted by path.

    Hidden folders (``.git``, a cache) and Office's own lock files (``~$name.docx``) are left out -- they are never
    documents a person meant to test. ``formats`` narrows it further. ``NotADirectoryError`` if ``root`` is not a
    folder: a mistyped path is a setup error to see at once, not an empty run that looks like a clean one.
    """
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a directory")
    known = adapters if adapters is not None else ADAPTERS
    wanted = {f.lower() for f in formats} if formats is not None else None
    found: list[Path] = []
    for folder, subfolders, names in os.walk(root):
        subfolders[:] = sorted(d for d in subfolders if not d.startswith("."))
        for name in names:
            if name.startswith("~$"):
                continue
            suffix = Path(name).suffix[1:].lower()
            if suffix in known and (wanted is None or suffix in wanted):
                found.append(Path(folder) / name)
    return sorted(found)


def run_file(path: Path, root: Path, *, adapters: dict[str, Adapter] | None = None) -> CorpusResult:
    """Runs the three generic checks on one corpus file. Never raises for a finding about the file (a crash in an
    importer is an ``"error"`` result); an unreadable *path* does, since that is a setup problem."""
    start = time.monotonic()
    fmt = path.suffix[1:].lower()
    relative = path.relative_to(root).as_posix()
    stages = dict.fromkeys(_STAGES, "skipped")
    adapter = (adapters if adapters is not None else ADAPTERS).get(fmt)
    if adapter is None:
        return CorpusResult(relative, fmt, "error", stages, time.monotonic() - start, f"no adapter for {fmt!r}")

    source = path.read_bytes()
    try:
        baseline = adapter.import_fn(source)
    except (BadZipFile, PackageRefused) as exc:
        stages["import"] = "rejected"
        return CorpusResult(relative, fmt, "rejected", stages, time.monotonic() - start, _describe(exc))
    except Exception as exc:  # a crash in claudia's reader is the result, not something to propagate
        stages["import"] = "error"
        return CorpusResult(relative, fmt, "error", stages, time.monotonic() - start, _describe(exc))
    stages["import"] = "pass"

    result = CorpusResult(relative, fmt, "pass", stages, 0.0)
    if adapter.apply_edits_fn is not None:
        _round_trip(adapter, adapter.apply_edits_fn, source, baseline, result)
    result.status = _overall(stages)
    result.duration_s = time.monotonic() - start
    return result


def run_corpus(
    root: Path,
    *,
    formats: set[str] | None = None,
    fail_fast: bool = False,
    adapters: dict[str, Adapter] | None = None,
) -> Iterator[CorpusResult]:
    """:func:`~claudia_test_documents.run_corpus_file` over everything
    :func:`~claudia_test_documents.discover_corpus` finds, one result at a time so a caller can print as it goes.
    ``fail_fast`` stops after the first ``"fail"`` or ``"error"`` -- a ``"rejected"`` file is not a problem and does
    not stop it."""
    for path in discover(root, formats=formats, adapters=adapters):
        result = run_file(path, root, adapters=adapters)
        yield result
        if fail_fast and result.status in {"fail", "error"}:
            return


def summarize(results: list[CorpusResult]) -> dict[str, Any]:
    """Counts per status, the total, and the paths of the files that need a look (failed or errored; a rejected
    file is not one of them)."""
    counts = dict.fromkeys(("pass", "fail", "error", "rejected"), 0)
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return {
        "total": len(results),
        "counts": counts,
        "needs_attention": [r.path for r in results if r.status in {"fail", "error"}],
    }


def write_report(path: Path, root: Path, results: list[CorpusResult]) -> None:
    """The results as one JSON file (creating its folder): the corpus' root, a summary and every file's entry, in
    the order they ran. Timings are left out, so two reports of the same corpus differ only where the outcome did
    -- ``diff old.json new.json`` is then the answer to "what did this change fix or break?"."""
    document = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "root": str(root),
        "summary": summarize(results),
        "files": [r.as_report_entry() for r in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _round_trip(
    adapter: Adapter,
    apply_edits: Callable[[bytes, Any, Any], bytes],
    source: bytes,
    baseline: Any,
    result: CorpusResult,
) -> None:
    """Stages two and three, recorded on ``result``: the no-op edit, re-export and re-import, then the parts."""
    stages = result.stages
    try:
        working = adapter.import_fn(source)  # a second, independent import: the edit must not touch `baseline`
        edited = apply_edits(source, baseline, working)
        reimported = adapter.import_fn(edited)
    except Exception as exc:
        stages["round_trip"] = "error"
        result.detail = _describe(exc)
        return

    difference = _first_difference(_state(baseline), _state(reimported))
    if difference is None:
        stages["round_trip"] = "pass"
    else:
        stages["round_trip"] = "fail"
        result.detail = f"the model changed through a no-op edit at {difference}"

    try:
        before, after = read_parts(source), read_parts(edited)
    except Exception as exc:  # a format whose files are not zip packages has no parts to compare
        stages["preserve"] = "skipped"
        result.detail = result.detail or f"parts not compared: {_describe(exc)}"
        return
    result.dropped_parts = sorted(set(before) - set(after))
    result.changed_parts = sorted(name for name in before if name in after and before[name] != after[name])
    if result.dropped_parts:
        stages["preserve"] = "fail"
        result.detail = result.detail or f"parts missing after re-export: {', '.join(result.dropped_parts)}"
    else:
        stages["preserve"] = "pass"


def _overall(stages: dict[str, Status]) -> Status:
    if "error" in stages.values():
        return "error"
    if "fail" in stages.values():
        return "fail"
    return "pass"


def _state(model: Any) -> Any:
    """The comparable form of a model: its own ``serialize()`` when it has one (every real model does), else itself."""
    serialize = getattr(model, "serialize", None)
    return serialize() if callable(serialize) else model


def _first_difference(a: Any, b: Any, where: str = "") -> str | None:
    """Where two plain-data values first differ, as a path like ``paragraphs[3].text``; ``None`` if they are equal."""
    if isinstance(a, dict) and isinstance(b, dict):
        for key in a.keys() | b.keys():
            if key not in a or key not in b:
                return f"{where}.{key}" if where else str(key)
        for key in a:
            found = _first_difference(a[key], b[key], f"{where}.{key}" if where else str(key))
            if found is not None:
                return found
        return None
    if isinstance(a, list | tuple) and isinstance(b, list | tuple):
        for index, (x, y) in enumerate(zip(a, b, strict=False)):
            found = _first_difference(x, y, f"{where}[{index}]")
            if found is not None:
                return found
        return f"{where}[{min(len(a), len(b))}]" if len(a) != len(b) else None
    return None if a == b else (where or "<root>")


def _describe(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"
