"""One font file: what it is called, how it looks and what it may be used for (E3.3)."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont

from .collection import Collection

FONT_SUFFIXES = frozenset({".ttf", ".otf"})
RESTRICTED_EMBEDDING = 0x0002  # OS/2 fsType: the font may not be embedded in documents
ITALIC_SELECTION = 0x01  # OS/2 fsSelection
ITALIC_MAC_STYLE = 0x02  # head macStyle
WILDCARDS = "*?"  # the engine setup hides files by name pattern, so a name must not contain these


class FontProblem(ValueError):
    """A font file that is not used; the message says why."""


@dataclass(frozen=True)
class FontFile:
    """A font of the catalogue. Its ``sha256`` is that of the file's bytes: the same bytes in the browser (as WOFF2)
    and in the typesetting engine give the same letter shapes."""

    path: Path
    family: str
    style: str
    weight: int
    italic: bool
    sha256: str
    collection: str
    licence: str
    redistributable: bool
    math: bool

    def to_data(self) -> dict:
        """The font as plain data for clients: everything but the place on the server's disk."""
        return {
            "family": self.family,
            "style": self.style,
            "weight": self.weight,
            "italic": self.italic,
            "sha256": self.sha256,
            "collection": self.collection,
            "licence": self.licence,
            "redistributable": self.redistributable,
            "math": self.math,
        }


def read_font(path: str | Path, collection: Collection) -> FontFile:
    """Read a font file of ``collection``; :class:`FontProblem` if it cannot be used.

    A font is refused when it is not a font, has no family name, carries a wildcard in its file name, or forbids
    embedding (the *restricted* bit of its OS/2 table). The two other embedding bits, preview and print and editable,
    do not restrict: Latin Modern sets both."""
    path = Path(path)
    if any(character in path.name for character in WILDCARDS):
        raise FontProblem(f"{path.name}: a file name with a wildcard (* or ?) cannot be hidden exactly; rename it")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise FontProblem(f"{path.name}: cannot be read: {error}") from error
    try:
        font = TTFont(io.BytesIO(data), lazy=True)
        names, os2, head = font["name"], font["OS/2"], font["head"]
        family = names.getDebugName(16) or names.getDebugName(1)
        style = names.getDebugName(17) or names.getDebugName(2) or ""
        weight = int(os2.usWeightClass)
        fs_type = int(os2.fsType)
        italic = bool(os2.fsSelection & ITALIC_SELECTION) or bool(head.macStyle & ITALIC_MAC_STYLE)
        math = "MATH" in font
    except Exception as error:  # noqa: BLE001 - fontTools raises many kinds of errors on damaged files
        raise FontProblem(f"{path.name}: not a font that can be read ({error})") from error
    if not family:
        raise FontProblem(f"{path.name}: the font has no family name")
    if fs_type & RESTRICTED_EMBEDDING:
        raise FontProblem(f"{path.name}: the font forbids embedding (OS/2 fsType {fs_type}), so it is not used")
    record = collection.record
    return FontFile(
        path=path,
        family=family,
        style=style,
        weight=weight,
        italic=italic,
        sha256=hashlib.sha256(data).hexdigest(),
        collection=record.name,
        licence=record.licence,
        redistributable=record.redistributable,
        math=math,
    )
