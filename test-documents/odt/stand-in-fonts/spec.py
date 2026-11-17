"""The styles of a text with the fonts odt files set (E3.13, bug 1; ``test-documents/stand-in-fonts.json``): each
style of the model takes the font its style in the file has, from wherever the file says it (body text from the
default style, the others from a font face or ``fo:font-family``), followed by its generic family. No stand-in
is written into the document. An edit to the body text keeps every font, and the file keeps naming them."""

from __future__ import annotations

import json
from pathlib import Path

from claudia_composes import Run, TextModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

TABLE = json.loads((Path(__file__).parents[2] / "stand-in-fonts.json").read_text(encoding="utf-8"))
GENERIC = {entry["family"]: entry["generic"] for entry in TABLE["fonts"]}
STAND_INS = {e["stand_in"] for e in TABLE["fonts"]} - {e["family"] for e in TABLE["fonts"]} - {None}


def _stack(family: str) -> str:
    return f"{chr(39) + family + chr(39) if ' ' in family else family}, {GENERIC[family]}"


def import_checks(model: TextModel) -> None:
    for entry in TABLE["text_styles"]:
        assert model.styles.computed(entry["style"])["font-family"] == _stack(entry["family"]), entry


def modify(model: TextModel) -> TextModel:
    body = next(block for block in model.blocks if block.style == "body")
    model.insert(body.id, len(body.text), " (edited)", [Run(len(" (edited)"), None)])
    return model


def after_checks(model: TextModel) -> None:
    import_checks(model)
    assert any(block.text.endswith("(edited)") for block in model.blocks)


def no_stand_in_is_written(exported: bytes) -> None:
    written = b"".join(read_parts(exported).values()).decode("utf-8", "ignore")
    for stand_in in STAND_INS:
        assert stand_in not in written, f"{stand_in} is a stand-in, never written into the file"


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks, export_checks=no_stand_in_is_written)
