"""Zip-as-parts: an OPC package (docx/xlsx/pptx, and ods/odt/odp once those are added) is a zip archive of named
parts. ``read_parts``/``write_parts`` move between that and a plain ``dict[str, bytes]``; nothing here knows or
cares what any part actually contains -- that is exactly the point (D177)."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile


def read_parts(zip_bytes: bytes) -> dict[str, bytes]:
    """Every part of a zip package, by its name inside the archive, in the archive's own order."""
    with ZipFile(BytesIO(zip_bytes)) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def write_parts(parts: dict[str, bytes]) -> bytes:
    """The inverse of :func:`read_parts`: a zip package holding exactly these parts, in the order given."""
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as zf:
        for name, data in parts.items():
            zf.writestr(name, data)
    return out.getvalue()
