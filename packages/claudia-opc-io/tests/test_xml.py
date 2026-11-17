"""parse_xml reads the XML of a package that anybody may have written (SEC-15): no entity is ever expanded."""

from __future__ import annotations

import pytest
from lxml import etree

from claudia_opc_io import parse_xml

BILLION_LAUGHS = (
    b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
    + b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
    + b'<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">'
    + b'<!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">]><lolz>&lol4;</lolz>'
)


def test_ordinary_xml_is_read():
    root = parse_xml(b'<a xmlns="urn:x"><b n="1">text</b></a>')
    assert root.tag == "{urn:x}a"
    assert root[0].text == "text"


def test_an_internal_entity_is_not_expanded():
    root = parse_xml(b'<!DOCTYPE a [<!ENTITY x "expanded">]><a>&x;</a>')
    assert "expanded" not in "".join(root.itertext())


def test_a_billion_laughs_document_does_not_grow():
    root = parse_xml(BILLION_LAUGHS)
    assert len("".join(root.itertext())) < 100


def test_an_external_entity_does_not_read_a_file(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("the secret")
    root = parse_xml(f'<!DOCTYPE a [<!ENTITY x SYSTEM "{secret.as_uri()}">]><a>&x;</a>'.encode())
    assert "the secret" not in "".join(root.itertext())


def test_broken_xml_raises_what_lxml_raises():
    with pytest.raises(etree.XMLSyntaxError):
        parse_xml(b"<a>")


def test_a_very_deep_document_is_refused_rather_than_read():
    deep = b"<a>" * 5000 + b"</a>" * 5000
    with pytest.raises(etree.XMLSyntaxError):
        parse_xml(deep)
