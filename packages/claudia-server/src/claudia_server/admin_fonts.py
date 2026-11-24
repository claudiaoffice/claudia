"""``/api/admin/fonts``: Server settings ▸ Fonts (E3.13 f, D1041). Administrators only.

The page shows the server's catalogue (:class:`~claudia_server.fonts.FontService`): its collections (the starter set
as one card, "Shipped with Claudia"; the operator's ``--fonts`` folders; those added here), its families with what
each stands in for, and every font it does not use, with the reason as a code the page puts in words. Who may receive
a collection's fonts (``may_go``) is ``anywhere`` or ``this-server`` (D1041).

Adding is check first, then add, and nothing on the server changes before the second step:

* ``POST /api/admin/fonts/files`` holds one file (the bytes as the body, its name in ``X-Claudia-Name``, as for
  ``/api/uploads``) and answers a token. A file is held for :data:`HOLD_SECONDS` at most, for the administrator who
  brought it; ``DELETE /api/admin/fonts/files`` ``{"files": [token...]}`` lets go of files given up (CODE-49).
  ``limits`` in the page says how much one administrator may have waiting.
* ``POST /api/admin/fonts/check`` ``{"files": [token...]}`` says what each font would become
  (:func:`claudia_fonts.check_files`).
* ``POST /api/admin/fonts/collections`` ``{"files", "name", "licence", "may_go"}`` adds them as a collection under
  ``STATE_DIR/fonts``, uses the held files up, reads the catalogue again, and answers the page (201).
* ``PATCH`` and ``DELETE /api/admin/fonts/collections/{id}`` rename and remove a collection added here; the starter set
  and the operator's folders are answered with 409.

Every answer but the check and the upload is the whole page (``GET /api/admin/fonts``), so the page never works out a
change itself. ``format`` rises when a field changes meaning or goes away.
"""

import asyncio
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from claudia_core.clock import utc_now
from claudia_fonts import (
    DEFAULT_GENERICS,
    AddRefused,
    Collection,
    FontFile,
    Problem,
    add_collection,
    check_files,
    remove_collection,
)
from claudia_fonts import rename_collection as rename_in_record
from claudia_fonts.adding import MAX_BYTES, MAX_FILES

from .fonts import FontService, Origin
from .i18n import message_of, msg
from .uploads import file_name, read_body

#: The format of ``GET /api/admin/fonts``.
ADMIN_FONTS_FORMAT = 1
#: How long a file brought for Add fonts… is held before it is dropped.
HOLD_SECONDS = 30 * 60
SHIPPED_ID = "shipped"
SHIPPED_NAME = "Shipped with Claudia"
JsonBody = Annotated[dict, Body()]
#: One change of a catalogue at a time (a server has one).
_CHANGING = asyncio.Lock()


@dataclass
class _Held:
    admin: str
    name: str
    data: bytes = field(repr=False)
    expires: float


class FontUploads:
    """The files brought for Add fonts…, held by token for the administrator who brought them, until they are added,
    let go of, or :data:`HOLD_SECONDS` pass. Each administrator may have at most
    :data:`~claudia_fonts.adding.MAX_FILES` files and :data:`~claudia_fonts.adding.MAX_BYTES` bytes waiting, so what
    one of them left behind never blocks another (CODE-49)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._held: dict[str, _Held] = {}

    def _expire(self) -> None:
        now = self._clock()
        for token in [t for t, held in self._held.items() if held.expires <= now]:
            del self._held[token]

    def _of(self, admin: str) -> list[_Held]:
        return [held for held in self._held.values() if held.admin == admin]

    def put(self, admin: str, name: str, data: bytes) -> str:
        """Hold a file for ``admin``; its token. ``HTTPException(503)`` when too much of theirs is waiting."""
        self._expire()
        waiting = self._of(admin)
        if len(waiting) >= MAX_FILES or sum(len(h.data) for h in waiting) + len(data) > MAX_BYTES:
            raise HTTPException(
                503,
                msg(
                    "too many fonts are waiting to be added: at most {files} files or {mb} MB at once; "
                    "close Add fonts… to let go of them",
                    files=MAX_FILES,
                    mb=MAX_BYTES // (1024 * 1024),
                ),
            )
        token = secrets.token_urlsafe(18)
        self._held[token] = _Held(admin, name, data, self._clock() + HOLD_SECONDS)
        return token

    def files(self, admin: str, tokens: object) -> list[tuple[str, bytes]]:
        """The files ``admin`` holds by ``tokens``, in order. ``HTTPException(400)`` for anything else."""
        self._expire()
        if not (isinstance(tokens, list) and tokens and all(isinstance(t, str) for t in tokens)):
            raise HTTPException(400, msg("files must be a list of tokens from /api/admin/fonts/files"))
        if any(t not in self._held or self._held[t].admin != admin for t in tokens):
            raise HTTPException(400, msg("a file is no longer held; choose it again"))
        return [(self._held[t].name, self._held[t].data) for t in tokens]

    def drop(self, admin: str, tokens: object) -> int:
        """Let go of the files ``admin`` holds by ``tokens`` (added, or given up); how many there were. Other tokens
        are ignored: a file that went after a while, or someone else's."""
        dropped = 0
        for token in tokens if isinstance(tokens, list) else ():
            if isinstance(token, str) and token in self._held and self._held[token].admin == admin:
                del self._held[token]
                dropped += 1
        return dropped


def _problem(problem: Problem) -> dict:
    return {
        "file": problem.path.name,
        "code": problem.code,
        "detail": problem.detail,
        "family": problem.family,
        "style": problem.style,
    }


def _style(font: FontFile) -> dict:
    return {
        "style": font.style,
        "weight": font.weight,
        "italic": font.italic,
        "sha256": font.sha256,
        "outlines": font.outlines,
        "variable": bool(font.axes),
    }


class _Page:
    """``GET /api/admin/fonts`` for one catalogue: which collection each font and problem belongs to, by folder."""

    def __init__(self, service: FontService) -> None:
        self.service = service
        self.catalogue = service.catalogue
        self.collections = list(self.catalogue.collections)

    def origin(self, collection: Collection) -> Origin:
        return self.service.origin_of(collection)

    def card_id(self, collection: Collection) -> str:
        """The shipped set is one card; an added collection is named by its folder; an operator's by its place."""
        origin = self.origin(collection)
        if origin == "shipped":
            return SHIPPED_ID
        if origin == "added":
            return collection.folder.name
        return f"operator-{self.collections.index(collection) + 1}"

    def owner(self, path) -> Collection | None:  # noqa: ANN001 - a Path
        return next((c for c in self.collections if path == c.folder or path.is_relative_to(c.folder)), None)

    def body(self, *, access_secret_set: bool) -> dict:
        fonts_by_card: dict[str, list[FontFile]] = {}
        for font in self.catalogue.fonts():
            owner = self.owner(font.path)
            fonts_by_card.setdefault(self.card_id(owner) if owner else "", []).append(font)
        problems_by_card: dict[str, list[Problem]] = {}
        for problem in self.catalogue.problems:
            owner = self.owner(problem.path)
            problems_by_card.setdefault(self.card_id(owner) if owner else "", []).append(problem)
        not_usable = [p for p in self.catalogue.problems if p.not_usable]
        return {
            "format": ADMIN_FONTS_FORMAT,
            "counts": {
                "families": len(self.catalogue.families()),
                "files": len(self.catalogue.fonts()),
                "collections": len(self.cards()),
                "not_usable": len(not_usable),
            },
            "collections": [
                self._card(card, members, fonts_by_card.get(card, []), problems_by_card.get(card, []))
                for card, members in self.cards().items()
            ],
            "families": self._families(),
            "problems": [_problem(p) | {"collection": p.collection} for p in not_usable],
            "access_secret_set": access_secret_set,
            "can_add": self.service.added_root is not None,
            "limits": {"files": MAX_FILES, "bytes": MAX_BYTES},
        }

    def cards(self) -> dict[str, list[Collection]]:
        cards: dict[str, list[Collection]] = {}
        for collection in self.collections:
            cards.setdefault(self.card_id(collection), []).append(collection)
        return cards

    def _card(self, card: str, members: list[Collection], fonts: list[FontFile], problems: list[Problem]) -> dict:
        first = members[0].record
        origin = self.origin(members[0])
        licences = sorted({m.record.licence for m in members})
        return {
            "id": card,
            "name": SHIPPED_NAME if card == SHIPPED_ID else first.name,
            "origin": origin,
            "editable": origin == "added",
            "licence": " · ".join(licences),
            "may_go": first.may_go,
            "families": sorted({f.family for f in fonts}, key=str.casefold),
            "files": len(fonts),
            "problems": sum(1 for p in problems if p.not_usable),
            "added_by": first.added_by,
            "added": first.added,
            "source": first.source,
        }

    def _families(self) -> list[dict]:
        out = []
        problems = [p for p in self.catalogue.problems if p.family and p.not_usable]
        generics = {name: font for name, font in DEFAULT_GENERICS.items() if name != "fallback"}
        for family in self.catalogue.families():
            fonts = self.catalogue.fonts_of(family)
            owner = self.owner(fonts[0].path)
            card = self.card_id(owner) if owner else ""
            stands_in = list(self.catalogue.stands_in_for(family))
            stands_in += [name for name, font in generics.items() if font.casefold() == family.casefold()]
            out.append(
                {
                    "family": family,
                    "styles": [_style(font) for font in fonts],
                    "collection": SHIPPED_NAME if card == SHIPPED_ID else (owner.record.name if owner else ""),
                    "collection_id": card,
                    "may_go": "anywhere" if fonts[0].redistributable else "this-server",
                    "stands_in_for": stands_in,
                    "problems": [
                        _problem(p) for p in problems if p.family and p.family.casefold() == family.casefold()
                    ],
                }
            )
        return out


def font_admin_routes(
    router: APIRouter,
    service: FontService,
    require_admin: Callable,
    access_secret_set: Callable[[], bool],
) -> None:
    """The ``/api/admin/fonts`` routes, on the admin router (whose ``require_admin`` signs every one of them in)."""
    uploads = FontUploads()

    def page() -> dict:
        return _Page(service).body(access_secret_set=access_secret_set())

    _adding_routes(router, service, require_admin, uploads, page)
    _collection_routes(router, service, require_admin, page)


def _adding_routes(
    router: APIRouter, service: FontService, require_admin: Callable, uploads: FontUploads, page: Callable[[], dict]
) -> None:
    """The page itself, and Add fonts…: hold a file, check, add."""
    Signedin = Annotated[str, Depends(require_admin)]

    @router.get("/fonts")
    async def fonts_page(admin: Signedin):
        return page()

    @router.post("/fonts/files")
    async def hold_file(request: Request, admin: Signedin):
        data = await read_body(request, MAX_BYTES)
        name = file_name(request.headers.get("x-claudia-name"))
        return {"token": uploads.put(admin, name, data), "name": name, "size": len(data)}

    @router.delete("/fonts/files")
    async def let_go(admin: Signedin, body: JsonBody):
        return {"dropped": uploads.drop(admin, body.get("files"))}

    @router.post("/fonts/check")
    async def check(admin: Signedin, body: JsonBody):
        files = uploads.files(admin, body.get("files"))
        try:
            checks = await asyncio.to_thread(check_files, files, service.catalogue)
        except AddRefused as exc:
            raise HTTPException(400, message_of(exc)) from exc
        added = [c for c in checks if c.verdict == "added"]
        families = sorted({c.family for c in added if c.family}, key=str.casefold)
        shipped = {c.record.name for c in service.catalogue.collections if service.origin_of(c) == "shipped"}
        lines = [c.to_data() for c in checks]
        for line in lines:  # a font of the starter set is replaced from the one card the page shows for it
            if line["code"] == "replaces" and line["detail"] in shipped:
                line["detail"] = SHIPPED_NAME
        return {"files": lines, "adds": len(added), "families": families}

    @router.post("/fonts/collections", status_code=201)
    async def add(admin: Signedin, body: JsonBody):
        if service.added_root is None:
            raise HTTPException(409, msg("this server has no folder to add fonts to"))
        may_go = body.get("may_go")
        if may_go not in ("anywhere", "this-server"):
            raise HTTPException(400, msg("may_go must be anywhere or this-server"))
        name, licence = body.get("name"), body.get("licence")
        if not (isinstance(name, str) and isinstance(licence, str)):
            raise HTTPException(400, msg("a collection needs a name and a licence"))
        tokens = body.get("files")
        files = uploads.files(admin, tokens)
        async with _CHANGING:
            try:
                await asyncio.to_thread(
                    add_collection,
                    service.added_root,
                    files,
                    service.catalogue,
                    name=name,
                    licence=licence,
                    redistributable=may_go == "anywhere",
                    added_by=admin,
                    added=utc_now()[:10],
                )
            except AddRefused as exc:
                raise HTTPException(400, message_of(exc)) from exc
            uploads.drop(admin, tokens)
            await asyncio.to_thread(service.reload)
        return page()


def _collection_routes(
    router: APIRouter, service: FontService, require_admin: Callable, page: Callable[[], dict]
) -> None:
    """Rename and remove a collection added in the server settings."""
    Signedin = Annotated[str, Depends(require_admin)]

    def editable(card: str) -> Collection:
        current = _Page(service)
        members = current.cards().get(card)
        if not members:
            raise HTTPException(404, msg("no such collection"))
        if current.origin(members[0]) != "added":
            raise HTTPException(409, msg("only a collection added in the server settings can be changed here"))
        return members[0]

    @router.patch("/fonts/collections/{card}")
    async def rename(card: str, admin: Signedin, body: JsonBody):
        name = body.get("name")
        if not isinstance(name, str):
            raise HTTPException(400, msg("a collection needs a name"))
        async with _CHANGING:
            collection = editable(card)
            try:
                await asyncio.to_thread(rename_in_record, collection.folder, name)
            except AddRefused as exc:
                raise HTTPException(400, message_of(exc)) from exc
            await asyncio.to_thread(service.reload)
        return page()

    @router.delete("/fonts/collections/{card}")
    async def remove(card: str, admin: Signedin):
        async with _CHANGING:
            collection = editable(card)
            assert service.added_root is not None  # an added collection has a root
            await asyncio.to_thread(remove_collection, service.added_root, collection.folder)
            await asyncio.to_thread(service.reload)
        return page()
