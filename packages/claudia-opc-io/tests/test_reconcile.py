"""reconcile: restore whatever a format library's save() was not asked to touch, from the original bytes."""

from __future__ import annotations

from claudia_opc_io import owns, read_parts, reconcile, write_parts


def test_an_owned_part_keeps_the_regenerated_version():
    original = write_parts({"word/document.xml": b"old text"})
    regenerated = write_parts({"word/document.xml": b"new text"})
    out = reconcile(original, regenerated, owns(["word/document.xml"]))
    assert read_parts(out) == {"word/document.xml": b"new text"}


def test_an_unowned_part_is_restored_even_though_the_library_rewrote_it():
    # A library save() regenerates the whole package: `styles.xml` here changed even though nothing asked it to
    # (the same failure mode openpyxl's own save() showed for pivot tables). Reconcile must undo that.
    original = write_parts({"word/document.xml": b"old text", "word/styles.xml": b"original styles"})
    regenerated = write_parts({"word/document.xml": b"new text", "word/styles.xml": b"regenerated styles"})
    out = reconcile(original, regenerated, owns(["word/document.xml"]))
    assert read_parts(out) == {"word/document.xml": b"new text", "word/styles.xml": b"original styles"}


def test_an_unowned_part_the_library_dropped_is_restored_too():
    original = write_parts({"word/document.xml": b"text", "word/media/image1.png": b"\x89PNG..."})
    regenerated = write_parts({"word/document.xml": b"text"})  # the library's save() silently lost the image
    out = reconcile(original, regenerated, owns(["word/document.xml"]))
    assert read_parts(out)["word/media/image1.png"] == b"\x89PNG..."


def test_a_part_only_the_regenerated_package_has_is_kept():
    original = write_parts({"word/document.xml": b"text"})
    regenerated = write_parts({"word/document.xml": b"text", "docProps/app.xml": b"brand new part"})
    out = reconcile(original, regenerated, owns(["word/document.xml"]))
    assert read_parts(out)["docProps/app.xml"] == b"brand new part"


def test_owns_is_a_simple_membership_test():
    test = owns(["a", "b"])
    assert test("a") is True
    assert test("c") is False
