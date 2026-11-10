"""A chart lives in its own package parts (``xl/charts/chart1.xml``, ``xl/drawings/drawing1.xml``), referenced
from a sheet the edit never touches at all -- xlsx's own analogue of pptx's beyond-claudia/image fixture, not its
table: unlike a pptx table (embedded directly in the slide part it shares with the edited text box), a chart's
definition is never inline in any worksheet's own XML, so this is a whole-part guarantee either way. openpyxl has
no object model for a pivot chart or a cell's content behind one -- ``xlsx_to_workbook`` cannot see it, same as a
picture is invisible to ``pptx_to_slides`` (D219)."""

from __future__ import annotations

from claudia_computes import SheetId, WorkbookModel
from claudia_test_documents.case import Case


def import_checks(model: WorkbookModel) -> None:
    assert [sheet.name for sheet in model.sheets.values()] == ["Data", "Chart"]
    data = model.sheets[SheetId("s1")]
    assert data.cells[(0, 0)] == {"t": "text", "v": "Region"}
    assert data.cells[(1, 1)] == {"t": "int", "v": 100}
    assert model.sheets[SheetId("s2")].cells == {}  # the chart itself is not modeled at all


def modify(model: WorkbookModel) -> WorkbookModel:
    sheet = model.sheets[SheetId("s1")]
    model.store(sheet, 1, 1, {"t": "int", "v": 999})  # North's amount, the chart's own source data
    return model


def after_checks(model: WorkbookModel) -> None:
    assert model.sheets[SheetId("s1")].cells[(1, 1)] == {"t": "int", "v": 999}
    assert model.sheets[SheetId("s2")].cells == {}


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["xl/charts/chart1.xml", "xl/drawings/drawing1.xml"],
)
