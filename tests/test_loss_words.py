"""Every code an export can report has words in the Export dialog (UX-70, D405).

The converters report what a file cannot hold as codes (``Loss(kind, detail, count)``); the web app says each kind in
words (``web/app/lib/export-losses.ts``), and a kind it has no words for is only "Something this format has no place
for", with its code. This reads the codes the Python sources report and the kinds the web app words, so a new code is
either put into words or named here as one only an import reports (an import says how much it left out, not what).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS = ROOT / "web" / "app" / "lib" / "export-losses.ts"
#: ``losses.add("x"``, ``lost.add(``, ``log.add(``, ``self._lose(``, ``Loss("x"``; an f-string code such as
#: ``f"removed-{kind}"`` is read up to its first ``{``, as the prefix of a family of codes.
REPORTED = re.compile(r'(?:\b(?:losses|lost|log)\.add|\b_lose|\bLoss)\(\s*f?"([a-z-]+)(\{)?')
#: The server's own codes, written as answers (``"kind": "not-patched"``).
ANSWERED = re.compile(r'"kind": "([a-z-]+)"')
#: The codes only an import reports.
IMPORT_ONLY = {
    "filter",
    "formatting",
    "heading-level",
    "hidden-sheet",
    "link",
    "named-range",
    "notes",
    "outside",
    "protection",
    "table",
    "turn",
    "validation",
}


def _reported() -> set[str]:
    """The codes the converters and the server report; a family of codes as its prefix and ``*`` (``removed-*``)."""
    found = set()
    for path in ROOT.glob("packages/*/src/**/*.py"):
        for code, family in REPORTED.findall(path.read_text(encoding="utf-8")):
            found.add(f"{code}*" if family else code)
    office_export = ROOT / "packages" / "claudia-server" / "src" / "claudia_server" / "office_export.py"
    found |= set(ANSWERED.findall(office_export.read_text(encoding="utf-8")))
    return found


def _worded() -> set[str]:
    """The kinds ``export-losses.ts`` has words for: the keys of ``WORDS`` and the families of ``FAMILIES``."""
    source = WORDS.read_text(encoding="utf-8")
    keys = set()
    for table, suffix in (("WORDS", ""), ("FAMILIES", "*")):
        body = re.search(rf"^const {table}\b.*?^\}}", source, re.MULTILINE | re.DOTALL)
        assert body is not None, f"export-losses.ts has no table {table}"
        keys |= {key + suffix for key in re.findall(r"^  '?([a-z-]+)'?: ", body.group(0), re.MULTILINE)}
    return keys


def test_every_code_an_export_reports_has_words():
    worded = _worded()
    families = tuple(code.removesuffix("*") for code in worded if code.endswith("*"))

    def has_words(code: str) -> bool:
        return code in worded or code.removesuffix("*").startswith(families)

    assert sorted(code for code in _reported() - IMPORT_ONLY if not has_words(code)) == []


def test_the_codes_named_as_import_only_are_still_reported():
    assert sorted(IMPORT_ONLY - _reported()) == []
