"""The stand-ins (E3.13): the font of each generic family, the names that stand for one, the open fonts of the same
widths as the common office fonts, and the font a file names for a style (CODE-42)."""

import json
from pathlib import Path

import pytest

from claudia_core.stand_ins import GENERIC_ALIASES, GENERIC_FONTS, SAME_WIDTHS, css_family, file_font, generic_font

SAMPLE = Path(__file__).resolve().parents[3] / "test-documents" / "stand-in-fonts.json"
TABLE = json.loads(SAMPLE.read_text(encoding="utf-8"))
GENERIC_FAMILIES = TABLE["generic_families"]
FONTS = TABLE["fonts"]


@pytest.mark.parametrize("entry", GENERIC_FAMILIES, ids=lambda e: e["css"])
def test_a_file_names_the_font_a_generic_family_is_shown_with(entry):
    assert file_font(entry["css"]) == entry["font"]


def test_a_file_names_the_first_family_as_it_is_otherwise():
    assert file_font("Georgia, serif") == "Georgia"
    assert file_font("'Times New Roman', 'Liberation Serif', serif") == "Times New Roman"
    assert file_font(' ,  "Segoe UI" , sans-serif') == "Segoe UI"
    assert file_font("") is None and file_font(" , ") is None


def test_every_generic_name_stands_for_one_of_three_families():
    assert set(GENERIC_FONTS) == {"serif", "sans-serif", "monospace", "fallback"}
    assert set(GENERIC_ALIASES.values()) == {"serif", "sans-serif", "monospace"}
    assert {"serif", "sans-serif", "monospace", "system-ui"} <= set(GENERIC_ALIASES)
    assert generic_font("SYSTEM-UI") == GENERIC_FONTS["sans-serif"]
    assert generic_font("Arial") is None


def test_the_same_width_table_names_open_fonts_for_the_office_fonts():
    assert SAME_WIDTHS["Arial"] == "Arimo" and SAME_WIDTHS["Calibri"] == "Carlito"
    assert not set(SAME_WIDTHS) & set(GENERIC_ALIASES)


@pytest.mark.parametrize("entry", FONTS, ids=lambda e: e["family"])
def test_a_font_a_file_names_becomes_a_font_family_with_its_generic_family(entry):
    family = entry["family"]
    quoted = f"'{family}'" if " " in family else family
    assert css_family(family) == f"{quoted}, {entry['generic']}"


def test_a_font_name_is_quoted_unless_it_is_a_plain_word():
    assert css_family(" 'Gill Sans' ") == "'Gill Sans', sans-serif"
    assert css_family("MS-Mincho") == "MS-Mincho, sans-serif"
    assert css_family("ＭＳ明朝") == "'ＭＳ明朝', sans-serif"
    assert css_family("3Dumb") == "'3Dumb', sans-serif"
