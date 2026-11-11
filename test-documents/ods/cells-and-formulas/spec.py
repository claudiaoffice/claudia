"""A file written by LibreOffice itself (converted from the xlsx fixture of the same name, then checked in): its
cells and the ``SUM`` formula (written as ``of:=SUM([.C2:.C7])``) import as typed cell contents, the formula
translated to Excel text and its cached value read back through the model's own calculator. Editing one amount
leaves every other cell alone and the formula keeps its ``table:formula``, only its cached value changes (D413)."""

from __future__ import annotations

from claudia_computes import SheetId, WorkbookModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case


def import_checks(model: WorkbookModel) -> None:
    assert [sheet.name for sheet in model.sheets.values()] == ["Data", "Notes"]
    data = model.sheets[SheetId("s1")]
    assert data.cells[(0, 0)] == {"t": "text", "v": "Region"}
    assert data.cells[(1, 2)] == {"t": "int", "v": 100}
    assert data.cells[(7, 2)] == {"t": "formula", "v": "=SUM(C2:C7)"}
    assert model.value(SheetId("s1"), 7, 2) == 840
    assert model.sheets[SheetId("s2")].cells[(0, 0)] == {"t": "text", "v": "Six regions, two products."}


def modify(model: WorkbookModel) -> WorkbookModel:
    model.store(model.sheets[SheetId("s1")], 1, 2, {"t": "int", "v": 999})
    return model


def after_checks(model: WorkbookModel) -> None:
    data = model.sheets[SheetId("s1")]
    assert data.cells[(1, 2)] == {"t": "int", "v": 999}
    assert data.cells[(7, 2)] == {"t": "formula", "v": "=SUM(C2:C7)"}
    assert model.value(SheetId("s1"), 7, 2) == 1739


def formula_is_kept(original: bytes, edited: bytes) -> None:
    before = read_parts(original)["content.xml"].decode()
    after = read_parts(edited)["content.xml"].decode()
    assert "SUM([.C2:.C7])" in before and "SUM([.C2:.C7])" in after
    assert 'office:value="1739"' in after and 'office:value="840"' not in after


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["styles.xml", "META-INF/manifest.xml"],
    preserve_elements=formula_is_kept,
)
