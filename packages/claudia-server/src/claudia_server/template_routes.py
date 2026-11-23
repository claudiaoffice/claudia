"""``/api/templates``: the templates a person can start a presentation from (E10.4, E10.22, D1538).

* ``GET /api/templates?locale=de`` lists them (:func:`~claudia_server.template_library.describe`), the built-in one in
  the language asked.
* ``POST /api/templates/{id}/upload?locale=de`` makes the new presentation the template starts, as a file held like any
  upload (``POST /api/uploads``) and answers what the upload answers. What makes it a document is the usual way in:
  ``hello`` with ``create: true`` and ``upload: <token>``, so the person who asks becomes its owner and nothing is
  logged as an export. The presentation is a copy with one slide; its things are named in ``locale``.

Whoever may make documents may ask: with an access secret, only those who know it.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request

from claudia_core.clock import utc_now
from claudia_creates import SlideModel
from claudia_creates.template import start_from_template
from claudia_document_file import write_export

from .protocol import normalize_locale
from .suite import Suite
from .template_library import TemplateLibrary, describe
from .thing_names import name_unnamed_things
from .uploads import UploadDesk, UploadRefused


def template_router(
    library: TemplateLibrary,
    suite: Suite,
    uploads: UploadDesk,
    may_make: Callable[[Request], None],
    address_of: Callable[[Request], str],
) -> APIRouter:
    router = APIRouter(prefix="/api/templates")

    @router.get("")
    async def listing(request: Request, locale: str = "en"):
        may_make(request)
        language = normalize_locale(locale)
        return {"templates": [describe(entry, language) for entry in library.entries()]}

    @router.post("/{template_id}/upload")
    async def start(template_id: str, request: Request, locale: str = "en"):
        may_make(request)
        template = library.get(template_id)
        if template is None:
            raise HTTPException(404, "no such template")
        module = suite.module(SlideModel.app)
        if module is None:
            raise HTTPException(422, f"this server does not host {SlideModel.app}")
        deck = start_from_template(template)
        name_unnamed_things(deck, normalize_locale(locale))
        data = write_export(
            deck.app, deck.state_schema, deck.serialize(), exporter=template.info.name, exported_at=utc_now()
        )
        try:
            held = uploads.put(address_of(request), f"{template.info.name}.claudia-export.zip", data)
        except UploadRefused as exc:
            raise HTTPException(exc.status, exc.message) from exc
        return {**held.describe(), "hosted": True}

    return router
