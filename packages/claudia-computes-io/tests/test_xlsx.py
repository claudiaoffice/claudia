"""workbook_to_xlsx/xlsx_to_workbook/apply_edits_to_xlsx: a real workbook exported, reimported, and edited in
place; plus add_pivot_table, a pivot table added additively."""

from __future__ import annotations

import zipfile
from io import BytesIO

import openpyxl
import pytest
from claudia_computes_io import (
    UnsupportedEdit,
    add_pivot_table,
    apply_edits_to_xlsx,
    workbook_to_xlsx,
    xlsx_to_workbook,
)
from lxml import etree
from openpyxl.drawing.image import Image as XLImage
from PIL import Image

from claudia_computes import Sheet, SheetId, WorkbookModel

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


def test_cells_and_a_formula_survive_import():
    model = workbook_with_data()
    sheet = model.sheets[SheetId("s1")]
    sheet.cells[(7, 0)] = {"t": "formula", "v": "=SUM(C2:C7)"}
    reimported = xlsx_to_workbook(workbook_to_xlsx(model))
    sheet_back = reimported.sheets[SheetId("s1")]
    assert sheet_back.name == "Data"
    assert sheet_back.cells[(0, 0)] == {"t": "text", "v": "Region"}
    assert sheet_back.cells[(1, 2)] == {"t": "int", "v": 100}
    assert sheet_back.cells[(7, 0)] == {"t": "formula", "v": "=SUM(C2:C7)"}


def test_a_formula_calculates_after_import():
    model = WorkbookModel()
    sheet = Sheet(SheetId("s1"), "Data")
    model.sheets[sheet.id] = sheet
    sheet.cells[(0, 0)] = {"t": "int", "v": 10}
    sheet.cells[(1, 0)] = {"t": "int", "v": 20}
    sheet.cells[(2, 0)] = {"t": "formula", "v": "=SUM(A1:A2)"}
    reimported = xlsx_to_workbook(workbook_to_xlsx(model))
    assert reimported.value(SheetId("s1"), 2, 0) == 30


def test_several_sheets_keep_their_names_and_order_on_import():
    model = workbook_with_data()
    model.sheets[SheetId("s2")] = Sheet(SheetId("s2"), "Notes")
    reimported = xlsx_to_workbook(workbook_to_xlsx(model))
    assert [sheet.name for sheet in reimported.sheets.values()] == ["Data", "Notes"]


def test_apply_edits_changes_only_the_touched_cell():
    base = workbook_to_xlsx(workbook_with_data())
    baseline = xlsx_to_workbook(base)
    current = xlsx_to_workbook(base)
    current.store(current.sheets[SheetId("s1")], 1, 2, {"t": "int", "v": 999})

    edited = apply_edits_to_xlsx(base, baseline, current)
    reimported = xlsx_to_workbook(edited)
    sheet = reimported.sheets[SheetId("s1")]
    assert sheet.cells[(1, 2)] == {"t": "int", "v": 999}
    assert sheet.cells[(0, 0)] == {"t": "text", "v": "Region"}  # untouched cell survives


def test_apply_edits_can_clear_a_cell_and_add_a_new_one():
    base = workbook_to_xlsx(workbook_with_data())
    baseline = xlsx_to_workbook(base)
    current = xlsx_to_workbook(base)
    sheet = current.sheets[SheetId("s1")]
    current.store(sheet, 1, 2, None)  # clear an existing cell
    current.store(sheet, 10, 0, {"t": "text", "v": "Total"})  # add a brand-new one

    edited = apply_edits_to_xlsx(base, baseline, current)
    reimported = xlsx_to_workbook(edited)
    sheet_back = reimported.sheets[SheetId("s1")]
    assert (1, 2) not in sheet_back.cells
    assert sheet_back.cells[(10, 0)] == {"t": "text", "v": "Total"}


def test_apply_edits_leaves_an_untouched_sheet_byte_identical():
    model = workbook_with_data()
    model.sheets[SheetId("s2")] = Sheet(SheetId("s2"), "Notes")
    model.sheets[SheetId("s2")].cells[(0, 0)] = {"t": "text", "v": "Do not touch me"}
    base = workbook_to_xlsx(model)
    baseline = xlsx_to_workbook(base)
    current = xlsx_to_workbook(base)
    current.store(current.sheets[SheetId("s1")], 1, 2, {"t": "int", "v": 999})

    edited = apply_edits_to_xlsx(base, baseline, current)
    with zipfile.ZipFile(BytesIO(base)) as z:
        before = z.read("xl/worksheets/sheet2.xml")
    with zipfile.ZipFile(BytesIO(edited)) as z:
        after = z.read("xl/worksheets/sheet2.xml")
    assert before == after


def test_apply_edits_preserves_an_image_on_an_untouched_sheet():
    # openpyxl mutates an embedded picture's drawing XML on ANY load+resave, even with zero related edits --
    # a pure round-trip artifact, confirmed empirically (D220's implementation note). Only owning the touched
    # sheet's own worksheet part (never the whole package) is what lets this survive byte-identical.
    wb = openpyxl.Workbook()
    data_sheet = wb.active
    data_sheet.title = "Data"
    data_sheet["A1"] = "North"
    pics_sheet = wb.create_sheet("Pics")
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=(200, 50, 50)).save(buffer, format="PNG")
    buffer.seek(0)
    pics_sheet.add_image(XLImage(buffer), "A1")
    out = BytesIO()
    wb.save(out)
    original = out.getvalue()

    baseline = xlsx_to_workbook(original)
    current = xlsx_to_workbook(original)
    data_id = next(sid for sid, s in current.sheets.items() if s.name == "Data")
    current.store(current.sheets[data_id], 0, 0, {"t": "text", "v": "Northwest"})

    edited = apply_edits_to_xlsx(original, baseline, current)
    with zipfile.ZipFile(BytesIO(original)) as z:
        before = {
            "xl/drawings/drawing1.xml": z.read("xl/drawings/drawing1.xml"),
            "xl/media/image1.png": z.read("xl/media/image1.png"),
        }  # noqa: E501
    with zipfile.ZipFile(BytesIO(edited)) as z:
        after = {name: z.read(name) for name in before}
    assert before == after

    reimported = xlsx_to_workbook(edited)
    assert reimported.sheets[data_id].cells[(0, 0)] == {"t": "text", "v": "Northwest"}


def test_apply_edits_refuses_an_added_sheet():
    base = workbook_to_xlsx(workbook_with_data())
    baseline = xlsx_to_workbook(base)
    current = xlsx_to_workbook(base)
    current.sheets[SheetId("s2")] = Sheet(SheetId("s2"), "Extra")
    with pytest.raises(UnsupportedEdit):
        apply_edits_to_xlsx(base, baseline, current)


def test_apply_edits_refuses_a_renamed_sheet():
    base = workbook_to_xlsx(workbook_with_data())
    baseline = xlsx_to_workbook(base)
    current = xlsx_to_workbook(base)
    current.sheets[SheetId("s1")].name = "Renamed"
    with pytest.raises(UnsupportedEdit):
        apply_edits_to_xlsx(base, baseline, current)


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


def test_add_pivot_table_escapes_xml_metacharacters_in_cell_data():
    # A cell value containing XML metacharacters must not be able to break out of the attribute it is written
    # into and inject a sibling element -- this is the OOXML-injection hole the field data for a pivot cache
    # passes straight through unescaped if the XML is hand-built with plain string interpolation.
    model = WorkbookModel()
    sheet = Sheet(SheetId("s1"), "Data")
    model.sheets[sheet.id] = sheet
    sheet.cells[(0, 0)] = {"t": "text", "v": "Region"}
    sheet.cells[(0, 1)] = {"t": "text", "v": "Amount"}
    malicious = 'North"><injected/><x a="'
    sheet.cells[(1, 0)] = {"t": "text", "v": malicious}
    sheet.cells[(1, 1)] = {"t": "int", "v": 100}
    sheet.cells[(2, 0)] = {"t": "text", "v": "South"}
    sheet.cells[(2, 1)] = {"t": "int", "v": 150}

    base = workbook_to_xlsx(model)
    out = add_pivot_table(base, source_sheet="Data", source_range="A1:B3", row_field="Region", value_field="Amount")

    with zipfile.ZipFile(BytesIO(out)) as z:
        cache_def = z.read("xl/pivotCache/pivotCacheDefinition1.xml")

    root = etree.fromstring(cache_def)  # must still be well-formed XML
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    assert root.findall(f".//{{{ns}}}injected") == []  # no element was injected
    shared_values = {s.get("v") for s in root.findall(f".//{{{ns}}}s")}
    assert malicious in shared_values  # the value itself survives, as data, not as markup
