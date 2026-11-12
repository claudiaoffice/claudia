"""Building an OpenDocument package, and checking that a file is one (D401)."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from claudia_odf_io import MIME, new_package, problems, read_manifest
from claudia_opc_io import read_parts, write_parts

CONTENT = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.3"/>'
)
STYLES = CONTENT.replace(b"document-content", b"document-styles")


def a_text_package(**extra) -> bytes:
    return new_package("text", CONTENT, STYLES, extra=extra)


def test_a_new_package_has_the_parts_of_an_opendocument_file():
    parts = read_parts(a_text_package())
    assert list(parts) == ["mimetype", "content.xml", "styles.xml", "meta.xml", "META-INF/manifest.xml"]
    assert parts["mimetype"] == MIME["text"].encode()


def test_the_media_types_are_those_of_the_three_apps():
    assert MIME == {
        "text": "application/vnd.oasis.opendocument.text",
        "spreadsheet": "application/vnd.oasis.opendocument.spreadsheet",
        "presentation": "application/vnd.oasis.opendocument.presentation",
    }


def test_a_new_package_is_one_that_passes_the_check():
    assert problems(a_text_package()) == []


def test_the_manifest_lists_every_part_with_its_media_type():
    manifest = read_manifest(
        read_parts(a_text_package(**{"Pictures/a.png": (b"\x89PNG", "image/png")}))["META-INF/manifest.xml"]
    )
    assert manifest["/"] == MIME["text"]
    assert manifest["content.xml"] == "text/xml"
    assert manifest["Pictures/a.png"] == "image/png"
    assert "mimetype" not in manifest and "META-INF/manifest.xml" not in manifest


def test_an_extra_part_is_in_the_zip_too():
    assert read_parts(a_text_package(**{"Pictures/a.png": (b"\x89PNG", "image/png")}))["Pictures/a.png"] == b"\x89PNG"


def test_the_same_input_gives_the_same_bytes():
    assert a_text_package() == a_text_package()


def test_a_document_with_a_given_meta_part_keeps_it():
    meta = b"<office:document-meta/>"
    assert read_parts(new_package("text", CONTENT, STYLES, meta=meta))["meta.xml"] == meta


def test_an_unknown_kind_is_an_error():
    with pytest.raises(KeyError):
        new_package("drawing", CONTENT, STYLES)


# -- the check ------------------------------------------------------------------------------------------------------
def test_a_file_that_is_not_a_zip_is_one_problem():
    assert problems(b"not a zip")[0].startswith("not a zip file")


def test_a_compressed_mimetype_is_a_problem():
    parts = read_parts(a_text_package())
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in parts.items():
            zf.writestr(name, data)
    assert any("mimetype" in p and "stored" in p for p in problems(out.getvalue()))


def test_a_mimetype_that_is_not_first_is_a_problem():
    parts = read_parts(a_text_package())
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr("content.xml", parts["content.xml"])
        zf.writestr("mimetype", parts["mimetype"], compress_type=zipfile.ZIP_STORED)
    assert any("first" in p for p in problems(out.getvalue()))


def test_an_unknown_mimetype_is_a_problem():
    parts = read_parts(a_text_package())
    parts["mimetype"] = b"application/zip"
    assert any("media type" in p for p in problems(write_parts(parts)))


def test_a_manifest_that_disagrees_with_the_mimetype_is_a_problem():
    parts = read_parts(a_text_package())
    parts["META-INF/manifest.xml"] = parts["META-INF/manifest.xml"].replace(
        MIME["text"].encode(), MIME["presentation"].encode()
    )
    assert any("manifest" in p and "media type" in p for p in problems(write_parts(parts)))


def test_a_part_missing_from_the_manifest_is_a_problem():
    parts = read_parts(a_text_package())
    parts["Pictures/loose.png"] = b"x"
    assert any("Pictures/loose.png" in p and "manifest" in p for p in problems(write_parts(parts)))


def test_a_manifest_entry_without_a_part_is_a_problem():
    parts = read_parts(a_text_package())
    del parts["styles.xml"]
    assert any("styles.xml" in p for p in problems(write_parts(parts)))


def test_a_part_that_is_not_well_formed_is_a_problem():
    parts = read_parts(a_text_package())
    parts["content.xml"] = b"<a><b></a>"
    assert any("content.xml" in p and "well-formed" in p for p in problems(write_parts(parts)))


def test_a_content_part_without_a_version_is_a_problem():
    parts = read_parts(a_text_package())
    parts["content.xml"] = CONTENT.replace(b' office:version="1.3"', b"")
    assert any("content.xml" in p and "version" in p for p in problems(write_parts(parts)))


def test_a_directory_entry_needs_no_manifest_line_of_its_own_but_may_have_one():
    parts = read_parts(a_text_package(**{"Configurations2/": (b"", "application/vnd.sun.xml.ui.configuration")}))
    assert problems(write_parts(parts)) == []
