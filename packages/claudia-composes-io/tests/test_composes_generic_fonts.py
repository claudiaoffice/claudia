"""A style whose font is a generic family is written into a docx or an odt as the font Claudia shows it with, from
the shared sample of the stand-ins (``test-documents/xlsx/stand-in-fonts``, CODE-42): before, ``serif`` became
Liberation Serif, which no server shows."""

import json
from io import BytesIO
from pathlib import Path

import pytest
from claudia_composes_io import text_to_docx, text_to_odt
from docx import Document
from lxml import etree

from claudia_composes import Block, TextModel
from claudia_core import StyleDef
from claudia_odf_io import NS
from claudia_opc_io import read_parts

SAMPLE = Path(__file__).resolve().parents[3] / "test-documents" / "stand-in-fonts.json"
GENERIC_FAMILIES = json.loads(SAMPLE.read_text(encoding="utf-8"))["generic_families"]


def with_font(css_family: str) -> TextModel:
    model = TextModel([Block("b1", "callout", "words")])
    model.styles.add(StyleDef("callout", "Call out", "", "body", {"font-family": css_family}))
    return model


@pytest.mark.parametrize("entry", GENERIC_FAMILIES, ids=lambda e: e["css"])
def test_a_docx_names_the_font_a_generic_family_is_shown_with(entry):
    data = text_to_docx(with_font(entry["css"]))
    assert Document(BytesIO(data)).styles["Call out"].font.name == entry["font"]


@pytest.mark.parametrize("entry", GENERIC_FAMILIES, ids=lambda e: e["css"])
def test_an_odt_names_the_font_a_generic_family_is_shown_with(entry):
    styles = etree.fromstring(read_parts(text_to_odt(with_font(entry["css"])))["styles.xml"])
    text = styles.find("office:styles/style:style[@style:name='Call_20_out']/style:text-properties", NS)
    assert text.get(f"{{{NS['fo']}}}font-family").strip("'") == entry["font"]
