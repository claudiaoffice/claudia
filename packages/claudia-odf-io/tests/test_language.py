"""How an OpenDocument file says its language (D454, D461): ``fo:language``, ``fo:script`` and ``fo:country`` of the
default paragraph style; written, read back and changed in a kept file."""

from __future__ import annotations

import pytest
from lxml import etree

from claudia_odf_io import (
    NO_LANGUAGE,
    NS,
    OdfError,
    XmlPart,
    default_style_xml,
    language_from_parts,
    parts_of_language,
    patch_language,
    read_language,
)

STYLES = (
    '<office:document-styles xmlns:office="{office}" xmlns:style="{style}" xmlns:fo="{fo}">'
    "<office:styles>{default}</office:styles></office:document-styles>"
)


def styles(default: str = "") -> bytes:
    return STYLES.format(office=NS["office"], style=NS["style"], fo=NS["fo"], default=default).encode()


@pytest.mark.parametrize("tag", ["de", "de-AT", "sr-Latn-RS", "es-419"])
def test_a_tag_goes_through_the_three_parts_and_back(tag):
    assert language_from_parts(*parts_of_language(tag)) == tag


def test_no_language_is_what_libreoffice_writes_for_none():
    assert parts_of_language(None) == (NO_LANGUAGE[0], None, None)
    assert language_from_parts("zxx", None, "none") is None
    assert language_from_parts("", None, None) is None
    assert language_from_parts("x", None, None) is None  # not a tag


def test_the_default_style_of_a_language_is_read_back():
    assert default_style_xml(None) == ""
    assert read_language(etree.fromstring(styles(default_style_xml("de-CH")))) == "de-CH"
    assert read_language(etree.fromstring(styles())) is None
    assert read_language(None) is None


def test_a_language_is_given_changed_and_taken_away():
    part = XmlPart(styles(default_style_xml("de")))
    assert patch_language(part, "de", "en-GB") is True
    assert read_language(etree.fromstring(part.result())) == "en-GB"
    part = XmlPart(styles(default_style_xml("sr-Latn-RS")))
    assert patch_language(part, "sr-Latn-RS", "ru") is True
    assert read_language(etree.fromstring(part.result())) == "ru"
    assert patch_language(part, "ru", "ru") is False


def test_a_file_with_no_default_style_is_given_one():
    part = XmlPart(styles())
    assert patch_language(part, None, "it") is True
    assert read_language(etree.fromstring(part.result())) == "it"
    assert patch_language(XmlPart(styles()), None, None) is False


def test_a_file_without_styles_cannot_be_given_a_language():
    bare = XmlPart(f'<office:document-styles xmlns:office="{NS["office"]}"/>'.encode())
    with pytest.raises(OdfError):
        patch_language(bare, None, "de")
