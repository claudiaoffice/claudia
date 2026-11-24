"""The server's refusals over plain HTTP, said in the language of the page that asked (CODE-92, D31, D322).

A document's refusals reach its connection in the connection's language. The HTTP routes (the administrator's pages
above all) have no connection: their pages send their App Language as ``Accept-Language``, and a refusal whose detail
is a message (``msg``) is said in it. A refusal that must carry more than its sentence (the seconds to wait, the reason
of a failure) is a :class:`Refused`.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from .i18n import Message, localized
from .protocol import normalize_locale


class Refused(HTTPException):
    """A refusal with more in its answer than ``detail``: each of ``extra`` is a field of the JSON beside it."""

    def __init__(self, status_code: int, detail: str, *, headers: dict[str, str] | None = None, **extra: Any) -> None:
        super().__init__(status_code, detail, headers)
        self.extra = extra


def request_locale(request: Request) -> str:
    """The language a request asks to be answered in: the first of its ``Accept-Language``, else English."""
    first = request.headers.get("accept-language", "").split(",")[0].split(";")[0].strip()
    return normalize_locale(first)


async def _answer(request: Request, error: Exception) -> Response:
    assert isinstance(error, StarletteHTTPException)  # (registered for exactly this class)
    extra = getattr(error, "extra", {})
    if not isinstance(error.detail, Message) and not extra:
        return await http_exception_handler(request, error)
    detail = localized(error.detail, request_locale(request))
    return JSONResponse({"detail": detail, **extra}, status_code=error.status_code, headers=error.headers)


def install(app: FastAPI) -> None:
    """Say the refusals of every route of ``app`` in the language its request asks for."""
    app.add_exception_handler(StarletteHTTPException, _answer)
