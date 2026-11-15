"""Two widths and two heights that somebody set, a column with a fill, a column nobody sized and a data validation
(written the way Excel lays them out). The model has the sizes; a width and a height changed in Claudia are patched
into the file, and the other column keeps its width and fill and the validation stays (D458)."""

from __future__ import annotations

from claudia_computes import SheetId, WorkbookModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

PLAN = SheetId("s1")


def import_checks(model: WorkbookModel) -> None:
    sheet = model.sheets[PLAN]
    assert sheet.col_widths == {1: 140, 2: 84}
    assert sheet.row_heights == {0: 40, 2: 60}


def modify(model: WorkbookModel) -> WorkbookModel:
    sheet = model.sheets[PLAN]
    sheet.col_widths[1] = 200
    sheet.row_heights[1] = 50
    model.store(sheet, 3, 0, {"t": "text", "v": "Test"})
    return model


def after_checks(model: WorkbookModel) -> None:
    sheet = model.sheets[PLAN]
    assert sheet.col_widths == {1: 200, 2: 84}
    assert sheet.row_heights == {0: 40, 1: 50, 2: 60}


def others_stay(original: bytes, edited: bytes) -> None:
    sheet = read_parts(edited)["xl/worksheets/sheet1.xml"].decode()
    assert "<dataValidation " in sheet, "the validation stays"
    column = next(part for part in sheet.split("<col ") if 'min="3"' in part)
    assert 'width="12"' in column and "style=" in column, "the column nobody resized keeps its width and fill"


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_elements=others_stay,
)
