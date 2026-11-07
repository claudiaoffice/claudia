"""Housekeeping the gate checks for directly, because each failure mode was found by accident once already.

A ``.rej`` or ``.orig`` file is a rejected patch or a backup left by a merge tool; it does not belong in history, and
a stray one can hide a change that never landed the way ``uv.lock.rej`` did (CODE-07).
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# D146/CODE-10: a regressed `ruff format` (0.15.0-0.17.4) once rewrote a valid `except (A, B):` into the invalid
# `except A, B:` (Python 2's removed syntax). The pin in pyproject.toml stops it recurring from *that* tool, but
# does not itself re-parenthesize whatever it had already broken, and `ast.parse`/`compile()` are not safe checks
# here either: an interpreter that happens to accept the unparenthesized form (as this project's own sandboxed dev
# environment was found to, 2026-11-07) would let the real bug straight through a check built on them. A plain
# text scan has no such blind spot: it catches the pattern on any interpreter, including the one running this test.
_COMMA_EXCEPT = re.compile(r"^\s*except [A-Za-z_][A-Za-z0-9_.]*\s*,\s*[A-Za-z_]", re.MULTILINE)


def test_no_rej_or_orig_files_are_tracked():
    result = subprocess.run(
        ["git", "ls-files", "*.rej", "*.orig"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    tracked = [line for line in result.stdout.splitlines() if line]
    assert not tracked, f"rejected-patch or backup files are tracked and must not be: {tracked}"


def test_no_except_clause_uses_the_removed_python_2_comma_syntax():
    result = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True)
    offenders = []
    for name in result.stdout.splitlines():
        if not name or name.startswith("claudiaoffice-log/"):
            continue  # notes and logs, not source; code in them is illustrative (matches [tool.ruff] exclude)
        text = (ROOT / name).read_text(encoding="utf-8")
        if _COMMA_EXCEPT.search(text):
            offenders.append(name)
    assert not offenders, (
        f"these files catch multiple exception types without parentheses — Python 2's removed syntax, a "
        f"SyntaxError on a standard Python 3 interpreter (this one may be a rare exception, see the note above); "
        f"wrap each in parentheses, `except (A, B):` (D146/CODE-10): {offenders}"
    )
