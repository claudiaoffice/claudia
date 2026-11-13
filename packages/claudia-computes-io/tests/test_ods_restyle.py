"""A changed look written into an edited ods file: automatic styles of its own, named styles added, everything
else as the file had it (D349, D413)."""

from __future__ import annotations

from claudia_computes_io import apply_edits_to_ods, ods_to_workbook
from test_ods import cell, num, row, table
from test_ods_looks import an_ods, style_of

from claudia_computes import SheetId
from claudia_computes.limits import MAX_COLS, MAX_ROWS
from claudia_opc_io import read_parts

COLUMNS = '<table:table-column table:number-columns-repeated="6" table:default-cell-style-name="Default"/>'
ROWS = row(
    num(1, extra=' table:style-name="ce1"'),
    num(2, extra=' table:style-name="ce1"'),
    num(3, extra=' table:style-name="ce2"'),
) + row(cell('table:number-columns-repeated="6"'), repeat=10)


def put(model, area, style, layer="range"):  # noqa: ANN001
    sheet = model.sheets[SheetId("s1")]
    for slot in ("box", "words"):
        sheet.cell_styles.replace(slot, layer, area, [(area, style)])


def edit(change) -> tuple[bytes, bytes]:  # noqa: ANN001
    original = an_ods(table("Data", ROWS, COLUMNS))
    baseline, current = ods_to_workbook(original), ods_to_workbook(original)
    change(current)
    return original, apply_edits_to_ods(original, baseline, current)


def parts(data: bytes) -> tuple[str, str]:
    found = read_parts(data)
    return found["content.xml"].decode(), found["styles.xml"].decode()


def test_nothing_restyled_is_the_original():
    original, out = edit(lambda model: None)
    assert out == original


def test_a_restyled_cell_gets_an_automatic_style_of_its_own_and_a_new_named_style():
    original, out = edit(lambda model: put(model, (0, 2, 0, 2), "header"))
    content, styles = parts(out)
    assert 'style:name="claudia-ce1"' in content and 'style:parent-style-name="header"' in content
    assert 'style:display-name="Header"' in styles
    assert parts(original)[0].count('style:name="ce') == content.count('style:name="ce')  # the file's own stay
    again = ods_to_workbook(out)
    assert again.styles.get(style_of(again, 0, 2)).name == "Header"
    assert again.styles.get(style_of(again, 0, 0)).to_name  # A1 kept its look


def test_the_files_own_named_style_is_the_parent_and_a_changed_style_reaches_its_cells():
    def change(model):  # noqa: ANN001, ANN202
        heading = next(style for style in model.styles if style.name == "Heading")
        put(model, (5, 1, 5, 1), heading.id)
        provisional = style_of(model, 0, 0)
        model.styles.set_css(provisional, {**model.styles.get(provisional).css, "color": "#00ff00"})

    _, out = edit(change)
    content, styles = parts(out)
    assert 'style:parent-style-name="Heading"' in content
    assert styles == parts(an_ods(table("Data", ROWS, COLUMNS)))[1]  # nothing new to name
    again = ods_to_workbook(out)
    assert again.styles.get(style_of(again, 5, 1)).name == "Heading"
    assert again.styles.get(style_of(again, 0, 1)).css["color"] == "#00ff00"


def test_rows_and_columns_take_their_looks_and_repeated_ones_are_cut():
    def change(model):  # noqa: ANN001, ANN202
        put(model, (3, 0, 4, MAX_COLS - 1), "input", "row")
        put(model, (0, 4, MAX_ROWS - 1, 4), "note", "column")

    _, out = edit(change)
    content, _ = parts(out)
    assert content.count('table:number-rows-repeated="2"') >= 1  # rows 4 and 5 cut out of the ten
    again = ods_to_workbook(out)
    assert again.styles.get(style_of(again, 3, 5)).name == "Input"
    assert again.styles.get(style_of(again, 4, 0)).name == "Input"
    assert again.styles.get(style_of(again, 8, 4)).name == "Note"
    assert again.styles.get(style_of(again, 8, 3)).name == "Body text"


def test_a_restyled_cell_that_also_gets_a_value():
    def change(model):  # noqa: ANN001, ANN202
        put(model, (12, 1, 12, 1), "note")
        model.store(model.sheets[SheetId("s1")], 12, 1, {"t": "int", "v": 7})

    _, out = edit(change)
    again = ods_to_workbook(out)
    assert again.sheets[SheetId("s1")].cells[(12, 1)] == {"t": "int", "v": 7}
    assert again.styles.get(style_of(again, 12, 1)).name == "Note"
