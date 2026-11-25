"""Every story that is done has a test of its key risk, marked "must not break" (coding standards §2, PROC-68).

The mark names the story whose risk the test covers, in the form of the place the test lives:

* Python: ``@pytest.mark.must_not_break("E7.11")`` on the test function;
* Gherkin: the tag ``@must-not-break:E7.11`` on the scenario;
* TypeScript (vitest): ``[must not break: E7.11]`` in the test's title.

A story that was done before the rule stands in ``NOT_MARKED_YET``. The list only shrinks: a story that gets its mark is
taken off it, and a story that is done from now on comes with its mark.
"""

import ast
import re
from pathlib import Path

from test_backlog import STORY_ID, tasks, unquoted

ROOT = Path(__file__).resolve().parent.parent
GHERKIN_TAG = re.compile(r"@must-not-break:(E\d+(?:\.\d+)?)\b")
VITEST_TITLE = re.compile(r"\[must not break: (E\d+(?:\.\d+)?)\]")

#: Done before the rule of 2026-11-25; the owner says which test covers each one's key risk.
NOT_MARKED_YET = frozenset(
    [
        "E0.3",
        "E0.4",
        "E0.5",
        "E1.1",
        "E1.2",
        "E1.3",
        "E1.4",
        "E1.5",
        "E1.6",
        "E1.7",
        "E1.8",
        "E1.10",
        "E1.11",
        "E1.12",
        "E2.1",
        "E2.5",
        "E2.6",
        "E2.7",
        "E2.10",
        "E3.1",
        "E3.7",
        "E3.8",
        "E3.14",
        "E4.1",
        "E4.2",
        "E4.7",
        "E5.14",
        "E6.13",
        "E6.16",
        "E6.24",
        "E7.2",
        "E7.10",
        "E9.2",
        "E9.4",
        "E9.21",
        "E9.22",
        "E9.23",
        "E9.25",
        "E9.26",
        "E9.30",
        "E9.31",
        "E10.12",
        "E10.15",
        "E10.18",
        "E11.4",
        "E11.8",
    ]
)


def python_marks(path: Path) -> list[tuple[str, str]]:
    """``(story, test name)`` for every test in ``path`` marked ``must_not_break``."""
    return [
        (str(decorator.args[0].value), node.name)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for decorator in node.decorator_list
        if isinstance(decorator, ast.Call)
        and ast.unparse(decorator.func).endswith("mark.must_not_break")
        and decorator.args
        and isinstance(decorator.args[0], ast.Constant)
    ]


def marks() -> list[tuple[str, str]]:
    """Every "must not break" mark of the repository: ``(story, where)``."""
    found = []
    for pattern in ("packages/*/tests/**/*.py", "tests/**/*.py", "clients/*/tests/**/*.py"):
        for path in sorted(ROOT.glob(pattern)):
            found += [(story, f"{path.relative_to(ROOT)}::{name}") for story, name in python_marks(path)]
    for path in sorted((ROOT / "claudiaoffice-log" / "specs").glob("**/*.feature")):
        found += [(story, str(path.relative_to(ROOT))) for story in GHERKIN_TAG.findall(path.read_text("utf-8"))]
    for folder in ("web/tests", "layout/tests", "clients/neutralino/tests"):
        for path in sorted((ROOT / folder).glob("**/*.test.ts")):
            found += [(story, str(path.relative_to(ROOT))) for story in VITEST_TITLE.findall(path.read_text("utf-8"))]
    return found


def stories() -> dict[str, str]:
    """The backlog's stories by their E-number, with their status."""
    found = {}
    for fields in tasks().values():
        number = STORY_ID.match(unquoted(fields.get("title", "")))
        if number:
            found[number.group(0)] = unquoted(fields.get("status", ""))
    return found


def test_every_mark_names_a_story_of_the_backlog():
    known = stories()
    assert [(story, where) for story, where in marks() if story not in known] == []


def test_every_story_that_is_done_has_a_test_that_must_not_break():
    marked = {story for story, _ in marks()}
    done = {story for story, status in stories().items() if status == "done"}
    assert sorted(done - marked - NOT_MARKED_YET) == [], "mark the test of each story's key risk (coding standards §2)"


def test_the_list_of_stories_not_marked_yet_only_shrinks():
    marked = {story for story, _ in marks()}
    assert sorted(NOT_MARKED_YET & marked) == [], "these have their mark now: take them off NOT_MARKED_YET"


def test_the_three_forms_are_found(tmp_path):
    test = tmp_path / "test_x.py"
    test.write_text('import pytest\n@pytest.mark.must_not_break("E1.2")\ndef test_a():\n    pass\n', encoding="utf-8")
    assert [story for story, _ in python_marks(test)] == ["E1.2"]
    assert GHERKIN_TAG.findall("  @core @must-not-break:E9.21\n  Scenario: x") == ["E9.21"]
    assert VITEST_TITLE.findall("it('[must not break: E6.13] keeps the style', () => {})") == ["E6.13"]
