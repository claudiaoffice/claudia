"""The decision log is one file per decision, and every ``D<number>`` anywhere resolves to exactly one of them.

DOC-01 began this test: D70-D82 and D97-D99 had each been allocated twice, and the collision was live in the source
(``claudia_container/crypto.py`` cited D74 meaning the cryptographic primitives while ``claudia_server/composes.py``
cited D75 meaning the styling details). It happened again with D151, D160, D177-D179 and D204, because branches
written in parallel each picked "the next free number". Since 2026-11-10 the log is a folder
(``claudiaoffice-log/decision-log/``, see its ``README.md``) and numbers are handed out in ranges (``ranges.md``).

What this checks:

* every decision file is named ``<number>-<status>-<applies-to>-<description>.md``, and its front matter agrees;
* no number is allocated twice, and every number lies in a range ``ranges.md`` has handed out and not in one it
  forbids;
* every ``D<n>`` cited in the code, docs and changelogs, in a backlog story's ``decisions`` field and in the
  decisions themselves names a decision that exists;
* supersession is consistent: a superseded decision names its successor, and both sides agree.

``_rounds.md`` and the implementation notes are history: they may name an old number on purpose while explaining a
renumbering, so they are not scanned.
"""

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "claudiaoffice-log" / "decision-log"
TASKS = ROOT / "claudiaoffice-log" / "Projects" / "claudia-office" / "_tasks"
NOT_DECISIONS = {"README.md", "ranges.md", "_rounds.md"}

STATUSES = ("current", "undecided", "superseded", "blocking")
SCOPES = ("composes", "computes", "creates", "all")
NAME = re.compile(rf"^(\d{{4}})-({'|'.join(STATUSES)})-({'|'.join(SCOPES)})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
CITED = re.compile(r"\bD(\d+)\b")
DECISIONS_FIELD = "p4t0cldrmw2k8l7j"  # the dotpm custom field named "decisions" (claudiaoffice-log/README.md)

# "the source": everywhere a docstring, comment or changelog can cite a decision.
SCAN_DIRS = ("packages", "clients", "web", "scripts", "tests", "docs")
SCAN_SUFFIXES = {".py", ".ts", ".vue", ".md"}
SCAN_FILES = ("CHANGELOG.md", "CONTRIBUTING.md", "README.md")  # top-level, so outside SCAN_DIRS
PRUNE = {"node_modules", ".venv", ".git", ".nuxt", ".output", "dist", "_build", "__pycache__"}


def front_matter(path: Path) -> dict[str, str]:
    """The ``key: value`` lines of a file's front matter, values as written (quotes stripped)."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, f"{path.name}: no front matter"
    fields = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip('"')
    return fields


def id_list(value: str) -> list[str]:
    return re.findall(r"D\d+", value)


def decision_files() -> list[Path]:
    return sorted(p for p in LOG_DIR.glob("*.md") if p.name not in NOT_DECISIONS)


def decisions() -> dict[str, dict[str, str]]:
    return {f"D{int(NAME.match(p.name).group(1))}": front_matter(p) for p in decision_files() if NAME.match(p.name)}


def source_files():
    for name in SCAN_DIRS:
        base = ROOT / name
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in PRUNE]
            for filename in filenames:
                if Path(filename).suffix in SCAN_SUFFIXES:
                    yield Path(dirpath) / filename
    for name in SCAN_FILES:
        path = ROOT / name
        if path.is_file():
            yield path


def ranges(heading: str) -> list[tuple[int, int]]:
    """The ``D<a>–D<b>`` ranges in the first column of the table under ``heading`` in ranges.md."""
    text = (LOG_DIR / "ranges.md").read_text(encoding="utf-8")
    section = text.split(f"## {heading}", 1)[1].split("\n## ", 1)[0]
    found = []
    for row in re.findall(r"^\| (D\d+[–-]D\d+) \|", section, re.M):
        low, high = (int(n) for n in re.findall(r"\d+", row))
        found.append((low, high))
    assert found, f"no ranges under {heading!r} in ranges.md"
    return found


def test_every_decision_file_is_named_by_the_convention_and_agrees_with_its_front_matter():
    wrong = []
    for path in decision_files():
        match = NAME.match(path.name)
        if not match:
            wrong.append(f"{path.name}: not <number>-<status>-<applies-to>-<description>.md")
            continue
        number, status, scope, _ = match.groups()
        fields = front_matter(path)
        if fields.get("id") != f"D{int(number)}":
            wrong.append(f"{path.name}: front matter id is {fields.get('id')!r}")
        if fields.get("status") != status:
            wrong.append(f"{path.name}: front matter status is {fields.get('status')!r}")
        if fields.get("applies-to") != scope:
            wrong.append(f"{path.name}: front matter applies-to is {fields.get('applies-to')!r}")
    assert not wrong, "\n".join(wrong)


def test_no_number_is_allocated_twice():
    numbers = [int(NAME.match(p.name).group(1)) for p in decision_files() if NAME.match(p.name)]
    twice = sorted({n for n in numbers if numbers.count(n) > 1})
    assert not twice, f"allocated more than once in decision-log/: {[f'D{n}' for n in twice]}"


def test_every_number_lies_in_a_handed_out_range():
    given, forbidden = ranges("Handed out"), ranges("Never to be used")
    outside = []
    for ident in decisions():
        n = int(ident[1:])
        if not any(low <= n <= high for low, high in given):
            outside.append(f"{ident}: in no range of ranges.md — ask for one before writing a decision")
        if any(low <= n <= high for low, high in forbidden):
            outside.append(f"{ident}: in a range ranges.md says is never to be used")
    assert not outside, "\n".join(outside)


def test_every_cited_decision_exists():
    valid = set(decisions())
    assert len(valid) > 100, "decision-log/ has almost no decisions — the folder or the name pattern moved"
    unresolved = []
    for path in source_files():
        text = path.read_text(encoding="utf-8")
        for match in CITED.finditer(text):
            if f"D{match.group(1)}" not in valid:
                line = text.count("\n", 0, match.start()) + 1
                unresolved.append(f"{path.relative_to(ROOT)}:{line}: D{match.group(1)}")
    unresolved.extend(
        f"{path.relative_to(ROOT)}: D{cite}"
        for path in decision_files()
        for cite in sorted(set(CITED.findall(path.read_text(encoding="utf-8"))))
        if f"D{cite}" not in valid
    )
    assert not unresolved, "cited but not in decision-log/:\n" + "\n".join(unresolved)


def test_every_backlog_story_cites_decisions_that_exist():
    valid = set(decisions())
    unresolved = [
        f"{path.name}: {cite}"
        for path in sorted(TASKS.glob("*.md"))
        for cite in id_list(front_matter(path).get(DECISIONS_FIELD, ""))
        if cite not in valid
    ]
    assert not unresolved, "a story's decisions field names a decision that does not exist:\n" + "\n".join(unresolved)


def test_supersession_is_named_on_both_sides():
    log = decisions()
    wrong = []
    for ident, fields in sorted(log.items(), key=lambda kv: int(kv[0][1:])):
        successors = id_list(fields.get("superseded-by", ""))
        if fields["status"] == "superseded" and not successors:
            wrong.append(f"{ident}: superseded, but names no successor")
        if successors and fields["status"] != "superseded":
            wrong.append(f"{ident}: names a successor but its status is {fields['status']!r}")
        wrong.extend(
            f"{ident}: superseded by {other}, which does not list it under supersedes"
            for other in successors
            if other not in log or ident not in id_list(log[other].get("supersedes", ""))
        )
        wrong.extend(
            f"{ident}: supersedes {older}, which does not name it under superseded-by"
            for older in id_list(fields.get("supersedes", ""))
            if older not in log or ident not in id_list(log[older].get("superseded-by", ""))
        )
    assert not wrong, "\n".join(wrong)
