"""workbook_to_xlsx and add_pivot_table: a real workbook exported, then a pivot table added additively."""

from __future__ import annotations

import zipfile
from io import BytesIO

import openpyxl
import pytest

from claudia_computes import Sheet, SheetId, WorkbookModel
from claudia_computes_io import add_pivot_table, workbook_to_xlsx

ROWS = [
    ("North", "Widget", 100),
    ("North", "Gadget", 150),
    ("South", "Widget", 200),
    ("South", "Gadget", 120),
    ("East", "Widget", 130),
    ("West", "Gadget", 140),
]


def workbook_with_data() -> WorkbookModel:
    model = WorkbookModel()
    sheet = Sheet(SheetId("s1"), "Data")
    model.sheets[sheet.id] = sheet
    sheet.cells[(0, 0)] = {"t": "text", "v": "Region"}
    sheet.cells[(0, 1)] = {"t": "text", "v": "Product"}
    sheet.cells[(0, 2)] = {"t": "text", "v": "Amount"}
    for r, (region, product, amount) in enumerate(ROWS, start=1):
        sheet.cells[(r, 0)] = {"t": "text", "v": region}
        sheet.cells[(r, 1)] = {"t": "text", "v": product}
        sheet.cells[(r, 2)] = {"t": "int", "v": amount}
    return model


def test_cells_and_a_formula_survive_the_base_export():
    model = workbook_with_data()
    sheet = model.sheets[SheetId("s1")]
    sheet.cells[(7, 0)] = {"t": "formula", "v": "=SUM(C2:C7)"}
    wb = openpyxl.load_workbook(BytesIO(workbook_to_xlsx(model)))
    ws = wb["Data"]
    assert ws["A1"].value == "Region"
    assert ws["C2"].value == 100
    assert ws["A8"].value == "=SUM(C2:C7)"


def test_several_sheets_keep_their_names_and_order():
    model = workbook_with_data()
    model.sheets[SheetId("s2")] = Sheet(SheetId("s2"), "Notes")
    wb = openpyxl.load_workbook(BytesIO(workbook_to_xlsx(model)))
    assert wb.sheetnames == ["Data", "Notes"]


def test_an_empty_workbook_still_exports_a_sheet():
    wb = openpyxl.load_workbook(BytesIO(workbook_to_xlsx(WorkbookModel())))
    assert wb.sheetnames == ["Sheet1"]


def test_add_pivot_table_builds_the_three_parts_and_wires_them_up():
    base = workbook_to_xlsx(workbook_with_data())
    out = add_pivot_table(base, source_sheet="Data", source_range="A1:C7", row_field="Region", value_field="Amount")

    with zipfile.ZipFile(BytesIO(out)) as z:
        names = set(z.namelist())
        assert "xl/pivotCache/pivotCacheDefinition1.xml" in names
        assert "xl/pivotCache/pivotCacheRecords1.xml" in names
        assert "xl/pivotTables/pivotTable1.xml" in names
        records = z.read("xl/pivotCache/pivotCacheRecords1.xml").decode("utf-8")
        assert 'count="6"' in records  # six data rows in ROWS


def test_add_pivot_table_survives_an_openpyxl_round_trip():
    base = workbook_to_xlsx(workbook_with_data())
    out = add_pivot_table(base, source_sheet="Data", source_range="A1:C7", row_field="Region", value_field="Amount")

    wb = openpyxl.load_workbook(BytesIO(out))
    resaved = BytesIO()
    wb.save(resaved)

    with zipfile.ZipFile(resaved) as z:
        names = set(z.namelist())
    assert "xl/pivotCache/pivotCacheDefinition1.xml" in names
    assert "xl/pivotTables/pivotTable1.xml" in names


def test_add_pivot_table_refuses_an_unknown_field():
    base = workbook_to_xlsx(workbook_with_data())
    with pytest.raises(ValueError, match="Region"):
        add_pivot_table(base, source_sheet="Data", source_range="A1:C7", row_field="Country", value_field="Amount")
