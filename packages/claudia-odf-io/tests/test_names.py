"""Names in OpenDocument: the namespaces, and how a style's name is spelled."""

from __future__ import annotations

import pytest

from claudia_odf_io import decode_style_name, encode_style_name, local_name, qname


def test_a_prefixed_name_becomes_a_clark_name():
    assert qname("text:p") == "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"


def test_an_unknown_prefix_is_an_error_not_a_guess():
    with pytest.raises(KeyError):
        qname("nope:p")


def test_local_name_is_the_part_after_the_namespace():
    assert local_name(qname("text:h")) == "h"
    assert local_name("plain") == "plain"


@pytest.mark.parametrize(
    ("display", "encoded"),
    [
        ("Heading 1", "Heading_20_1"),  # what LibreOffice writes
        ("Standard", "Standard"),
        ("Quotations", "Quotations"),
        ("Remark", "Remark"),
        ("My style (new)", "My_20_style_20__28_new_29_"),
        ("1st", "_31_st"),  # a name must not start with a digit
        ("Größe", "Größe"),  # letters of any script are fine
    ],
)
def test_style_names_are_spelled_the_way_odf_producers_spell_them(display, encoded):
    assert encode_style_name(display) == encoded


@pytest.mark.parametrize("display", ["Heading 1", "Standard", "My style (new)", "1st", "a_b", "x.y-z", "Größe", "a\tb"])
def test_decoding_undoes_encoding(display):
    assert decode_style_name(encode_style_name(display)) == display


def test_decoding_reads_the_short_and_the_long_escape():
    assert decode_style_name("Heading_20_1") == "Heading 1"
    assert decode_style_name("A_x0020_B") == "A B"  # the four-digit form some producers use


def test_a_lookalike_that_is_not_an_escape_is_left_alone():
    assert decode_style_name("a_zz_b") == "a_zz_b"
