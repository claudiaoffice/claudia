"""A cell style whose font is a generic family is written into an xlsx or an ods as the font Claudia shows it with,
from the shared sample of the stand-ins (``test-documents/xlsx/stand-in-fonts``, CODE-42): before, the file named the
font ``serif`` or ``system-ui``, which no office program has."""

import json
from pathlib import Path

import pytest
from claudia_computes_io import workbook_to_ods, workbook_to_xlsx

from claudia_computes import WorkbookModel
from claudia_opc_io import read_parts

SAMPLE = Path(__file__).resolve().parents[3] / "test-documents" / "stand-in-fonts.json"
GENERIC_FAMILIES = json.loads(SAMPLE.read_text(encoding="utf-8"))["generic_families"]


def with_font(css_family: str) -> WorkbookModel:
    model = WorkbookModel.empty()
    model.styles.set_css("body-text", {**model.styles.get("body-text").css, "font-family": css_family})
    return model


@pytest.mark.parametrize("entry", GENERIC_FAMILIES, ids=lambda e: e["css"])
def test_an_xlsx_names_the_font_a_generic_family_is_shown_with(entry):
    styles = read_parts(workbook_to_xlsx(with_font(entry["css"])))["xl/styles.xml"].decode()
    assert f'<name val="{entry["font"]}"/>' in styles


@pytest.mark.parametrize("entry", GENERIC_FAMILIES, ids=lambda e: e["css"])
def test_an_ods_names_the_font_a_generic_family_is_shown_with(entry):
    written = read_parts(workbook_to_ods(with_font(entry["css"])))["styles.xml"].decode()
    font = entry["font"]
    assert f'fo:font-family="{font}"' in written or f"fo:font-family=\"'{font}'\"" in written
