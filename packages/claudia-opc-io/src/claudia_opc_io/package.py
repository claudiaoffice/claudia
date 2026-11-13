"""Zip-as-parts: an OPC package (docx/xlsx/pptx) or an OpenDocument package (odt/ods/odp) is a zip archive of named
parts. ``read_parts``/``write_parts`` move between that and a plain ``dict[str, bytes]``; nothing here knows or
cares what any part actually contains -- that is exactly the point (D217).

One rule of OpenDocument lives here because it is a rule of the zip, not of any format's content: a part called
``mimetype`` is written first and stored, not compressed (ODF 1.3 part 3, 3.3), so that a program can read the type
of a file at a fixed place in it without unzipping. LibreOffice does not mind either way, but ``file``, browsers,
file managers and upload filters do (D401)."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

#: The part that must come first, uncompressed, in an OpenDocument package.
MIMETYPE = "mimetype"
#: Every part gets this timestamp (the earliest a zip can hold), so the same parts always give the same bytes; a
#: part's modification time is nothing a document means, and a package that differs from its twin by the clock is
#: one nobody can compare, cache or sign.
_EPOCH = (1980, 1, 1, 0, 0, 0)


def read_parts(zip_bytes: bytes) -> dict[str, bytes]:
    """Every part of a zip package, by its name inside the archive, in the archive's own order."""
    with ZipFile(BytesIO(zip_bytes)) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def write_parts(parts: dict[str, bytes]) -> bytes:
    """The inverse of :func:`read_parts`: a zip package holding exactly these parts, in the order given -- except
    that a part named ``mimetype`` comes first and is stored without compression. The same parts always give the
    same bytes."""
    ordered = sorted(parts, key=lambda name: name != MIMETYPE)  # stable: only ``mimetype`` moves, to the front
    out = BytesIO()
    with ZipFile(out, "w") as zf:
        for name in ordered:
            info = ZipInfo(name, _EPOCH)
            info.compress_type = ZIP_STORED if name == MIMETYPE else ZIP_DEFLATED
            zf.writestr(info, parts[name])
    return out.getvalue()
