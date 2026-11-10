"""Running one catalogue entry through the three tiers (D218): import checks, an edit-and-reexport round trip,
targeted preservation, and (opt-in) the visual backstop. See :mod:`claudia_test_documents.case` for what a
``spec.py`` declares and :mod:`claudia_test_documents.adapters` for what a format needs to support which stages.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from claudia_opc_io import read_parts

from .adapters import ADAPTERS, Adapter
from .case import Case, Model
from .loader import load_case

#: Every stage's status: "pass"/"fail" (a check ran and said so), "error" (the check itself raised something
#: other than AssertionError -- a bug in the spec or the adapter, not a finding about the file), "n/a" (the case
#: defines no check for this stage), "skipped" (the stage needs a capability -- an adapter's ``apply_edits_fn``
#: -- this format does not have yet).
Status = str


@dataclass
class RunResult:
    status: Status  # "pass" if every stage is pass/n_a/skipped; "fail"/"error" otherwise
    stages: dict[str, Status]
    duration_s: float
    detail: str | None = None

    def as_last_run(self, *, at: str, commit: str | None) -> dict:
        """This result, shaped as a catalogue entry's ``last_run`` block."""
        return {
            "at": at,
            "commit": commit,
            "status": self.status,
            "stages": self.stages,
            "duration_s": round(self.duration_s, 3),
            "detail": self.detail,
        }


def run_case(
    entry: dict, library_root: Path, *, visual: bool = False, adapters: dict[str, Adapter] | None = None
) -> RunResult:
    """Runs the catalogue entry ``entry`` (a dict as :func:`claudia_test_documents.catalogue.load` returns one)
    against the real files under ``library_root`` -- the catalogue's own directory (``entry["source"]``/
    ``entry["spec"]`` are relative to it, same as the catalogue file itself). Never raises for a finding about
    the test case itself -- a failed assertion or a format without the needed adapter capability becomes a
    stage result, not an exception -- but a genuinely broken spec file (:func:`load_case`'s own errors) or a
    missing source file does, since those are setup problems to fix, not results to record. ``adapters``
    defaults to the real :data:`ADAPTERS` registry; a test passes its own to run against a fake format with no
    real io package."""
    start = time.monotonic()
    stages: dict[str, Status] = {"import": "n/a", "round_trip": "n/a", "preserve": "n/a", "visual": "not_run"}
    detail: str | None = None

    adapter = (adapters if adapters is not None else ADAPTERS).get(entry["format"])
    if adapter is None:
        stages = dict.fromkeys(stages, "skipped")
        return RunResult("fail", stages, time.monotonic() - start, f"no adapter registered for {entry['format']!r}")

    source_bytes = (library_root / entry["source"]).read_bytes()
    case = load_case(library_root / entry["spec"], entry["id"])

    baseline = adapter.import_fn(source_bytes)
    stages["import"], detail = _check(case.import_checks, baseline, detail)

    if adapter.apply_edits_fn is None:
        stages["round_trip"] = stages["preserve"] = "skipped"
    else:
        working = adapter.import_fn(source_bytes)  # a second, independent import: `modify` never touches `baseline`
        current = case.modify(working) if case.modify is not None else working
        edited_bytes = adapter.apply_edits_fn(source_bytes, baseline, current)

        reimported = adapter.import_fn(edited_bytes)
        stages["round_trip"], detail = _check_round_trip(case, reimported, edited_bytes, detail)

        stages["preserve"], detail = _check_preserve(case, source_bytes, edited_bytes, detail)

        if visual and case.visual:
            stages["visual"], detail = _check_visual(entry, library_root, source_bytes, edited_bytes, detail)

    failed = {"fail", "error"}
    overall: Status = "fail" if failed & set(stages.values()) else "pass"
    return RunResult(overall, stages, time.monotonic() - start, detail)


def _check(check: Callable[[Model], None] | None, model: Model, detail: str | None) -> tuple[Status, str | None]:
    if check is None:
        return "n/a", detail
    try:
        check(model)
    except AssertionError as exc:
        return "fail", detail or str(exc)
    except Exception as exc:  # a check's own bug is a result to report, not to propagate
        return "error", detail or f"{type(exc).__name__}: {exc}"
    return "pass", detail


def _check_round_trip(
    case: Case, reimported: Model, edited_bytes: bytes, detail: str | None
) -> tuple[Status, str | None]:
    """``after_checks`` (``import_checks`` when not given) against the reimported model, and ``export_checks``
    against the raw re-exported bytes -- both belong to "did this round trip come out right", just inspected
    two different ways; a stage result where either one disagrees is the whole stage's result."""
    after_checks = case.after_checks if case.after_checks is not None else case.import_checks
    model_status, detail = _check(after_checks, reimported, detail)
    export_status, detail = _check_bytes(case.export_checks, edited_bytes, detail)
    statuses = {model_status, export_status}
    if statuses & {"fail", "error"}:
        return ("error" if "error" in statuses else "fail"), detail
    if "pass" in statuses:
        return "pass", detail
    return "n/a", detail


def _check_bytes(check: Callable[[bytes], None] | None, data: bytes, detail: str | None) -> tuple[Status, str | None]:
    if check is None:
        return "n/a", detail
    try:
        check(data)
    except AssertionError as exc:
        return "fail", detail or str(exc)
    except Exception as exc:  # a check's own bug is a result to report, not to propagate
        return "error", detail or f"{type(exc).__name__}: {exc}"
    return "pass", detail


def _check_preserve(
    case: Case, source_bytes: bytes, edited_bytes: bytes, detail: str | None
) -> tuple[Status, str | None]:
    if not case.preserve_parts and case.preserve_elements is None:
        return "n/a", detail
    if case.preserve_parts:
        before, after = read_parts(source_bytes), read_parts(edited_bytes)
        for name in case.preserve_parts:
            if before.get(name) != after.get(name):
                return "fail", detail or f"{name} did not survive the round trip unchanged"
    if case.preserve_elements is not None:
        try:
            case.preserve_elements(source_bytes, edited_bytes)
        except AssertionError as exc:
            return "fail", detail or str(exc)
        except Exception as exc:  # same reporting stance as `_check`
            return "error", detail or f"{type(exc).__name__}: {exc}"
    return "pass", detail


def _check_visual(
    entry: dict, library_root: Path, source_bytes: bytes, edited_bytes: bytes, detail: str | None
) -> tuple[Status, str | None]:
    from .render import (
        visual_diff,  # imported lazily: Pillow/soffice are only needed when --visual is actually asked for
    )

    suffix = f".{entry['format']}"
    artifacts_dir = library_root / "_artifacts" / entry["id"]
    within_tolerance, score, diff_path = visual_diff(source_bytes, edited_bytes, suffix, artifacts_dir)
    if within_tolerance:
        return "pass", detail
    return "fail", detail or f"visual difference {score:.3f} exceeds tolerance (see {diff_path})"
