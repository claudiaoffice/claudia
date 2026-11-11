"""Fail on known vulnerabilities in the npm dependencies (SEC-08).

``uv run python scripts/check_npm_audit.py``                  audit every ``package-lock.json``
``uv run python scripts/check_npm_audit.py --level high``     only high and critical advisories fail

Asks ``npm audit`` about each lockfile (``web/`` and every ``clients/*``), development tools included: a flaw in
``vitest`` runs on the laptop of everyone who runs the tests. Only the lockfile is read, so no ``node_modules`` is
needed, but the registry has to answer. Exit status: ``0`` clean, ``1`` an advisory at or above the level (or a
broken allow-list), ``3`` the audit could not be done (no npm, no network). The gate treats ``3`` as a skip, which CI
turns into a failure (PROC-02): an audit that did not happen is never reported as a clean one.

A finding is fixed by updating the direct dependency that brings the package in, or by an ``overrides`` entry in that
``package.json`` where the dependent has no newer release. What cannot be fixed is recorded in ``pyproject.toml`` with
the reason, one entry per advisory::

    [[tool.claudia.npm-audit-allow]]
    advisory = "GHSA-xxxx-xxxx-xxxx"
    reason = "why this one is acceptable, and what to wait for"

An entry that nothing needs any more fails the check, so the list only ever holds what it must.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

#: Exit status for "the audit could not be done"; ``scripts/check_debt.py`` reads it as a skip.
UNREACHABLE = 3
LEVELS = ("info", "low", "moderate", "high", "critical")
DEFAULT_LEVEL = "moderate"
TABLE = "[[tool.claudia.npm-audit-allow]]"


class Unreachable(Exception):
    """npm could not give an answer: no registry, a timeout, or output that is not an audit report."""


@dataclass(frozen=True)
class Advisory:
    """One published vulnerability, as ``npm audit`` names it."""

    ident: str
    package: str
    severity: str
    title: str
    url: str


@dataclass(frozen=True)
class Allowed:
    """An advisory the project accepts, and why."""

    advisory: str
    reason: str


@dataclass
class Verdict:
    """What :func:`judge` found: the failures, the advisories allowed (with reasons), how many are below the level."""

    failures: list[str] = field(default_factory=list)
    allowed: dict[str, str] = field(default_factory=dict)
    below_level: int = 0

    @property
    def ok(self) -> bool:
        return not self.failures


def rank(severity: str) -> int:
    """Position on the scale; a severity npm adds later counts as the worst, so it is never waved through."""
    return LEVELS.index(severity) if severity in LEVELS else len(LEVELS)


def advisories(report: dict[str, Any]) -> list[Advisory]:
    """Every advisory in an ``npm audit --json`` report, once each, in the order npm lists them.

    A vulnerable package lists its advisories in ``via`` next to the names of other vulnerable packages it depends
    on; only the advisories are read, because the names are the same findings seen from further up.
    """
    found: dict[str, Advisory] = {}
    for vulnerability in report.get("vulnerabilities", {}).values():
        for via in vulnerability.get("via", []):
            if isinstance(via, dict):
                url = str(via.get("url", ""))
                ident = url.rsplit("/", 1)[-1] or str(via.get("source", "?"))
                found.setdefault(
                    ident,
                    Advisory(
                        ident, str(via.get("name", "?")), str(via.get("severity", "")), str(via.get("title", "")), url
                    ),
                )
    return list(found.values())


def direct_dependents(report: dict[str, Any], package: str) -> list[str]:
    """The packages in ``package.json`` that bring ``package`` in: what to update (or to put an override beside)."""
    vulnerabilities = report.get("vulnerabilities", {})
    direct: set[str] = set()
    seen: set[str] = set()
    pending = [package]
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        entry = vulnerabilities.get(name, {})
        if entry.get("isDirect"):
            direct.add(name)
        else:
            pending.extend(entry.get("effects", []))
    return sorted(direct)


def describe(project: str, report: dict[str, Any], found: Advisory) -> str:
    """One failure, with what is needed to act on it: the advisory, its link, and the dependency to update."""
    route = ", ".join(direct_dependents(report, found.package)) or "what depends on it"
    return (
        f"{project}: {found.package} is {found.severity}, {found.ident}: {found.title}. "
        f"Update {route}, or add an override ({found.url})"
    )


def judge(reports: dict[str, dict[str, Any]], *, level: str, allow: list[Allowed]) -> Verdict:
    """The reports of every project against the level and the allow-list."""
    verdict = Verdict()
    reasons = {entry.advisory: entry.reason for entry in allow}
    needed: set[str] = set()
    for project, report in reports.items():
        for found in advisories(report):
            if rank(found.severity) < rank(level):
                verdict.below_level += 1
            elif found.ident in reasons:
                needed.add(found.ident)
                verdict.allowed[found.ident] = reasons[found.ident]
            else:
                verdict.failures.append(describe(project, report, found))
    verdict.failures += [
        f"pyproject.toml: the allow-list entry {ident} is not needed any more (no advisory at or above {level} "
        f"matches it): remove it from {TABLE}"
        for ident in reasons
        if ident not in needed
    ]
    return verdict


def read_allowlist(pyproject: Path) -> list[Allowed]:
    """The ``[[tool.claudia.npm-audit-allow]]`` entries; one without a written reason is refused."""
    with pyproject.open("rb") as handle:
        entries = tomllib.load(handle).get("tool", {}).get("claudia", {}).get("npm-audit-allow", [])
    allowed = []
    for entry in entries:
        advisory = str(entry.get("advisory", "")).strip()
        reason = str(entry.get("reason", "")).strip()
        if not advisory:
            raise SystemExit(f"{pyproject.name}: every {TABLE} entry needs an `advisory` (a GHSA id)")
        if not reason:
            raise SystemExit(f"{pyproject.name}: the entry for {advisory} needs a written `reason`")
        allowed.append(Allowed(advisory, reason))
    return allowed


def lockfiles(root: Path = ROOT) -> list[Path]:
    """The lockfiles to audit: the web app's and every client's. A test fails if the repository has another."""
    return sorted([*root.glob("web/package-lock.json"), *root.glob("clients/*/package-lock.json")])


def error_text(output: Any) -> str:
    """What npm says went wrong when its JSON is an error object instead of a report: the code and the message."""
    if not isinstance(output, dict):
        return "unexpected output"
    error = output.get("error")
    code = error.get("code", "") if isinstance(error, dict) else ""
    return f"{code} {output.get('message', '')}".strip() or "unexpected output"


def run_audit(
    npm: str,
    folder: Path,
    *,
    run: Callable[..., Any] = subprocess.run,
    attempts: int = 2,
    pause: float = 3.0,
    timeout: float = 120,
) -> dict[str, Any]:
    """Ask npm to audit the lockfile in ``folder``; try again once, because a registry hiccups now and then.

    npm exits non-zero when it finds something, so the exit status says nothing: the report does. Output that is no
    report (an error object, text, nothing) raises :class:`Unreachable`.
    """
    problem = ""
    for attempt in range(attempts):
        if attempt:
            time.sleep(pause)
        try:
            result = run(
                [npm, "audit", "--package-lock-only", "--json"],
                cwd=folder,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            problem = f"npm audit did not answer within {timeout:.0f} s"
            continue
        try:
            report = json.loads(result.stdout)
        except ValueError:
            problem = f"npm audit printed no report: {(result.stdout + result.stderr).strip()[:200] or 'nothing'}"
            continue
        if isinstance(report, dict) and "vulnerabilities" in report:
            return report
        problem = f"npm audit could not run: {error_text(report)}"
    raise Unreachable(problem.strip())


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail on known vulnerabilities in the npm dependencies.")
    parser.add_argument(
        "--level",
        choices=[name for name in LEVELS if name != "info"],
        default=DEFAULT_LEVEL,
        help=f"the least severity that fails (default: {DEFAULT_LEVEL})",
    )
    return parser.parse_args(argv)


def main(
    argv: list[str],
    *,
    root: Path = ROOT,
    which: Callable[[str], str | None] = shutil.which,
    audit: Callable[[str, Path], dict[str, Any]] = run_audit,
) -> int:
    """Audit every lockfile, print what was found, and return the exit status (see the module docstring)."""
    args = parse_args(argv)
    npm = which("npm")
    if npm is None:
        print("could not audit: npm is not installed")
        return UNREACHABLE
    files = lockfiles(root)
    if not files:
        print(f"no package-lock.json found under {root}: nothing to audit, which is a mistake")
        return 1
    reports: dict[str, dict[str, Any]] = {}
    for lockfile in files:
        project = lockfile.parent.relative_to(root).as_posix()
        try:
            reports[project] = audit(npm, lockfile.parent)
        except Unreachable as problem:
            print(f"could not audit {project}: {problem}")
            return UNREACHABLE
        print(f"audited {project}")
    verdict = judge(reports, level=args.level, allow=read_allowlist(root / "pyproject.toml"))
    for ident, reason in sorted(verdict.allowed.items()):
        print(f"allowed {ident}: {reason}")
    for failure in verdict.failures:
        print(f"FAILED {failure}")
    below = f"; {verdict.below_level} below {args.level} not counted" if verdict.below_level else ""
    print(f"npm audit: {'no advisory at or above ' + args.level if verdict.ok else 'advisories to deal with'}{below}")
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
