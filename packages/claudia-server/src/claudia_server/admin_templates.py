"""``/api/admin/templates``: Server settings ▸ Templates (E10.22, D1537). Administrators only.

The page lists the templates of the server (:class:`~claudia_server.template_library.TemplateLibrary`): the built-in
Basic one and those added here. Adding is check first, then add, and nothing on the server changes before the second
step. The file is the body of the request, as for ``/api/uploads``: a template is a few hundred kilobytes, so it is
sent again rather than held between the two steps.

* ``POST /api/admin/templates/check`` says what the file would become: ``{name, purpose, language, layouts}``; 400 with
  a sentence for a file that is no template or has a name another template has.
* ``POST /api/admin/templates`` adds it and answers the whole page (201).
* ``DELETE /api/admin/templates/{id}`` removes an added template and answers the whole page; the built-in one is
  answered with 409, an id nobody has with 404.

``format`` of the page rises when a field changes meaning or goes away.
"""

import asyncio
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from claudia_creates.template import TemplateRefused
from claudia_document_file import ExportRefused

from .template_library import MAX_TEMPLATE_BYTES, TemplateLibrary, describe
from .uploads import read_body

ADMIN_TEMPLATES_FORMAT = 1
#: One change of the library at a time (a server has one).
_CHANGING = asyncio.Lock()


def template_admin_routes(router: APIRouter, library: TemplateLibrary, require_admin: Callable) -> None:
    """The ``/api/admin/templates`` routes, on the admin router (whose ``require_admin`` signs every one of them in)."""
    Signedin = Annotated[str, Depends(require_admin)]

    def page() -> dict:
        return {
            "format": ADMIN_TEMPLATES_FORMAT,
            "templates": [{**describe(entry, "en"), "removable": not entry.builtin} for entry in library.entries()],
        }

    @router.get("/templates")
    async def templates_page(admin: Signedin):
        return page()

    @router.post("/templates/check")
    async def check(request: Request, admin: Signedin):
        data = await read_body(request, MAX_TEMPLATE_BYTES)
        try:
            template = await asyncio.to_thread(library.check, data)
        except (ExportRefused, TemplateRefused) as exc:
            raise HTTPException(400, str(exc)) from exc
        return {**template.info.to_data(), "layouts": [layout.name for layout in template.model.layouts]}

    @router.post("/templates", status_code=201)
    async def add(request: Request, admin: Signedin):
        data = await read_body(request, MAX_TEMPLATE_BYTES)
        async with _CHANGING:
            try:
                await asyncio.to_thread(library.add, data, added_by=admin)
            except (ExportRefused, TemplateRefused) as exc:
                raise HTTPException(400, str(exc)) from exc
        return page()

    @router.delete("/templates/{template_id}")
    async def remove(template_id: str, admin: Signedin):
        async with _CHANGING:
            try:
                await asyncio.to_thread(library.remove, template_id)
            except TemplateRefused as exc:
                raise HTTPException(409, str(exc)) from exc
            except KeyError:
                raise HTTPException(404, "no such template") from None
        return page()
