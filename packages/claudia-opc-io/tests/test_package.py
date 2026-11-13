"""read_parts/write_parts: a zip package as a plain dict of its parts, and back."""

from __future__ import annotations

import zipfile
from io import BytesIO

from claudia_opc_io import read_parts, write_parts


def a_zip(parts: dict[str, bytes]) -> bytes:
    return write_parts(parts)


def test_read_parts_returns_every_part_by_name():
    zip_bytes = a_zip({"[Content_Types].xml": b"<a/>", "word/document.xml": b"<b/>"})
    assert read_parts(zip_bytes) == {"[Content_Types].xml": b"<a/>", "word/document.xml": b"<b/>"}


def test_write_then_read_round_trips_exactly():
    parts = {"[Content_Types].xml": b"<a/>", "word/document.xml": b"<b/>", "word/styles.xml": b"<c/>"}
    assert read_parts(write_parts(parts)) == parts


def test_part_names_keep_their_order():
    parts = {"[Content_Types].xml": b"1", "word/document.xml": b"2", "word/styles.xml": b"3"}
    with_zip = write_parts(parts)
    with zipfile.ZipFile(BytesIO(with_zip)) as zf:
        assert zf.namelist() == list(parts)


# -- the ``mimetype`` rule of OpenDocument (and EPUB): first in the archive, stored, so that a program can read the
# -- type of a file at a fixed place in it, without unzipping (ODF 1.3 part 3, 3.3). `file` and the type sniffing of
# -- browsers, file managers and upload filters depend on it; LibreOffice itself does not.
def test_a_mimetype_part_is_written_first_even_when_listed_later():
    data = write_parts({"content.xml": b"<a/>", "mimetype": b"application/vnd.oasis.opendocument.text"})
    with zipfile.ZipFile(BytesIO(data)) as zf:
        assert zf.namelist() == ["mimetype", "content.xml"]


def test_a_mimetype_part_is_stored_not_compressed_and_the_others_are_compressed():
    data = write_parts({"mimetype": b"application/vnd.oasis.opendocument.text", "content.xml": b"<a/>" * 50})
    with zipfile.ZipFile(BytesIO(data)) as zf:
        assert zf.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert zf.getinfo("content.xml").compress_type == zipfile.ZIP_DEFLATED


def test_a_mimetype_entry_starts_the_file_in_plain_view():
    # the bytes a sniffer reads: "PK", then the name at offset 30 and the type right behind it (no extra field)
    kind = b"application/vnd.oasis.opendocument.spreadsheet"
    data = write_parts({"content.xml": b"<a/>", "mimetype": kind})
    assert data[30:38] == b"mimetype"
    assert data[38 : 38 + len(kind)] == kind


def test_the_other_parts_keep_their_order_behind_mimetype():
    data = write_parts({"b": b"1", "mimetype": b"x", "a": b"2", "c": b"3"})
    with zipfile.ZipFile(BytesIO(data)) as zf:
        assert zf.namelist() == ["mimetype", "b", "a", "c"]


def test_a_package_without_mimetype_is_written_as_before():
    parts = {"[Content_Types].xml": b"<a/>", "word/document.xml": b"<b/>"}
    with zipfile.ZipFile(BytesIO(write_parts(parts))) as zf:
        assert all(info.compress_type == zipfile.ZIP_DEFLATED for info in zf.infolist())


def test_the_same_parts_always_give_the_same_bytes():
    parts = {"mimetype": b"x", "content.xml": b"<a/>"}
    assert write_parts(parts) == write_parts(parts)


def test_a_directory_entry_survives_a_round_trip():
    parts = {"mimetype": b"x", "Configurations2/toolbar/": b"", "content.xml": b"<a/>"}
    assert read_parts(write_parts(parts)) == parts
