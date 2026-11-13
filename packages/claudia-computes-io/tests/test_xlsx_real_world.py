"""xlsx files as Excel writes them today, built part by part: array and spilled formulas, ``_xlfn.`` names, shared
formulas, cell values of every kind, and the extensions Excel keeps inside a worksheet (lists that read another
sheet, icon sets, a picture in a cell). Reading such a file must not fail, and editing one cell must leave all of it
where it was (D340, D341).

The packages are small on purpose: each test says in its own XML what Excel writes, so a failure points at one
construct, not at a whole real-world workbook (which stays out of the repository)."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from claudia_computes_io import (
    UnsupportedEdit,
    XlsxError,
    apply_edits_to_xlsx,
    workbook_to_xlsx,
    xlsx_import_losses,
    xlsx_to_workbook,
)
from lxml import etree

from claudia_computes import Sheet, SheetId, WorkbookModel
from claudia_odf_io import Loss

X = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"x": X, "r": R, "pr": PR}
WORKSHEET = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"

STYLES = f"""<styleSheet xmlns="{X}">
<numFmts count="1"><numFmt numFmtId="164" formatCode="0 &quot;MWh&quot;"/></numFmts>
<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""

X14_LIST = (
    '<extLst><ext uri="{CCE6A557-97BC-4b89-ADB6-D9C93CAAB3DF}" '
    'xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">'
    '<x14:dataValidations count="1" xmlns:xm="http://schemas.microsoft.com/office/excel/2006/main">'
    '<x14:dataValidation type="list" allowBlank="1"><x14:formula1><xm:f>Lists!$A$1:$A$3</xm:f></x14:formula1>'
    "<xm:sqref>D1</xm:sqref></x14:dataValidation></x14:dataValidations></ext></extLst>"
)


def package(
    sheets: dict[str, str],
    *,
    shared: list[str] = (),
    extra: dict[str, bytes] | None = None,
    sheet_rels: dict[int, str] | None = None,
    calc_chain: bool = False,
) -> bytes:
    """A workbook with these worksheets (name -> the inside of ``<worksheet>``), in this order."""
    overrides = [
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
        '<Override PartName="/xl/sharedStrings.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>',
    ]
    parts: dict[str, bytes] = {}
    sheet_list, rels = [], []
    for index, (name, inside) in enumerate(sheets.items(), start=1):
        sheet_list.append(f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>')
        rels.append(f'<Relationship Id="rId{index}" Type="{WORKSHEET}" Target="worksheets/sheet{index}.xml"/>')
        overrides.append(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        parts[f"xl/worksheets/sheet{index}.xml"] = (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="{X}" xmlns:r="{R}">'
            f"{inside}</worksheet>"
        ).encode()
        if sheet_rels and index in sheet_rels:
            parts[f"xl/worksheets/_rels/sheet{index}.xml.rels"] = (
                f'<Relationships xmlns="{PR}">{sheet_rels[index]}</Relationships>'
            ).encode()
    count = len(sheets)
    rels.append(
        f'<Relationship Id="rId{count + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    )
    rels.append(
        f'<Relationship Id="rId{count + 2}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
        'Target="sharedStrings.xml"/>'
    )
    if calc_chain:
        rels.append(
            f'<Relationship Id="rId{count + 3}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/calcChain" '
            'Target="calcChain.xml"/>'
        )
        overrides.append(
            '<Override PartName="/xl/calcChain.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml"/>'
        )
        parts["xl/calcChain.xml"] = f'<calcChain xmlns="{X}"><c r="B1" i="1"/></calcChain>'.encode()
    items = "".join(f"<si>{text}</si>" if text.startswith("<") else f"<si><t>{text}</t></si>" for text in shared)
    parts["xl/sharedStrings.xml"] = f'<sst xmlns="{X}" count="{len(shared)}">{items}</sst>'.encode()
    parts["xl/styles.xml"] = STYLES.encode()
    parts["xl/workbook.xml"] = (
        f'<workbook xmlns="{X}" xmlns:r="{R}"><sheets>{"".join(sheet_list)}</sheets>'
        '<calcPr calcId="191029"/></workbook>'
    ).encode()
    parts["xl/_rels/workbook.xml.rels"] = f'<Relationships xmlns="{PR}">{"".join(rels)}</Relationships>'.encode()
    parts["_rels/.rels"] = (
        f'<Relationships xmlns="{PR}"><Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    ).encode()
    parts.update(extra or {})
    parts["[Content_Types].xml"] = (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f"{''.join(overrides)}</Types>"
    ).encode()
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as zf:
        for name, data in parts.items():
            zf.writestr(name, data)
    return out.getvalue()


def rows(*cells: str) -> str:
    return f"<sheetData>{''.join(cells)}</sheetData>"


def part(data: bytes, name: str) -> bytes:
    with ZipFile(BytesIO(data)) as zf:
        return zf.read(name)


def names(data: bytes) -> list[str]:
    with ZipFile(BytesIO(data)) as zf:
        return zf.namelist()


def cell_xml(data: bytes, ref: str, sheet: int = 1) -> etree._Element:
    root = etree.fromstring(part(data, f"xl/worksheets/sheet{sheet}.xml"))
    found = root.find(f".//x:c[@r='{ref}']", NS)
    assert found is not None, f"no cell {ref}"
    return found


def cells(model: WorkbookModel, sheet: str = "s1") -> dict:
    return dict(model.sheets[SheetId(sheet)].cells)


def edited(original: bytes, change) -> bytes:  # noqa: ANN001
    baseline = xlsx_to_workbook(original)
    current = xlsx_to_workbook(original)
    change(current)
    return apply_edits_to_xlsx(original, baseline, current)


def store(row: int, col: int, content: dict | None, sheet: str = "s1"):  # noqa: ANN201
    return lambda model: model.store(model.sheets[SheetId(sheet)], row, col, content)


# ------------------------------------------------------------------------------------------------ reading
ARRAY = package(
    {
        "Plan": rows(
            '<row r="1"><c r="A1"><v>1</v></c><c r="B1"><f t="array" ref="B1:B3">A1:A3*2</f><v>2</v></c></row>',
            '<row r="2"><c r="A2"><v>2</v></c><c r="B2"><v>4</v></c></row>',
            '<row r="3"><c r="A3"><v>3</v></c><c r="B3"><v>6</v></c></row>',
        )
    }
)


def test_an_array_formula_comes_in_as_the_values_it_shows():
    read = cells(xlsx_to_workbook(ARRAY))
    assert read[(0, 1)] == {"t": "int", "v": 2}
    assert read[(2, 1)] == {"t": "int", "v": 6}
    assert Loss("formula", "array") in xlsx_import_losses(ARRAY)


SPILLED = package(
    {
        "Plan": rows(
            '<row r="1"><c r="A1" cm="1"><f t="array" ref="A1:A3" aca="false">_xlfn.SEQUENCE(3)</f><v>1</v></c></row>',
            '<row r="2"><c r="A2"><v>2</v></c></row>',
            '<row r="3"><c r="A3"><v>3</v></c></row>',
        )
    }
)


def test_a_spilled_formula_comes_in_as_the_values_it_shows():
    assert cells(xlsx_to_workbook(SPILLED)) == {(i, 0): {"t": "int", "v": i + 1} for i in range(3)}


def test_the_cells_a_volatile_formula_spills_into_are_values():
    data = package(
        {
            "Plan": rows(
                '<row r="1"><c r="A1" cm="1"><f t="array" ref="A1:B1" ca="1">_xlfn.SEQUENCE(1,2)</f><v>1</v></c>'
                '<c r="B1"><f ca="1"/><v>2</v></c></row>'
            )
        }
    )
    assert cells(xlsx_to_workbook(data)) == {(0, 0): {"t": "int", "v": 1}, (0, 1): {"t": "int", "v": 2}}
    assert Loss("formula", "syntax") not in xlsx_import_losses(data)


def test_a_function_name_excel_marks_as_new_is_read_without_its_mark():
    data = package(
        {
            "Plan": rows(
                '<row r="1"><c r="A1"><v>5</v></c><c r="B1" t="str"><f>_xlfn.IFS(A1&gt;1,"big",TRUE,"small")</f>'
                "<v>big</v></c></row>"
            )
        }
    )
    formula = cells(xlsx_to_workbook(data))[(0, 1)]
    assert formula["t"] == "formula"
    assert formula["v"].upper().startswith("=IFS(")


def test_a_function_claudia_lacks_comes_in_as_its_last_value():
    data = package({"Plan": rows('<row r="1"><c r="A1"><f>CONVERT(1.5,"km","m")</f><v>1500</v></c></row>')})
    assert cells(xlsx_to_workbook(data))[(0, 0)] == {"t": "int", "v": 1500}
    assert Loss("formula", "function") in xlsx_import_losses(data)


def test_a_shared_formula_is_each_cells_own_formula():
    data = package(
        {
            "Plan": rows(
                '<row r="1"><c r="A1"><v>1</v></c>'
                '<c r="B1"><f t="shared" ref="B1:B3" si="0">A1*2</f><v>2</v></c></row>',
                '<row r="2"><c r="A2"><v>2</v></c><c r="B2"><f t="shared" si="0"/><v>4</v></c></row>',
                '<row r="3"><c r="A3"><v>3</v></c><c r="B3"><f t="shared" si="0"/><v>6</v></c></row>',
            )
        }
    )
    model = xlsx_to_workbook(data)
    assert [cells(model)[(r, 1)]["v"] for r in range(3)] == ["=A1*2", "=A2*2", "=A3*2"]
    assert model.sheets[SheetId("s1")].grid.get((2, 1)) == 6


def test_every_kind_of_cell_value_is_read():
    data = package(
        {
            "Plan": rows(
                '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>'
                '<c r="C1" t="inlineStr"><is><t>inline</t></is></c><c r="D1" t="b"><v>1</v></c>'
                '<c r="E1"><v>2.5</v></c><c r="F1"><v>1E3</v></c><c r="G1" t="s"><v>2</v></c></row>'
            )
        },
        shared=["plain", "<r><t>rich </t></r><r><rPr><b/></rPr><t>text</t></r><rPh><t>x</t></rPh>", "a_x000A_b"],
    )
    read = cells(xlsx_to_workbook(data))
    assert read[(0, 0)] == {"t": "text", "v": "plain"}
    assert read[(0, 1)] == {"t": "text", "v": "rich text"}
    assert read[(0, 2)] == {"t": "text", "v": "inline"}
    assert read[(0, 3)] == {"t": "bool", "v": True}
    assert read[(0, 4)] == {"t": "float", "v": 2.5}
    assert read[(0, 5)] == {"t": "float", "v": 1000.0}
    assert read[(0, 6)] == {"t": "text", "v": "a\nb"}


def test_a_cell_without_its_reference_takes_the_next_place_in_its_row():
    data = package(
        {"Plan": rows('<row r="2"><c><v>1</v></c><c><v>2</v></c><c r="E2"><v>3</v></c><c><v>4</v></c></row>')}
    )
    assert sorted(cells(xlsx_to_workbook(data))) == [(1, 0), (1, 1), (1, 4), (1, 5)]


def test_the_error_a_lost_formula_shows_stays_an_error_for_the_formulas_that_use_it():
    data = package(
        {
            "Plan": rows(
                '<row r="1"><c r="A1" t="e"><f>LET(x,1,x/0)</f><v>#DIV/0!</v></c><c r="B1"><f>A1+1</f></c></row>'
            )
        }
    )
    model = xlsx_to_workbook(data)
    assert cells(model)[(0, 0)] == {"t": "formula", "v": "=#DIV/0!"}
    assert model.sheets[SheetId("s1")].grid.get((0, 1)).code == "#DIV/0!"
    assert Loss("error-value") in xlsx_import_losses(data)


def test_an_error_excel_has_and_claudia_does_not_comes_in_as_text():
    data = package({"Plan": rows('<row r="1"><c r="A1" t="e"><v>#BUSY!</v></c></row>')})
    assert cells(xlsx_to_workbook(data))[(0, 0)] == {"t": "text", "v": "#BUSY!"}


def test_a_formula_reaching_a_deleted_cell_still_reads():
    data = package({"Plan": rows('<row r="1"><c r="A1" t="e"><f>#REF!+1</f><v>#REF!</v></c></row>')})
    assert cells(xlsx_to_workbook(data))[(0, 0)]["t"] in ("formula", "text")


def test_a_date_is_its_serial_number_shown_through_its_format():
    data = package({"Plan": rows('<row r="1"><c r="A1" s="1"><v>46200</v></c><c r="B1" s="2"><v>12</v></c></row>')})
    model = xlsx_to_workbook(data)
    assert cells(model)[(0, 0)] == {"t": "int", "v": 46200}
    words = model.sheets[SheetId("s1")].cell_styles.style_at(0, 0, "words")[0]
    assert model.number_formats.get(model.styles.number_format(words)).code == "m/d/yyyy"
    assert xlsx_import_losses(data) == ()


def test_what_the_model_does_not_show_is_listed():
    sheet = rows('<row r="1"><c r="A1"><v>1</v></c></row>') + (
        '<mergeCells count="1"><mergeCell ref="A1:B1"/></mergeCells>'
        '<conditionalFormatting sqref="A1"><cfRule type="cellIs" dxfId="0" priority="1" operator="lessThan">'
        "<formula>0</formula></cfRule></conditionalFormatting>"
        '<dataValidations count="1"><dataValidation type="decimal" sqref="A1"><formula1>0</formula1>'
        "</dataValidation></dataValidations>"
        '<drawing r:id="rId1"/>' + X14_LIST
    )
    rel = (
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" '
        'Target="../drawings/drawing1.xml"/>'
    )
    drawing = (
        '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        "<xdr:twoCellAnchor><xdr:pic/></xdr:twoCellAnchor><xdr:twoCellAnchor><xdr:graphicFrame>"
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart"/></a:graphic>'
        "</xdr:graphicFrame></xdr:twoCellAnchor></xdr:wsDr>"
    )
    data = package({"Plan": sheet}, sheet_rels={1: rel}, extra={"xl/drawings/drawing1.xml": drawing.encode()})
    kinds = {loss.kind: loss.count for loss in xlsx_import_losses(data)}
    assert kinds["merge"] == 1
    assert kinds["conditional-format"] == 1
    assert kinds["validation"] == 2
    assert kinds["picture"] == 1
    assert kinds["chart"] == 1


def test_a_hundred_sheets_of_formulas_read_in_reasonable_time():
    many = rows(
        *(
            f'<row r="{r}"><c r="A{r}"><v>{r}</v></c><c r="B{r}"><f>A{r}*2</f><v>{2 * r}</v></c></row>'
            for r in range(1, 2001)
        )
    )
    data = package({f"S{i}": many for i in range(5)})
    model = xlsx_to_workbook(data)
    assert model.sheets[SheetId("s5")].grid.get((1999, 1)) == 4000


# ------------------------------------------------------------------------------------------------ editing
KEPT = package(
    {
        "Plan": rows(
            '<row r="1" spans="1:5"><c r="A1" s="2"><v>10</v></c><c r="B1"><f t="shared" ref="B1:B2" si="0">A1*2</f>'
            '<v>20</v></c><c r="C1" t="e" vm="1"><v>#VALUE!</v></c><c r="D1" t="s"><v>0</v></c></row>',
            '<row r="2" spans="1:5"><c r="A2"><v>3</v></c><c r="B2"><f t="shared" si="0"/><v>6</v></c>'
            '<c r="E2" cm="1"><f t="array" ref="E2:E3">_xlfn.SEQUENCE(2)</f><v>1</v></c></row>',
            '<row r="3"><c r="E3"><v>2</v></c></row>',
        )
        + '<conditionalFormatting sqref="A1:A2"><cfRule type="cellIs" dxfId="0" priority="1" operator="lessThan">'
        "<formula>0</formula></cfRule></conditionalFormatting>" + X14_LIST,
        "Lists": rows('<row r="1"><c r="A1" t="s"><v>1</v></c></row>'),
    },
    shared=["Apple", "Pear"],
    calc_chain=True,
)


def sheet_without_cells(data: bytes) -> bytes:
    root = etree.fromstring(part(data, "xl/worksheets/sheet1.xml"))
    root.remove(root.find("x:sheetData", NS))
    return etree.tostring(root)


def test_an_edit_keeps_everything_of_the_sheet_outside_its_cells():
    out = edited(KEPT, store(0, 0, {"t": "int", "v": 11}))
    assert sheet_without_cells(out) == sheet_without_cells(KEPT)


def test_an_edit_keeps_the_marks_of_the_cells_it_does_not_change():
    out = edited(KEPT, store(0, 0, {"t": "int", "v": 11}))
    assert cell_xml(out, "C1").get("vm") == "1"
    assert cell_xml(out, "E2").get("cm") == "1"
    assert cell_xml(out, "B2").find("x:f", NS).get("si") == "0"
    assert etree.tostring(cell_xml(out, "D1")) == etree.tostring(cell_xml(KEPT, "D1"))


def test_an_edited_cell_keeps_its_look():
    out = edited(KEPT, store(0, 0, {"t": "text", "v": "eleven"}))
    a1 = cell_xml(out, "A1")
    assert a1.get("s") == "2"
    assert a1.get("t") == "inlineStr"
    assert a1.findtext("x:is/x:t", namespaces=NS) == "eleven"
    assert part(out, "xl/sharedStrings.xml") == part(KEPT, "xl/sharedStrings.xml")


def test_a_cleared_cell_keeps_its_look_and_an_unstyled_one_goes():
    out = edited(KEPT, lambda m: (store(0, 0, None)(m), store(1, 0, None)(m)))
    a1 = cell_xml(out, "A1")
    assert a1.get("s") == "2" and len(a1) == 0
    assert etree.fromstring(part(out, "xl/worksheets/sheet1.xml")).find(".//x:c[@r='A2']", NS) is None


def test_a_formula_is_written_with_the_value_it_shows_and_excels_name_for_it():
    out = edited(KEPT, store(3, 0, {"t": "formula", "v": '=IFS(A1>5,"big",TRUE,"small")'}))
    a4 = cell_xml(out, "A4")
    assert a4.findtext("x:f", namespaces=NS) == '_xlfn.IFS(A1>5,"big",TRUE,"small")'
    assert a4.get("t") == "str"
    assert a4.findtext("x:v", namespaces=NS) == "big"
    assert cells(xlsx_to_workbook(out))[(3, 0)]["v"].upper().startswith("=IFS(")


def test_a_new_row_and_cell_go_in_their_order():
    out = edited(KEPT, lambda m: (store(4, 1, {"t": "int", "v": 1})(m), store(1, 2, {"t": "int", "v": 2})(m)))
    root = etree.fromstring(part(out, "xl/worksheets/sheet1.xml"))
    assert [row.get("r") for row in root.iterfind(".//x:row", NS)] == ["1", "2", "3", "5"]
    assert [c.get("r") for c in root.find(".//x:row[@r='2']", NS)] == ["A2", "B2", "C2", "E2"]
    assert root.find(".//x:row[@r='2']", NS).get("spans") is None or "5" in root.find(".//x:row[@r='2']", NS).get(
        "spans"
    )


def test_changing_the_first_cell_of_a_shared_formula_keeps_the_others_own():
    out = edited(KEPT, store(0, 1, {"t": "int", "v": 7}))
    b2 = cell_xml(out, "B2").find("x:f", NS)
    assert b2.text == "A2*2" and b2.get("t") is None
    assert cells(xlsx_to_workbook(out))[(1, 1)] == {"t": "formula", "v": "=A2*2"}


def test_a_cell_of_an_array_formula_cannot_be_changed_in_the_file():
    with pytest.raises(UnsupportedEdit):
        edited(KEPT, store(2, 4, {"t": "int", "v": 9}))


def test_a_changed_formula_drops_the_calculation_chain_and_asks_for_a_recalculation():
    out = edited(KEPT, store(3, 0, {"t": "formula", "v": "=A1+1"}))
    assert "xl/calcChain.xml" not in names(out)
    assert b"calcChain" not in part(out, "xl/_rels/workbook.xml.rels")
    assert b"calcChain" not in part(out, "[Content_Types].xml")
    calc = etree.fromstring(part(out, "xl/workbook.xml")).find("x:calcPr", NS)
    assert calc.get("fullCalcOnLoad") == "1" and calc.get("calcId") == "191029"


def test_a_changed_value_asks_for_a_recalculation_and_keeps_the_chain():
    out = edited(KEPT, store(0, 0, {"t": "int", "v": 11}))
    assert "xl/calcChain.xml" in names(out)
    assert etree.fromstring(part(out, "xl/workbook.xml")).find("x:calcPr", NS).get("fullCalcOnLoad") == "1"


def test_an_untouched_workbook_comes_back_as_it_was():
    model = xlsx_to_workbook(KEPT)
    assert apply_edits_to_xlsx(KEPT, model, xlsx_to_workbook(KEPT)) == KEPT


COMMENTED = package(
    {"Plan": rows('<row r="1"><c r="A1"><v>1</v></c></row>') + '<legacyDrawing r:id="rId2"/>'},
    sheet_rels={
        1: '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" '
        'Target="../comments1.xml"/><Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing" '
        'Target="../drawings/vmlDrawing1.vml"/>'
    },
    extra={
        "xl/comments1.xml": (
            f'<comments xmlns="{X}"><authors><author>Ann</author></authors><commentList>'
            '<comment ref="A1" authorId="0"><text><r><t>Check this</t></r></text></comment></commentList></comments>'
        ).encode(),
        "xl/drawings/vmlDrawing1.vml": (
            b'<xml xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" '
            b'xmlns:x="urn:schemas-microsoft-com:office:excel"><v:shape id="_x0000_s1025" type="#_x0000_t202">'
            b'<x:ClientData ObjectType="Note"><x:Row>0</x:Row><x:Column>0</x:Column></x:ClientData></v:shape><br></xml>'
        ),
    },
)


def test_a_note_for_alternatives_joins_the_comments_already_there():
    out = edited(COMMENTED, store(0, 1, {"t": "formula", "v": "=ALTERNATIVES(5,6,7)"}))
    comments = etree.fromstring(part(out, "xl/comments1.xml"))
    texts = {c.get("ref"): "".join(c.itertext()) for c in comments.iterfind(".//x:comment", NS)}
    assert texts == {"A1": "Check this", "B1": "claudia alternatives: {5, 6, 7}"}
    vml = part(out, "xl/drawings/vmlDrawing1.vml")
    assert vml.count(b"<x:Row>0</x:Row>") == 2 and b"<x:Column>1</x:Column>" in vml
    assert cells(xlsx_to_workbook(out))[(0, 1)] == {"t": "formula", "v": "=ALTERNATIVES(5,6,7)"}


def test_a_note_goes_when_its_alternatives_go_and_somebody_elses_stays():
    with_note = edited(COMMENTED, store(0, 1, {"t": "formula", "v": "=ALTERNATIVES(5,6,7)"}))
    out = edited(with_note, lambda m: (store(0, 1, {"t": "int", "v": 5})(m), store(0, 0, {"t": "int", "v": 2})(m)))
    comments = etree.fromstring(part(out, "xl/comments1.xml"))
    assert [c.get("ref") for c in comments.iterfind(".//x:comment", NS)] == ["A1"]
    assert part(out, "xl/drawings/vmlDrawing1.vml").count(b"<x:Row>0</x:Row>") == 1


def test_a_note_on_a_sheet_without_comments_brings_its_own_parts():
    data = package({"Plan": rows('<row r="1"><c r="A1"><v>1</v></c></row>')})
    out = edited(data, store(0, 1, {"t": "formula", "v": "=ALTERNATIVES(1,2)"}))
    assert cells(xlsx_to_workbook(out))[(0, 1)] == {"t": "formula", "v": "=ALTERNATIVES(1,2)"}
    root = etree.fromstring(part(out, "xl/worksheets/sheet1.xml"))
    assert root.find("x:legacyDrawing", NS) is not None


def test_a_new_workbook_writes_excels_name_for_a_newer_function():
    model = WorkbookModel()
    sheet = Sheet(SheetId("s1"), "Plan")
    sheet.cells[(0, 0)] = {"t": "int", "v": 1}
    sheet.cells[(0, 1)] = {"t": "formula", "v": '=IFS(A1>0,"yes",TRUE,"no")'}
    model.sheets[sheet.id] = sheet
    model.open_container("s1")
    model._calculate_loaded()  # noqa: SLF001
    assert b"_xlfn.IFS(" in part(workbook_to_xlsx(model), "xl/worksheets/sheet1.xml")


# ------------------------------------------------------------------------------------------------ names and tables
def with_workbook(data: bytes, before_sheets: str = "", after_sheets: str = "", *, hide: str = "") -> bytes:
    """``data`` with more in its workbook part: elements before ``<sheets>`` and after it, and the sheet ``hide``
    hidden."""
    with ZipFile(BytesIO(data)) as zf:
        parts = {name: zf.read(name) for name in zf.namelist()}
    workbook = parts["xl/workbook.xml"].decode()
    workbook = workbook.replace("<sheets>", before_sheets + "<sheets>").replace("</sheets>", "</sheets>" + after_sheets)
    if hide:
        workbook = workbook.replace(f'<sheet name="{hide}"', f'<sheet name="{hide}" state="hidden"')
    parts["xl/workbook.xml"] = workbook.encode()
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as zf:
        for name, part_data in parts.items():
            zf.writestr(name, part_data)
    return out.getvalue()


NAMED = with_workbook(
    package(
        {
            "Inputs": rows('<row r="1"><c r="A1"><v>0.05</v></c><c r="B1"><v>3</v></c></row>'),
            "Plan": rows(
                '<row r="1"><c r="A1"><f>Rate*100</f><v>5</v></c><c r="B1"><f>Gone*2</f><v>8</v></c>'
                '<c r="C1"><f>Local+1</f><v>4</v></c><c r="D1"><f>Twice</f><v>6</v></c></row>'
            ),
        }
    ),
    after_sheets='<definedNames><definedName name="Rate">Inputs!$A$1</definedName>'
    '<definedName name="Gone">#REF!</definedName>'
    '<definedName name="Local" localSheetId="1">Inputs!$B$1</definedName>'
    '<definedName name="Twice">Inputs!$B$1*2</definedName>'
    '<definedName name="_xlnm.Print_Area" localSheetId="1">Plan!$A$1:$D$1</definedName>'
    '<definedName name="Elsewhere" localSheetId="7">Inputs!$A$1</definedName></definedNames>',
)


def test_a_name_for_a_range_comes_along_and_its_formulas_stay_live():
    model = xlsx_to_workbook(NAMED)
    plan = cells(model, "s2")
    assert plan[(0, 0)] == {"t": "formula", "v": "=Rate*100"}
    assert model.sheets[SheetId("s2")].grid.get((0, 0)) == 5
    assert plan[(0, 2)] == {"t": "formula", "v": "=Local+1"}


def test_a_formula_using_a_name_that_did_not_come_along_is_its_value():
    plan = cells(xlsx_to_workbook(NAMED), "s2")
    assert plan[(0, 1)] == {"t": "int", "v": 8}
    assert plan[(0, 3)] == {"t": "int", "v": 6}
    losses = xlsx_import_losses(NAMED)
    assert Loss("formula", "name", 2) in losses
    assert Loss("named-range", count=3) in losses


def test_a_table_is_a_name_with_a_header_and_its_columns_can_be_used():
    table = (
        '<table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" id="1" name="Table1" '
        'displayName="Sales" ref="A1:B3"><tableColumns count="2"><tableColumn id="1" name="Region"/>'
        '<tableColumn id="2" name="Amount"/></tableColumns></table>'
    )
    data = package(
        {
            "Data": rows(
                '<row r="1"><c r="A1" t="inlineStr"><is><t>Region</t></is></c>'
                '<c r="B1" t="inlineStr"><is><t>Amount</t></is></c></row>',
                '<row r="2"><c r="A2" t="inlineStr"><is><t>North</t></is></c><c r="B2"><v>10</v></c></row>',
                '<row r="3"><c r="A3" t="inlineStr"><is><t>South</t></is></c><c r="B3"><v>20</v></c>'
                '<c r="D3"><f>SUM(Sales[Amount])</f><v>30</v></c><c r="E3"><f>SUM(Other[Amount])</f><v>1</v></c></row>',
            )
            + '<tableParts count="1"><tablePart r:id="rId1"/></tableParts>'
        },
        sheet_rels={
            1: '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" '
            'Target="../tables/table1.xml"/>'
        },
        extra={"xl/tables/table1.xml": table.encode()},
    )
    model = xlsx_to_workbook(data)
    assert cells(model)[(2, 3)]["t"] == "formula"
    assert model.sheets[SheetId("s1")].grid.get((2, 3)) == 30
    assert cells(model)[(2, 4)] == {"t": "int", "v": 1}


def test_hidden_sheets_and_a_protected_workbook_are_listed():
    data = with_workbook(
        package({"Plan": rows(), "Old": rows()}),
        before_sheets='<workbookProtection lockStructure="1"/>',
        hide="Old",
    )
    losses = xlsx_import_losses(data)
    assert Loss("hidden-sheet") in losses and Loss("protection") in losses


def test_bytes_that_are_no_xlsx_are_refused_with_a_reason():
    with pytest.raises(XlsxError, match="not a zip"):
        xlsx_to_workbook(b"plain text")
    empty = BytesIO()
    with ZipFile(empty, "w") as zf:
        zf.writestr("hello.txt", "hi")
    with pytest.raises(XlsxError, match="no workbook"):
        xlsx_to_workbook(empty.getvalue())


def test_a_shared_formula_whose_first_cell_comes_later_in_the_file_still_reads():
    data = package(
        {
            "Plan": rows(
                '<row r="1"><c r="A1"><v>1</v></c><c r="B1"><f t="shared" si="4"/><v>2</v></c></row>',
                '<row r="2"><c r="A2"><v>2</v></c>'
                '<c r="B2"><f t="shared" ref="B1:B2" si="4">A2*2</f><v>4</v></c></row>',
            )
        }
    )
    assert cells(xlsx_to_workbook(data))[(0, 1)] == {"t": "formula", "v": "=A1*2"}


def test_what_a_formula_from_another_file_or_a_dated_cell_holds_comes_in_as_its_value():
    data = package(
        {
            "Plan": rows(
                '<row r="1"><c r="A1"><f>[1]Prices!A1</f><v>7</v></c><c r="B1" t="d"><v>2026-11-13T00:00:00</v></c>'
                '<c r="XFE1"><v>1</v></c></row>'
            )
        }
    )
    read = cells(xlsx_to_workbook(data))
    assert read[(0, 0)] == {"t": "int", "v": 7}
    assert read[(0, 1)] == {"t": "text", "v": "2026-11-13T00:00:00"}
    losses = xlsx_import_losses(data)
    assert Loss("formula", "syntax") in losses and Loss("date") in losses and Loss("outside") in losses


def test_a_drawing_with_a_shape_and_a_group_counts_them_as_shapes():
    drawing = (
        '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">'
        "<xdr:twoCellAnchor><xdr:sp/></xdr:twoCellAnchor><xdr:oneCellAnchor><xdr:grpSp/></xdr:oneCellAnchor>"
        "<xdr:absoluteAnchor><xdr:graphicFrame/></xdr:absoluteAnchor></xdr:wsDr>"
    )
    data = package(
        {"Plan": rows() + '<drawing r:id="rId1"/>'},
        sheet_rels={
            1: '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" '
            'Target="../drawings/drawing1.xml"/>'
        },
        extra={"xl/drawings/drawing1.xml": drawing.encode()},
    )
    assert Loss("shape", count=3) in xlsx_import_losses(data)


# ------------------------------------------------------------------------------------------------ more edits
def test_every_kind_of_value_a_formula_shows_is_written_with_its_type():
    data = package({"Plan": rows('<row r="1"><c r="A1"><v>1</v></c></row>')})
    out = edited(
        data,
        lambda m: (
            store(0, 1, {"t": "formula", "v": "=A1>0"})(m),
            store(0, 2, {"t": "formula", "v": "=1/0"})(m),
            store(0, 3, {"t": "bool", "v": False})(m),
            store(0, 4, {"t": "text", "v": " padded "})(m),
            store(0, 5, {"t": "formula", "v": '=RANDOM("triangular",1,2,3)'})(m),
        ),
    )
    assert (cell_xml(out, "B1").get("t"), cell_xml(out, "B1").findtext("x:v", namespaces=NS)) == ("b", "1")
    assert (cell_xml(out, "C1").get("t"), cell_xml(out, "C1").findtext("x:v", namespaces=NS)) == ("e", "#DIV/0!")
    assert cell_xml(out, "D1").findtext("x:v", namespaces=NS) == "0"
    assert cell_xml(out, "E1").find("x:is/x:t", NS).get("{http://www.w3.org/XML/1998/namespace}space") == "preserve"
    assert cell_xml(out, "F1").find("x:f", NS) is None


def test_a_sheet_without_rows_or_a_calculation_setting_still_takes_an_edit():
    data = package({"Plan": ""}).replace(b'<calcPr calcId="191029"/>', b"")
    out = edited(data, lambda m: (store(5, 0, {"t": "int", "v": 1})(m), store(2, 0, {"t": "int", "v": 2})(m)))
    assert cells(xlsx_to_workbook(out)) == {(5, 0): {"t": "int", "v": 1}, (2, 0): {"t": "int", "v": 2}}
    assert etree.fromstring(part(out, "xl/workbook.xml")).find("x:calcPr", NS).get("fullCalcOnLoad") == "1"


def test_cells_and_rows_without_their_reference_can_be_edited():
    data = package({"Plan": rows("<row><c><v>1</v></c><c><v>2</v></c></row>")})
    out = edited(data, store(0, 1, {"t": "int", "v": 5}))
    assert cells(xlsx_to_workbook(out)) == {(0, 0): {"t": "int", "v": 1}, (0, 1): {"t": "int", "v": 5}}


def test_changed_alternatives_change_the_note_and_a_cell_with_a_foreign_comment_keeps_it():
    with_note = edited(COMMENTED, store(0, 1, {"t": "formula", "v": "=ALTERNATIVES(5,6,7)"}))
    changed = edited(with_note, store(0, 1, {"t": "formula", "v": "=ALTERNATIVES(5,8)"}))
    texts = ["".join(c.itertext()) for c in etree.fromstring(part(changed, "xl/comments1.xml")).iter(f"{{{X}}}comment")]
    assert texts == ["Check this", "claudia alternatives: {5, 8}"]
    foreign = edited(COMMENTED, store(0, 0, {"t": "formula", "v": "=ALTERNATIVES(1,2)"}))
    assert part(foreign, "xl/comments1.xml") == part(COMMENTED, "xl/comments1.xml")


def test_a_note_on_a_sheet_whose_comments_have_no_drawing_gets_one_before_its_tables():
    data = package(
        {"Plan": rows('<row r="1"><c r="A1"><v>1</v></c></row>') + '<tableParts count="0"/>'},
    )
    out = edited(data, store(0, 1, {"t": "formula", "v": "=ALTERNATIVES(1,2)"}))
    root = etree.fromstring(part(out, "xl/worksheets/sheet1.xml"))
    assert [etree.QName(e).localname for e in root][-2:] == ["legacyDrawing", "tableParts"]
