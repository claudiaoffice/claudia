"""The server's fonts for its clients (E3.3, D905): the catalogue as data, and the font files themselves.

Layout and PDF export run in the client (D901), so a client must lay out with exactly the font files every other
client uses. The server is where those files live: its font catalogue (``claudia_fonts.Catalogue``, read from the
folders given with ``--fonts``) lists every font with the SHA-256 of its file, and the files are served under that
hash. A file's address never changes its meaning, so browsers may keep it for good.

* ``GET /api/fonts`` - the catalogue: each font that may be handed out (family, style, weight, slant, axes, outlines,
  hash and licence), the metric-compatible substitutions, the font of each generic family (``generics``: serif,
  sans-serif, monospace and the fallback, E3.13), and the catalogue's digest. All from
  :mod:`claudia_core.stand_ins`, so a client never keeps a table of its own.
* ``GET /api/fonts/{sha256}`` - the file itself (TrueType or OpenType), for layout and for embedding in a PDF.
* ``GET /api/fonts/{sha256}.woff2`` - the same font as WOFF2, for showing text in a page.

Fonts are public on purpose, like the web app's own files (D92): they say nothing about any document. A collection
whose fonts may go to this server's own people only (D1041: ``redistributable: false``, "This server" on Server
settings ▸ Fonts) is listed and served only to a request that shows it is one of them (``local``: the server's access
secret, or an administrator's session); on a server without an access secret that is everyone who reaches it. A file
that changed on disk since the catalogue read it is refused rather than served under the old hash.

The collections come from three places, read in this order, a later font replacing an earlier one of the same family
and style: the starter set shipped with ``claudia_fonts`` (D500, *shipped*), the operator's ``--fonts`` folders
(*operator*), and the collections added through the server settings (``STATE_DIR/fonts``, *added*,
:mod:`claudia_server.admin_fonts`). :meth:`FontService.reload` reads them again after a change.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from claudia_fonts import (
    DEFAULT_GENERICS,
    Catalogue,
    Collection,
    FontFile,
    NotServable,
    WebFontCache,
    collection_folders,
)

#: The format of ``GET /api/fonts``; it rises when a field changes meaning or goes away.
FONTS_FORMAT = 1
_HASH = re.compile(r"[0-9a-f]{64}")
_FOREVER = "public, max-age=31536000, immutable"
_MEDIA = {".ttf": "font/ttf", ".otf": "font/otf"}

Origin = Literal["shipped", "operator", "added"]
"""Where a collection comes from, the starter set (D500), the operator's ``--fonts`` or the server settings (D1041)."""


@dataclass
class FontService:
    """The fonts a server hands to its clients: a catalogue, where its collections come from, and a folder for the
    WOFF2 files made from it."""

    catalogue: Catalogue
    webfont_dir: Path
    sources: tuple[tuple[Path, Origin], ...] = ()
    """The folders collections are read from (a collection folder or a folder of them), in order, with their origin."""
    added_root: Path | None = None
    """Where the server settings add collections (``STATE_DIR/fonts``); ``None`` for a server that cannot."""
    _origins: dict[Path, Origin] = field(default_factory=dict, repr=False)

    @classmethod
    def from_folders(
        cls,
        folders: Iterable[str | Path],
        webfont_dir: str | Path,
        *,
        shipped: Iterable[str | Path] = (),
        added_root: str | Path | None = None,
    ) -> FontService:
        """The fonts of every collection in ``shipped``, then ``folders`` (the operator's), then ``added_root`` (each a
        collection folder, or a folder of them)."""
        sources: list[tuple[Path, Origin]] = [(Path(f), "shipped") for f in shipped]
        sources += [(Path(f), "operator") for f in folders]
        if added_root is not None:
            sources.append((Path(added_root), "added"))
        service = cls(Catalogue.from_collections([]), Path(webfont_dir), tuple(sources), _path(added_root))
        service.reload()
        return service

    def reload(self) -> None:
        """Read every collection again (after one was added, renamed or removed): from now on the listing and the
        files are the new catalogue's."""
        origins: dict[Path, Origin] = {}
        for source, origin in self.sources:
            for folder in collection_folders(source):
                origins[folder] = origin
        self._origins = origins
        self.catalogue = Catalogue.from_folders(origins)

    def origin_of(self, collection: Collection) -> Origin:
        """Where a collection of the catalogue comes from (*operator* for one the service was not built with)."""
        return self._origins.get(collection.folder, "operator")

    def servable(self, *, local: bool = False) -> list[FontFile]:
        """The fonts that may be handed out, by family, weight and slant: those that may go anywhere, and with
        ``local`` (the request comes from this server's own people) those for this server too."""
        return [f for f in self.catalogue.fonts() if f.redistributable or local]

    def listing(
        self, substitutions: Mapping[str, str], generics: Mapping[str, str] = DEFAULT_GENERICS, *, local: bool = False
    ) -> dict:
        """The body of ``GET /api/fonts``; ``local`` as for :meth:`servable`."""
        return {
            "format": FONTS_FORMAT,
            "digest": self.catalogue.digest,
            "fonts": [f.to_data() | {"file": f"/api/fonts/{f.sha256}"} for f in self.servable(local=local)],
            "substitutions": dict(substitutions),
            "generics": dict(generics),
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


def _path(value: str | Path | None) -> Path | None:
    return None if value is None else Path(value)


def font_router(
    service: FontService,
    substitutions: Mapping[str, str],
    local: Callable[[Request], bool] = lambda _request: False,
) -> APIRouter:
    """The ``/api/fonts`` routes of a server. ``local`` says whether a request comes from the server's own people,
    who may also get the fonts for this server only (D1041)."""
    router = APIRouter(prefix="/api/fonts")
    cache = WebFontCache(service.webfont_dir)

    def find(sha256: str, request: Request) -> FontFile:
        font = service.catalogue.by_hash(sha256) if _HASH.fullmatch(sha256) else None
        if font is None or not (font.redistributable or local(request)):
            raise HTTPException(404, "no such font")
        return font

    @router.get("")
    async def listing(request: Request) -> JSONResponse:
        # the listing changes when fonts are added, so it is checked each time; the files below never change. Private:
        # with fonts for this server only, what a response holds depends on who asked.
        body = service.listing(substitutions, local=local(request))
        return JSONResponse(body, headers={"Cache-Control": "no-cache, private", "Vary": "Authorization"})

    # Not `async`: FastAPI runs a plain function in its thread pool. Making a WOFF2 file takes seconds (PERF-09) and
    # reading and hashing a large font takes a while too; on the event loop every other request would wait for it.
    @router.get("/{name}")
    def font_file(name: str, request: Request) -> Response:
        if name.endswith(".woff2"):
            font = find(name.removesuffix(".woff2"), request)
            try:
                path = cache.get(font, local=True)  # find() has checked who may have it
            except NotServable as error:
                raise HTTPException(409, str(error)) from error
            return FileResponse(path, media_type="font/woff2", headers=_kept(font))
        font = find(name, request)
        data = font.path.read_bytes()
        if hashlib.sha256(data).hexdigest() != font.sha256:
            raise HTTPException(409, "the font file changed since the server read it; the server must reload its fonts")
        media = _MEDIA.get(font.path.suffix.lower(), "application/octet-stream")
        return Response(data, media_type=media, headers=_kept(font))

    return router


def _kept(font: FontFile) -> dict[str, str]:
    """How long a font file may be kept: for good, and by anyone in between for a font that may go anywhere; only by
    the person's own browser for one that is for this server only (D1041)."""
    if font.redistributable:
        return {"Cache-Control": _FOREVER}
    return {"Cache-Control": "private, max-age=31536000, immutable", "Vary": "Authorization"}
