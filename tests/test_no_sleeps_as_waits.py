"""A test does not wait by the clock for something to happen (coding standards §2, PROC-66). The tests are read, and the
fakes the packages ship for them (``testing.py``).

A nap that stands in for "it has happened by now" fails whenever the machine is slower than the nap: on CI's runners
that was a ping that took 50 ms, a model that had not started after 20 ms, a log not written after 600 ms. A test waits
for the thing itself instead: an event (``Hold.begun``, ``HostedDocument.rendered``, ``Assistant.idle``), or a poll
that asks again and again until a generous deadline. So a sleep in test code is allowed in three places only:

* ``sleep(0)``: a yield to the event loop, not a wait;
* inside a loop: the pace of a poll;
* with a comment that says which of the two other kinds it is, on its line: ``# work:`` (a stand-in for slow work,
  which the test does not wait for) or ``# must not happen:`` (a bounded wait for something that must *not* happen,
  which on a slow machine may miss a bug but never fails a sound build).
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLEEPS = {"time.sleep", "asyncio.sleep", "sleep"}
SAID = ("# work:", "# must not happen:")


def files_of_tests() -> list[Path]:
    return sorted(
        path
        for pattern in (
            "packages/*/tests/**/*.py",
            "packages/*/src/*/testing.py",
            "tests/**/*.py",
            "clients/*/tests/**/*.py",
        )
        for path in ROOT.glob(pattern)
    )


def in_a_loop(node: ast.AST, parents: dict) -> bool:
    """Is ``node`` inside a loop of its own function?"""
    parent = parents.get(node)
    while parent is not None and not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        if isinstance(parent, (ast.While, ast.For, ast.AsyncFor)):
            return True
        parent = parents.get(parent)
    return False


def naps(path: Path) -> list[int]:
    """The lines of ``path`` with a sleep that is neither a yield, nor a poll's pace, nor said to be work or a wait for
    something that must not happen."""
    source = path.read_text(encoding="utf-8")
    lines, tree = source.splitlines(), ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and ast.unparse(node.func) in SLEEPS):
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 0:
            continue
        if any(said in lines[node.lineno - 1] for said in SAID):
            continue
        if not in_a_loop(node, parents):
            found.append(node.lineno)
    return found


def test_no_test_sleeps_to_wait_for_something_to_happen():
    found = {str(path.relative_to(ROOT)): lines for path in files_of_tests() if (lines := naps(path))}
    assert found == {}, (
        "wait for the thing itself (an event, or a poll with a deadline), or say on the line what the sleep is"
        f" (# work: or # must not happen:): {found}"
    )


def test_the_check_finds_a_nap_and_lets_the_others_be(tmp_path):
    test = tmp_path / "test_example.py"
    test.write_text(
        "import asyncio, time\n"
        "def test_a():\n"
        "    time.sleep(0.2)\n"  # line 3: a nap
        "    while True:\n"
        "        time.sleep(0.01)\n"  # a poll's pace
        "    time.sleep(0.3)  # must not happen: it would be gone by now\n"
        "async def test_b():\n"
        "    await asyncio.sleep(0)\n"  # a yield
        "    await asyncio.sleep(0.05)\n"  # line 9: a nap
        "def work():\n"
        "    time.sleep(1)  # work: the stand-in is slow\n",
        encoding="utf-8",
    )
    assert naps(test) == [3, 9]
