"""Bring each translation up to date with the template (E5.7, D31, D148): ``msgmerge`` without GNU gettext, which is
not on every contributor's machine (``compile_mo.py`` has the same reason for being pure Python).

``uv run python scripts/update_po.py``           rewrite ``po/<language>.po`` for every language but the pseudo-locale
``uv run python scripts/update_po.py --check``   fail if one of them is not what that rewrite would produce

After ``scripts/extract_i18n.py`` has rewritten ``po/claudia.pot``, a translation still has the strings that went
away and lacks the ones that came. This keeps what is translated, drops what is gone, adds what is new with an empty
``msgstr`` (an untranslated string renders as its English ``msgid`` — ``po_to_json.py``, ``compile_mo.py`` — so a
half-finished language is usable, not broken), and refreshes each entry's ``#:`` places from the template. The
order is the template's, so a diff shows only what changed. ``po/xx.po`` is skipped: ``make_pseudolocale.py``
writes it whole.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from po_to_json import parse_po  # noqa: E402  (a sibling script, not a package)

ROOT = Path(__file__).resolve().parent.parent
PO_DIR = ROOT / "po"
POT_PATH = PO_DIR / "claudia.pot"
PSEUDO = "xx"

_ENTRY = re.compile(r'^#: (?P<places>.*)\nmsgid "(?P<msgid>(?:[^"\\]|\\.)*)"\nmsgstr ""$', re.M)
_HEADER = re.compile(r'\A(msgid ""\nmsgstr ""\n(?:"[^\n]*"\n)*)')


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _unquote(literal: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", '"': '"', "\\": "\\"}.get(m.group(1), m.group(0)), literal)


def merge(template: str, translation: str) -> str:
    """``translation`` rewritten to hold exactly the template's strings: its own translations where it has them,
    an empty ``msgstr`` where it does not, and the template's header and places."""
    header = _HEADER.match(template)
    if header is None:
        raise ValueError("the template has no header entry")
    translated = parse_po(translation)
    parts = [header.group(1)]
    for entry in _ENTRY.finditer(template):
        msgid = _unquote(entry.group("msgid"))
        parts.append(
            f"\n#: {entry.group('places')}\nmsgid {_quote(msgid)}\nmsgstr {_quote(translated.get(msgid, ''))}\n"
        )
    return "".join(parts)


def languages() -> list[Path]:
    """Every ``po/<language>.po`` that is a real translation (not the pseudo-locale)."""
    return sorted(p for p in PO_DIR.glob("*.po") if p.stem != PSEUDO)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if a translation would change, instead of writing")
    args = parser.parse_args(argv)

    template = POT_PATH.read_text(encoding="utf-8")
    stale = []
    for path in languages():
        current = path.read_text(encoding="utf-8")
        merged = merge(template, current)
        if merged == current:
            continue
        stale.append(path)
        if not args.check:
            path.write_text(merged, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
    if args.check and stale:
        for path in stale:
            print(f"{path.relative_to(ROOT)} is out of date — run scripts/update_po.py and commit it", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
