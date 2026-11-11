"""Wrapping a Word, Excel, PowerPoint or OpenDocument export for the wire, shared by all three apps'
``export_office`` (D212, D401).

Each app converts its own model to bytes with its own converter (``claudia_composes_io.text_to_docx`` and the
like, no tracked changes: just the document as it stands now) and hands the result here to be wrapped the same
way every time. A format whose converter can say what the file could not hold (the OpenDocument ones) hands the
list along too, as codes for the interface to put into words; it is not in the answer for a format that cannot.
The wire protocol is JSON text frames (``protocol.py``), so there is no binary download channel either: the bytes
travel back as base64 text, the mirror image of ``images.py``'s decode. This module has no app-specific
knowledge, exactly as ``images.py`` does not."""

from __future__ import annotations

import base64
from collections.abc import Iterable

from claudia_odf_io import Loss

CONTENT_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "odt": "application/vnd.oasis.opendocument.text",
}


def office_export(fmt: str, data: bytes, losses: Iterable[Loss] | None = None) -> dict:
    """``data`` (the bytes of a file in format ``fmt``) as `export_office` returns it: `{format, content_type,
    data}`, `data` base64 text -- and, when ``losses`` is given (even empty), `losses`: a list of `{kind, detail,
    count}` for what the file could not hold."""
    answer: dict = {"format": fmt, "content_type": CONTENT_TYPES[fmt], "data": base64.b64encode(data).decode("ascii")}
    if losses is not None:
        answer["losses"] = [{"kind": loss.kind, "detail": loss.detail, "count": loss.count} for loss in losses]
    return answer
