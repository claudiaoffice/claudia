"""``meta.xml``: who made a document and when, and keeping that true when Claudia edits a file (D411).

A document's title, its creator, the day it was made and the day it was last saved are not part of its text, but
every program shows them (File ▸ Properties) and a reviewer reads a tracked change's date against them. Claudia has
them: the container keeps when a document was made and the log says when and by whom each change was made. This
module turns that into ``meta.xml``.

* :func:`new_meta` writes the part for a new file.
* :func:`update_meta` is the way back for an edited import: like the paragraphs of ``content.xml`` (D401) it edits by
  splicing, so what the file says that Claudia has no use for -- the program that made it, how long it was edited, its
  statistics, the keywords, the user-defined properties -- stays exactly as it was.
* :func:`update_package_meta` does that for the parts of a whole package, also when the file has no ``meta.xml``.

Dates are written as UTC to the second, with a ``Z``: LibreOffice reads that (and any offset) and says so in every
format it converts to. :func:`odf_date` is the one place that turns the server's times into them."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import UTC, datetime
from xml.sax.saxutils import escape

from lxml import etree

from .names import NS, qname
from .paragraph import xml_safe
from .splice import OdfError, XmlPart

#: What the ``meta:generator`` of a file says after Claudia has written or changed it.
GENERATOR = "Claudia"
_DECLARATION = b'<?xml version="1.0" encoding="UTF-8"?>\n'
_MANIFEST = "META-INF/manifest.xml"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class DocumentInfo:
    """What a document says about itself. Dates are ISO 8601 (any zone; no zone means UTC, as every time the server
    stamps is); ``None`` is "not known" and leaves the file's own value alone."""

    title: str | None = None
    created: str | None = None
    creator: str | None = None
    modified: str | None = None
    modifier: str | None = None


def odf_date(moment: str) -> str:
    """``moment`` (ISO 8601) as the UTC second ODF wants: ``2026-11-11T17:13:05Z``. :class:`OdfError` when it is not
    a date."""
    try:
        parsed = datetime.fromisoformat(moment)
    except ValueError:
        raise OdfError(f"{moment!r} is not a date") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime(_DATE_FORMAT)


def _field(prefix: str, local: str, value: str) -> str:
    return f"<{prefix}:{local}>{escape(xml_safe(value))}</{prefix}:{local}>"


def _fields(info: DocumentInfo, *, with_generator: bool) -> list[tuple[str, str, str]]:
    """``(prefix, name, text)`` of every field ``info`` knows, in the order a program writes them."""
    wanted = [
        ("meta", "generator", GENERATOR if with_generator else None),
        ("dc", "title", info.title),
        ("meta", "initial-creator", info.creator),
        ("meta", "creation-date", odf_date(info.created) if info.created else None),
        ("dc", "creator", info.modifier),
        ("dc", "date", odf_date(info.modified) if info.modified else None),
    ]
    return [(prefix, local, value) for prefix, local, value in wanted if value is not None]


def new_meta(info: DocumentInfo) -> bytes:
    """The ``meta.xml`` of a new file: what ``info`` knows, and Claudia as the generator. The same input always gives
    the same bytes."""
    body = "".join(_field(prefix, local, value) for prefix, local, value in _fields(info, with_generator=True))
    return (
        _DECLARATION
        + f'<office:document-meta xmlns:office="{NS["office"]}" xmlns:meta="{NS["meta"]}" xmlns:dc="{NS["dc"]}" '
        f'office:version="1.3"><office:meta>{body}</office:meta></office:document-meta>'.encode()
    )


def _meta_element(root: etree._Element) -> etree._Element:
    found = root.find("office:meta", NS)
    if found is None:
        raise OdfError("this file's meta.xml has no office:meta element")
    return found


def read_info(meta_xml: bytes) -> DocumentInfo:
    """What a ``meta.xml`` says about the document: title, who made it and when, who last saved it and when. A date
    that cannot be read is left out."""
    try:
        root = etree.fromstring(meta_xml, etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError as problem:
        raise OdfError(f"this file's meta.xml is not well-formed XML: {problem}") from problem
    meta = _meta_element(root)

    def text(prefix: str, local: str) -> str | None:
        found = meta.find(f"{prefix}:{local}", NS)
        return (found.text or None) if found is not None else None

    def date(prefix: str, local: str) -> str | None:
        value = text(prefix, local)
        try:
            return odf_date(value) if value else None
        except OdfError:
            return None

    return DocumentInfo(
        text("dc", "title"),
        date("meta", "creation-date"),
        text("meta", "initial-creator"),
        date("dc", "date"),
        text("dc", "creator"),
    )


def update_meta(meta_xml: bytes | None, info: DocumentInfo) -> bytes:
    """``meta_xml`` as it is after Claudia saved the document: the modification date and who made it set from ``info``
    (what ``info`` does not know stays), the edit counted in ``meta:editing-cycles``, Claudia named as the generator,
    and what the file lacks of its title, creator and creation date filled in -- those are never overwritten: they
    say who made the document and when, which an edit does not change. Everything else is as it was, byte for byte.
    ``None`` (a file with no ``meta.xml``) gives :func:`new_meta` with the edit counted once."""
    if meta_xml is None:
        return update_meta(new_meta(info), info)
    part = XmlPart(meta_xml)
    meta = _meta_element(part.root)
    added: list[etree._Element] = []

    def put(prefix: str, local: str, value: str, *, only_if_missing: bool = False) -> None:
        existing = meta.find(f"{prefix}:{local}", NS)
        if existing is None:
            added.append(part.make(f"{prefix}:{local}", text=xml_safe(value)))
        elif not only_if_missing:
            changed = copy.copy(existing)  # (a deep copy: the element has no children worth keeping)
            for child in list(changed):
                changed.remove(child)
            changed.text = xml_safe(value)
            part.replace(existing, changed)

    for prefix, local, value in _fields(info, with_generator=True):
        put(prefix, local, value, only_if_missing=local in {"title", "initial-creator", "creation-date"})
    put("meta", "editing-cycles", str(_cycles(meta) + 1))
    if added:
        part.insert_into(meta, *added)
    return part.result()


def _cycles(meta: etree._Element) -> int:
    found = meta.find("meta:editing-cycles", NS)
    try:
        return max(0, int((found.text or "").strip())) if found is not None else 0
    except ValueError:
        return 0


def update_package_meta(parts: dict[str, bytes], info: DocumentInfo) -> None:
    """:func:`update_meta` for the parts of a package (as ``read_parts`` gives them), in place. A file with no
    ``meta.xml`` gets one, and the manifest an entry for it."""
    had = "meta.xml" in parts
    parts["meta.xml"] = update_meta(parts.get("meta.xml"), info)
    if had:
        return
    if _MANIFEST not in parts:
        raise OdfError("this file has no manifest to list its metadata in")
    manifest = XmlPart(parts[_MANIFEST])
    listed = {entry.get(qname("manifest:full-path")) for entry in manifest.root}
    if "meta.xml" not in listed:
        manifest.insert_into(
            manifest.root,
            manifest.make("manifest:file-entry", {"manifest:full-path": "meta.xml", "manifest:media-type": "text/xml"}),
        )
        parts[_MANIFEST] = manifest.result()
