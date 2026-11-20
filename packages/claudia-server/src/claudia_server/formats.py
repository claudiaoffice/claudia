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
import json
import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

from claudia_container import MAX_DESCRIPTION, MAX_TAGS, clean_details, read_export
from claudia_opc_io import check_package

from .i18n import DEFAULT_LOCALE
from .thing_names import name_unnamed_things

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
CLAUDIA_EXPORT = "claudia-export"
"""A Claudia export, the unencrypted zip of D1270: it comes in as a new document (D1272)."""
_ODF = {
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/vnd.oasis.opendocument.presentation": "odp",
}
_OOXML = {"word/document.xml": "docx", "xl/workbook.xml": "xlsx", "ppt/presentation.xml": "pptx"}
_MAX_SMALL_ENTRY = 4096  # ``mimetype`` and ``format`` are a few dozen bytes
_MAX_EXPORT_INFO = 64 * 1024


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
                if declared.startswith(b"claudia-export "):
                    return Sniffed(CLAUDIA_EXPORT, _export_app(archive))
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


def _export_header(archive: zipfile.ZipFile) -> dict | None:
    """``export.json`` of an export, if it is a small entry that reads as an object (the rest is not touched)."""
    try:
        info = archive.getinfo("export.json")
        if info.file_size > _MAX_EXPORT_INFO:
            return None
        header = json.loads(archive.read(info))
    except (KeyError, ValueError, TypeError):
        return None
    return header if isinstance(header, dict) else None


def _export_app(archive: zipfile.ZipFile) -> str | None:
    """The app an export says it is of, read from ``export.json`` alone."""
    app = (_export_header(archive) or {}).get("app")
    return app if isinstance(app, str) and app in {app for app, _ in FORMATS.values()} else None


def export_made(data: bytes) -> tuple[str, str]:
    """Who made an export and when, as the file says it (shown to the person who imports it): ``("", "")`` for a file
    that does not say. Only ``export.json`` is read."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            header = _export_header(archive) or {}
    except (zipfile.BadZipFile, OSError, ValueError, EOFError):
        return "", ""
    who, when = header.get("exporter"), header.get("exported_at")
    return (who if isinstance(who, str) else "")[:200], (when if isinstance(when, str) else "")[:40]


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


def import_state(
    fmt: str, data: bytes, locale: str = DEFAULT_LOCALE, *, state_schema: int | None = None
) -> tuple[dict, list[dict]]:
    """The state an import of ``data`` (a file of format ``fmt``) makes, as ``serialize()`` gives it, and what the
    document will not show, as ``{kind, detail, count}``. For a Claudia export (D1272) it is the export's own state,
    refused if its ``state_schema`` is not ``state_schema``. Raises whatever the reader raises for a broken file, and
    ``claudia_opc_io.PackageRefused`` for a zip that unpacks to far too much (SEC-15): the office libraries open the
    zip themselves, so this is the one place every format passes before any of them does.

    A thing of the file that has no name (a slide, a paragraph the file did not bookmark) is named by what it is, in
    ``locale``, the language of the one who imports (E1.13, D1311)."""
    if fmt == CLAUDIA_EXPORT:
        exported = read_export(data)
        if state_schema is not None and exported.state_schema != state_schema:
            raise ValueError("the export was made by another version of Claudia and has another shape of state")
        return exported.state, []
    read, losses_of = _reader(fmt)
    check_package(data)
    model = read(data)
    name_unnamed_things(model, locale)
    losses = (
        []
        if losses_of is None
        else [{"kind": loss.kind, "detail": loss.detail, "count": loss.count} for loss in losses_of(data)]
    )
    return model.serialize(), losses


# -- what a file says about itself ------------------------------------------------------------------------------------
_DC = "{http://purl.org/dc/elements/1.1/}"
_OOXML_KEYWORDS = "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}keywords"
_ODF_KEYWORD = "{urn:oasis:names:tc:opendocument:xmlns:meta:1.0}keyword"
_PROPERTIES_PART = {"docx": "docProps/core.xml", "xlsx": "docProps/core.xml", "pptx": "docProps/core.xml"}
_MAX_PROPERTIES = 64 * 1024  # the part is a few hundred bytes; a larger one is not read (and cannot be a bomb)
_KEYWORD_SEPARATORS = re.compile(r"[,;]")
#: What the template of a library puts in ``description`` of every file it writes: nobody wrote it about this document.
_BOILERPLATE = frozenset({"generated by python-docx", "generated using python-pptx"})


def file_details(fmt: str, data: bytes) -> tuple[str, tuple[str, ...]]:
    """The description and tags an office file already carries, to offer to the person when they import it: Dublin
    Core ``description`` (``subject`` when there is no description) and the keywords, from ``docProps/core.xml`` of
    Word, Excel and PowerPoint and ``meta.xml`` of OpenDocument.

    What does not fit Claudia's limits is cut down or left out, never refused: a file is not rejected for its
    properties. A part that is too large, not XML, or has a DOCTYPE (entities) says nothing. Always
    ``("", ())`` for a file that has none."""
    part = _PROPERTIES_PART.get(fmt, "meta.xml")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo(part)
            if info.file_size > _MAX_PROPERTIES:
                return "", ()
            raw = archive.read(info)
        if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
            return "", ()
        root = ElementTree.fromstring(raw)  # noqa: S314 - no DOCTYPE, so no entities; the size is capped above
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError, OSError, ValueError, EOFError):
        return "", ()
    return _tidy(_describe(root, odf=fmt not in _PROPERTIES_PART))


def _describe(root: ElementTree.Element, *, odf: bool) -> tuple[str, list[str]]:
    def texts(tag: str) -> list[str]:
        return [(found.text or "") for found in root.iter(tag)]

    description = next(
        (text for text in texts(_DC + "description") if text.strip() and text.strip().casefold() not in _BOILERPLATE),
        "",
    )
    if not description.strip():
        description = next((text for text in texts(_DC + "subject") if text.strip()), "")
    keywords = (
        texts(_ODF_KEYWORD)
        if odf
        else [part for text in texts(_OOXML_KEYWORDS) for part in _KEYWORD_SEPARATORS.split(text)]
    )
    return description, keywords


def _tidy(found: tuple[str, list[str]]) -> tuple[str, tuple[str, ...]]:
    description, keywords = found
    try:
        text, _ = clean_details(description[:MAX_DESCRIPTION], ())
    except ValueError:
        text = ""
    tags: dict[str, None] = {}
    for keyword in keywords:
        try:
            cleaned = clean_details("", [keyword])[1]
        except ValueError:
            continue  # too long, or not a tag: left out
        tags.update(dict.fromkeys(cleaned))
    return text, tuple(tags)[:MAX_TAGS]
