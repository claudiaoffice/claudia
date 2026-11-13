"""Tiny fonts for tests: real TrueType files built on the spot, so that no binary fixture is committed.

Not part of the public API (like ``claudia_core.testing``); other packages' tests may use it.
"""

from __future__ import annotations

from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables.DefaultTable import DefaultTable

UNITS = 1000
FS_SELECTION_ITALIC = 0x01
FS_SELECTION_REGULAR = 0x40
MAC_STYLE_ITALIC = 0x02


def _glyph(points: list[tuple[int, int]]):
    pen = TTGlyphPen(None)
    pen.moveTo(points[0])
    for point in points[1:]:
        pen.lineTo(point)
    pen.closePath()
    return pen.glyph()


def make_font(
    path: str | Path,
    family: str = "Test Sans",
    style: str = "Regular",
    *,
    weight: int = 400,
    italic: bool = False,
    fs_type: int = 0,
    math: bool = False,
    typographic: bool = False,
    version: str = "1.0",
    axes: tuple[tuple[str, float, float, float], ...] = (),
) -> Path:
    """Write a small valid TrueType font with one letter (``A``) and return its path.

    ``fs_type`` is the embedding permission of the OS/2 table; ``math`` adds a (meaningless) ``MATH`` table, which is
    all the catalogue looks at; with ``typographic`` the family and style are stored as the typographic names (IDs 16
    and 17) and the legacy family (ID 1) is ``"<family> <style>"``, as fonts with many weights do. Different
    ``version`` strings make different bytes. ``axes`` (tag, minimum, default, maximum) adds an ``fvar`` table, which
    makes the font look variable to a reader (it has no variation data)."""
    target = Path(path)
    builder = FontBuilder(UNITS, isTTF=True)
    builder.setupGlyphOrder([".notdef", "A"])
    builder.setupCharacterMap({65: "A"})
    builder.setupGlyf({".notdef": TTGlyphPen(None).glyph(), "A": _glyph([(0, 0), (0, 700), (500, 700)])})
    builder.setupHorizontalMetrics({".notdef": (500, 0), "A": (600, 0)})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    names = {"familyName": family, "styleName": style, "version": f"Version {version}"}
    if typographic:
        names |= {"familyName": f"{family} {style}", "styleName": "Regular"}
        names |= {"typographicFamily": family, "typographicSubfamily": style}
    builder.setupNameTable(names)
    builder.setupOS2(
        sTypoAscender=800,
        sTypoDescender=-200,
        usWinAscent=800,
        usWinDescent=200,
        usWeightClass=weight,
        fsType=fs_type,
        fsSelection=FS_SELECTION_ITALIC if italic else FS_SELECTION_REGULAR,
    )
    builder.setupPost()
    builder.font["head"].macStyle = MAC_STYLE_ITALIC if italic else 0
    if axes:
        builder.setupFvar([(tag, low, default, high, tag) for tag, low, default, high in axes], [])
    if math:
        table = DefaultTable("MATH")
        table.data = b"\x00\x01\x00\x00"
        builder.font["MATH"] = table
    builder.save(target)
    return target
