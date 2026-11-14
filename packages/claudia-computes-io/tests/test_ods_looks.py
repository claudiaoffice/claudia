"""The look of an ods file's cells comes in as styles and named number formats, as an xlsx file's does (E6.14,
D378, D379); and a number style and an Excel code are the same thing written two ways."""

from __future__ import annotations

import pytest
from claudia_computes_io import ods_import_losses, ods_to_workbook
from claudia_computes_io.odf_numbers import code_of, number_style
from lxml import etree
from test_ods import DECLS, HEAD, cell, num, row, table

from claudia_computes import SheetId
from claudia_computes.limits import MAX_ROWS
from claudia_odf_io import NS, new_package

STYLES = """
<style:default-style style:family="table-cell">
  <style:text-properties style:font-name="Liberation Sans" fo:font-size="10pt"/>
</style:default-style>
<style:style style:name="Default" style:family="table-cell"/>
<style:style style:name="Heading" style:family="table-cell" style:parent-style-name="Default">
  <style:text-properties fo:font-weight="bold" fo:font-size="14pt"/>
</style:style>
<number:currency-style style:name="N1P0"><number:number number:decimal-places="2" number:min-decimal-places="2"
  number:min-integer-digits="1" number:grouping="true"/><number:text> </number:text>
  <number:currency-symbol>€</number:currency-symbol></number:currency-style>
<number:currency-style style:name="N1"><style:text-properties fo:color="#ff0000"/><number:text>-</number:text>
  <number:number number:decimal-places="2" number:min-decimal-places="2" number:min-integer-digits="1"
  number:grouping="true"/><number:text> </number:text><number:currency-symbol>€</number:currency-symbol>
  <style:map style:condition="value()&gt;=0" style:apply-style-name="N1P0"/></number:currency-style>
<number:date-style style:name="N2"><number:day number:style="long"/><number:text>.</number:text>
  <number:month number:style="long"/><number:text>.</number:text><number:year number:style="long"/></number:date-style>
"""
FONTS = '<style:font-face style:name="Liberation Sans" svg:font-family="&apos;Liberation Sans&apos;"/>'
AUTOMATIC = """
<style:style style:name="ce1" style:family="table-cell" style:parent-style-name="Default">
  <style:table-cell-properties fo:background-color="#dddddd" fo:border-bottom="0.74pt solid #000000"
    style:text-align-source="fix"/>
  <style:paragraph-properties fo:text-align="center"/>
  <style:text-properties fo:font-weight="bold"/>
</style:style>
<style:style style:name="ce2" style:family="table-cell" style:parent-style-name="Heading">
  <style:text-properties fo:color="#ff0000"/>
</style:style>
<style:style style:name="ce3" style:family="table-cell" style:parent-style-name="Default" style:data-style-name="N1"/>
<style:style style:name="ce4" style:family="table-cell" style:parent-style-name="Default" style:data-style-name="N2"/>
<style:style style:name="ce5" style:family="table-cell" style:parent-style-name="Default">
  <style:table-cell-properties style:rotation-angle="90"/>
</style:style>
"""


def an_ods(*tables: str) -> bytes:
    content = (
        f'{HEAD}<office:document-content {DECLS} office:version="1.3"><office:font-face-decls>{FONTS}'
        f"</office:font-face-decls><office:automatic-styles>{AUTOMATIC}</office:automatic-styles><office:body>"
        f"<office:spreadsheet>{''.join(tables)}</office:spreadsheet></office:body></office:document-content>"
    )
    styles = (
        f'{HEAD}<office:document-styles {DECLS} office:version="1.3"><office:font-face-decls>{FONTS}'
        f"</office:font-face-decls><office:styles>{STYLES}</office:styles></office:document-styles>"
    )
    return new_package("spreadsheet", content.encode(), styles.encode())


def style_of(model, row: int, col: int) -> str:
    return model.sheets[SheetId("s1")].cell_styles.style_at(row, col, "words")[0]


def test_the_default_cell_style_becomes_body_text():
    model = ods_to_workbook(an_ods(table("Data", row(num(1)))))
    body = model.styles.get("body-text").css
    assert (body["font-family"], body["font-size"]) == ("'Liberation Sans', sans-serif", "10pt")
    assert style_of(model, 0, 0) == "body-text"


def test_an_automatic_style_is_a_provisional_style_and_a_named_one_keeps_its_name():
    model = ods_to_workbook(
        an_ods(table("Data", row(num(1, extra=' table:style-name="ce1"'), num(2, extra=' table:style-name="ce2"'))))
    )
    direct = model.styles.get(style_of(model, 0, 0))
    assert direct.name == "Body text · bold, light grey fill, black line below, …"
    assert direct.css["text-align"] == "center"
    assert direct.css["border-bottom"] == "1px solid #000000"
    red = model.styles.get(style_of(model, 0, 1))
    assert red.name == "Heading · red text"
    heading = model.styles.get(red.based_on)
    assert (heading.name, heading.to_name, heading.css) == (
        "Heading",
        False,
        {"font-weight": "bold", "font-size": "14pt"},
    )


def test_number_styles_become_named_formats_and_dates_show_as_dates():
    date = cell('table:style-name="ce4" office:value-type="date" office:date-value="2026-11-13"')
    bare = cell('office:value-type="date" office:date-value="2026-11-13"')
    data = an_ods(table("Data", row(num(-3.5, extra=' table:style-name="ce3"'), date, bare)))
    model = ods_to_workbook(data)
    money = model.number_formats.get(model.styles.number_format(style_of(model, 0, 0)))
    assert money.code == '#,##0.00 "€";[Red]-#,##0.00 "€"'
    assert model.number_formats.get(model.styles.number_format(style_of(model, 0, 1))).code == "dd.mm.yyyy"
    losses = {(loss.kind, loss.detail): loss.count for loss in ods_import_losses(data)}
    assert losses[("date", "")] == 1  # only the date without a date style


def test_column_and_row_styles_and_long_runs():
    columns = (
        '<table:table-column table:default-cell-style-name="Default"/>'
        '<table:table-column table:number-columns-repeated="2" table:default-cell-style-name="ce1"/>'
    )
    rows = (
        row(num(1), num(2, extra=' table:style-name="Default"'))
        + '<table:table-row table:default-cell-style-name="ce2"><table:table-cell/></table:table-row>'
        + row(cell('table:style-name="ce2" table:number-columns-repeated="3"'), repeat=40)
    )
    data = an_ods(table("Data", rows, columns))
    model = ods_to_workbook(data)
    ranges = model.sheets[SheetId("s1")].cell_styles.to_data()
    boxed, red = style_of(model, 50, 1), style_of(model, 1, 0)
    assert ["words", "column", 0, 1, MAX_ROWS - 1, 2, boxed] in ranges
    assert ["words", "range", 0, 1, 0, 1, "body-text"] in ranges  # B1 says Default in a styled column
    assert ["words", "row", 1, 0, 1, 16383, red] in ranges
    assert ["words", "range", 2, 0, 41, 2, red] in ranges  # 120 cells of one run: one range


def test_what_no_style_holds_is_counted_per_cell():
    data = an_ods(table("Data", row(cell('table:style-name="ce5" table:number-columns-repeated="2"'))))
    losses = {(loss.kind, loss.detail): loss.count for loss in ods_import_losses(data)}
    assert losses[("look", "rotation")] == 2


@pytest.mark.parametrize(
    "code",
    [
        "0",
        "0.00",
        "#,##0",
        "#,##0.00;[Red]-#,##0.00",
        "0.0%",
        "0.00E+00",
        "# ?/?",
        "@",
        "dd.mm.yyyy",
        "d/m/yy",
        "mmmm yyyy",
        "dddd, d. mmmm",
        "hh:mm",
        "[h]:mm:ss",
        "h:mm AM/PM",
        "hh:mm:ss.00",
        '#,##0" MWh"',
        '0" MWh";-0" MWh";"–"',
    ],
)
def test_a_code_goes_to_a_number_style_and_back(code):
    elements = number_style(code, "N7")
    names = {element.get(f"{{{NS['style']}}}name"): element for element in elements}
    assert code_of(elements[-1], names) == code
    for element in elements:  # the parts are the ones ODF has
        assert etree.QName(element).namespace == NS["number"]


def test_a_number_style_for_every_number_and_one_for_text_are_two_sections():
    numbers = etree.fromstring(
        f'<number:date-style {DECLS} style:name="N9P0"><number:month number:style="long" number:textual="true"/>'
        "<number:text> </number:text><number:year/></number:date-style>"
    )
    words = etree.fromstring(
        f'<number:text-style {DECLS} style:name="N9"><number:text-content/>'
        '<style:map style:condition="value()&lt;=1.7976931348623157E+308" style:apply-style-name="N9P0"/>'
        "</number:text-style>"
    )
    assert code_of(words, {"N9P0": numbers, "N9": words}) == "mmmm yy;@"


def test_a_new_file_has_a_default_style_named_styles_and_automatic_ones_and_comes_back():
    from claudia_computes_io import workbook_to_ods
    from test_xlsx_looks import styled_workbook

    from claudia_opc_io import read_parts

    data = workbook_to_ods(styled_workbook())
    parts = read_parts(data)
    styles, content = parts["styles.xml"].decode(), parts["content.xml"].decode()
    assert 'style:name="Default"' in styles and 'style:display-name="Header"' in styles
    assert 'table:default-cell-style-name="ce' in content and "number:number-style" in content
    again = ods_to_workbook(data)
    header = again.styles.get(style_of(again, 0, 0))
    assert (header.name, header.to_name) == ("Header", False)
    heat = again.styles.get(style_of(again, 1, 1))
    assert heat.to_name and heat.css == {"font-weight": "bold"}
    assert again.number_formats.get(again.styles.number_format(heat.id)).code == '#,##0.0" MWh"'
    assert again.styles.get(style_of(again, 50, 3)).name == "Input"


def test_the_less_common_parts_of_an_ods_look():
    from claudia_computes_io.ods_looks import read_looks

    automatic = """
    <style:style style:name="odd" style:family="table-cell">
      <style:table-cell-properties fo:border="2.5pt dotted #ff0000" fo:diagonal-bl-tr="0.74pt solid #000000"
        style:shrink-to-fit="true" style:repeat-content="true" style:vertical-align="top" fo:wrap-option="wrap"
        style:text-align-source="value-type"/>
      <style:paragraph-properties fo:text-align="end" fo:margin-left="0.5cm"/>
      <style:text-properties fo:font-family="'Times New Roman'" fo:font-weight="700" fo:font-style="italic"
        style:text-underline-style="solid" style:text-underline-type="double" style:text-line-through-style="solid"
        style:text-position="super 58%" fo:color="#00ff00" style:use-window-font-color="true"/>
    </style:style>
    <number:number-style style:name="bad"><number:text>[</number:text></number:number-style>
    <style:style style:name="worse" style:family="table-cell" style:data-style-name="bad"/>
    <style:style style:name="loop" style:family="table-cell" style:parent-style-name="loop"/>
    """
    content = etree.fromstring(
        f"<office:document-content {DECLS}><office:automatic-styles>{automatic}</office:automatic-styles>"
        "</office:document-content>"
    )
    looks = read_looks({}, content)
    _, odd = looks.look("odd")
    css = odd.style
    assert css["font-family"] == "'Times New Roman', 'Liberation Serif', serif"
    assert (css["font-weight"], css["font-style"]) == ("bold", "italic")
    assert css["text-decoration"] == "underline line-through"
    assert "color" not in css  # the window's text colour
    assert css["border-top"] == "3px dotted #ff0000"
    assert (css["vertical-align"], css["white-space"], css["padding-left"]) == ("top", "pre-wrap", "14.2pt")
    assert "text-align" not in css  # aligned by what the cell holds
    assert set(odd.unmapped) == {"diagonal", "shrink", "fill", "double-underline", "superscript"}
    assert looks.look("worse")[1].code in ("General", '"["')
    assert looks.look("loop")[0] is None
    assert looks.look("missing") == (None, looks.normal)


def test_a_new_ods_writes_marks_wrapping_indent_and_frames():
    from claudia_computes_io import workbook_to_ods
    from test_xlsx_looks import styled_workbook

    from claudia_core import StyleDef
    from claudia_opc_io import read_parts

    model = styled_workbook()
    model.styles.add(StyleDef("loud", "Loud", "a shout", "body-text", {
        "text-decoration": "underline line-through", "padding-left": "18pt", "white-space": "pre-wrap",
        "text-align": "right", "vertical-align": "top", "border-top": "2px dashed rgba(0, 0, 0, 0.5)",
        "font-family": "'Liberation Sans', sans-serif"}))  # fmt: skip
    sheet = model.sheets[SheetId("s1")]
    for slot in ("box", "words"):
        sheet.cell_styles.replace(slot, "range", (8, 0, 8, 0), [((8, 0, 8, 0), "loud")])
    content = read_parts(workbook_to_ods(model))["content.xml"].decode()
    for part in ('style:text-underline-style="solid"', 'style:text-line-through-style="solid"',
                 'fo:margin-left="18pt"', 'fo:wrap-option="wrap"', 'fo:text-align="end"', 'style:vertical-align="top"',
                 'fo:border-top="1.5pt dashed #808080"', "fo:font-family=\"'Liberation Sans'\""):  # fmt: skip
        assert part in content
    again = ods_to_workbook(workbook_to_ods(model))
    assert again.styles.get(style_of(again, 8, 0)).name == "Loud"


@pytest.mark.parametrize(
    ("maps", "code"),
    [
        ('<style:map style:condition="value()&lt;0" style:apply-style-name="M1"/>', "0;[Red]0"),
        ('<style:map style:condition="value()&gt;100" style:apply-style-name="M1"/>', "[>100][Red]0;0"),
        ('<style:map style:condition="value()&lt;=lots" style:apply-style-name="M1"/>', "[<=lots][Red]0;0"),
        ('<style:map style:condition="value()&gt;=0" style:apply-style-name="nowhere"/>', "0"),
    ],
)
def test_maps_of_a_number_style_become_sections(maps, code):
    other = etree.fromstring(
        f'<number:number-style {DECLS} style:name="M1"><style:text-properties fo:color="#ff0000"/>'
        '<number:number number:min-integer-digits="1"/></number:number-style>'
    )
    own = etree.fromstring(
        f'<number:number-style {DECLS} style:name="M0"><number:number number:min-integer-digits="1"/>{maps}'
        "</number:number-style>"
    )
    assert code_of(own, {"M0": own, "M1": other}) == code


@pytest.mark.parametrize(
    ("code", "back"),
    [
        ("[>100]0;0", "[>100]0;0"),
        ("# ?/4", "# ?/4"),
        ('0.0E+00 "m"', '0.0E+00" m"'),
        ("General", "General"),
        ("0\\%", '0"%"'),
    ],
)
def test_more_codes_through_a_number_style(code, back):
    elements = number_style(code, "N8")
    names = {element.get(f"{{{NS['style']}}}name"): element for element in elements}
    assert code_of(elements[-1], names) == back
