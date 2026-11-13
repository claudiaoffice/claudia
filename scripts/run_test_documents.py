"""Run some or all of the test-document library (``test-documents/``, D218) and record how it went.

``uv run python scripts/run_test_documents.py``                      every enabled entry, Tiers 1-2
``uv run python scripts/run_test_documents.py --format docx``
``uv run python scripts/run_test_documents.py --feature beyond-claudia/table``
``uv run python scripts/run_test_documents.py --id a,b``              several specific entries
``uv run python scripts/run_test_documents.py --tag beyond-claudia``
``uv run python scripts/run_test_documents.py --visual``              also runs the slow Tier 3 pass
``uv run python scripts/run_test_documents.py --report``              prints current status, runs nothing
``uv run python scripts/run_test_documents.py --no-write``            prints results without touching catalogue.json

Exits non-zero if anything run failed. A filtered run leaves every entry it did not cover exactly as its
``last_run`` already was -- running one entry does not mark the rest of the catalogue "not run".

See ``test-documents/README.md`` for the catalogue's layout and how to add a case.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from claudia_test_documents import Entry, RunResult, load_catalogue, run_case, save_catalogue, select

ROOT = Path(__file__).resolve().parent.parent
LIBRARY_ROOT = ROOT / "test-documents"
CATALOGUE_PATH = LIBRARY_ROOT / "catalogue.json"


def main() -> int:
    args = _parse_args()
    entries = load_catalogue(CATALOGUE_PATH)

    if args.report:
        _print_report(entries)
        return 0

    selected = select(
        entries,
        formats=set(args.format) if args.format else None,
        features=set(args.feature) if args.feature else None,
        ids=set(args.id) if args.id else None,
        tags=set(args.tag) if args.tag else None,
    )
    if not selected:
        print("no catalogue entry matches the given filters", file=sys.stderr)
        return 1

    commit = _current_commit()
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    any_failed = False
    for entry in selected:
        result = run_case(entry, LIBRARY_ROOT, visual=args.visual)
        _print_result(entry, result)
        if not args.no_write:
            entry["last_run"] = result.as_last_run(at=now, commit=commit)
        if result.status != "pass":
            any_failed = True
            if args.fail_fast:
                break

    if not args.no_write:
        save_catalogue(CATALOGUE_PATH, entries)

    return 1 if any_failed else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--format", action="append", help="only this format (repeatable)")
    parser.add_argument("--feature", action="append", help="only this feature (repeatable)")
    parser.add_argument("--id", action="append", help="only this entry id (repeatable)")
    parser.add_argument("--tag", action="append", help="only entries with this tag (repeatable)")
    parser.add_argument("--visual", action="store_true", help="also run the slow Tier 3 visual pass")
    parser.add_argument("--report", action="store_true", help="print current status and run nothing")
    parser.add_argument("--no-write", action="store_true", help="print results without updating catalogue.json")
    parser.add_argument("--fail-fast", action="store_true", help="stop after the first failing entry")
    return parser.parse_args()


def _current_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout.strip()


def _print_result(entry: Entry, result: RunResult) -> None:
    stage_summary = " ".join(f"{name}={status}" for name, status in result.stages.items())
    print(f"{result.status.upper():5} {entry['id']:35} {stage_summary}")
    if result.detail:
        print(f"      {result.detail}")


def _print_report(entries: list[Entry]) -> None:
    for entry in entries:
        last_run = entry.get("last_run")
        if last_run is None:
            print(f"{'NEVER':5} {entry['id']:35} (never run)")
            continue
        stage_summary = " ".join(f"{name}={status}" for name, status in last_run["stages"].items())
        print(f"{last_run['status'].upper():5} {entry['id']:35} {stage_summary}  ({last_run['at']})")


if __name__ == "__main__":
    sys.exit(main())
