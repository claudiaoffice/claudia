"""Wrapping a Word, Excel, PowerPoint or OpenDocument export for the wire, shared by all three apps'
``export_office`` (D212, D401, D411).

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

from claudia_core import CommandLog
from claudia_odf_io import DocumentInfo, Loss

CONTENT_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "odt": "application/vnd.oasis.opendocument.text",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
}


def document_info(log: CommandLog, branch: str | None = None) -> DocumentInfo:
    """When a document was made and last changed, and by whom, from the log of the line ``branch`` (the active one
    when none): the first entry made it, the last changed it (D411). An empty log knows neither. The text app's
    ``export_info`` also dates its suggestions; the others have nothing else to date."""
    path = log.path(log.head(branch if branch is not None else log.active))
    if not path:
        return DocumentInfo()
    first, last = path[0], path[-1]
    return DocumentInfo(None, first.time, first.author, last.time, last.author)


def office_export(fmt: str, data: bytes, losses: Iterable[Loss] | None = None) -> dict:
    """``data`` (the bytes of a file in format ``fmt``) as `export_office` returns it: `{format, content_type,
    data}`, `data` base64 text -- and, when ``losses`` is given (even empty), `losses`: a list of `{kind, detail,
    count}` for what the file could not hold."""
    answer: dict = {"format": fmt, "content_type": CONTENT_TYPES[fmt], "data": base64.b64encode(data).decode("ascii")}
    if losses is not None:
        answer["losses"] = [{"kind": loss.kind, "detail": loss.detail, "count": loss.count} for loss in losses]
    return answer
