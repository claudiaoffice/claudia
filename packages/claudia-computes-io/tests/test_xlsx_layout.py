"""Row heights and column widths in xlsx files (D458): written on export, read on import, patched into a kept file."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import openpyxl
import pytest
from claudia_computes_io import (
    apply_edits_to_xlsx,
    workbook_to_xlsx,
    xlsx_export_losses,
    xlsx_to_workbook,
    xlsx_unwritten_changes,
)
from claudia_computes_io.xlsx_layout import height_of, size_of_height, size_of_width, width_of
from lxml import etree

from claudia_computes import Sheet, SheetId, WorkbookModel
from claudia_computes.model import DEFAULT_COL_WIDTH, DEFAULT_ROW_HEIGHT
from claudia_odf_io import Loss

DATA = SheetId("s1")
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"x": MAIN}


def a_model(*, widths: dict[int, float] | None = None, heights: dict[int, float] | None = None) -> WorkbookModel:
    model = WorkbookModel()
    model.sheets[DATA] = Sheet(DATA, "Data")
    model.open_holder(str(DATA))
    sheet = model.sheets[DATA]
    sheet.cells[(0, 0)] = {"t": "text", "v": "Item"}
    sheet.cells[(1, 1)] = {"t": "int", "v": 4}
    sheet.col_widths.update(widths or {})
    sheet.row_heights.update(heights or {})
    model._calculate_loaded()
    return model


def sheet_xml(data: bytes) -> etree._Element:
    with ZipFile(BytesIO(data)) as package:
        return etree.fromstring(package.read("xl/worksheets/sheet1.xml"))


def cols_of(data: bytes) -> list[tuple[int, int, float | None, bool]]:
    return [
        (
            int(col.get("min", "0")),
            int(col.get("max", "0")),
            float(col.get("width")) if col.get("width") else None,
            col.get("customWidth") in ("1", "true"),
        )
        for col in sheet_xml(data).iterfind("x:cols/x:col", NS)
    ]


def rows_of(data: bytes) -> dict[int, tuple[float | None, bool]]:
    return {
        int(row.get("r", "0")): (
            float(row.get("ht")) if row.get("ht") else None,
            row.get("customHeight") in ("1", "true"),
        )
        for row in sheet_xml(data).iterfind("x:sheetData/x:row", NS)
    }


# ------------------------------------------------------------------------------------------------ units
def test_a_width_in_pixels_goes_to_characters_and_back_to_the_same_pixels():
    for pixels in (16, 64, 96, 120, 333, 2000):
        assert size_of_width(width_of(pixels)) == pixels


def test_a_height_in_pixels_goes_to_points_and_back_to_the_same_pixels():
    for pixels in (8, 20, 26, 40, 500):
        assert size_of_height(height_of(pixels)) == pixels


def test_the_sizes_of_the_model_default_are_what_excel_shows_at_that_size():
    assert width_of(DEFAULT_COL_WIDTH) == pytest.approx(13.714286, abs=1e-6)
    assert height_of(DEFAULT_ROW_HEIGHT) == 19.5


# ------------------------------------------------------------------------------------------------ fresh export
def test_the_widths_and_heights_of_a_fresh_export_are_in_the_file():
    data = workbook_to_xlsx(a_model(widths={1: 150, 2: 150, 4: 40}, heights={0: 52, 3: 13}))
    assert cols_of(data) == [
        (2, 3, pytest.approx(150 / 7), True),
        (5, 5, pytest.approx(40 / 7), True),
    ]
    rows = rows_of(data)
    assert rows[1] == (39.0, True)
    assert rows[4] == (9.75, True)


def test_a_fresh_export_says_what_a_line_without_a_size_shows_at():
    root = sheet_xml(workbook_to_xlsx(a_model()))
    pr = root.find("x:sheetFormatPr", NS)
    assert pr is not None
    assert float(pr.get("defaultColWidth", "0")) == pytest.approx(13.714286, abs=1e-6)
    assert float(pr.get("defaultRowHeight", "0")) == 19.5
    assert pr.get("customHeight") in ("1", "true")


def test_a_column_with_a_look_and_a_width_keeps_both():
    from test_xlsx_looks import styled_workbook  # noqa: PLC0415

    model = styled_workbook()
    sheet = next(iter(model.sheets.values()))
    sheet.col_widths[3] = 150
    sheet.col_widths[4] = 150
    reread = next(iter(xlsx_to_workbook(workbook_to_xlsx(model)).sheets.values()))
    assert reread.col_widths == {3: 150, 4: 150}


def test_a_look_only_column_does_not_get_a_width_of_its_own():
    """openpyxl's default of 13 characters would come back as a column of 91 pixels."""
    from test_xlsx_looks import styled_workbook  # noqa: PLC0415

    reread = xlsx_to_workbook(workbook_to_xlsx(styled_workbook()))
    assert next(iter(reread.sheets.values())).col_widths == {}


def test_a_size_beyond_what_excel_holds_is_written_at_the_limit_and_said():
    model = a_model(widths={0: 2000}, heights={0: 1000})
    data = workbook_to_xlsx(model)
    assert cols_of(data)[0][2] == 255.0
    assert rows_of(data)[1][0] == 409.5
    assert Loss("layout", "beyond-excel-limits", 2) in xlsx_export_losses(model)


def test_nothing_of_layout_is_reported_as_unwritten_any_more():
    model = a_model(widths={1: 150}, heights={0: 52})
    assert [loss for loss in xlsx_unwritten_changes(model) if loss.kind == "layout"] == []


# ------------------------------------------------------------------------------------------------ import
def test_the_widths_and_heights_of_a_file_come_in():
    model = xlsx_to_workbook(workbook_to_xlsx(a_model(widths={1: 150, 2: 150, 4: 40}, heights={0: 52, 3: 13})))
    sheet = model.sheets[DATA]
    assert sheet.col_widths == {1: 150, 2: 150, 4: 40}
    assert sheet.row_heights == {0: 52, 3: 13}


def a_file_with(cols: str = "", rows: str = "") -> bytes:
    """A file written by openpyxl whose sheet XML is then given ``cols`` (before the data) and ``rows`` (the first
    rows)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    ws["A2"] = "y"
    out = BytesIO()
    wb.save(out)
    with ZipFile(BytesIO(out.getvalue())) as package:
        parts = {name: package.read(name) for name in package.namelist()}
    xml = parts["xl/worksheets/sheet1.xml"].decode()
    if cols:
        xml = xml.replace("<sheetData>", f"<cols>{cols}</cols><sheetData>", 1)
    if rows:
        xml = xml.replace('<row r="1">', f'<row r="1" {rows}>', 1)
    parts["xl/worksheets/sheet1.xml"] = xml.encode()
    result = BytesIO()
    with ZipFile(result, "w") as package:
        for name, content in parts.items():
            package.writestr(name, content)
    return result.getvalue()


def test_only_a_width_somebody_set_comes_in_not_the_one_the_file_left_to_the_application():
    data = a_file_with('<col min="1" max="1" width="30" customWidth="1"/><col min="2" max="2" width="20"/>')
    assert xlsx_to_workbook(data).sheets[next(iter(xlsx_to_workbook(data).sheets))].col_widths == {0: 210}


def test_only_a_height_somebody_set_comes_in():
    data = a_file_with(rows='ht="30" customHeight="1"')
    sheet = next(iter(xlsx_to_workbook(data).sheets.values()))
    assert sheet.row_heights == {0: 40}
    data = a_file_with(rows='ht="30"')
    assert next(iter(xlsx_to_workbook(data).sheets.values())).row_heights == {}


def test_a_run_of_columns_with_one_width_comes_in_column_by_column():
    data = a_file_with('<col min="2" max="4" width="20" customWidth="1"/>')
    sheet = next(iter(xlsx_to_workbook(data).sheets.values()))
    assert sheet.col_widths == {1: 140, 2: 140, 3: 140}


def test_a_width_run_over_the_whole_sheet_comes_in_for_the_columns_the_model_sizes_and_is_not_reported():
    from claudia_computes_io import xlsx_import_losses  # noqa: PLC0415

    data = a_file_with('<col min="1" max="16384" width="20" customWidth="1"/>')
    sheet = next(iter(xlsx_to_workbook(data).sheets.values()))
    assert sorted(sheet.col_widths) == list(range(256))
    assert all(loss.kind != "layout" for loss in xlsx_import_losses(data))


def test_a_width_equal_to_the_models_default_does_not_come_in_as_a_width():
    data = a_file_with('<col min="1" max="1" width="13.714286" customWidth="1"/>')
    assert next(iter(xlsx_to_workbook(data).sheets.values())).col_widths == {}


# ------------------------------------------------------------------------------------------------ patch
def patched(original: bytes, change) -> tuple[bytes, WorkbookModel]:  # noqa: ANN001
    baseline = xlsx_to_workbook(original)
    current = xlsx_to_workbook(original)
    change(next(iter(current.sheets.values())))
    return apply_edits_to_xlsx(original, baseline, current), current


def test_a_width_changed_is_patched_into_the_file_and_nothing_else_moves():
    original = workbook_to_xlsx(a_model(widths={1: 150}))
    data, current = patched(original, lambda sheet: sheet.col_widths.update({1: 200, 3: 80}))
    assert cols_of(data) == [
        (2, 2, pytest.approx(200 / 7), True),
        (4, 4, pytest.approx(80 / 7), True),
    ]
    assert xlsx_to_workbook(data).sheets[DATA].col_widths == {1: 200, 3: 80}
    assert xlsx_to_workbook(data).sheets[DATA].cells == current.sheets[DATA].cells


def test_a_height_changed_is_patched_into_the_file():
    original = workbook_to_xlsx(a_model(heights={0: 52}))
    data, _ = patched(original, lambda sheet: sheet.row_heights.update({0: 60, 5: 33}))
    assert xlsx_to_workbook(data).sheets[DATA].row_heights == {0: 60, 5: 33}
    assert rows_of(data)[6] == (24.75, True)


def test_a_size_given_up_is_written_as_the_models_default_so_it_reads_back_as_none():
    original = workbook_to_xlsx(a_model(widths={1: 150}, heights={0: 52}))

    def give_up(sheet: Sheet) -> None:
        sheet.col_widths.clear()
        sheet.row_heights.clear()

    data, _ = patched(original, give_up)
    reread = xlsx_to_workbook(data).sheets[DATA]
    assert reread.col_widths == {}
    assert reread.row_heights == {}
    assert rows_of(data)[1] == (19.5, True)


def test_a_width_inside_a_run_of_the_file_cuts_the_run_and_the_columns_around_it_keep_theirs():
    original = a_file_with('<col min="2" max="5" width="20" customWidth="1"/>')
    data, _ = patched(original, lambda sheet: sheet.col_widths.update({2: 300}))
    assert cols_of(data) == [
        (2, 2, 20.0, True),
        (3, 3, pytest.approx(300 / 7), True),
        (4, 5, 20.0, True),
    ]


def test_a_width_beyond_excels_limit_is_written_at_the_limit_and_said_by_the_unwritten_changes():
    original = workbook_to_xlsx(a_model())
    baseline = xlsx_to_workbook(original)
    current = xlsx_to_workbook(original)
    current.sheets[DATA].col_widths[0] = 2000
    data = apply_edits_to_xlsx(original, baseline, current)
    assert cols_of(data)[0][2] == 255.0
    assert Loss("layout", "beyond-excel-limits", 1) in xlsx_unwritten_changes(current, baseline)


def test_an_unchanged_layout_gives_back_the_original_bytes():
    original = workbook_to_xlsx(a_model(widths={1: 150}, heights={0: 52}))
    baseline = xlsx_to_workbook(original)
    assert apply_edits_to_xlsx(original, baseline, xlsx_to_workbook(original)) == original


def test_a_sheet_with_a_changed_size_keeps_its_looks_and_its_other_columns():
    from test_xlsx_looks import style_of, styled_workbook  # noqa: PLC0415

    original = workbook_to_xlsx(styled_workbook())
    baseline = xlsx_to_workbook(original)
    current = xlsx_to_workbook(original)
    next(iter(current.sheets.values())).col_widths[3] = 222
    data = apply_edits_to_xlsx(original, baseline, current)
    reread = xlsx_to_workbook(data)
    assert next(iter(reread.sheets.values())).col_widths == {3: 222}
    assert reread.styles.get(style_of(reread, 50, 3)).name == "Input"
