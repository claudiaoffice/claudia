"""Hold each package to its coverage floor (CODE-01).

``uv run python scripts/check_coverage.py``            compare the last measured run with the floors
``uv run python scripts/check_coverage.py --ratchet``  raise the floors to what was measured (never lowers one)

The measuring is done by the test suite itself: the gate's ``tests`` step runs pytest with ``--cov``, which writes
``.coverage`` at the repository root (``[tool.coverage.run]`` in ``pyproject.toml`` says what is measured). This
script only reads that file, so it costs nothing on top of the suite.

The floors are in ``pyproject.toml`` under ``[tool.claudia.coverage-floors]``, one whole percentage per package
(statements and branches together). A floor starts at what the package reached when it got one and only goes up:
when a change lifts a package past its floor by a whole point the script says so, and ``--ratchet`` writes the new
value, to be committed with the change that earned it. Lowering a floor is a decision, made by editing the table by
hand, with the reason in the commit message.
"""

from __future__ import annotations

import argparse
import io
import math
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import coverage

ROOT = Path(__file__).resolve().parent.parent
TABLE = "[tool.claudia.coverage-floors]"


@dataclass
class Report:
    """What :func:`compare` found: the floors not held, and the ones that could go up."""

    failures: list[str] = field(default_factory=list)
    raisable: dict[str, int] = field(default_factory=dict)


def compare(measured: dict[str, float], floors: dict[str, int]) -> Report:
    """Measured percentages against the floors, package by package."""
    report = Report()
    for name in sorted(measured.keys() | floors.keys()):
        if name not in measured:
            report.failures.append(f"{name}: has a floor of {floors[name]}% but was not measured")
        elif name not in floors:
            report.failures.append(f"{name}: {measured[name]:.1f}% has no floor yet (run with --ratchet to set it)")
        elif measured[name] < floors[name]:
            report.failures.append(f"{name}: {measured[name]:.1f}% is below its floor of {floors[name]}%")
        elif math.floor(measured[name]) > floors[name]:
            report.raisable[name] = math.floor(measured[name])
    return report


def ratcheted(floors: dict[str, int], measured: dict[str, float]) -> dict[str, int]:
    """The floors raised to the whole percentage each package reached; a new package gets its first floor."""
    raised = dict(floors)
    for name, percent in measured.items():
        raised[name] = max(raised.get(name, 0), math.floor(percent))
    return raised


def measure(data_file: Path, packages: Path) -> dict[str, float]:
    """The percentage of each package's ``src`` that the run behind ``data_file`` reached."""
    if not data_file.is_file():
        raise SystemExit(f"no coverage data at {data_file}: run the tests with --cov first (the gate's `tests` step)")
    cov = coverage.Coverage(data_file=str(data_file), config_file=False)
    cov.load()
    measured: dict[str, float] = {}
    for src in sorted(packages.glob("*/src")):
        try:
            measured[src.parent.name] = cov.report(include=[str(src.resolve() / "*")], file=io.StringIO())
        except coverage.exceptions.NoDataError:
            continue  # nothing of this package ran at all; compare() names it if it has a floor
    return measured


def read_floors(pyproject: Path) -> dict[str, int]:
    """The ``[tool.claudia.coverage-floors]`` table."""
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return dict(data.get("tool", {}).get("claudia", {}).get("coverage-floors", {}))


def write_floors(pyproject: Path, floors: dict[str, int]) -> None:
    """Rewrite the table's entries in place, sorted by name; its comments and everything around it stay as they are."""
    lines = pyproject.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.strip() == TABLE) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("[")), len(lines))
    comments = [line for line in lines[start:end] if line.lstrip().startswith("#")]
    entries = [f'"{name}" = {floors[name]}\n' for name in sorted(floors)]
    tail = ["\n"] if end < len(lines) else []
    pyproject.write_text("".join([*lines[:start], *comments, *entries, *tail, *lines[end:]]), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ratchet", action="store_true", help="raise the floors to what was measured")
    args = parser.parse_args(argv)
    pyproject = ROOT / "pyproject.toml"
    measured = measure(ROOT / ".coverage", ROOT / "packages")
    floors = read_floors(pyproject)
    if args.ratchet:
        floors = ratcheted(floors, measured)
        write_floors(pyproject, floors)
    report = compare(measured, floors)
    for name in sorted(measured):
        floor = "-" if name not in floors else f"{floors[name]}%"
        print(f"  {name.removeprefix('claudia-'):16} {measured[name]:5.1f}%   floor {floor}")
    for name, value in report.raisable.items():
        print(f"{name} could hold a floor of {value}% now: run with --ratchet and commit it")
    for failure in report.failures:
        print(failure, file=sys.stderr)
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
