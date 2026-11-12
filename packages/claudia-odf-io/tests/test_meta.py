"""meta.xml: the title, the dates and the people of a document (D411)."""

from __future__ import annotations

import pytest
from lxml import etree

from claudia_odf_io import (
    NS,
    DocumentInfo,
    OdfError,
    new_meta,
    new_package,
    odf_date,
    problems,
    read_info,
    read_manifest,
    update_meta,
    update_package_meta,
)
from claudia_opc_io import read_parts, write_parts

META_HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n'
DECLS = f'xmlns:office="{NS["office"]}" xmlns:meta="{NS["meta"]}" xmlns:dc="{NS["dc"]}"'


def a_meta(inner: str) -> bytes:
    return (
        f'{META_HEAD}<office:document-meta {DECLS} office:version="1.3">'
        f"<office:meta>{inner}</office:meta></office:document-meta>"
    ).encode()


def texts(data: bytes) -> dict[str, str]:
    root = etree.fromstring(data)
    meta = root.find("office:meta", NS)
    assert meta is not None
    return {etree.QName(child).localname: child.text or "" for child in meta}


class TestOdfDate:
    @pytest.mark.parametrize(
        ("given", "written"),
        [
            ("2026-11-11T17:13:05Z", "2026-11-11T17:13:05Z"),
            ("2026-11-11T17:13:05+00:00", "2026-11-11T17:13:05Z"),
            ("2026-11-11T18:13:05+01:00", "2026-11-11T17:13:05Z"),
            ("2026-11-11T17:13:05.987654Z", "2026-11-11T17:13:05Z"),
            ("2026-11-11T17:13:05", "2026-11-11T17:13:05Z"),  # no zone: the server's times are UTC
        ],
    )
    def test_is_utc_to_the_second(self, given, written):
        assert odf_date(given) == written

    def test_a_time_that_is_not_one_is_an_error(self):
        with pytest.raises(OdfError, match="not a date"):
            odf_date("yesterday")


class TestNewMeta:
    def test_has_what_it_is_given(self):
        info = DocumentInfo("Plan", "2026-01-02T03:04:05Z", "Ann", "2026-11-11T17:13:05Z", "Bob")
        found = texts(new_meta(info))
        assert found["title"] == "Plan"
        assert found["initial-creator"] == "Ann"
        assert found["creation-date"] == "2026-01-02T03:04:05Z"
        assert found["creator"] == "Bob"
        assert found["date"] == "2026-11-11T17:13:05Z"
        assert found["generator"].startswith("Claudia")

    def test_leaves_out_what_it_is_not_given(self):
        assert set(texts(new_meta(DocumentInfo()))) == {"generator"}

    def test_escapes_text(self):
        assert texts(new_meta(DocumentInfo(title="Q&A <draft>")))["title"] == "Q&A <draft>"

    def test_is_the_same_bytes_each_time(self):
        info = DocumentInfo("Plan", "2026-01-02T03:04:05Z", "Ann")
        assert new_meta(info) == new_meta(info)

    def test_goes_into_a_new_package(self):
        info = DocumentInfo("Plan", modified="2026-11-11T17:13:05Z")
        data = new_package("text", b"<x/>", b"<y/>", meta=new_meta(info))
        assert read_info(read_parts(data)["meta.xml"]).title == "Plan"


class TestReadInfo:
    def test_reads_what_new_meta_wrote(self):
        info = DocumentInfo("Plan", "2026-01-02T03:04:05Z", "Ann", "2026-11-11T17:13:05Z", "Bob")
        assert read_info(new_meta(info)) == info

    def test_a_file_without_them_has_none(self):
        assert read_info(a_meta("<meta:generator>X</meta:generator>")) == DocumentInfo()

    def test_a_date_with_fractions_is_read_to_the_second(self):
        info = read_info(a_meta("<meta:creation-date>2020-05-06T07:08:09.123456789</meta:creation-date>"))
        assert info.created == "2020-05-06T07:08:09Z"

    def test_not_xml_is_an_error(self):
        with pytest.raises(OdfError):
            read_info(b"nope")


class TestUpdateMeta:
    ORIGINAL = a_meta(
        "<meta:generator>LibreOffice/24.2</meta:generator><dc:title>Plan</dc:title>"
        "<meta:initial-creator>Ann</meta:initial-creator><meta:creation-date>2020-01-01T00:00:00</meta:creation-date>"
        "<dc:creator>Ann</dc:creator><dc:date>2020-02-02T00:00:00</dc:date>"
        "<meta:editing-cycles>4</meta:editing-cycles><meta:editing-duration>PT5M</meta:editing-duration>"
        '<meta:document-statistic meta:page-count="2" meta:word-count="10"/>'
    )

    def test_sets_when_and_by_whom(self):
        info = DocumentInfo(modified="2026-11-11T17:13:05Z", modifier="Bob")
        found = texts(update_meta(self.ORIGINAL, info))
        assert found["date"] == "2026-11-11T17:13:05Z"
        assert found["creator"] == "Bob"

    def test_counts_the_edit_and_names_the_program(self):
        found = texts(update_meta(self.ORIGINAL, DocumentInfo(modified="2026-11-11T17:13:05Z")))
        assert found["editing-cycles"] == "5"
        assert found["generator"].startswith("Claudia")

    def test_keeps_who_made_it_and_when(self):
        info = DocumentInfo("Other", "2030-01-01T00:00:00Z", "Eve", "2026-11-11T17:13:05Z", "Bob")
        found = texts(update_meta(self.ORIGINAL, info))
        assert found["initial-creator"] == "Ann"
        assert found["creation-date"] == "2020-01-01T00:00:00"
        assert found["title"] == "Plan"

    def test_every_byte_it_does_not_edit_is_the_originals(self):
        info = DocumentInfo(modified="2026-11-11T17:13:05Z", modifier="Bob")
        result = update_meta(self.ORIGINAL, info)
        for keep in (
            b"<dc:title>Plan</dc:title>",
            b"<meta:initial-creator>Ann</meta:initial-creator>",
            b"<meta:editing-duration>PT5M</meta:editing-duration>",
            b'<meta:document-statistic meta:page-count="2" meta:word-count="10"/>',
            META_HEAD.encode(),
        ):
            assert keep in result

    def test_adds_what_the_file_lacks(self):
        info = DocumentInfo("Plan", "2026-01-02T03:04:05Z", "Ann", "2026-11-11T17:13:05Z", "Bob")
        found = texts(update_meta(a_meta("<meta:generator>X</meta:generator>"), info))
        assert found["title"] == "Plan"
        assert found["initial-creator"] == "Ann"
        assert found["creation-date"] == "2026-01-02T03:04:05Z"
        assert found["editing-cycles"] == "1"

    def test_an_empty_meta_element_is_opened(self):
        data = f'{META_HEAD}<office:document-meta {DECLS} office:version="1.3"><office:meta/></office:document-meta>'
        found = texts(update_meta(data.encode(), DocumentInfo(modified="2026-11-11T17:13:05Z")))
        assert found["date"] == "2026-11-11T17:13:05Z"

    def test_no_meta_part_makes_one(self):
        found = texts(update_meta(None, DocumentInfo("Plan", modified="2026-11-11T17:13:05Z")))
        assert found["title"] == "Plan"
        assert found["date"] == "2026-11-11T17:13:05Z"

    def test_a_count_that_is_not_a_number_starts_again(self):
        data = a_meta("<meta:editing-cycles>many</meta:editing-cycles>")
        assert texts(update_meta(data, DocumentInfo(modified="2026-11-11T17:13:05Z")))["editing-cycles"] == "1"

    def test_the_prefixes_of_the_file_are_used(self):
        data = (
            f'{META_HEAD}<o:document-meta xmlns:o="{NS["office"]}" xmlns:m="{NS["meta"]}" xmlns:d="{NS["dc"]}" '
            'o:version="1.3"><o:meta><d:date>2020-02-02T00:00:00</d:date></o:meta></o:document-meta>'
        ).encode()
        result = update_meta(data, DocumentInfo(modified="2026-11-11T17:13:05Z", modifier="Bob"))
        assert b"<d:date>2026-11-11T17:13:05Z</d:date>" in result
        assert read_info(result).modified == "2026-11-11T17:13:05Z"

    def test_without_a_date_nothing_about_when_changes(self):
        found = texts(update_meta(self.ORIGINAL, DocumentInfo(modifier="Bob")))
        assert found["date"] == "2020-02-02T00:00:00"
        assert found["creator"] == "Bob"

    def test_the_same_edit_twice_gives_the_same_bytes(self):
        info = DocumentInfo(modified="2026-11-11T17:13:05Z", modifier="Bob")
        assert update_meta(self.ORIGINAL, info) == update_meta(self.ORIGINAL, info)


class TestUpdatePackageMeta:
    def test_replaces_the_part(self):
        parts = read_parts(new_package("text", b"<x/>", b"<y/>"))
        update_package_meta(parts, DocumentInfo(title="Plan", modified="2026-11-11T17:13:05Z"))
        assert read_info(parts["meta.xml"]).modified == "2026-11-11T17:13:05Z"

    def test_a_file_without_meta_gets_the_part_and_a_manifest_entry(self):
        parts = read_parts(new_package("text", b"<x/>", b"<y/>"))
        del parts["meta.xml"]
        parts["META-INF/manifest.xml"] = parts["META-INF/manifest.xml"].replace(
            b'<manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>', b""
        )
        update_package_meta(parts, DocumentInfo(title="Plan", modified="2026-11-11T17:13:05Z"))
        assert read_manifest(parts["META-INF/manifest.xml"])["meta.xml"] == "text/xml"
        assert read_info(parts["meta.xml"]).title == "Plan"

    def test_the_result_is_a_sound_package(self):
        versioned = f'{META_HEAD}<office:document-content {DECLS} office:version="1.3"/>'.encode()
        parts = read_parts(new_package("text", versioned, versioned))
        update_package_meta(parts, DocumentInfo(modified="2026-11-11T17:13:05Z"))
        assert problems(write_parts(parts)) == []
