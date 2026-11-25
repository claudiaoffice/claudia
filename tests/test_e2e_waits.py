"""The browser tests wait in a way the page's Content-Security-Policy allows (PROC-60).

Playwright runs a bare expression given to ``wait_for_function`` (``"document.querySelector('.x')"``) through ``eval``,
which the page's policy forbids: it works only when the condition already holds at the first look, and fails with an
``EvalError`` as soon as it has to poll. A function (``"sel => document.querySelector(sel)"``, with ``arg``) is not
evaluated that way, and a locator's ``wait_for`` not at all. Measured 2026-11-25 against a page served with
``script-src 'self'``: the bare expression failed, the other two waited.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: what a function given as text starts with: `x =>`, `(a, b) =>`, `([a, b]) =>`, `function`, `async`
A_FUNCTION = re.compile(r"^\s*(async\b|function\b|\w+\s*=>|\(.*?\)\s*=>)", re.DOTALL)


def bare_expressions(path: Path) -> list[int]:
    """The lines of ``path`` where ``wait_for_function`` is given a bare expression as text."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "wait_for_function" or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str) and not A_FUNCTION.match(first.value):
            found.append(node.lineno)
    return found


def test_a_bare_expression_is_found_and_a_function_is_not(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text(
        "page.wait_for_function(\"document.querySelector('.health.open')\")\n"
        "page.wait_for_function('sel => document.querySelector(sel)', arg='.x')\n"
        "page.wait_for_function('([sel, n]) => document.querySelectorAll(sel).length > n', arg=['.x', 1])\n"
        "page.wait_for_function(SHOWN, arg=1)\n",
        encoding="utf-8",
    )
    assert bare_expressions(sample) == [1]


def test_no_browser_test_waits_for_a_bare_expression():
    offenders = {
        str(path.relative_to(ROOT)): lines
        for path in sorted((ROOT / "tests" / "e2e").rglob("*.py"))
        if (lines := bare_expressions(path))
    }
    assert not offenders, (
        "wait_for_function with a bare expression fails on the page's Content-Security-Policy once it has to poll"
        f" (PROC-60): wait with a locator, or give a function and its arg instead: {offenders}"
    )
