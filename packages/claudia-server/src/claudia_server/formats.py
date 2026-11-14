"""What kind of file a person brought, and the document an import makes of it (D438, D440).

:func:`sniff` looks at the bytes only, never at the name: a zip whose ``mimetype`` says OpenDocument, a zip with the
parts of Word, Excel or PowerPoint, or a Claudia document (a zip whose first entry is ``format``). It reads the
listing and at most two tiny entries, so a hostile file costs nothing to refuse.

:func:`import_state` runs the reader of the format (``claudia_computes_io.xlsx_to_workbook`` and its siblings) and
answers the model's own ``serialize()`` form and what the model does not show, as loss codes. It is a plain function
of picklable arguments, so the server runs it in its worker pool (D134, D436): reading a large workbook neither stops
the event loop nor takes the server down when a reader crashes.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

#: The formats an import reads, the app each becomes, and its own words for people.
FORMATS: dict[str, tuple[str, str]] = {
    "docx": ("composes", "Word document"),
    "odt": ("composes", "OpenDocument text"),
    "xlsx": ("computes", "Excel workbook"),
    "ods": ("computes", "OpenDocument spreadsheet"),
    "pptx": ("creates", "PowerPoint presentation"),
    "odp": ("creates", "OpenDocument presentation"),
}
CLAUDIA = "claudia"
_ODF = {
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/vnd.oasis.opendocument.presentation": "odp",
}
_OOXML = {"word/document.xml": "docx", "xl/workbook.xml": "xlsx", "ppt/presentation.xml": "pptx"}
_MAX_SMALL_ENTRY = 4096  # ``mimetype`` and ``format`` are a few dozen bytes


class UnknownFormat(ValueError):
    """The bytes are none of the formats Claudia opens."""


@dataclass(frozen=True)
class Sniffed:
    """What a file is: ``fmt`` (a key of ``FORMATS``, or ``"claudia"``) and the app its document belongs to (for a
    Claudia document, ``None`` until its manifest is read)."""

    fmt: str
    app: str | None


def _small(archive: zipfile.ZipFile, name: str) -> bytes | None:
    try:
        info = archive.getinfo(name)
    except KeyError:
        return None
    if info.file_size > _MAX_SMALL_ENTRY:
        return None
    return archive.read(info)


def sniff(data: bytes) -> Sniffed:
    """The kind of file ``data`` is. ``UnknownFormat`` for anything else."""
    if not data.startswith(b"PK\x03\x04"):
        raise UnknownFormat("not a document Claudia can open")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if infos and infos[0].filename == "format":
                declared = _small(archive, "format") or b""
                if declared.startswith(b"claudia-document "):
                    return Sniffed(CLAUDIA, None)
            mimetype = (_small(archive, "mimetype") or b"").decode("ascii", "replace").strip()
            if mimetype in _ODF:
                fmt = _ODF[mimetype]
                return Sniffed(fmt, FORMATS[fmt][0])
            names = {info.filename for info in infos}
            if "[Content_Types].xml" in names:
                for part, fmt in _OOXML.items():
                    if part in names:
                        return Sniffed(fmt, FORMATS[fmt][0])
    except (zipfile.BadZipFile, OSError, ValueError, EOFError) as error:
        raise UnknownFormat("not a document Claudia can open") from error
    raise UnknownFormat("not a document Claudia can open")


def _reader(fmt: str):  # noqa: ANN202 - one of six reader functions
    """The reader of ``fmt`` and its losses function."""
    if fmt in ("xlsx", "ods"):
        import claudia_computes_io as computes_io

        if fmt == "xlsx":
            return computes_io.xlsx_to_workbook, computes_io.xlsx_import_losses
        return computes_io.ods_to_workbook, computes_io.ods_import_losses
    if fmt in ("docx", "odt"):
        import claudia_composes_io as composes_io

        if fmt == "docx":
            return composes_io.docx_to_text, composes_io.docx_import_losses
        return composes_io.odt_to_text, composes_io.odt_import_losses
    if fmt in ("pptx", "odp"):
        import claudia_creates_io as creates_io

        if fmt == "pptx":
            return creates_io.pptx_to_slides, creates_io.pptx_import_losses
        return creates_io.odp_to_slides, creates_io.odp_import_losses
    raise UnknownFormat(f"{fmt} cannot be imported")


def import_state(fmt: str, data: bytes) -> tuple[dict, list[dict]]:
    """The state an import of ``data`` (a file of format ``fmt``) makes, as ``serialize()`` gives it, and what the
    document will not show, as ``{kind, detail, count}``. Raises whatever the reader raises for a broken file."""
    read, losses_of = _reader(fmt)
    model = read(data)
    losses = (
        []
        if losses_of is None
        else [{"kind": loss.kind, "detail": loss.detail, "count": loss.count} for loss in losses_of(data)]
    )
    return model.serialize(), losses
