"""One cell per font that office files ask for most (E3.13), the shared sample of every test of the font stand-ins
(``test-documents/stand-in-fonts.json`` says which fonts and what a server shows them with).

A cell keeps the name of its font as the file says it, followed only by its generic family: the stand-in is chosen
where the document is shown (the catalogue, the layout library), never written into the document. The edit changes
one value; after export and import every cell still names its own font, so a file that came in with Arial goes out
with Arial."""

from __future__ import annotations

import json
from pathlib import Path

from claudia_computes import SheetId, WorkbookModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

FONTS = SheetId("s1")
EXPECTED = json.loads((Path(__file__).parents[2] / "stand-in-fonts.json").read_text(encoding="utf-8"))["fonts"]


def _quoted(family: str) -> str:
    return f"'{family}'" if " " in family else family


def _stack(model: WorkbookModel, row: int) -> str:
    style_id = model.sheets[FONTS].cell_styles.style_at(row, 0, "words")[0]
    return model.styles.get(style_id).css["font-family"]


def import_checks(model: WorkbookModel) -> None:
    for row, entry in enumerate(EXPECTED):
        assert _stack(model, row) == f"{_quoted(entry['family'])}, {entry['generic']}", entry["family"]


def modify(model: WorkbookModel) -> WorkbookModel:
    model.store(model.sheets[FONTS], 0, 1, {"t": "int", "v": 42})
    return model


def after_checks(model: WorkbookModel) -> None:
    import_checks(model)
    assert model.sheets[FONTS].cells[(0, 1)] == {"t": "int", "v": 42}


def every_font_is_named_in_the_file(exported: bytes) -> None:
    styles = read_parts(exported)["xl/styles.xml"].decode()
    for entry in EXPECTED:
        assert f'<name val="{entry["family"]}"/>' in styles, entry["family"]
    for stand_in in {e["stand_in"] for e in EXPECTED} - {e["family"] for e in EXPECTED} - {None}:
        assert f'"{stand_in}"' not in styles, f"{stand_in} is a stand-in, never written into the file"


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    export_checks=every_font_is_named_in_the_file,
)
