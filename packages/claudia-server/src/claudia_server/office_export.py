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
import hashlib
import logging
from collections.abc import Callable, Iterable
from typing import cast

from claudia_core import CommandLog, DocumentModel, Import
from claudia_odf_io import DocumentInfo, Loss, LossLog

log = logging.getLogger("claudia_server")

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


def import_of(log_: CommandLog, branch: str | None = None) -> Import | None:
    """The ``core.Import`` this document was made with, on the line ``branch`` (the active one when none); ``None``
    for a document that was not imported (D438)."""
    for entry in log_.path(log_.head(branch if branch is not None else log_.active)):
        if isinstance(entry.command, Import):
            return entry.command
    return None


def export_with_original[M: DocumentModel](
    ctx,  # noqa: ANN001 - protocol.Context (imported here it would be circular)
    fmt: str,
    model_cls: type[M],
    patch: Callable[[bytes, M, M, LossLog], bytes],
    fresh: Callable[[], dict],
    unwritten: Callable[[M, M], Iterable[Loss]] | None = None,
    *,
    not_patched: str = "",
) -> dict:
    """``export_office`` for a document that may have been imported (D441). When it was imported from a file of
    ``fmt`` and that file is kept, the answer is that file with the edits since the import patched in (``patch``:
    the app's ``apply_edits_to_<fmt>(original, baseline, current)``, which may add to the ``LossLog`` it is given what
    the patch itself could not keep), and says ``patched: true``: everything Claudia does not show stays as the file
    had it. Its ``losses`` are what the patch said and what ``unwritten(current, baseline)`` says of the edits the
    patch has no place for (D299, D405). Otherwise, or when the edits cannot be patched in, the answer is
    ``fresh()``; in the second case its losses also say ``not-patched``, with the reason. ``not_patched`` is a reason
    given by the caller why the original is not to be patched this time (what was asked for cannot be patched in):
    the answer is ``fresh()`` and says ``not-patched`` with that reason, when there is an original."""
    imported = import_of(ctx.document.log, ctx.document.branch)
    if imported is None or imported.fmt != fmt or not imported.kept:
        return fresh()
    if not_patched:
        return _noted(fresh(), not_patched)
    original = ctx.original()
    if original is None or hashlib.sha256(original).hexdigest() != imported.sha256:
        log.warning("the kept original of %s is missing or not the imported file", ctx.doc_id)
        return _noted(fresh(), "the kept file is missing")
    try:
        baseline, current, found = model_cls.restore(imported.state), cast(M, ctx.document.model), LossLog()
        data = patch(original, baseline, current, found)
        lost = (*found.result(), *(unwritten(current, baseline) if unwritten is not None else ()))
    except Exception as exc:  # noqa: BLE001 - every writer has its own UnsupportedEdit; any failure means "write anew"
        log.info("cannot patch the edits of %s into its original: %s", ctx.doc_id, exc)
        return _noted(fresh(), str(exc))
    answer = office_export(fmt, data, lost)
    answer["patched"] = True
    return answer


def _noted(answer: dict, reason: str) -> dict:
    answer.setdefault("losses", []).append({"kind": "not-patched", "detail": reason, "count": 1})
    return answer
