"""check_package and read_parts refuse a zip that would exhaust the machine reading it (SEC-15).

A "zip bomb" is a few kilobytes on disk that unpack to gigabytes. The sizes of every part are in the archive's
directory, so a package is judged before one byte of it is unpacked.
"""

from __future__ import annotations

import os
import zipfile
from io import BytesIO

import pytest

from claudia_opc_io import DEFAULT_LIMITS, PackageLimits, PackageRefused, check_package, read_parts, write_parts

MIB = 1024 * 1024


def a_zip(parts: dict[str, bytes]) -> bytes:
    return write_parts(parts)


def test_an_ordinary_package_is_let_through():
    data = a_zip({"[Content_Types].xml": b"<a/>", "word/document.xml": b"<b>" + b"words " * 1000 + b"</b>"})
    check_package(data)
    assert read_parts(data)["[Content_Types].xml"] == b"<a/>"


def test_a_part_larger_than_the_limit_is_refused_by_its_declared_size():
    data = a_zip({"big.xml": bytes(5 * MIB)})  # five MiB of zeros: a few kilobytes on disk
    assert len(data) < 100 * 1024
    with pytest.raises(PackageRefused, match=r"big\.xml"):
        check_package(data, PackageLimits(max_part_bytes=1 * MIB))


def test_a_package_whose_parts_together_unpack_to_too_much_is_refused():
    data = a_zip({f"part{i}.xml": bytes(1 * MIB) for i in range(4)})
    with pytest.raises(PackageRefused, match="together"):
        check_package(data, PackageLimits(max_total_bytes=3 * MIB, max_ratio=None))


def test_a_package_with_too_many_parts_is_refused():
    data = a_zip({f"p{i}.xml": b"<a/>" for i in range(20)})
    with pytest.raises(PackageRefused, match="20 parts"):
        check_package(data, PackageLimits(max_members=10))


def test_a_package_that_unpacks_to_far_more_than_it_weighs_is_refused():
    data = a_zip({"zeros.xml": bytes(8 * MIB)})
    with pytest.raises(PackageRefused, match="compress"):
        check_package(data, PackageLimits(max_ratio=50, ratio_from_bytes=1 * MIB))


def test_the_ratio_is_not_judged_for_a_small_package():
    data = a_zip({"zeros.xml": bytes(20_000)})  # 20 KB of zeros compresses a hundredfold, and is harmless
    check_package(data, PackageLimits(max_ratio=50, ratio_from_bytes=1 * MIB))


def test_read_parts_judges_the_package_before_it_unpacks_anything(monkeypatch):
    data = a_zip({"zeros.xml": bytes(5 * MIB)})

    def unpacking(self, name, *_unused):
        raise AssertionError("a part was unpacked")

    monkeypatch.setattr(zipfile.ZipFile, "read", unpacking)
    with pytest.raises(PackageRefused):
        read_parts(data, PackageLimits(max_part_bytes=1 * MIB))


def test_the_default_limits_let_a_large_real_document_through():
    """A deck of full-resolution photographs is tens of MiB: the defaults are for bombs, not for such files."""
    data = a_zip({"ppt/media/photo.png": os.urandom(40 * MIB)})
    check_package(data, DEFAULT_LIMITS)


def test_the_limits_say_what_they_are_in_the_message():
    data = a_zip({"big.xml": bytes(5 * MIB)})
    with pytest.raises(PackageRefused) as refused:
        check_package(data, PackageLimits(max_part_bytes=1 * MIB))
    assert "5 MiB" in str(refused.value) and "1 MiB" in str(refused.value)


def test_a_file_that_is_not_a_zip_is_left_for_the_reader_to_name():
    with pytest.raises(zipfile.BadZipFile):
        check_package(b"this is not a zip")


def test_a_directory_entry_costs_nothing():
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for i in range(5):
            archive.writestr(f"dir{i}/", b"")
    check_package(out.getvalue(), PackageLimits(max_members=3))


def test_limits_must_be_positive():
    with pytest.raises(ValueError, match="positive"):
        PackageLimits(max_members=0)
