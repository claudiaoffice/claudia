"""A pseudo-locale (E5.7, D31): every ``msgid`` in ``po/claudia.pot`` "translated" by a mechanical transform, so a
screen full of pseudo-text shows at a glance whether something was missed — a string that stayed in plain English
is a string that never reached the catalog, long before a real translator is involved.

``uv run python scripts/make_pseudolocale.py``   write ``po/xx.po`` from ``po/claudia.pot``

The transform (``pseudo``) does three things real translations tend to do, on purpose exaggerated so a lapse is
obvious rather than merely odd-looking:

* every vowel gets an accent (``a`` → ``à``, and so on) — catches anything rendered from a hard-coded string
  instead of looked up in the catalog, since plain ASCII vowels would stand out against the accented ones around
  them;
* the text is padded by about 40%, wrapped in brackets — catches layout that assumes English-length strings (many
  real languages run longer, German especially);
* ``{placeholder}``\\ s (``createTranslator``'s interpolation syntax, ``web/app/lib/i18n.ts``) are left untouched,
  not accented or padded — catches a placeholder's name itself getting mangled, which would silently break the
  substitution instead of merely looking odd.

``xx`` is not a real BCP-47 tag some real browser or OS would ever send: it is only ever reached by asking for it
explicitly (a future ``?locale=xx`` or a Config-menu "Pseudolocale (testing)" entry — not built in this slice), so
it can never show up in a bug report as if it were a real locale."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POT_PATH = ROOT / "po" / "claudia.pot"
PSEUDO_PO_PATH = ROOT / "po" / "xx.po"

_VOWELS = str.maketrans("aeiouAEIOU", "àéîôûÀÉÎÔÛ")
_PLACEHOLDER = re.compile(r"\{\w+\}")


def pseudo(text: str) -> str:
    """``text``, pseudo-translated (see the module docstring); ``{placeholder}``\\ s pass through unchanged."""

    def accented(fragment: str) -> str:
        return fragment.translate(_VOWELS)

    parts = _PLACEHOLDER.split(text)
    placeholders = _PLACEHOLDER.findall(text)
    pieces = []
    for i, part in enumerate(parts):
        pieces.append(accented(part))
        if i < len(placeholders):
            pieces.append(placeholders[i])
    body = "".join(pieces)
    pad = max(0, round(len(text) * 0.4))
    return "[" + body + "~" * pad + "]"


def _po_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _po_unescape(literal: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(m.group(1), m.group(0)), literal)


# a POT entry: optional comment lines, then msgid, then msgstr "" — reused as-is except for the msgstr
_ENTRY = re.compile(r'((?:#.*\n)*)msgid "((?:[^"\\]|\\.)*)"\nmsgstr ""\n', re.MULTILINE)


def render_pseudo_po(pot_text: str) -> str:
    """``pot_text`` with every entry's ``msgstr`` filled in with its pseudo-translation; the header (whose own
    ``msgid`` is the empty string, never pseudo-translated) and every comment are carried over unchanged."""

    def replace(match: re.Match[str]) -> str:
        comments, raw_msgid = match.group(1), match.group(2)
        if raw_msgid == "":
            return match.group(0)  # the header entry: left alone, not pseudo-translated
        return f'{comments}msgid "{raw_msgid}"\nmsgstr {_po_string(pseudo(_po_unescape(raw_msgid)))}\n'

    return _ENTRY.sub(replace, pot_text)


def main(argv: list[str]) -> int:
    del argv  # no options yet; kept for symmetry with the other i18n scripts and future flags
    if not POT_PATH.is_file():
        print(f"no such file: {POT_PATH} — run scripts/extract_i18n.py first", file=sys.stderr)
        return 1
    rendered = render_pseudo_po(POT_PATH.read_text(encoding="utf-8"))
    PSEUDO_PO_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {PSEUDO_PO_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
