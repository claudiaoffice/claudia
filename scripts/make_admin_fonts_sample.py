"""Make the sample a test adds on Server settings ▸ Fonts (E3.13 f, ``web/e2e/admin-fonts.cjs``): a "house font" of four
styles, made from the shipped Carlito (SIL OFL 1.1, which allows renaming a modified copy) under the family name
Hausschrift Sans and without its licence fields, as a licensed font of an organisation often comes; its Bold Italic
forbids embedding (OS/2 fsType 2), so the check leaves it out.

    uv run python scripts/make_admin_fonts_sample.py /tmp/house-fonts
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont

from claudia_fonts import builtin_folder

FAMILY = "Hausschrift Sans"
STYLES = ("Regular", "Italic", "Bold", "BoldItalic")
RESTRICTED = 2


def make(target: Path) -> list[Path]:
    """The four files in ``target``; their paths."""
    target.mkdir(parents=True, exist_ok=True)
    made = []
    for style in STYLES:
        font = TTFont(builtin_folder() / "carlito" / f"Carlito-{style}.ttf")
        names = font["name"]
        shown = {"BoldItalic": "Bold Italic"}.get(style, style)
        for record in list(names.names):
            if record.nameID in (13, 14):  # a house font names no licence: the administrator says it
                names.removeNames(nameID=record.nameID)
        names.setName(FAMILY, 1, 3, 1, 0x409)
        names.setName(shown, 2, 3, 1, 0x409)
        names.setName(f"{FAMILY} {shown}", 4, 3, 1, 0x409)
        names.setName(f"HausschriftSans-{style}", 6, 3, 1, 0x409)
        names.removeNames(nameID=16)
        names.removeNames(nameID=17)
        if style == "BoldItalic":
            font["OS/2"].fsType = RESTRICTED
        path = target / f"HausschriftSans-{style}.ttf"
        font.save(path)
        made.append(path)
    return made


if __name__ == "__main__":
    for path in make(Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/house-fonts")):
        print(path)
