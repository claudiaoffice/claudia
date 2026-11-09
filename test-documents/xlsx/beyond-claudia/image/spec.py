"""A picture lives in its own package part (``xl/media/image1.png``), on a sheet the edit never touches at all --
the mechanic D204's implementation note calls out as the one that actually needs the touched-sheets-only reconcile
strategy: openpyxl mutates an embedded picture's drawing XML on ANY load+resave, even with zero related edits, so
only owning the edited sheet's own worksheet part (never the whole package) lets this picture's parts survive
byte-for-byte identical. ``xlsx_to_workbook`` has no model for a picture at all, same as a picture is invisible to
``pptx_to_slides`` (D179) and a table to ``docx_to_text`` (D177)."""

from __future__ import annotations

from claudia_computes import SheetId, WorkbookModel
from claudia_test_documents.case import Case


def import_checks(model: WorkbookModel) -> None:
    assert [sheet.name for sheet in model.sheets.values()] == ["Data", "Pics"]
    assert model.sheets[SheetId("s1")].cells == {(0, 0): {"t": "text", "v": "North"}}
    assert model.sheets[SheetId("s2")].cells == {}  # the picture is not modeled at all


def modify(model: WorkbookModel) -> WorkbookModel:
    sheet = model.sheets[SheetId("s1")]
    model.store(sheet, 0, 0, {"t": "text", "v": "Northwest"})
    return model


def after_checks(model: WorkbookModel) -> None:
    assert model.sheets[SheetId("s1")].cells == {(0, 0): {"t": "text", "v": "Northwest"}}
    assert model.sheets[SheetId("s2")].cells == {}


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["xl/media/image1.png", "xl/drawings/drawing1.xml"],
)
