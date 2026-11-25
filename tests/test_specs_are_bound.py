"""Every scenario in ``claudiaoffice-log/specs`` is run by a test, or says which test checks it (E11.8, PROC-40, D1450).

The owner approves scenarios before they are built; a feature file that no test reads is an approved behaviour that
nothing checks, and nobody notices. On 2026-11-21 four files ran nowhere. A file passes when one of these holds:

- a ``test_*.py`` in ``tests/e2e/specs`` binds it with ``scenarios("…/<file>.feature")``;
- every scenario carries the tag of the test that checks it (``@unit:<path>``, ``@io:<path>``, ``@e2e:<script>``), on
  the scenario, on all of its ``Examples``, or once on the ``Feature:`` for all of them;
- it is a draft waiting for the owner's review: ``@draft`` on its ``Feature:`` line (D1451).
"""

from __future__ import annotations

import re
from pathlib import Path

from gherkin.parser import Parser
from gherkin.token_scanner import TokenScanner

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "claudiaoffice-log" / "specs"
STEP_CODE = ROOT / "tests" / "e2e" / "specs"
TASKS = ROOT / "claudiaoffice-log" / "Projects" / "claudia-office" / "_tasks"
TEST_TAGS = ("@unit:", "@io:", "@e2e:")
#: Approved files that cannot be bound yet, each with the story or bug that binds it. Only ever shrinks: the test below
#: fails when an entry is no longer needed. Adding an entry is a decision for the owner, not a way to get CI green.
NOT_BOUND_YET = {}
HOW_TO_FIX = (
    "Bind the file in a tests/e2e/specs/test_<feature>.py with scenarios(...); or tag every scenario with the test that"
    " checks it (@unit:<path>, @io:<path>, @e2e:<script>); or, while the owner has not approved it yet, put @draft on"
    " its Feature: line (claudiaoffice-log/specs/README.md, Tags)."
)
# scenarios(...) binds a whole file; scenario(file, name) binds one scenario and does not count
_BINDING = re.compile(r"""\bscenarios\(\s*["']([^"']+\.feature)["']""")


def _feature(path: Path) -> dict:
    return Parser().parse(TokenScanner(path.read_text(encoding="utf-8")))["feature"]


def _tags(node: dict) -> list[str]:
    return [tag["name"] for tag in node.get("tags", [])]


def _scenarios(node: dict, inherited: list[str]) -> list[tuple[str, list[str], list[list[str]]]]:
    """(name, its tags with those of the feature and rule, the tags of each Examples block) of every scenario."""
    found = []
    for child in node.get("children", []):
        if "rule" in child:
            rule = child["rule"]
            found += _scenarios(rule, inherited + _tags(rule))
        elif "scenario" in child:
            scenario = child["scenario"]
            examples = [_tags(block) for block in scenario.get("examples", [])]
            found.append((scenario["name"], inherited + _tags(scenario), examples))
    return found


def _has_test_tag(tags: list[str]) -> bool:
    return any(tag.startswith(TEST_TAGS) for tag in tags)


def _checked_by_a_tag(tags: list[str], examples: list[list[str]]) -> bool:
    return _has_test_tag(tags) or (bool(examples) and all(_has_test_tag(block) for block in examples))


def _bound() -> set[Path]:
    bound = set()
    for test in STEP_CODE.glob("test_*.py"):
        for target in _BINDING.findall(test.read_text(encoding="utf-8")):
            bound.add((test.parent / target).resolve())
    return bound


def _features() -> list[Path]:
    return sorted(SPECS.rglob("*.feature"))


def _name(path: Path) -> str:
    return path.relative_to(SPECS).as_posix()


def _is_draft(path: Path) -> bool:
    return "@draft" in _tags(_feature(path))


def _unchecked(path: Path, bound: set[Path]) -> list[str]:
    """The scenarios of an approved file that no test checks (none when the file is bound)."""
    if path.resolve() in bound:
        return []
    feature = _feature(path)
    scenarios = _scenarios(feature, _tags(feature))
    return [name for name, tags, examples in scenarios if not _checked_by_a_tag(tags, examples)]


def test_every_spec_file_is_run_by_a_test():
    bound = _bound()
    lost = []
    for path in _features():
        if _name(path) in NOT_BOUND_YET or _is_draft(path):
            continue
        unchecked = _unchecked(path, bound)
        if unchecked:
            lost.append(f"{_name(path)}: {len(unchecked)} scenario(s) no test checks, e.g. {unchecked[0]!r}")
    assert not lost, "spec files that no test runs:\n" + "\n".join(lost) + "\n" + HOW_TO_FIX


def test_the_list_of_files_not_bound_yet_only_shrinks():
    bound = _bound()
    done = [
        name
        for name in NOT_BOUND_YET
        if not (SPECS / name).is_file() or _is_draft(SPECS / name) or not _unchecked(SPECS / name, bound)
    ]
    assert not done, f"take these out of NOT_BOUND_YET, they are run (or gone) now: {done}"


def test_a_draft_is_not_run_before_the_owner_has_approved_it():
    """Approving a draft and binding it is one commit: the one that takes ``@draft`` off."""
    bound = _bound()
    early = [_name(path) for path in _features() if _is_draft(path) and path.resolve() in bound]
    assert not early, f"bound but still marked @draft (approved? then take @draft off): {early}"


def _all_tags(paths: list[Path]) -> set[str]:
    found = set()
    for path in paths:
        feature = _feature(path)
        found.update(_tags(feature))
        for _, tags, examples in _scenarios(feature, []):
            found.update(tags)
            for block in examples:
                found.update(block)
    return found


def _files_that_run() -> list[Path]:
    """The files that run now. A draft or a file in NOT_BOUND_YET may name a test that its feature's branch will write
    first, so its tags are promises, checked once it runs."""
    return [path for path in _features() if _name(path) not in NOT_BOUND_YET and not _is_draft(path)]


def test_a_test_tag_names_a_test_that_exists_and_is_run(run_e2e):
    """``@e2e:<script>`` must name a script of ``SCRIPTS``, which ``./run-e2e.sh regression`` and CI run (D1452)."""
    scripts = {script.name for script in run_e2e.SCRIPTS}
    wrong = []
    for tag in sorted(t for t in _all_tags(_files_that_run()) if t.startswith(TEST_TAGS)):
        kind, target = tag[1:].split(":", 1)
        if kind == "e2e":
            name = target.removesuffix(".cjs")
            if not (ROOT / "web" / "e2e" / target).is_file():
                wrong.append(f"{tag}: there is no web/e2e/{target}")
            elif name not in scripts:
                wrong.append(f"{tag}: ./run-e2e.sh regression (and so CI) does not run it")
        elif not (ROOT / target.split("::")[0]).exists():
            wrong.append(f"{tag}: there is no {target.split('::')[0]}")
    assert not wrong, "test tags that point at nothing that runs:\n" + "\n".join(wrong)


def test_a_pending_tag_names_a_story_that_is_not_done():
    """``@pending:<story>`` waits for a story; when the story is done the scenario should run, not wait."""
    stale = []
    for tag in sorted(t for t in _all_tags(_features()) if t.startswith("@pending:")):
        story = tag.removeprefix("@pending:").lower()
        for task in TASKS.glob(f"{story}-*.md"):
            status = re.search(r'^status:\s*"?([\w-]+)', task.read_text(encoding="utf-8"), re.MULTILINE)
            if status and status[1] == "done":
                stale.append(f"{tag}: {task.name} is done")
    assert not stale, "scenarios still waiting for a story that is done:\n" + "\n".join(stale)
