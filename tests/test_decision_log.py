"""Every ``D<number>`` cited in the source resolves to exactly one entry in the decision log (DOC-01).

D70-D82 and D97-D99 were each allocated twice, by documents written in parallel before the 2026-11-05 renumbering,
and the collision was live in the source, not only in prose: ``claudia_container/crypto.py`` cited D72, D73 and D74
meaning hidden names, the plain manifest and the cryptographic primitives, while ``claudia_server/composes.py`` cited
D73 and D75 meaning styling-is-CSS and the styling details — the same number, two meanings, two directories apart.

This is the gate line the fix asked for: it reads every citation outside ``claudiaoffice-log/`` (the log itself, and
its own historical record of the collision, where an "old number" is expected to mean something else by design) and
checks it against the log's own numbered rows. "Resolves to exactly one entry" is two separate guarantees: the id
is in the log at all, and the log never lists it twice.
"""

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECISION_LOG = ROOT / "claudiaoffice-log" / "decision-log.md"

ROW = re.compile(r"^\| (D\d+) \|", re.MULTILINE)  # a decision's own row: "D<n>" is the first table cell
CITED = re.compile(r"\bD(\d+)\b")

# "the source": everywhere a docstring, comment or changelog can cite a decision. claudiaoffice-log/ is excluded on
# purpose: it is the log and its own notes about the collision, which legitimately uses an "old number" to mean
# something else while explaining the renumbering.
SCAN_DIRS = ("packages", "clients", "web", "scripts", "tests", "docs")
SCAN_SUFFIXES = {".py", ".ts", ".vue", ".md"}
SCAN_FILES = ("CHANGELOG.md", "CONTRIBUTING.md", "README.md")  # top-level, so outside SCAN_DIRS
PRUNE = {"node_modules", ".venv", ".git", ".nuxt", ".output", "dist", "_build", "__pycache__"}


def decision_rows() -> list[str]:
    return ROW.findall(DECISION_LOG.read_text(encoding="utf-8"))


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


def test_decision_log_never_allocates_a_number_twice():
    rows = decision_rows()
    seen_twice = {row for row in rows if rows.count(row) > 1}
    assert not seen_twice, f"allocated more than once in decision-log.md: {sorted(seen_twice)}"


def test_every_cited_decision_resolves_to_one_entry_in_the_log():
    valid = set(decision_rows())
    assert valid, "no rows matched in decision-log.md — the row pattern or the file moved"
    unresolved = []
    for path in source_files():
        text = path.read_text(encoding="utf-8")
        for match in CITED.finditer(text):
            cite = f"D{match.group(1)}"
            if cite not in valid:
                line = text.count("\n", 0, match.start()) + 1
                unresolved.append(f"{path.relative_to(ROOT)}:{line}: {cite}")
    assert not unresolved, (
        "cited but not in decision-log.md (or claudiaoffice-log/ has the real number):\n" + "\n".join(unresolved)
    )
