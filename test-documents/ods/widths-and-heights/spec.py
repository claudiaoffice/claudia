"""A width and a height that somebody set, rows LibreOffice sizes by their content, columns left at its own width and a
validation, laid out the way LibreOffice does. The model has the sizes that were set; a width and a height changed in
Claudia are patched into the file (the run of rows and the run of columns are cut), and the validation stays (D458)."""

from __future__ import annotations

from claudia_computes import SheetId, WorkbookModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

PLAN = SheetId("s1")


def import_checks(model: WorkbookModel) -> None:
    sheet = model.sheets[PLAN]
    assert sheet.col_widths[0] == 170
    assert sheet.col_widths[1] == 85 and max(sheet.col_widths) == 255
    assert sheet.row_heights == {0: 53}


def modify(model: WorkbookModel) -> WorkbookModel:
    sheet = model.sheets[PLAN]
    sheet.col_widths[0] = 220
    sheet.row_heights[2] = 70
    model.store(sheet, 3, 0, {"t": "text", "v": "Test"})
    return model


def after_checks(model: WorkbookModel) -> None:
    sheet = model.sheets[PLAN]
    assert sheet.col_widths[0] == 220 and sheet.col_widths[1] == 85
    assert sheet.row_heights == {0: 53, 2: 70}


def others_stay(original: bytes, edited: bytes) -> None:
    content = read_parts(edited)["content.xml"].decode()
    assert 'table:name="val1"' in content, "the validation stays"
    assert 'style:column-width="2.258cm"' in content, "the file's own style of the other columns stays"


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["styles.xml", "META-INF/manifest.xml"],
    preserve_elements=others_stay,
)
