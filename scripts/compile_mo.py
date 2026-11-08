"""Compile a ``.po`` catalog into gettext's binary ``.mo`` format (E5.7, D31's groundwork, D160): GNU ``msgfmt`` is
not something every contributor's machine has, and is not in this project's own sandboxes either (``apt-get install
gettext`` has no installation candidate here), so this reimplements the one narrow slice of it Claudia actually
needs, in pure Python, with no new dependency.

``uv run python scripts/compile_mo.py po/de.po de``
    write ``clients/linux/src/claudia_shell_gtk/locale/de/LC_MESSAGES/claudia.mo``
``uv run python scripts/compile_mo.py po/de.po de --check``
    fail if that ``.mo`` would change, instead of writing it (the CI gate, same shape as ``extract_i18n.py``'s)
``uv run python scripts/compile_mo.py po/de.po de --locale-dir DIR``
    write ``DIR/de/LC_MESSAGES/claudia.mo`` instead

Reuses :func:`po_to_json.parse_po` as the one and only ``.po`` reader this project has, rather than writing a third
slightly-different one alongside ``extract_i18n.py``'s writer and ``make_pseudolocale.py``'s regex-based rewriter —
so a ``.po`` quirk (multi-line continuation, the four escapes this project's tooling supports, the header entry and
any untranslated ``msgstr ""`` both left out of the returned catalog) is read the same way everywhere.

What is new here is only the binary ``.mo`` encoding itself: four little-endian 32-bit header words (the GNU magic
number, format revision ``0``, the string count, and the offsets of the originals/translations tables), each table
a run of ``(length, offset)`` pairs into one block of NUL-terminated strings. No hash table is written
(``hash_size=0``, ``hash_offset`` pointing just past the translations table): CPython's own
``gettext.GNUTranslations._parse`` — the one and only reader ``i18n.install_translation`` ever points at — never
looks at it; a hash table is purely an optional lookup accelerator for other implementations this project does not
need. A synthetic header entry (``msgid ""``) declaring ``charset=UTF-8`` is always the first string pair, even
though :func:`po_to_json.parse_po` strips the ``.po`` file's own header entry: without it, CPython's own reader
falls back to decoding every string as plain ASCII (``self._charset or 'ascii'``), which would simply crash on the
first umlaut a real German string contains.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_LOCALE_DIR = ROOT / "clients" / "linux" / "src" / "claudia_shell_gtk" / "locale"

MAGIC = 0x950412DE
HEADER_WORDS = 7  # magic, revision, N, originals-table offset, translations-table offset, hash size, hash offset
DOMAIN = "claudia"  # must match i18n.DOMAIN (clients/linux/src/claudia_shell_gtk/i18n.py)


def _parse_po(text: str) -> dict[str, str]:
    """``{msgid: msgstr}`` for every translated entry of ``text`` — see this module's docstring for why this is
    ``po_to_json.parse_po`` itself, loaded from its sibling script, rather than a second reader."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    from po_to_json import parse_po  # type: ignore[import-not-found]  # a sibling script, not an installed package

    return parse_po(text)


def compile_mo(catalog: dict[str, str]) -> bytes:
    """``catalog`` (``{msgid: msgstr}``, already excluding the header and any untranslated entry —
    :func:`po_to_json.parse_po`'s own job) as gettext ``.mo`` bytes. Sorted by ``msgid`` for a small, meaningful
    diff between compiles — ``gettext.GNUTranslations`` reads every entry regardless of order, so this is for
    humans reading the bytes, not a correctness requirement."""
    entries: list[tuple[str, str]] = [("", "Content-Type: text/plain; charset=UTF-8\n"), *sorted(catalog.items())]
    count = len(entries)
    originals = [msgid.encode("utf-8") for msgid, _ in entries]
    translations = [msgstr.encode("utf-8") for _, msgstr in entries]

    header_size = HEADER_WORDS * 4
    originals_table_offset = header_size
    translations_table_offset = originals_table_offset + count * 8
    hash_offset = translations_table_offset + count * 8  # hash_size is 0: nothing is ever stored there, see above
    strings_offset = hash_offset

    position = strings_offset
    originals_table = b""
    for raw in originals:
        originals_table += struct.pack("<2I", len(raw), position)
        position += len(raw) + 1  # +1: the NUL terminator every string is stored with
    translations_table = b""
    for raw in translations:
        translations_table += struct.pack("<2I", len(raw), position)
        position += len(raw) + 1

    header = struct.pack("<7I", MAGIC, 0, count, originals_table_offset, translations_table_offset, 0, hash_offset)
    strings = b"".join(raw + b"\x00" for raw in originals) + b"".join(raw + b"\x00" for raw in translations)
    return header + originals_table + translations_table + strings


def _mo_path(locale: str, locale_dir: Path) -> Path:
    return locale_dir / locale / "LC_MESSAGES" / f"{DOMAIN}.mo"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("po_file", type=Path, help="the .po file to compile")
    parser.add_argument("locale", help="the BCP-47-ish tag the catalog is installed under, e.g. de")
    parser.add_argument("--locale-dir", type=Path, default=DEFAULT_LOCALE_DIR, help="defaults to the bundled one")
    parser.add_argument(
        "--check", action="store_true", help="fail if the compiled .mo would change, instead of writing it"
    )
    args = parser.parse_args(argv)

    if not args.po_file.is_file():
        print(f"no such file: {args.po_file}", file=sys.stderr)
        return 1
    catalog = _parse_po(args.po_file.read_text(encoding="utf-8"))
    compiled = compile_mo(catalog)
    out_path = _mo_path(args.locale, args.locale_dir)

    if args.check:
        current = out_path.read_bytes() if out_path.is_file() else None
        if current != compiled:
            print(f"{out_path} is out of date — run scripts/compile_mo.py to fix it", file=sys.stderr)
            return 1
        print(f"{out_path} is up to date")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(compiled)
    print(f"wrote {out_path} ({len(catalog)} translated string(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
