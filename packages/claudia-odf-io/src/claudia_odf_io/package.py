"""An OpenDocument package: building one from its parts, and checking that a file is one (D401).

The zip rules (``mimetype`` first and stored) are in ``claudia_opc_io.write_parts``; what this adds is what only
OpenDocument has: the manifest that lists every part with its media type, and the three media types of the apps."""

from __future__ import annotations

import zipfile
from io import BytesIO

from lxml import etree

from claudia_opc_io import write_parts

from .meta import DocumentInfo, new_meta
from .names import NS

#: The media types of the three kinds of document, by the name of the kind.
MIME = {
    "text": "application/vnd.oasis.opendocument.text",
    "spreadsheet": "application/vnd.oasis.opendocument.spreadsheet",
    "presentation": "application/vnd.oasis.opendocument.presentation",
}
#: The version of the specification that new documents are written as, and the one LibreOffice writes.
VERSION = "1.3"
_MANIFEST = "META-INF/manifest.xml"
_XML_PARTS = ("content.xml", "styles.xml", "meta.xml", "settings.xml")
_DECLARATION = b'<?xml version="1.0" encoding="UTF-8"?>\n'


def _manifest(kind: str, entries: list[tuple[str, str]]) -> bytes:
    lines = [
        f'<manifest:file-entry manifest:full-path="/" manifest:version="{VERSION}" manifest:media-type="{MIME[kind]}"/>'
    ]
    lines += [
        f'<manifest:file-entry manifest:full-path="{path}" manifest:media-type="{media}"/>' for path, media in entries
    ]
    return (
        _DECLARATION
        + f'<manifest:manifest xmlns:manifest="{NS["manifest"]}" manifest:version="{VERSION}">'.encode()
        + "".join(lines).encode()
        + b"</manifest:manifest>"
    )


def new_package(
    kind: str,
    content: bytes,
    styles: bytes,
    *,
    meta: bytes | None = None,
    extra: dict[str, tuple[bytes, str]] | None = None,
) -> bytes:
    """A new OpenDocument file of ``kind`` (``"text"``, ``"spreadsheet"`` or ``"presentation"``) from its content
    and styles parts, and the document's metadata (a minimal one if none is given). ``extra`` has the other parts
    -- pictures, embedded objects -- by name, each with its bytes and media type. The same input always gives the
    same bytes."""
    parts: dict[str, bytes] = {"mimetype": MIME[kind].encode(), "content.xml": content, "styles.xml": styles}
    parts["meta.xml"] = meta if meta is not None else new_meta(DocumentInfo())
    entries = [("content.xml", "text/xml"), ("styles.xml", "text/xml"), ("meta.xml", "text/xml")]
    for name, (data, media_type) in (extra or {}).items():
        parts[name] = data
        entries.append((name, media_type))
    parts[_MANIFEST] = _manifest(kind, entries)
    return write_parts(parts)


def read_manifest(manifest_xml: bytes) -> dict[str, str]:
    """The manifest as ``{part name: media type}``; the document itself is ``"/"``."""
    root = etree.fromstring(manifest_xml)
    path, media = (f"{{{NS['manifest']}}}{name}" for name in ("full-path", "media-type"))
    return {entry.get(path, ""): entry.get(media, "") for entry in root.iter(f"{{{NS['manifest']}}}file-entry")}


def problems(data: bytes) -> list[str]:
    """What is wrong with ``data`` as an OpenDocument file, as sentences; nothing is wrong when the list is empty.
    It checks the packaging (``mimetype`` first and stored, a manifest that agrees with the zip) and that the XML
    parts are well-formed; it is not a validation against the schema."""
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile:
        return ["not a zip file"]
    found: list[str] = []
    names = archive.namelist()
    if names[:1] != ["mimetype"]:
        found.append("the mimetype part is not the first one in the file")
    mimetype = ""
    if "mimetype" in names:
        info = archive.getinfo("mimetype")
        if info.compress_type != zipfile.ZIP_STORED:
            found.append("the mimetype part is compressed; it must be stored")
        mimetype = archive.read("mimetype").decode("ascii", "replace")
        if mimetype not in MIME.values():
            found.append(f"the media type {mimetype!r} is not one of the OpenDocument kinds")
    found += _manifest_problems(archive, names, mimetype)
    for name in _XML_PARTS:
        if name in names:
            found += _xml_problems(name, archive.read(name))
    return found


def _manifest_problems(archive: zipfile.ZipFile, names: list[str], mimetype: str) -> list[str]:
    if _MANIFEST not in names:
        return ["there is no manifest (META-INF/manifest.xml)"]
    try:
        manifest = read_manifest(archive.read(_MANIFEST))
    except etree.XMLSyntaxError as problem:
        return [f"the manifest is not well-formed XML: {problem}"]
    found = []
    if mimetype and manifest.get("/") != mimetype:
        found.append(
            f"the manifest gives the document the media type {manifest.get('/')!r}, the mimetype part {mimetype!r}"
        )
    found.extend(
        f"{name} is not listed in the manifest"
        for name in names
        if not name.endswith("/") and name not in {"mimetype", _MANIFEST} and name not in manifest
    )
    found.extend(
        f"the manifest lists {path}, which is not in the file"
        for path in manifest
        if path != "/" and not path.endswith("/") and path not in names
    )
    return found


def _xml_problems(name: str, data: bytes) -> list[str]:
    try:
        root = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError as problem:
        return [f"{name} is not well-formed XML: {problem}"]
    if name in {"content.xml", "styles.xml"} and root.get(f"{{{NS['office']}}}version") is None:
        return [f"{name} does not say which version of OpenDocument it is (office:version)"]
    return []
