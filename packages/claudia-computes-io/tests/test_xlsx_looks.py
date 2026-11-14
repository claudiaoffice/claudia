"""The look of an xlsx file's cells comes in as styles and named number formats (E6.14, D378, D379).

Each test writes the ``styles.xml`` it needs: the file's default font, a few direct formats, a named style. The
cells then say which look they have by its place in ``cellXfs``."""

from __future__ import annotations

import pytest
from claudia_computes_io import cell_looks, xlsx_import_losses, xlsx_to_workbook
from claudia_computes_io.cell_looks import colour_name, difference, difference_words
from claudia_computes_io.xlsx_looks import read_looks, tinted
from test_xlsx_real_world import X, package, rows

from claudia_computes import SheetId
from claudia_computes.limits import MAX_COLS, MAX_ROWS
from claudia_odf_io import Loss

FONTS = (
    '<font><sz val="10"/><name val="Arial"/></font>'
    '<font><b/><sz val="10"/><name val="Arial"/></font>'
    '<font><sz val="10"/><color rgb="FFFF0000"/><name val="Arial"/></font>'
    '<font><b/><sz val="14"/><color theme="4" tint="-0.249977111117893"/><name val="Arial"/></font>'
)
FILLS = (
    '<fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FFD9D9D9"/><bgColor indexed="64"/></patternFill></fill>'
    '<fill><patternFill patternType="darkGrid"><fgColor indexed="10"/></patternFill></fill>'
)
BORDERS = (
    "<border><left/><right/><top/><bottom/><diagonal/></border>"
    '<border><left/><right/><top/><bottom style="thin"><color indexed="64"/></bottom><diagonal/></border>'
)


def styles(cell_xfs: list[str], *, named: str = "", named_xfs: str = "", formats: str = "") -> bytes:
    """A styles part with the fonts, fills and borders above, the default look first, and these looks."""
    xfs = ['<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>', *cell_xfs]
    return (
        f'<styleSheet xmlns="{X}">'
        f'<numFmts count="2"><numFmt numFmtId="164" formatCode="#,##0 &quot;MWh&quot;"/>'
        f'<numFmt numFmtId="165" formatCode="0.0%"/>{formats}</numFmts>'
        f"<fonts>{FONTS}</fonts><fills>{FILLS}</fills><borders>{BORDERS}</borders>"
        f'<cellStyleXfs><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>{named_xfs}</cellStyleXfs>'
        f"<cellXfs>{''.join(xfs)}</cellXfs>"
        f'<cellStyles><cellStyle name="Normal" xfId="0" builtinId="0"/>{named}</cellStyles>'
        "</styleSheet>"
    ).encode()


def xf(font: int = 0, fill: int = 0, border: int = 0, number: int = 0, parent: int = 0, inside: str = "") -> str:
    return f'<xf numFmtId="{number}" fontId="{font}" fillId="{fill}" borderId="{border}" xfId="{parent}">{inside}</xf>'


def book(cell_xfs: list[str], sheet: str, **more: str):
    data = package({"Plan": sheet}, extra={"xl/styles.xml": styles(cell_xfs, **more)})
    return data, xlsx_to_workbook(data)


def style_of(model, row: int, col: int, slot: str = "words") -> str:
    return model.sheets[SheetId("s1")].cell_styles.style_at(row, col, slot)[0]


def test_the_default_font_of_the_file_becomes_body_text():
    _, model = book([], rows('<row r="1"><c r="A1"><v>1</v></c></row>'))
    body = model.styles.get("body-text").css
    assert body["font-family"] == "Arial, 'Liberation Sans', sans-serif"
    assert body["font-size"] == "10pt"
    assert body["vertical-align"] == "bottom"
    assert style_of(model, 0, 0) == "body-text"
    assert len(model.sheets[SheetId("s1")].cell_styles) == 0


def test_direct_formats_become_one_provisional_style_named_by_what_differs():
    sheet = rows(
        '<row r="1"><c r="A1" s="1"><v>1</v></c><c r="B1" s="1"><v>2</v></c><c r="C1" s="1"/></row>',
        '<row r="2"><c r="A2" s="1"><v>3</v></c><c r="B2" s="1"><v>4</v></c><c r="C2" s="1"/></row>',
    )
    _, model = book([xf(font=1, fill=2, border=1)], sheet)
    style = model.styles.get(style_of(model, 1, 2))
    assert style.name == "Body text · bold, light grey fill, line below"
    assert style.to_name
    assert style.based_on == "body-text"
    assert style.css == {"font-weight": "bold", "background-color": "#D9D9D9", "border-bottom": "1px solid @text"}
    cell_styles = model.sheets[SheetId("s1")].cell_styles
    assert cell_styles.to_data() == [
        ["box", "range", 0, 0, 1, 2, style.id],
        ["words", "range", 0, 0, 1, 2, style.id],
    ]


def test_a_number_format_becomes_a_named_format_and_part_of_the_style():
    sheet = rows('<row r="1"><c r="A1" s="1"><v>1200</v></c><c r="B1" s="2"><v>0.256</v></c></row>')
    _, model = book([xf(number=164), xf(number=165, font=1)], sheet)
    mwh = model.styles.get(style_of(model, 0, 0))
    assert mwh.name == "Body text · MWh"
    found = model.number_formats.get(model.styles.number_format(mwh.id))
    assert (found.name, found.code, found.to_name) == ("MWh", '#,##0 "MWh"', True)
    share = model.styles.get(style_of(model, 0, 1))
    assert share.name == "Body text · bold, percent, 1 decimal"
    assert model.number_formats.get(share.number_format).code == "0.0%"


def test_a_named_style_keeps_its_name_and_deviations_start_from_it():
    named_xfs = '<xf numFmtId="0" fontId="3" fillId="0" borderId="0"/>'
    named = '<cellStyle name="Heading 1" xfId="1" builtinId="16"/>'
    sheet = rows('<row r="1"><c r="A1" s="1"><v>1</v></c><c r="B1" s="2"><v>2</v></c><c r="C1" s="3"/></row>')
    _, model = book(
        [xf(font=3, parent=1), xf(font=3, fill=2, parent=1), xf(font=0, parent=1)], sheet, named=named,
        named_xfs=named_xfs,
    )  # fmt: skip
    heading = model.styles.get(style_of(model, 0, 0))
    assert (heading.name, heading.to_name, heading.based_on) == ("Heading 1", False, "body-text")
    assert heading.css == {"font-weight": "bold", "font-size": "14pt", "color": "#2F5597"}
    filled = model.styles.get(style_of(model, 0, 1))
    assert (filled.name, filled.based_on, filled.css) == (
        "Heading 1 · light grey fill",
        heading.id,
        {"background-color": "#D9D9D9"},
    )
    plain = model.styles.get(style_of(model, 0, 2))
    assert plain.css == {"font-weight": "normal", "font-size": "10pt", "color": "@text"}
    assert plain.name == "Heading 1 · 10pt, not bold, default text"


def test_a_name_the_workbook_has_already_gets_a_number():
    named = '<cellStyle name="Note" xfId="1" builtinId="10"/>'
    named_xfs = '<xf numFmtId="0" fontId="2" fillId="0" borderId="0"/>'
    _, model = book([xf(font=2, parent=1)], rows('<row r="1"><c r="A1" s="1"/></row>'), named=named,
                    named_xfs=named_xfs)  # fmt: skip
    assert model.styles.get(style_of(model, 0, 0)).name == "Note 2"
    assert model.styles.get("note").name == "Note"


def test_rows_and_columns_with_a_look_become_row_and_column_ranges():
    sheet = '<cols><col min="2" max="3" width="9" style="1" customWidth="1"/></cols>' + rows(
        '<row r="1"><c r="A1"><v>1</v></c><c r="B1" s="0"><v>2</v></c><c r="C1" s="1"><v>3</v></c></row>',
        '<row r="4" s="2" customFormat="1"><c r="B4" s="2"/></row>',
        '<row r="5" s="2" customFormat="1"/>',
    )
    _, model = book([xf(font=1), xf(fill=2)], sheet)
    ranges = model.sheets[SheetId("s1")].cell_styles.to_data()
    bold, filled = style_of(model, 0, 2), style_of(model, 3, 0)
    assert ["words", "column", 0, 1, MAX_ROWS - 1, 2, bold] in ranges
    assert ["words", "row", 3, 0, 4, MAX_COLS - 1, filled] in ranges
    assert ["words", "range", 0, 1, 0, 1, "body-text"] in ranges  # B1 says Normal in a bold column
    assert len(ranges) == 6


def test_what_no_style_holds_is_counted_per_cell():
    rotated = xf(inside='<alignment textRotation="90" horizontal="center"/>')
    sheet = rows('<row r="1"><c r="A1" s="1"><v>1</v></c><c r="B1" s="1"/><c r="C1" s="2"/></row>')
    data, model = book([rotated, xf(fill=3)], sheet)
    assert model.styles.get(style_of(model, 0, 0)).css == {"text-align": "center"}
    losses = xlsx_import_losses(data)
    assert Loss("look", "rotation", 2) in losses
    assert Loss("look", "pattern", 1) in losses


def test_alignment_wrapping_and_indent():
    aligned = xf(inside='<alignment horizontal="right" vertical="center" wrapText="1" indent="2"/>')
    _, model = book([aligned], rows('<row r="1"><c r="A1" s="1"/></row>'))
    style = model.styles.get(style_of(model, 0, 0))
    assert style.css == {
        "text-align": "right",
        "vertical-align": "middle",
        "white-space": "pre-wrap",
        "padding-left": "18pt",
    }
    assert style.name == "Body text · right-aligned, vertically centred, wrapped, …"


def test_an_unknown_number_format_shows_as_general_and_is_counted():
    data, model = book([xf(number=27)], rows('<row r="1"><c r="A1" s="1"><v>5</v></c></row>'))
    assert style_of(model, 0, 0) == "body-text"
    assert Loss("look", "number-format", 1) in xlsx_import_losses(data)


def test_a_sheet_with_more_looks_than_ranges_keeps_the_largest(monkeypatch):
    monkeypatch.setattr(cell_looks, "MAX_STYLE_RANGES", 4)
    sheet = rows(
        '<row r="1"><c r="A1" s="1"/><c r="B1" s="1"/><c r="C1" s="1"/><c r="E1" s="2"/></row>',
        '<row r="2"><c r="A2" s="1"/><c r="B2" s="1"/><c r="C2" s="1"/><c r="G1" s="2"/></row>',
    )
    data, model = book([xf(font=1), xf(fill=2)], sheet)
    assert len(model.sheets[SheetId("s1")].cell_styles) == 4
    assert style_of(model, 1, 2) != "body-text"
    assert Loss("look", "too-many-ranges", 1) in xlsx_import_losses(data)


def test_a_file_without_styles_has_excels_default_look():
    looks = read_looks({})
    assert looks.normal.style["font-family"].startswith("Calibri")
    assert looks.look(3) == looks.normal


@pytest.mark.parametrize(
    ("colour", "word"),
    [
        ("#D9D9D9", "light grey"),
        ("#808080", "grey"),
        ("#FF0000", "red"),
        ("#FFC000", "orange"),
        ("#00B050", "green"),
        ("#1F4E79", "dark blue"),
        ("#FFFFFF", "white"),
        ("#000000", "black"),
        ("#7030A0", "purple"),
        ("@accent/14", "accent"),
        ("transparent", "no"),
    ],
)
def test_a_colour_has_a_word(colour, word):
    assert colour_name(colour) == word


def test_a_tint_lightens_or_darkens_a_theme_colour():
    assert tinted("4472C4", -0.249977111117893) == "2F5597"
    assert tinted("000000", 0.5) == "808080"


def test_taking_away_what_a_parent_sets_writes_how_a_plain_cell_looks():
    parent = {"font-weight": "bold", "border-top": "1px solid @text", "font-size": "10pt"}
    assert difference(parent, {"font-size": "10pt"}) == {"font-weight": "normal", "border-top": "none"}
    assert difference_words({"border-top": "none"}) == ["no border"]
    framed = {f"border-{side}": "2px dashed #808080" for side in ("top", "right", "bottom", "left")}
    assert difference_words(framed) == ["thick dashed grey frame"]
    assert difference_words({"border-bottom": "1px solid @text"}) == ["line below"]


# ------------------------------------------------------------------------------------------------ a new file
def styled_workbook():
    """A workbook with a header row of Header, an input column, a provisional style with a number format."""
    from claudia_computes import NumberFormat, Sheet, WorkbookModel
    from claudia_core import StyleDef

    model = WorkbookModel()
    sheet = Sheet(SheetId("s1"), "Plan")
    model.sheets[sheet.id] = sheet
    model.open_container("s1")
    for (row, col), value in {(0, 0): "Year", (0, 1): "Heat", (1, 0): 2026, (1, 1): 1200.5}.items():
        sheet.cells[(row, col)] = {"t": "text" if isinstance(value, str) else type(value).__name__, "v": value}
    model.number_formats.add(NumberFormat("mwh", "MWh", '#,##0.0 "MWh"'))
    model.styles.add(StyleDef("heat", "Body text · bold, MWh", "imported", "body-text", {"font-weight": "bold"},
                              to_name=True))  # fmt: skip
    model.styles.set_number_format("heat", "mwh")
    for slot in ("box", "words"):
        sheet.cell_styles.replace(slot, "range", (0, 0, 0, 1), [((0, 0, 0, 1), "header")])
        sheet.cell_styles.replace(slot, "range", (1, 1, 1, 1), [((1, 1, 1, 1), "heat")])
        sheet.cell_styles.replace(slot, "column", (0, 3, MAX_ROWS - 1, 3), [((0, 3, MAX_ROWS - 1, 3), "input")])
    model._calculate_loaded()
    return model


def test_a_new_file_has_named_styles_direct_formats_and_number_formats():
    from claudia_computes_io import workbook_to_xlsx
    from openpyxl import load_workbook

    data = workbook_to_xlsx(styled_workbook())
    wb = load_workbook(__import__("io").BytesIO(data))
    ws = wb["Plan"]
    assert ws["A1"].style == "Header" and ws["A1"].font.b
    assert ws["B2"].style == "Normal" and ws["B2"].font.b and ws["B2"].number_format == '#,##0.0 "MWh"'
    assert ws.column_dimensions["D"].fill.fgColor.rgb not in (None, "00000000")
    assert wb._fonts[0].name == "Inter"  # noqa: SLF001 (Body text is Normal)


def test_a_new_file_comes_back_with_the_same_looks():
    from claudia_computes_io import workbook_to_xlsx

    again = xlsx_to_workbook(workbook_to_xlsx(styled_workbook()))
    header = again.styles.get(style_of(again, 0, 0))
    assert (header.name, header.to_name) == ("Header", False)
    heat = again.styles.get(style_of(again, 1, 1))
    assert heat.to_name and heat.css == {"font-weight": "bold"}
    assert again.number_formats.get(again.styles.number_format(heat.id)).code == '#,##0.0 "MWh"'
    assert again.styles.get(style_of(again, 50, 3)).name == "Input"
    assert again.styles.get("body-text").css["font-family"].startswith("Inter")


# ------------------------------------------------------------------------------------------------ the less common
THEME = (
    '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:themeElements><a:clrScheme name="x">'
    '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
    '<a:dk2><a:srgbClr val="0E2841"/></a:dk2><a:lt2><a:srgbClr val="E8E8E8"/></a:lt2>'
    '<a:accent1><a:srgbClr val="156082"/></a:accent1></a:clrScheme></a:themeElements></a:theme>'
)


def unusual_styles() -> bytes:
    fonts = (
        '<font><sz val="11"/><name val="Courier New"/></font>'
        '<font><i/><u val="double"/><strike/><vertAlign val="superscript"/><color theme="4"/><name val="Cambria"/>'
        "</font>"
    )
    fills = (
        '<fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
        '<fill><gradientFill degree="90"><stop position="0"><color rgb="FFFFFFFF"/></stop></gradientFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor indexed="1"/></patternFill></fill>'
    )
    borders = (
        "<border/>"
        '<border><start style="medium"><color theme="1" tint="0.5"/></start><end style="dashDot"/>'
        '<top style="double"><color auto="1"/></top><bottom style="hair"/>'
        '<diagonal style="thin"/></border>'
    )
    xfs = "".join(
        [
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>',
            '<xf numFmtId="44" fontId="1" fillId="2" borderId="1" xfId="0"/>',
            '<xf numFmtId="166" fontId="0" fillId="3" borderId="0" xfId="0">'
            '<alignment horizontal="centerContinuous" vertical="justify" shrinkToFit="1"/></xf>',
            '<xf numFmtId="167" fontId="0" fillId="0" borderId="0" xfId="0"><alignment horizontal="fill"/></xf>',
        ]
    )
    return (
        f'<styleSheet xmlns="{X}"><numFmts><numFmt numFmtId="166" formatCode="[Blue]0.0"/>'
        '<numFmt numFmtId="167" formatCode="GENERAL"/></numFmts>'
        f"<fonts>{fonts}</fonts><fills>{fills}</fills><borders>{borders}</borders>"
        '<cellStyleXfs><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        f"<cellXfs>{xfs}</cellXfs>"
        '<colors><indexedColors><rgbColor rgb="FF000000"/><rgbColor rgb="FFC00000"/></indexedColors></colors>'
        "</styleSheet>"
    ).encode()


def test_the_less_common_parts_of_a_look():
    looks = read_looks({"xl/styles.xml": unusual_styles(), "xl/theme/theme1.xml": THEME.encode()})
    assert looks.normal.style["font-family"] == "'Courier New', 'Liberation Mono', monospace"
    odd = looks.look(1)
    assert odd.style["font-style"] == "italic"
    assert odd.style["text-decoration"] == "underline line-through"
    assert odd.style["color"] == "#156082"  # the file's own theme
    assert odd.style["border-left"] == "2px solid #808080"  # start, the dark text colour half lighter
    assert odd.style["border-right"] == "1px dashed @text"
    assert odd.style["border-top"] == "3px double @text"
    assert odd.style["border-bottom"] == "1px dotted @text"
    assert set(odd.unmapped) == {"double-underline", "superscript", "gradient", "diagonal"}
    assert odd.code.startswith('_("$"* #,##0.00_)')
    filled = looks.look(2)
    assert filled.style["background-color"] == "#C00000"  # the file's own indexed colours
    assert filled.code == "[Blue]0.0"
    assert set(filled.unmapped) == {"center-across", "vertical-spread", "shrink"}
    assert looks.look(3).code == "General" and looks.look(3).unmapped == ("fill",)


def test_names_for_a_deviation_say_what_it_changes():
    words = difference_words(
        {
            "font-family": "Cambria, Caladea, serif",
            "font-style": "normal",
            "text-decoration": "line-through",
            "border-top": "1px solid #000000",
            "white-space": "nowrap",
            "padding-left": "0pt",
        }
    )
    assert words == ["Cambria", "upright", "struck through", "black line above", "not wrapped", "not indented"]
    assert colour_name("#ccc") == "light grey" and colour_name("rgb(255, 0, 0)") == "red"
    assert colour_name("currentcolor") == "currentcolor"


def test_a_long_name_ends_in_an_ellipsis_and_two_equal_names_get_numbers():
    from claudia_computes_io.cell_looks import _provisional

    assert _provisional("Body text", []) == "Body text · changed"
    long = _provisional("A rather long name for a parent style here", ["bold", "italic", "light grey fill"])
    assert long.endswith(", …") and len(long) <= 60
    assert _provisional("x" * 58, ["bold"]) == ("x" * 58 + " · …")[:60]


def test_a_new_file_writes_rows_formats_and_a_style_called_normal():
    import io

    from claudia_computes_io import workbook_to_xlsx
    from openpyxl import load_workbook

    from claudia_core import StyleDef

    model = styled_workbook()
    model.styles.add(StyleDef("normal", "Normal", "a style of that name", "body-text", {"font-style": "italic"}))
    model.styles.set_number_format("normal", "mwh")
    model.styles.add(StyleDef("loud", "Loud", "a shout", "body-text", {"text-decoration": "underline line-through",
                                                                     "padding-left": "18pt", "white-space": "pre-wrap",
                                                                     "text-align": "center"}))  # fmt: skip
    sheet = model.sheets[SheetId("s1")]
    for slot in ("box", "words"):
        sheet.cell_styles.replace(slot, "row", (5, 0, 6, MAX_COLS - 1), [((5, 0, 6, MAX_COLS - 1), "normal")])
        sheet.cell_styles.replace(slot, "range", (8, 0, 8, 0), [((8, 0, 8, 0), "loud")])
    wb = load_workbook(io.BytesIO(workbook_to_xlsx(model)))
    ws = wb["Plan"]
    assert ws.row_dimensions[6].font.i and ws.row_dimensions[7].font.i
    assert "Normal (claudia)" in wb.named_styles
    loud = ws["A9"]
    assert (loud.font.u, loud.font.strike, loud.alignment.indent, loud.alignment.wrap_text) == ("single", True, 2, True)
    assert loud.alignment.horizontal == "center"


def test_a_new_file_leaves_out_what_it_cannot_write_cell_by_cell(monkeypatch):
    from claudia_computes_io import xlsx_export_losses

    monkeypatch.setattr(cell_looks, "MAX_EXPORTED_CELLS", 3)
    model = styled_workbook()
    assert Loss("look", "too-many-cells", 3) in xlsx_export_losses(model)


def test_a_sheet_style_is_every_column():
    from claudia_computes_io.cell_looks import sheet_styling

    model = styled_workbook()
    sheet = model.sheets[SheetId("s1")]
    everything = (0, 0, MAX_ROWS - 1, MAX_COLS - 1)
    sheet.cell_styles.replace("box", "sheet", everything, [(everything, "note")])
    styling = sheet_styling(sheet)
    assert styling.columns[0] == (0, 2, ("note", "body-text"))
    assert styling.columns[1] == (3, 3, ("input", "input"))
    assert styling.columns[2] == (4, MAX_COLS - 1, ("note", "body-text"))


def test_a_default_with_a_format_named_formats_and_looks_twice():
    named_xfs = '<xf numFmtId="164" fontId="0" fillId="0" borderId="0"/>'
    named = '<cellStyle name="Energy" xfId="1"/>'
    xfs = [xf(fill=2), xf(fill=2), xf(number=164, parent=1), xf(number=165)]
    cells = "".join(f'<c r="{c}1" s="{i}"/>' for i, c in enumerate("ABCDE"))
    plain = b'<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
    two_decimals = styles(xfs, named=named, named_xfs=named_xfs).replace(plain, plain.replace(b'"0"', b'"2"', 1), 1)
    data = package({"Plan": rows(f'<row r="1">{cells}</row>')}, extra={"xl/styles.xml": two_decimals})
    model = xlsx_to_workbook(data)
    formats = {f.code: f for f in model.number_formats}
    assert model.styles.number_format("body-text") == formats["0.00"].id
    assert style_of(model, 0, 1) == style_of(model, 0, 2)  # the same look twice is one style
    energy = model.styles.get(style_of(model, 0, 3))
    assert energy.name == "Energy" and model.styles.number_format(energy.id) == formats['#,##0 "MWh"'].id


def test_a_format_id_the_book_has_is_skipped():
    from claudia_computes_io.cell_looks import Look, LookImport

    from claudia_computes import NumberFormat, WorkbookModel

    model = WorkbookModel()
    model.number_formats.add(NumberFormat("format-1", "Taken", "0"))
    making = LookImport(model, Look.of({}))
    assert making.format_id("0.0") == "format-2"
    assert making.format_id("0.0") == "format-2"
