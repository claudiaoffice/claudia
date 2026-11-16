"""The fonts of a text's styles survive a file written from nothing (E3.13, bug 1), on the shared sample: what
``docx_to_text`` and ``odt_to_text`` read is what ``text_to_docx`` and ``text_to_odt`` write."""

import json
from pathlib import Path

import pytest
from claudia_composes_io import (
    docx_import_losses,
    docx_to_text,
    odt_import_losses,
    odt_to_text,
    text_to_docx,
    text_to_odt,
)

LIBRARY = Path(__file__).resolve().parents[3] / "test-documents"
STYLES = [
    entry["style"] for entry in json.loads((LIBRARY / "stand-in-fonts.json").read_text(encoding="utf-8"))["text_styles"]
]
FORMATS = {
    "docx": (docx_to_text, text_to_docx, docx_import_losses),
    "odt": (odt_to_text, text_to_odt, odt_import_losses),
}


def fonts(model) -> dict[str, str]:
    return {style: model.styles.computed(style)["font-family"] for style in STYLES}


@pytest.mark.parametrize("fmt", FORMATS)
def test_the_fonts_of_the_sample_come_back_from_a_file_written_from_nothing(fmt):
    read, write, _ = FORMATS[fmt]
    model = read((LIBRARY / fmt / "stand-in-fonts" / f"source.{fmt}").read_bytes())
    assert fonts(read(write(model))) == fonts(model)


@pytest.mark.parametrize("fmt", FORMATS)
def test_the_fonts_of_the_sample_are_no_loss(fmt):
    _, _, losses = FORMATS[fmt]
    assert losses((LIBRARY / fmt / "stand-in-fonts" / f"source.{fmt}").read_bytes()) == ()
