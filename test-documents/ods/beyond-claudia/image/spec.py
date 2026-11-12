"""A picture (LibreOffice-written) in a part of its own (``Pictures/…``), placed by a frame on a sheet the edit
never touches. Editing a cell of the first sheet leaves the picture part and the manifest as they were (D413)."""

from __future__ import annotations

from claudia_computes import SheetId, WorkbookModel
from claudia_test_documents.case import Case

PICTURE = "Pictures/10000000000000100000001083524B19.png"


def import_checks(model: WorkbookModel) -> None:
    assert [sheet.name for sheet in model.sheets.values()] == ["Data", "Pics"]
    assert model.sheets[SheetId("s1")].cells == {(0, 0): {"t": "text", "v": "North"}}
    assert model.sheets[SheetId("s2")].cells == {}


def modify(model: WorkbookModel) -> WorkbookModel:
    model.store(model.sheets[SheetId("s1")], 0, 0, {"t": "text", "v": "Northwest"})
    return model


def after_checks(model: WorkbookModel) -> None:
    assert model.sheets[SheetId("s1")].cells == {(0, 0): {"t": "text", "v": "Northwest"}}
    assert model.sheets[SheetId("s2")].cells == {}


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=[PICTURE, "META-INF/manifest.xml"],
)
