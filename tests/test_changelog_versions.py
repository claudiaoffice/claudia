"""No CHANGELOG.md ever allocates the same version twice (CODE-12).

Found by accident: ``packages/claudia-server/CHANGELOG.md`` had two ``## [0.9.0]`` headers from two branches merged
in parallel (worker-pool and ai-sec-patch), with a third branch's ``## [0.10.0]`` sandwiched between them — and the
second ``## [0.9.0]`` block itself ran two unrelated releases together under one header, the second with no header
of its own. The same class of bug ``test_decision_log.py`` already catches for ``D<number>``, just one directory
over: concurrent branches each picking "the next number" without seeing each other's pick.

This only checks for an exact duplicate version string in one file — it says nothing about whether the numbers are
*complete* (a merge can just as easily drop a release's entry entirely, as the row-height/column-width and i18n
groundwork slices did here) or in descending order. Those are read, not mechanically checked.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)


def changelogs() -> list[Path]:
    return [ROOT / "CHANGELOG.md", *sorted((ROOT / "packages").glob("*/CHANGELOG.md"))]


def test_no_changelog_allocates_a_version_twice():
    offenders = []
    for path in changelogs():
        versions = HEADER.findall(path.read_text(encoding="utf-8"))
        dupes = sorted({v for v in versions if versions.count(v) > 1})
        if dupes:
            offenders.append(f"{path.relative_to(ROOT)}: {dupes}")
    assert not offenders, "a version header appears more than once:\n" + "\n".join(offenders)
