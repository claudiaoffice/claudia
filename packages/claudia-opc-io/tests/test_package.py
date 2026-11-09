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
