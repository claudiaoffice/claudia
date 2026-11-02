"""Look for technical debt: one command, the same in CI and on a laptop.

``uv run python scripts/check_debt.py``          everything
``uv run python scripts/check_debt.py --fast``   skip the documentation build and the performance guards

Each check prints what it found and the script exits non-zero if any check failed. The checks are:

* ruff       style, bugs, simplifications, performance anti-patterns
* mypy       types of the sources
* vulture    code nobody uses (``vulture_whitelist.py`` lists the reasoned exceptions)
* tests      the whole suite, with a note of the slowest ones
* docs       the Sphinx build with warnings as errors (every cross reference must resolve)
* perf       the scaling guards: the cost of hot paths must not grow with the history
* web tests  the web app's unit tests (vitest) and its types (vue-tsc), when Node and `npm install` in web/ are there
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = sorted(str(p) for p in ROOT.glob("packages/*/src"))
PERF = "packages/claudia-core/tests/test_performance.py"
DOCS_OUT = "docs/_build/html"


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    slow: bool = False
    cwd: Path = ROOT
    skip_reason: str = ""  # a check that cannot run here is skipped, not failed


def checks() -> list[Check]:
    run = ("uv", "run", "--quiet")
    return [
        Check("ruff", (*run, "ruff", "check", ".")),
        Check("mypy", (*run, "mypy", *SOURCES)),
        Check("vulture", (*run, "vulture")),
        Check("tests", (*run, "pytest", "--durations=5", "--deselect", PERF)),
        Check("docs", (*run, "sphinx-build", "-W", "--keep-going", "-q", "-b", "html", "docs", DOCS_OUT), slow=True),
        Check("perf", (*run, "pytest", PERF), slow=True),
        *web_checks(),
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


def main(argv: list[str]) -> int:
    fast = "--fast" in argv
    failed: list[str] = []
    for check in checks():
        if fast and check.slow:
            print(f"-- {check.name}: skipped (--fast)")
            continue
        if check.skip_reason:
            print(f"-- {check.name}: skipped ({check.skip_reason})")
            continue
        started = time.perf_counter()
        result = subprocess.run(check.command, cwd=check.cwd, capture_output=True, text=True, check=False)
        seconds = time.perf_counter() - started
        status = "ok" if result.returncode == 0 else "FAILED"
        print(f"-- {check.name}: {status} ({seconds:.1f}s)")
        if result.returncode != 0:
            failed.append(check.name)
            print((result.stdout + result.stderr).strip())
    print("\nTechnical debt check: " + ("everything is clean." if not failed else f"FAILED: {', '.join(failed)}"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
