"""custom_properties / set_custom_properties: the custom properties of an Office file (``docProps/custom.xml``), which
every Office program shows under File ▸ Properties ▸ Custom and keeps when it saves the file (E6.31, D1478)."""

from __future__ import annotations

from claudia_opc_io import CUSTOM_PART, custom_properties, read_parts, set_custom_properties, write_parts

TYPES = (
    b'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    b'<Default Extension="xml" ContentType="application/xml"/></Types>'
)
RELS = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
    b' Target="xl/workbook.xml"/></Relationships>'
)


def a_fresh_xlsx() -> dict[str, bytes]:
    return {"[Content_Types].xml": TYPES, "_rels/.rels": RELS, "xl/workbook.xml": b"<workbook/>"}


def test_a_property_set_is_read_back_after_the_package_is_written():
    parts = a_fresh_xlsx()
    set_custom_properties(parts, {"Claudia slides": '{"slides": ["Q1 & <Q2>"]}'})
    again = read_parts(write_parts(parts))
    assert custom_properties(again) == {"Claudia slides": '{"slides": ["Q1 & <Q2>"]}'}
    assert b'PartName="/docProps/custom.xml"' in again["[Content_Types].xml"]
    assert b'Target="docProps/custom.xml"' in again["_rels/.rels"]


def test_the_part_is_declared_and_related_once():
    parts = a_fresh_xlsx()
    set_custom_properties(parts, {"a": "1"})
    set_custom_properties(parts, {"b": "2"})
    assert custom_properties(parts) == {"a": "1", "b": "2"}
    assert parts["[Content_Types].xml"].count(b"/docProps/custom.xml") == 1
    assert parts["_rels/.rels"].count(b"docProps/custom.xml") == 1


def test_a_property_of_the_same_name_is_replaced_and_the_others_are_kept():
    parts = a_fresh_xlsx()
    set_custom_properties(parts, {"a": "1", "b": "2"})
    set_custom_properties(parts, {"a": "3"})
    assert custom_properties(parts) == {"a": "3", "b": "2"}


def test_a_file_without_custom_properties_has_none_and_one_that_is_not_xml_too():
    parts = a_fresh_xlsx()
    assert custom_properties(parts) == {}
    parts[CUSTOM_PART] = b"<not xml"
    assert custom_properties(parts) == {}


def test_only_text_properties_are_read():
    parts = a_fresh_xlsx()
    set_custom_properties(parts, {"a": "1"})
    parts[CUSTOM_PART] = parts[CUSTOM_PART].replace(
        b"</Properties>",
        (
            b'<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="9" name="n"><vt:i4>5</vt:i4></property>'
            b"</Properties>"
        ),
    )
    assert custom_properties(parts) == {"a": "1"}


def test_a_package_that_declares_the_part_already_is_not_given_a_second_declaration():
    parts = a_fresh_xlsx()
    set_custom_properties(parts, {"a": "1"})
    del parts[CUSTOM_PART]  # (a program dropped the part and kept what pointed at it)
    set_custom_properties(parts, {"b": "2"})
    assert custom_properties(parts) == {"b": "2"}
    assert parts["[Content_Types].xml"].count(b"/docProps/custom.xml") == 1
    assert parts["_rels/.rels"].count(b"docProps/custom.xml") == 1
