"""The custom properties of an OPC package (``docProps/custom.xml``), the same part in Word, Excel and PowerPoint
files: name and value pairs any program shows under File ▸ Properties ▸ Custom and keeps when it saves the file.

Claudia writes text properties only, and reads only those (``vt:lpwstr``, ``vt:bstr``); a property of another type is
the file's own and is left alone (E6.31, D1478).
"""

from __future__ import annotations

from collections.abc import Mapping

from lxml import etree

from .xml import parse_xml

#: The part that holds them.
CUSTOM_PART = "docProps/custom.xml"
_CUSTOM = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
_VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.custom-properties+xml"
_RELATIONSHIP = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties"
#: The format id every custom property carries (ECMA-376 part 1, 22.3.2.2).
_FMTID = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"
_TEXT = (f"{{{_VT}}}lpwstr", f"{{{_VT}}}bstr")
_DECLARATION = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def _root(parts: Mapping[str, bytes]) -> etree._Element | None:
    data = parts.get(CUSTOM_PART)
    if data is None:
        return None
    try:
        return parse_xml(data)
    except etree.XMLSyntaxError:
        return None


def custom_properties(parts: Mapping[str, bytes]) -> dict[str, str]:
    """The text properties of the package ``parts`` (as :func:`~claudia_opc_io.read_parts` gives it), by name; none
    for a package without the part or with one that is not XML."""
    root = _root(parts)
    found: dict[str, str] = {}
    for prop in [] if root is None else root.iterfind(f"{{{_CUSTOM}}}property"):
        value = next((child for child in prop if child.tag in _TEXT), None)
        if value is not None and prop.get("name"):
            found[prop.get("name", "")] = value.text or ""
    return found


def set_custom_properties(parts: dict[str, bytes], values: Mapping[str, str]) -> None:
    """Give the package ``parts`` (changed in place) the text properties ``values``: one of the same name is replaced,
    the others stay. The part is made, declared and related from the package when it has none."""
    root = _root(parts)
    if root is None:
        root = etree.Element(f"{{{_CUSTOM}}}Properties", nsmap={None: _CUSTOM, "vt": _VT})
        _declare(parts)
    for prop in list(root):
        if prop.get("name") in values:
            root.remove(prop)
    ids = [int(prop.get("pid", "1")) for prop in root if (prop.get("pid") or "").isdigit()]
    for number, (name, value) in enumerate(values.items(), start=max(ids, default=1) + 1):
        prop = etree.SubElement(root, f"{{{_CUSTOM}}}property", fmtid=_FMTID, pid=str(number), name=name)
        etree.SubElement(prop, f"{{{_VT}}}lpwstr").text = value
    parts[CUSTOM_PART] = _DECLARATION + etree.tostring(root, encoding="UTF-8")


def _declare(parts: dict[str, bytes]) -> None:
    """The part's media type in ``[Content_Types].xml`` and its relationship from the package, once each."""
    types = parse_xml(parts["[Content_Types].xml"])
    if not any(o.get("PartName") == f"/{CUSTOM_PART}" for o in types.iterfind(f"{{{_TYPES}}}Override")):
        etree.SubElement(types, f"{{{_TYPES}}}Override", PartName=f"/{CUSTOM_PART}", ContentType=_MEDIA_TYPE)
        parts["[Content_Types].xml"] = _DECLARATION + etree.tostring(types, encoding="UTF-8")
    rels = parse_xml(parts["_rels/.rels"])
    if not any(r.get("Type") == _RELATIONSHIP for r in rels):
        taken = {r.get("Id") for r in rels}
        rid = next(f"rId{n}" for n in range(1, len(taken) + 2) if f"rId{n}" not in taken)
        etree.SubElement(rels, f"{{{_RELS}}}Relationship", Id=rid, Type=_RELATIONSHIP, Target=CUSTOM_PART)
        parts["_rels/.rels"] = _DECLARATION + etree.tostring(rels, encoding="UTF-8")
