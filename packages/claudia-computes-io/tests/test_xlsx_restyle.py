"""A changed look written into an edited xlsx file: new entries in ``styles.xml``, never a changed one (D379, D371)."""

from __future__ import annotations

from claudia_computes_io import apply_edits_to_xlsx, xlsx_to_workbook
from lxml import etree
from test_xlsx_looks import book, style_of, xf
from test_xlsx_real_world import NS, rows

from claudia_computes import SheetId
from claudia_computes.limits import MAX_COLS, MAX_ROWS
from claudia_core import StyleDef
from claudia_opc_io import read_parts

SHEET = rows(
    '<row r="1"><c r="A1" s="1"><v>1</v></c><c r="B1" s="1"><v>2</v></c><c r="C1"><v>3</v></c></row>',
    '<row r="2"><c r="A2"><v>4</v></c></row>',
)


def edit(change) -> tuple[bytes, bytes]:  # noqa: ANN001
    original, baseline = book([xf(font=1, fill=2)], SHEET)
    current = xlsx_to_workbook(original)
    change(current)
    return original, apply_edits_to_xlsx(original, baseline, current)


def put(model, slot_area, style, layer="range"):  # noqa: ANN001
    sheet = model.sheets[SheetId("s1")]
    for slot in ("box", "words"):
        sheet.cell_styles.replace(slot, layer, slot_area, [(slot_area, style)])


def styles_of(data: bytes) -> etree._Element:
    return etree.fromstring(read_parts(data)["xl/styles.xml"])


def sheet_of(data: bytes) -> etree._Element:
    return etree.fromstring(read_parts(data)["xl/worksheets/sheet1.xml"])


def test_a_cell_given_a_named_style_points_at_a_new_look_and_the_old_ones_stay():
    original, out = edit(lambda model: put(model, (0, 2, 0, 2), "header"))
    before, after = styles_of(original), styles_of(out)
    old_xfs = before.findall("x:cellXfs/x:xf", NS)
    new_xfs = after.findall("x:cellXfs/x:xf", NS)
    assert [etree.tostring(x) for x in new_xfs[: len(old_xfs)]] == [etree.tostring(x) for x in old_xfs]
    assert len(new_xfs) == len(old_xfs) + 1
    assert "Header" in [s.get("name") for s in after.iterfind("x:cellStyles/x:cellStyle", NS)]
    cell = sheet_of(out).find(".//x:c[@r='C1']", NS)
    assert cell.get("s") == str(len(old_xfs))
    again = xlsx_to_workbook(out)
    assert again.styles.get(style_of(again, 0, 2)).name == "Header"
    assert again.styles.get(style_of(again, 0, 0)).to_name  # A1 kept its own look


def test_changing_a_style_changes_every_cell_that_has_it():
    def bolder(model):  # noqa: ANN001, ANN202
        provisional = style_of(model, 0, 0)
        model.styles.set_css(provisional, {"font-weight": "bold", "background-color": "#ff0000"})

    _, out = edit(bolder)
    sheet = sheet_of(out)
    a1, b1 = sheet.find(".//x:c[@r='A1']", NS), sheet.find(".//x:c[@r='B1']", NS)
    assert a1.get("s") == b1.get("s") != "1"
    again = xlsx_to_workbook(out)
    assert again.styles.get(style_of(again, 0, 1)).css["background-color"] == "#FF0000"


def test_naming_a_provisional_style_makes_it_a_named_style_of_the_file():
    def name(model):  # noqa: ANN001, ANN202
        model.styles.rename(style_of(model, 0, 0), "Key figure")

    _, out = edit(name)
    again = xlsx_to_workbook(out)
    key = again.styles.get(style_of(again, 0, 0))
    assert (key.name, key.to_name) == ("Key figure", False)


def test_an_empty_cell_given_a_look_is_written_and_a_style_taken_away_goes_back_to_normal():
    def change(model):  # noqa: ANN001, ANN202
        put(model, (4, 4, 4, 4), "note")
        put(model, (0, 0, 0, 0), "body-text")

    _, out = edit(change)
    sheet = sheet_of(out)
    assert sheet.find(".//x:c[@r='E5']", NS) is not None
    assert sheet.find(".//x:c[@r='A1']", NS).get("s") is None
    again = xlsx_to_workbook(out)
    assert again.styles.get(style_of(again, 4, 4)).name == "Note"


def test_rows_and_columns_take_their_looks():
    def change(model):  # noqa: ANN001, ANN202
        put(model, (5, 0, 6, MAX_COLS - 1), "input", "row")
        put(model, (0, 3, MAX_ROWS - 1, 4), "note", "column")

    _, out = edit(change)
    sheet = sheet_of(out)
    assert [r.get("customFormat") for r in sheet.iterfind(".//x:row", NS) if r.get("r") in ("6", "7")] == ["1", "1"]
    cols = sheet.findall("x:cols/x:col", NS)
    assert [(c.get("min"), c.get("max")) for c in cols] == [("4", "5")] and cols[0].get("style")
    again = xlsx_to_workbook(out)
    assert again.styles.get(style_of(again, 5, 7)).name == "Input"
    assert again.styles.get(style_of(again, 20, 3)).name == "Note"


def test_a_col_element_reaching_beyond_a_restyled_column_is_cut():
    original, baseline = book(
        [xf(font=1)], '<cols><col min="1" max="6" width="20" customWidth="1"/></cols>' + rows('<row r="1"/>')
    )
    current = xlsx_to_workbook(original)
    put(current, (0, 2, MAX_ROWS - 1, 2), "note", "column")
    cols = sheet_of(apply_edits_to_xlsx(original, baseline, current)).findall("x:cols/x:col", NS)
    assert [(c.get("min"), c.get("max"), c.get("width"), c.get("style") is not None) for c in cols] == [
        ("1", "2", "20", False),
        ("3", "3", "20", True),
        ("4", "6", "20", False),
    ]


def test_a_new_named_style_is_added_with_its_own_look():
    def change(model):  # noqa: ANN001, ANN202
        model.styles.add(StyleDef("total", "Total", "a sum", "body-text", {"font-weight": "bold"}))
        model.number_formats.add(__import__("claudia_computes").NumberFormat("eur", "€", '#,##0.00 "€"'))
        model.styles.set_number_format("total", "eur")
        put(model, (1, 0, 1, 0), "total")

    _, out = edit(change)
    styles = styles_of(out)
    assert "Total" in [s.get("name") for s in styles.iterfind("x:cellStyles/x:cellStyle", NS)]
    assert '#,##0.00 "€"' in [f.get("formatCode") for f in styles.iterfind("x:numFmts/x:numFmt", NS)]
    again = xlsx_to_workbook(out)
    total = again.styles.get(style_of(again, 1, 0))
    assert total.name == "Total" and again.number_formats.get(again.styles.number_format(total.id)).code == (
        '#,##0.00 "€"'
    )


def test_a_number_format_the_file_has_is_used_and_a_list_the_file_lacks_is_made():
    from test_xlsx_real_world import X, package

    from claudia_computes import NumberFormat

    def change(model):  # noqa: ANN001, ANN202
        model.number_formats.add(NumberFormat("pct", "%", "0%"))  # Excel's own number 9
        model.number_formats.add(NumberFormat("mwh", "MWh", '#,##0 "MWh"'))
        model.styles.add(StyleDef("share", "Share", "a part", "body-text", {}, number_format="pct"))
        model.styles.add(StyleDef("energy", "Energy", "an amount", "body-text", {}, number_format="mwh"))
        put(model, (0, 0, 0, 0), "share")
        put(model, (0, 1, 0, 1), "energy")

    bare = (
        f'<styleSheet xmlns="{X}"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellXfs></styleSheet>'
    )
    original = package({"Plan": rows('<row r="1"><c r="A1"><v>0.5</v></c><c r="B1"><v>9</v></c></row>')},
                       extra={"xl/styles.xml": bare.encode()})  # fmt: skip
    baseline, current = xlsx_to_workbook(original), xlsx_to_workbook(original)
    change(current)
    out = apply_edits_to_xlsx(original, baseline, current)
    styles = styles_of(out)
    names = [s.get("name") for s in styles.iterfind("x:cellStyles/x:cellStyle", NS)]
    assert names == ["Share", "Energy"]
    assert [f.get("formatCode") for f in styles.iterfind("x:numFmts/x:numFmt", NS)] == ['#,##0 "MWh"']
    assert [child.tag.split("}")[1] for child in styles][:2] == ["numFmts", "fonts"]  # in the schema's order
    again = xlsx_to_workbook(out)
    assert again.number_formats.get(again.styles.number_format(style_of(again, 0, 0))).code == "0%"
