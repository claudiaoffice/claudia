"""The server's fonts for its clients (E3.3, D905): the catalogue as data, and the font files themselves.

Layout and PDF export run in the client (D901), so a client must lay out with exactly the font files every other
client uses. The server is where those files live: its font catalogue (``claudia_fonts.Catalogue``, read from the
folders given with ``--fonts``) lists every font with the SHA-256 of its file, and the files are served under that
hash. A file's address never changes its meaning, so browsers may keep it for good.

* ``GET /api/fonts`` - the catalogue: each font that may be handed out (family, style, weight, slant, axes, outlines,
  hash and licence), the metric-compatible substitutions, and the catalogue's digest.
* ``GET /api/fonts/{sha256}`` - the file itself (TrueType or OpenType), for layout and for embedding in a PDF.
* ``GET /api/fonts/{sha256}.woff2`` - the same font as WOFF2, for showing text in a page.

Fonts are public on purpose, like the web app's own files (D92): they say nothing about any document. Only fonts
whose collection allows redistribution are listed or served, and a file that changed on disk since the catalogue
read it is refused rather than served under the old hash.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response

from claudia_fonts import Catalogue, FontFile, NotServable, WebFontCache, collection_folders

#: The format of ``GET /api/fonts``; it rises when a field changes meaning or goes away.
FONTS_FORMAT = 1
_HASH = re.compile(r"[0-9a-f]{64}")
_FOREVER = "public, max-age=31536000, immutable"
_MEDIA = {".ttf": "font/ttf", ".otf": "font/otf"}


@dataclass
class FontService:
    """The fonts a server hands to its clients: a catalogue and a folder for the WOFF2 files made from it."""

    catalogue: Catalogue
    webfont_dir: Path

    @classmethod
    def from_folders(cls, folders: Iterable[str | Path], webfont_dir: str | Path) -> FontService:
        """The fonts of every collection in ``folders`` (a collection folder, or a folder of them)."""
        collections = [c for folder in folders for c in collection_folders(folder)]
        return cls(Catalogue.from_folders(collections), Path(webfont_dir))

    def servable(self) -> list[FontFile]:
        """The fonts that may be handed out, by family, weight and slant."""
        return [f for f in self.catalogue.fonts() if f.redistributable]

    def listing(self, substitutions: Mapping[str, str]) -> dict:
        """The body of ``GET /api/fonts``."""
        return {
            "format": FONTS_FORMAT,
            "digest": self.catalogue.digest,
            "fonts": [f.to_data() | {"file": f"/api/fonts/{f.sha256}"} for f in self.servable()],
            "substitutions": dict(substitutions),
        }

    def summary(self) -> str:
        """One line for the start-up banner."""
        fonts = self.servable()
        if not fonts:
            return (
                "no fonts to hand out: print and PDF export need some "
                "(python -m claudia_fonts fetch DIR, then --fonts DIR)"
            )
        families = len({f.family.casefold() for f in fonts})
        return f"fonts: {len(fonts)} files in {families} families for clients (/api/fonts)"


def font_router(service: FontService, substitutions: Mapping[str, str]) -> APIRouter:
    """The ``/api/fonts`` routes of a server."""
    router = APIRouter(prefix="/api/fonts")
    cache = WebFontCache(service.webfont_dir)

    def find(sha256: str) -> FontFile:
        font = service.catalogue.by_hash(sha256) if _HASH.fullmatch(sha256) else None
        if font is None or not font.redistributable:
            raise HTTPException(404, "no such font")
        return font

    @router.get("")
    async def listing() -> JSONResponse:
        # the listing changes when fonts are added, so it is checked each time; the files below never change
        return JSONResponse(service.listing(substitutions), headers={"Cache-Control": "no-cache"})

    @router.get("/{name}")
    async def font_file(name: str) -> Response:
        if name.endswith(".woff2"):
            font = find(name.removesuffix(".woff2"))
            try:
                path = cache.get(font)
            except NotServable as error:
                raise HTTPException(409, str(error)) from error
            return FileResponse(path, media_type="font/woff2", headers={"Cache-Control": _FOREVER})
        font = find(name)
        data = font.path.read_bytes()
        if hashlib.sha256(data).hexdigest() != font.sha256:
            raise HTTPException(409, "the font file changed since the server read it; the server must reload its fonts")
        media = _MEDIA.get(font.path.suffix.lower(), "application/octet-stream")
        return Response(data, media_type=media, headers={"Cache-Control": _FOREVER})

    return router
