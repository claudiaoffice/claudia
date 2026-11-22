"""Row heights and column widths in ods files (D458): written on export, read on import, patched into a kept file."""

from __future__ import annotations

import pytest
from claudia_computes_io import (
    apply_edits_to_ods,
    ods_export_losses,
    ods_import_losses,
    ods_to_workbook,
    ods_unwritten_changes,
    workbook_to_ods,
)
from claudia_computes_io.ods_layout import pixels_of, text_of
from lxml import etree
from test_ods import an_ods, content_of, num, row, table, text

from claudia_computes import Sheet, SheetId, WorkbookModel
from claudia_odf_io import NS

DATA = SheetId("s1")
COLUMN = (
    '<style:style style:name="co{n}" style:family="table-column">'
    '<style:table-column-properties fo:break-before="auto" style:column-width="{w}"/></style:style>'
)
ROW = (
    '<style:style style:name="ro{n}" style:family="table-row">'
    '<style:table-row-properties fo:break-before="auto" style:row-height="{h}" '
    'style:use-optimal-row-height="{o}"/></style:style>'
)


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


def table_of(data: bytes) -> etree._Element:
    root = etree.fromstring(content_of(data).encode())
    return root.find(".//table:table", NS)


def styles_of(data: bytes, family: str) -> dict[str, float | None]:
    """The size each automatic style of ``family`` (``table-column``, ``table-row``) says, in cm."""
    root = etree.fromstring(content_of(data).encode())
    sizes: dict[str, float | None] = {}
    for style in root.iterfind(".//office:automatic-styles/style:style", NS):
        if style.get(f"{{{NS['style']}}}family") != family:
            continue
        properties = style[0]
        text = properties.get(f"{{{NS['style']}}}{'column-width' if family == 'table-column' else 'row-height'}")
        sizes[style.get(f"{{{NS['style']}}}name", "")] = float(text.removesuffix("cm")) if text else None
    return sizes


def widths_written(data: bytes) -> list[tuple[int, float | None]]:
    """``(columns, width in cm)`` of each ``table:table-column`` of the first table."""
    styles = styles_of(data, "table-column")
    out = []
    for column in table_of(data).iterfind("table:table-column", NS):
        count = int(column.get(f"{{{NS['table']}}}number-columns-repeated", "1"))
        out.append((count, styles.get(column.get(f"{{{NS['table']}}}style-name", ""))))
    return out


def heights_written(data: bytes) -> list[tuple[int, float | None]]:
    styles = styles_of(data, "table-row")
    out = []
    for each in table_of(data).iterfind("table:table-row", NS):
        count = int(each.get(f"{{{NS['table']}}}number-rows-repeated", "1"))
        out.append((count, styles.get(each.get(f"{{{NS['table']}}}style-name", ""))))
    return out


# ------------------------------------------------------------------------------------------------ units
@pytest.mark.parametrize(
    ("length", "pixels"),
    [
        ("2.54cm", 96),
        ("25.4mm", 96),
        ("1in", 96),
        ("72pt", 96),
        ("6pc", 96),
        ("96px", 96),
        ("0.5in", 48),
        ("2.258cm", 85),
    ],
)
def test_a_length_of_a_file_is_counted_in_pixels(length, pixels):
    assert pixels_of(length) == pixels


@pytest.mark.parametrize("length", ["", "wide", "12", "5em", "-1cm"])
def test_a_length_that_is_not_one_has_no_pixels(length):
    assert pixels_of(length) is None


def test_pixels_go_to_a_length_and_back_to_the_same_pixels():
    for pixels in (16, 26, 85, 96, 333, 2000):
        assert pixels_of(text_of(pixels)) == pixels


# ------------------------------------------------------------------------------------------------ fresh export
def test_the_widths_and_heights_of_a_fresh_export_are_in_the_file():
    data = workbook_to_ods(a_model(widths={1: 150, 2: 150, 4: 40}, heights={0: 52, 3: 13}))
    columns = widths_written(data)
    assert [count for count, _ in columns] == [1, 2, 1, 1]
    assert [round(width / 2.54 * 96) if width else None for _, width in columns] == [None, 150, None, 40]
    rows = heights_written(data)
    assert rows[0][0] == 1
    assert round(rows[0][1] / 2.54 * 96) == 52
    assert round(rows[3][1] / 2.54 * 96) == 13


def test_a_row_size_is_not_an_optimal_one():
    data = workbook_to_ods(a_model(heights={0: 52}))
    assert 'style:use-optimal-row-height="false"' in content_of(data)


def test_nothing_of_layout_is_reported_as_unwritten_any_more():
    model = a_model(widths={1: 150}, heights={0: 52})
    assert [loss for loss in ods_unwritten_changes(model) if loss.kind == "layout"] == []
    assert [loss for loss in ods_export_losses(model) if loss.kind == "layout"] == []


def test_the_widths_and_heights_come_back_from_a_fresh_export():
    model = ods_to_workbook(workbook_to_ods(a_model(widths={1: 150, 2: 150, 4: 40}, heights={0: 52, 3: 13})))
    sheet = model.sheets[DATA]
    assert sheet.col_widths == {1: 150, 2: 150, 4: 40}
    assert sheet.row_heights == {0: 52, 3: 13}


def test_two_columns_of_one_width_share_one_style_and_one_run():
    data = workbook_to_ods(a_model(widths={1: 150, 2: 150}))
    assert len(styles_of(data, "table-column")) == 1


# ------------------------------------------------------------------------------------------------ import
AUTOMATIC = (
    COLUMN.format(n=1, w="2.258cm")
    + COLUMN.format(n=2, w="4cm")
    + ROW.format(n=1, h="0.452cm", o="true")
    + ROW.format(n=2, h="1.5cm", o="false")
)


def a_file() -> bytes:
    columns = (
        '<table:table-column table:style-name="co2"/>'
        '<table:table-column table:style-name="co1" table:number-columns-repeated="6"/>'
    )
    rows = (
        row(num("1"))
        + '<table:table-row table:style-name="ro2"><table:table-cell/></table:table-row>'
        + '<table:table-row table:style-name="ro1" table:number-rows-repeated="1048570">'
        "<table:table-cell/></table:table-row>"
    )
    return an_ods(table("Data", rows, columns), automatic=AUTOMATIC)


def test_a_width_the_file_gives_comes_in_in_pixels():
    sheet = ods_to_workbook(a_file()).sheets[DATA]
    assert sheet.col_widths[0] == round(4 / 2.54 * 96)
    assert sheet.col_widths[1] == 85  # (the file's own width of 2.258cm: every column of a LibreOffice file has one)


def test_a_height_somebody_set_comes_in_and_an_optimal_one_does_not():
    sheet = ods_to_workbook(a_file()).sheets[DATA]
    assert sheet.row_heights == {1: round(1.5 / 2.54 * 96)}


def test_widths_past_the_columns_the_model_sizes_are_not_read_and_not_reported():
    columns = '<table:table-column table:style-name="co2" table:number-columns-repeated="1000"/>'
    data = an_ods(table("Data", row(num("1")), columns), automatic=COLUMN.format(n=2, w="4cm"))
    sheet = ods_to_workbook(data).sheets[DATA]
    assert max(sheet.col_widths) == 255
    assert all(loss.kind != "layout" for loss in ods_import_losses(data))


def test_a_width_equal_to_the_models_default_does_not_come_in_as_a_width():
    columns = '<table:table-column table:style-name="co1" table:number-columns-repeated="3"/>'
    data = an_ods(table("Data", row(num("1")), columns), automatic=COLUMN.format(n=1, w="2.54cm"))
    assert ods_to_workbook(data).sheets[DATA].col_widths == {}


def test_a_row_run_of_one_height_comes_in_row_by_row():
    rows = (
        '<table:table-row table:style-name="ro2" table:number-rows-repeated="3"><table:table-cell/></table:table-row>'
    )
    data = an_ods(table("Data", row(num("1")) + rows), automatic=ROW.format(n=2, h="1.5cm", o="false"))
    assert ods_to_workbook(data).sheets[DATA].row_heights == dict.fromkeys((1, 2, 3), 57)


# ------------------------------------------------------------------------------------------------ patch
def patched(original: bytes, change) -> tuple[bytes, WorkbookModel]:  # noqa: ANN001
    baseline, current = ods_to_workbook(original), ods_to_workbook(original)
    change(current.sheets[DATA])
    return apply_edits_to_ods(original, baseline, current), current


def test_a_width_changed_is_patched_into_the_file_and_the_other_columns_keep_theirs():
    original = a_file()
    data, _ = patched(original, lambda sheet: sheet.col_widths.update({2: 200}))
    after = ods_to_workbook(data).sheets[DATA]
    before = ods_to_workbook(original).sheets[DATA]
    assert after.col_widths == {**before.col_widths, 2: 200}
    assert after.row_heights == before.row_heights
    assert "co2" in content_of(data)  # (what is not changed stays as it was)


def test_a_height_changed_is_patched_into_the_file_including_in_a_run_of_equal_rows():
    original = a_file()
    data, _ = patched(original, lambda sheet: sheet.row_heights.update({1: 60, 2: 33}))
    assert ods_to_workbook(data).sheets[DATA].row_heights == {1: 60, 2: 33}


def test_a_size_given_up_reads_back_as_none():
    original = a_file()

    def give_up(sheet: Sheet) -> None:
        sheet.col_widths.pop(0)
        sheet.row_heights.pop(1)

    data, _ = patched(original, give_up)
    after = ods_to_workbook(data).sheets[DATA]
    assert 0 not in after.col_widths
    assert after.row_heights == {}


def test_a_row_beyond_the_last_one_of_the_file_gets_its_height():
    original = an_ods(table("Data", row(num("1"))))
    data, _ = patched(original, lambda sheet: sheet.row_heights.update({5: 44}))
    assert ods_to_workbook(data).sheets[DATA].row_heights == {5: 44}


def test_a_column_beyond_the_last_one_of_the_file_gets_its_width():
    original = an_ods(table("Data", row(num("1")), columns="<table:table-column/>"))
    data, _ = patched(original, lambda sheet: sheet.col_widths.update({3: 140}))
    assert ods_to_workbook(data).sheets[DATA].col_widths == {3: 140}


def test_a_changed_size_and_a_changed_cell_in_one_row_come_out_together():
    original = a_file()

    def both(sheet: Sheet) -> None:
        sheet.row_heights[0] = 70
        sheet.cells[(0, 0)] = {"t": "text", "v": "new"}

    data, current = patched(original, both)
    after = ods_to_workbook(data).sheets[DATA]
    assert after.row_heights[0] == 70
    assert after.cells[(0, 0)] == {"t": "text", "v": "new"}


def test_an_unchanged_layout_gives_back_the_original_bytes():
    original = a_file()
    assert apply_edits_to_ods(original, ods_to_workbook(original), ods_to_workbook(original)) == original


def test_a_file_without_a_changed_size_keeps_every_byte_of_its_cells():
    original = an_ods(table("Data", row(text("a"), num("1")) + row(text("b"))))
    data, _ = patched(original, lambda sheet: sheet.col_widths.update({0: 120}))
    assert "<text:p>a</text:p>" in content_of(data)
    assert ods_to_workbook(data).sheets[DATA].cells == ods_to_workbook(original).sheets[DATA].cells
