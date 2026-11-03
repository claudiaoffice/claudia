"""Web fonts: WOFF2 files made from the font files, named by hash, and the CSS that points at them (E3.3).

The files are never fetched from anywhere else: a client gets its fonts from the server it works with, so a document
looks the same offline and nothing about a person's documents leaks to a font CDN (D26).
"""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from fontTools.ttLib import TTFont

from .catalogue import Catalogue
from .font import FontFile


class NotServable(Exception):
    """A font that may not be handed to a client, or cannot be, and why."""


def _quote(text: str) -> str:
    """A CSS string: quotes, backslashes and line breaks cannot end it early."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\a ").replace("\r", "\\d ")
    return f'"{escaped}"'


def _woff2(data: bytes) -> bytes:
    font = TTFont(io.BytesIO(data))
    font.flavor = "woff2"
    out = io.BytesIO()
    font.save(out)
    return out.getvalue()


class WebFontCache:
    """Folder of ``<sha256>.woff2`` files, made on first use and kept. The name is the hash of the font file, so
    a file can be cached by browsers for ever: other bytes would have another name."""

    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)

    def get(self, font: FontFile) -> Path:
        """The WOFF2 file of ``font``, made now if it does not exist yet.

        :class:`NotServable` if the font's collection does not allow handing fonts out, or if the file on disk is no
        longer the one the catalogue read."""
        if not font.redistributable:
            raise NotServable(f"{font.family} {font.style} ({font.collection}) may not be handed out to clients")
        target = self._directory / f"{font.sha256}.woff2"
        if target.is_file():
            return target
        data = font.path.read_bytes()
        if hashlib.sha256(data).hexdigest() != font.sha256:
            raise NotServable(f"{font.path.name} changed since the catalogue was made; load the catalogue again")
        self._directory.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=self._directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "wb") as out:
                out.write(_woff2(data))
            os.replace(temporary, target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return target


def _rule(font: FontFile, url: str) -> str:
    slant = "italic" if font.italic else "normal"
    return (
        "@font-face {\n"
        f"  font-family: {_quote(font.family)};\n"
        f"  font-weight: {font.weight};\n"
        f"  font-style: {slant};\n"
        "  font-display: swap;\n"
        f'  src: url({_quote(url)}) format("woff2");\n'
        "}\n"
    )


def font_face_css(catalogue: Catalogue, family: str, url_for: Callable[[FontFile], str]) -> str:
    """The ``@font-face`` rules of a family, one per style, each pointing at the address ``url_for`` gives.

    Fonts that may not be handed out are left out, so the result can be empty. ``KeyError`` for an unknown family."""
    fonts = catalogue.fonts_of(family)
    if not fonts:
        raise KeyError(family)
    return "\n".join(_rule(font, url_for(font)) for font in fonts if font.redistributable)
