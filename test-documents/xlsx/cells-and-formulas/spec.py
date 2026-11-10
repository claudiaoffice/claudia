"""A worksheet's cells and a formula import as a Sheet's typed cell contents, with the formula's computed value
read back correctly through the model's own calculator; editing one cell leaves the formula -- which recalculates
against the new value -- and every other cell alone (D220, the xlsx analogue of pptx's shapes-and-text and docx's
heading-styles)."""

from __future__ import annotations

from claudia_computes import SheetId, WorkbookModel
from claudia_test_documents.case import Case


def import_checks(model: WorkbookModel) -> None:
    assert [sheet.name for sheet in model.sheets.values()] == ["Data", "Notes"]
    data = model.sheets[SheetId("s1")]
    assert data.cells[(0, 0)] == {"t": "text", "v": "Region"}
    assert data.cells[(1, 2)] == {"t": "int", "v": 100}
    assert data.cells[(7, 0)] == {"t": "text", "v": "Total"}
    assert data.cells[(7, 2)] == {"t": "formula", "v": "=SUM(C2:C7)"}
    assert model.value(SheetId("s1"), 7, 2) == 840  # 100 + 150 + 200 + 120 + 130 + 140
    notes = model.sheets[SheetId("s2")]
    assert notes.cells[(0, 0)] == {"t": "text", "v": "Six regions, two products."}


def modify(model: WorkbookModel) -> WorkbookModel:
    sheet = model.sheets[SheetId("s1")]
    model.store(sheet, 1, 2, {"t": "int", "v": 999})  # North/Widget's amount, 100 -> 999
    return model


def after_checks(model: WorkbookModel) -> None:
    data = model.sheets[SheetId("s1")]
    assert data.cells[(1, 2)] == {"t": "int", "v": 999}
    assert data.cells[(0, 0)] == {"t": "text", "v": "Region"}  # untouched
    assert model.value(SheetId("s1"), 7, 2) == 1739  # the formula recalculates with the new amount
    notes = model.sheets[SheetId("s2")]
    assert notes.cells[(0, 0)] == {"t": "text", "v": "Six regions, two products."}  # the other sheet is untouched


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks)
