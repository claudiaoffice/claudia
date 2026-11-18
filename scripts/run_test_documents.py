"""Run some or all of the test-document library (``test-documents/``, D218) and record how it went.

``uv run python scripts/run_test_documents.py``                      every enabled entry, Tiers 1-2
``uv run python scripts/run_test_documents.py --format docx``
``uv run python scripts/run_test_documents.py --feature beyond-claudia/table``
``uv run python scripts/run_test_documents.py --id a,b``              several specific entries
``uv run python scripts/run_test_documents.py --tag beyond-claudia``
``uv run python scripts/run_test_documents.py --visual``              also runs the slow Tier 3 pass
``uv run python scripts/run_test_documents.py --report``              prints current status, runs nothing
``uv run python scripts/run_test_documents.py --no-write``            prints results without touching catalogue.json
``uv run python scripts/run_test_documents.py --corpus DIR``          a folder of your own documents, no catalogue
``uv run python scripts/run_test_documents.py --corpus DIR --format xlsx --corpus-report out.json``

``--corpus DIR`` runs every document of a supported format under DIR (docx, xlsx, pptx, odt, ods, odp; other files
are ignored) through the three generic checks of ``claudia_test_documents.corpus`` -- imports, a no-op edit round-trips,
no package part goes missing -- without copying anything into ``test-documents/`` and without touching
``catalogue.json``. ``--format`` and ``--fail-fast`` narrow it; ``--corpus-report FILE`` also writes the results as
JSON, to diff between runs. A file that is not a readable package is "rejected", which is not a failure.

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

from claudia_test_documents import (
    CorpusResult,
    Entry,
    RunResult,
    load_catalogue,
    run_case,
    run_corpus,
    save_catalogue,
    select,
    summarize_corpus,
    write_corpus_report,
)

ROOT = Path(__file__).resolve().parent.parent
LIBRARY_ROOT = ROOT / "test-documents"
CATALOGUE_PATH = LIBRARY_ROOT / "catalogue.json"


def main() -> int:
    args = _parse_args()
    if args.corpus is not None:
        return _run_corpus(args)
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
    parser.add_argument(
        "--corpus",
        type=Path,
        metavar="DIR",
        help="run every document under DIR through the generic checks instead of the catalogue",
    )
    parser.add_argument(
        "--corpus-report", type=Path, metavar="FILE", help="with --corpus: also write the results to FILE as JSON"
    )
    args = parser.parse_args()
    if args.corpus is None and args.corpus_report is not None:
        parser.error("--corpus-report needs --corpus")
    if args.corpus is not None:
        # these choose catalogue entries, or write to the catalogue: they mean nothing for a folder with no catalogue
        given = {
            "--feature": args.feature,
            "--id": args.id,
            "--tag": args.tag,
            "--visual": args.visual,
            "--report": args.report,
            "--no-write": args.no_write,
        }
        unused = [flag for flag, value in given.items() if value]
        if unused:
            parser.error(f"{', '.join(unused)} cannot be combined with --corpus (they work on the catalogue)")
    return args


def _run_corpus(args: argparse.Namespace) -> int:
    root: Path = args.corpus.expanduser().resolve()
    if not root.is_dir():
        print(f"--corpus: {root} is not a directory", file=sys.stderr)
        return 2
    results: list[CorpusResult] = []
    for result in run_corpus(root, formats=set(args.format) if args.format else None, fail_fast=args.fail_fast):
        results.append(result)
        _print_corpus_result(result)
    if not results:
        print(f"no document of a supported format under {root}", file=sys.stderr)
        return 1

    summary = summarize_corpus(results)
    counts = " ".join(f"{status}={count}" for status, count in summary["counts"].items())
    print(f"\n{summary['total']} files: {counts}")
    if args.corpus_report is not None:
        write_corpus_report(args.corpus_report, root, results)
        print(f"report written to {args.corpus_report}")
    return 1 if summary["needs_attention"] else 0


def _print_corpus_result(result: CorpusResult) -> None:
    stage_summary = " ".join(f"{name}={status}" for name, status in result.stages.items())
    print(f"{result.status.upper():8} {result.path}  {stage_summary}")
    if result.detail:
        print(f"         {result.detail}")
    if result.changed_parts:
        print(f"         rewritten parts: {', '.join(result.changed_parts)}")


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
