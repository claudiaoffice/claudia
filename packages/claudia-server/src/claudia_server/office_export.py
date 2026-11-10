"""Wrapping a Word, Excel or PowerPoint export for the wire, shared by all three apps' ``export_office`` (D212).

Each app converts its own model to bytes with its own converter (``claudia_composes_io.text_to_docx`` and the
like, no tracked changes: just the document as it stands now) and hands the result here to be wrapped the same
way every time. The wire protocol is JSON text frames (``protocol.py``), so there is no binary download channel
either: the bytes travel back as base64 text, the mirror image of ``images.py``'s decode. This module has no
app-specific knowledge, exactly as ``images.py`` does not.
"""

from __future__ import annotations

import base64

CONTENT_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def office_export(fmt: str, data: bytes) -> dict:
    """``data`` (the bytes of a file in format ``fmt``) as `export_office` returns it: `{format, content_type,
    data}`, `data` base64 text."""
    return {"format": fmt, "content_type": CONTENT_TYPES[fmt], "data": base64.b64encode(data).decode("ascii")}
