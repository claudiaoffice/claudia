"""A note may only say "built" about a file that is actually in the tree (PROC-03).

``e4-e6-formulas-notes.md`` once described point-and-click cell references as built on 2026-11-03, naming
``web/app/lib/pointing.ts`` and two test files; none of it was in any commit on any branch — the patch had not been
pushed, and nothing caught it until this was checked by hand. The rule going forward: status lives in `backlog.md`
and is derived from the code, and a note never gets to outrun the commit that proves its claim.

This is the cheap guard the fix asked for: every paragraph in `claudiaoffice-log/` that says "built" and names a
root-relative path (`web/…`, `packages/…`, `clients/…`, `scripts/…`, `docs/…`) must have that path actually in the
tree. It is deliberately narrow — a bare filename like `` `window.py` `` or a path relative to something other than
the repository root is not unambiguous enough for a mechanical check and is left to a reader — but a path this
specific, claimed as built, and missing is exactly PROC-03's shape.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "claudiaoffice-log"

BUILT = re.compile(r"\bbuilt\b", re.IGNORECASE)
PATH = re.compile(r"`((?:web|packages|clients|scripts|docs)/[a-zA-Z0-9_.\-/]+)`")
# directories that a fresh, unbuilt checkout never has: naming one of these is not a claim the tree must satisfy
NOT_EXPECTED_IN_A_CHECKOUT = {"node_modules", ".venv", ".nuxt", ".output", "dist", "_build", "__pycache__"}


def paragraphs_claiming_built():
    for path in sorted(NOTES.rglob("*.md")):
        if ".obsidian" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for paragraph in re.split(r"\n\s*\n", text):
            if BUILT.search(paragraph):
                yield path, paragraph


def test_a_built_claim_names_only_files_that_exist():
    missing = []
    for note, paragraph in paragraphs_claiming_built():
        for match in PATH.finditer(paragraph):
            cited = match.group(1)
            if NOT_EXPECTED_IN_A_CHECKOUT & set(Path(cited).parts):
                continue
            if not (ROOT / cited).exists():
                missing.append(f"{note.relative_to(ROOT)}: claims {cited!r} is built, but it is not in the tree")
    assert not missing, "\n".join(missing)
