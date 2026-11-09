"""Look for technical debt: one command, the same in CI and on a laptop.

``uv run python scripts/check_debt.py``          everything
``uv run python scripts/check_debt.py --fast``   skip the documentation build and the performance guards
``uv run python scripts/check_debt.py --ci``     a skipped check fails the build, unless named with ``--allow-skip``

A check that cannot run here (no ``node_modules``, no Linux) is *skipped*, not failed, and the final line always says
so: ``clean except skipped: …`` rather than ``everything is clean.`` — a skip is never reported as clean (PROC-02).
``--ci`` goes one step further and turns an unnamed skip into a failure, so CI must say which skips it expects with
one ``--allow-skip NAME`` per check (for example the web checks in the Python job, which the separate ``web`` job
covers on its own runner). Each check prints what it found and the script exits non-zero if any check failed. The
checks are:

* ruff       style, bugs, simplifications, performance anti-patterns
* ruff format   the enforced formatting (CODE-08); run ``uv run ruff format .`` to fix what it finds
* mypy       types of the sources
* vulture    code nobody uses (``vulture_whitelist.py`` lists the reasoned exceptions)
* i18n extraction   ``po/claudia.pot`` is current (E5.7, D31); run ``uv run python scripts/extract_i18n.py`` to fix it
* mo compilation   the Gtk client's ``de`` catalog matches ``po/de.po`` (D160); run
             ``uv run python scripts/compile_mo.py po/de.po de`` to fix it -- there was nothing worth drifting from
             before this round's real German translations existed, which is why this check is new here
* tests      the whole suite, with a note of the slowest ones
* docs       the Sphinx build with warnings as errors (every cross reference must resolve)
* perf       the scaling guards: the cost of hot paths must not grow with the history
* web tests  the web app's unit tests (vitest) and its types (vue-tsc), when Node and `npm install` in web/ are there
* e2e greeting  ``./start.sh all`` in a real browser: three servers, each greeting with its own app (UX-10). Needs
             the web app built and a Chromium for Playwright (``uv run playwright install chromium``, or point
             ``$CLAUDIA_CHROMIUM`` at one); it skips, saying which is missing, when they are not there
* linux client  its types (for Python 3.12) and its tests on the distribution's Python (clients/linux/README.md);
             the tests are skipped where there is no Python 3.12+ with PyGObject, pytest and jsonschema
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = sorted(str(p) for p in ROOT.glob("packages/*/src"))
PERF = (
    "packages/claudia-core/tests/test_performance.py",
    "packages/claudia-computes/tests/test_formula_performance.py",
    "packages/claudia-computes/tests/test_index_performance.py",
)  # (each runs on its own: the packages' conftest files would clash)
#: The one browser-driven test: it starts three servers and wants the web app built, so it is its own step (UX-10).
E2E = "tests/e2e"
DOCS_OUT = "docs/_build/html"


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    slow: bool = False
    cwd: Path = ROOT
    skip_reason: str = ""  # a check that cannot run here is skipped, not failed


@dataclass(frozen=True)
class Outcome:
    """What one check did. ``detail`` is the failure output for ``"failed"``, the reason for ``"skipped"``."""

    name: str
    status: str  # "ok" | "failed" | "skipped"
    detail: str = ""


@dataclass(frozen=True)
class Args:
    fast: bool = False
    ci: bool = False
    allow_skip: frozenset[str] = frozenset()


def parse_args(argv: list[str]) -> Args:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true", help="skip the documentation build and the performance guards")
    parser.add_argument("--ci", action="store_true", help="an unnamed skip fails the build")
    parser.add_argument("--allow-skip", action="append", default=[], metavar="NAME", help="a check --ci may let skip")
    parsed = parser.parse_args(argv)
    return Args(fast=parsed.fast, ci=parsed.ci, allow_skip=frozenset(parsed.allow_skip))


def verdict(outcomes: list[Outcome], *, ci: bool, allow_skip: set[str] | frozenset[str]) -> tuple[list[str], str]:
    """The checks that count as failed, and the one summary line the gate prints: never claims "clean" over a skip.

    Pure and side-effect free, so it is tested directly without running any check for real. Under ``--ci`` a skip
    that is not in ``allow_skip`` fails the build; outside ``--ci`` a skip is always reported, never silently "clean".
    """
    failed = [o.name for o in outcomes if o.status == "failed"]
    skipped = [o for o in outcomes if o.status == "skipped"]
    if ci:
        failed += [o.name for o in skipped if o.name not in allow_skip]
    if failed:
        message = f"FAILED: {', '.join(failed)}"
    elif skipped:
        message = "clean except skipped: " + ", ".join(f"{o.name} ({o.detail})" for o in skipped)
    else:
        message = "everything is clean."
    return failed, message


def checks() -> list[Check]:
    run = ("uv", "run", "--quiet")
    return [
        Check("ruff", (*run, "ruff", "check", ".")),
        Check("ruff format", (*run, "ruff", "format", "--check", ".")),
        Check("mypy", (*run, "mypy", *SOURCES)),
        Check("vulture", (*run, "vulture")),
        Check("i18n extraction", (*run, "python", "scripts/extract_i18n.py", "--check")),
        Check("mo compilation", (*run, "python", "scripts/compile_mo.py", "po/de.po", "de", "--check")),
        Check(
            "tests",
            (*run, "pytest", "--durations=5", "--ignore", E2E, *[a for p in PERF for a in ("--deselect", p)]),
        ),
        Check("docs", (*run, "sphinx-build", "-W", "--keep-going", "-q", "-b", "html", "docs", DOCS_OUT), slow=True),
        *[Check(f"perf {Path(path).parts[1]}", (*run, "pytest", path), slow=True) for path in PERF],
        *web_checks(),
        *e2e_checks(),
        *linux_client_checks(),
    ]


def web_checks() -> list[Check]:
    """The web app's own checks; they need Node and the packages of ``web/`` (``npm install``)."""
    web = ROOT / "web"
    reason = ""
    if shutil.which("npm") is None:
        reason = "npm is not installed"
    elif not (web / "node_modules").is_dir():
        reason = "run `npm install` in web/ first"
    return [
        Check("web tests", ("npm", "test", "--silent"), cwd=web, skip_reason=reason),
        Check("web types", ("npm", "run", "typecheck", "--silent"), slow=True, cwd=web, skip_reason=reason),
    ]


def e2e_checks() -> list[Check]:
    """The one test that drives a real browser: ``./start.sh all``, and each server greeting with its own app.

    It skips, saying which of the two is missing, when the web app is not built or there is no Chromium for
    Playwright. The test works that out itself, so the reason is written once; this asks it.
    """
    try:
        sys.path.insert(0, str(ROOT))
        from tests.e2e.test_greeting import SKIP as reason
    except Exception as exc:  # noqa: BLE001 - an import that cannot even answer is a skip with its own reason
        reason = f"the browser test cannot load ({exc})"
    finally:
        sys.path.remove(str(ROOT))
    return [Check("e2e greeting", ("uv", "run", "--quiet", "pytest", E2E), slow=True, skip_reason=reason)]


def client_python() -> str | None:
    """The interpreter that runs the Linux client's tests: ``$CLAUDIA_CLIENT_PYTHON``, else the system's ``python3``.

    It must be the distribution's Python (the client's PyGObject lives there, not in the uv environment) and must have
    pytest and jsonschema; the tests that need GTK skip themselves when ``gi`` is missing.
    """
    for candidate in (os.environ.get("CLAUDIA_CLIENT_PYTHON"), "/usr/bin/python3"):
        if candidate and Path(candidate).is_file():
            probe = subprocess.run([candidate, "-c", "import pytest, jsonschema"], capture_output=True, check=False)
            if probe.returncode == 0:
                return candidate
    return None


def linux_client_checks() -> list[Check]:
    """The Linux client (``clients/linux``): its own Python floor (3.12) and its own tests."""
    client = ROOT / "clients" / "linux"
    python = client_python()
    reason = ""
    if sys.platform != "linux":
        reason = "the Linux client is checked on Linux"
    elif python is None:
        reason = "needs Python 3.12+ with pytest and jsonschema: set CLAUDIA_CLIENT_PYTHON (clients/linux/README.md)"
    mypy = ("uv", "run", "--quiet", "--project", str(ROOT), "mypy")
    xvfb = () if os.environ.get("DISPLAY") or not shutil.which("xvfb-run") else ("xvfb-run", "-a")
    return [
        # mypy runs on the uv environment but checks for 3.12 (clients/linux/pyproject.toml); --project keeps uv from
        # making an environment inside clients/linux
        Check("mypy linux client", (*mypy, "src", "tests"), cwd=client),
        Check("linux client tests", (*xvfb, str(python), "-m", "pytest"), cwd=client, skip_reason=reason),
    ]


def run_checks(the_checks: list[Check], *, fast: bool) -> list[Outcome]:
    """Run each check in turn, printing its line as it finishes, and collect what happened."""
    outcomes = []
    for check in the_checks:
        if fast and check.slow:
            print(f"-- {check.name}: skipped (--fast)")
            outcomes.append(Outcome(check.name, "skipped", "--fast"))
            continue
        if check.skip_reason:
            print(f"-- {check.name}: skipped ({check.skip_reason})")
            outcomes.append(Outcome(check.name, "skipped", check.skip_reason))
            continue
        started = time.perf_counter()
        result = subprocess.run(check.command, cwd=check.cwd, capture_output=True, text=True, check=False)
        seconds = time.perf_counter() - started
        ok = result.returncode == 0
        print(f"-- {check.name}: {'ok' if ok else 'FAILED'} ({seconds:.1f}s)")
        if ok:
            outcomes.append(Outcome(check.name, "ok"))
        else:
            detail = (result.stdout + result.stderr).strip()
            print(detail)
            outcomes.append(Outcome(check.name, "failed", detail))
    return outcomes


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    outcomes = run_checks(checks(), fast=args.fast)
    failed, message = verdict(outcomes, ci=args.ci, allow_skip=args.allow_skip)
    print("\nTechnical debt check: " + message)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
