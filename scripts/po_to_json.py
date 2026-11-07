"""Derive the web client's JSON catalog from a ``.po`` file (E5.7, D31): the one thing that keeps a single source of
translations true. The ``.po`` file stays the source anyone (a translator, ``msgfmt``, the Gtk client's own
``gettext``) edits; this script is the only place a second, derived copy is produced, so the two can never drift
apart by hand.

``uv run python scripts/po_to_json.py po/de.po de``                      write ``web/public/i18n/de.json``
``uv run python scripts/po_to_json.py po/de.po de --out-dir DIR``        write ``DIR/de.json`` instead

A ``msgid``/``msgstr`` pair with an empty ``msgstr`` is not yet translated, so it is left out: ``createTranslator``
(``web/app/lib/i18n.ts``) already falls back to the ``msgid`` itself for anything the catalog does not have, which
is exactly what an untranslated string should do. The header entry (``msgid ""``) is metadata, not a string, and is
always skipped.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = ROOT / "web" / "public" / "i18n"

_STRING_LINE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _unescape(literal: str) -> str:
    r"""One ``.po`` double-quoted string's content (without its quotes), with ``\\n``, ``\\t``, ``\\"`` and ``\\\\``
    resolved — the escapes ``.po`` files actually use; anything else is left as-is rather than guessed at."""
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(m.group(1), m.group(0)), literal)


def parse_po(text: str) -> dict[str, str]:
    """``{msgid: msgstr}`` for every *translated* entry in a ``.po``/``.pot`` file's text (empty ``msgstr`` and the
    header entry are both left out — see the module docstring)."""
    catalog: dict[str, str] = {}
    msgid: list[str] | None = None
    msgstr: list[str] | None = None
    field: str | None = None  # the field the next continuation string line belongs to: "msgid" or "msgstr"

    def flush() -> None:
        if msgid is not None and msgstr is not None:
            joined_id, joined_str = "".join(msgid), "".join(msgstr)
            if joined_id and joined_str:
                catalog[joined_id] = joined_str

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("msgid "):
            flush()
            msgid = [_unescape(m.group(1)) for m in _STRING_LINE.finditer(line)]
            msgstr = None
            field = "msgid"
        elif line.startswith("msgstr "):
            msgstr = [_unescape(m.group(1)) for m in _STRING_LINE.finditer(line)]
            field = "msgstr"
        elif line.startswith('"') and field is not None:
            target = msgid if field == "msgid" else msgstr
            assert target is not None
            target.append(_unescape(_STRING_LINE.match(line).group(1)))  # type: ignore[union-attr]
    flush()
    return catalog


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("po_file", type=Path, help="the .po file to convert")
    parser.add_argument("locale", help="the BCP-47-ish tag the catalog is written under, e.g. de or pt-BR")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="defaults to web/public/i18n")
    args = parser.parse_args(argv)

    if not args.po_file.is_file():
        print(f"no such file: {args.po_file}", file=sys.stderr)
        return 1
    catalog = parse_po(args.po_file.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{args.locale}.json"
    out_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out_path} ({len(catalog)} translated string(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
