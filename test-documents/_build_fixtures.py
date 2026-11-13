"""Regenerates every checked-in ``source.docx``/``source.pptx``/``source.xlsx`` and the hand-built
``source.odt``/``source.odp``/``source.ods`` in this library, deterministically (D218, D219, D220, D401, D412, D413).

A test document is checked in as a real, openable binary -- not just a Python function that builds one on the
fly, the way every other format test in this repo does -- because the whole point of a *library* is files a
person (or LibreOffice, or real Word/PowerPoint) can open directly, not just assertions about one. This script is
how they were made, and how to remake or extend them: nobody hand-edits a ``source.docx``/``source.pptx``.

``uv run python test-documents/_build_fixtures.py``
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import docx
import openpyxl
import pptx
from docx.shared import Inches
from openpyxl.chart import BarChart, Reference
from openpyxl.drawing.image import Image as XLImage
from PIL import Image
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu

from claudia_odf_io import NS, new_package
from claudia_opc_io import write_parts

ROOT = Path(__file__).resolve().parent
#: EMU per claudia slide unit on a 16:9 deck (``12_192_000 / 1600`` == ``6_858_000 / 900``, both exact) -- the
#: same scale ``claudia_creates_io.pptx`` itself uses, so a shape placed at claudia unit ``(x, y, w, h)`` here
#: imports back through ``pptx_to_slides`` at that exact position, with no rounding drift to account for.
_UNIT_EMU = 7620


def build_heading_styles() -> bytes:
    document = docx.Document()
    document.add_paragraph("Claudia Field Notes", style="Title")
    document.add_paragraph("Introduction", style="Heading 1")
    document.add_paragraph("This is the introduction.")
    document.add_paragraph("Background", style="Heading 2")
    document.add_paragraph("More background text.")
    return _bytes(document)


def build_tracked_change_suggestion() -> bytes:
    document = docx.Document()
    document.add_paragraph("The committee rejected the proposal.")
    return _bytes(document)


def build_beyond_claudia_table() -> bytes:
    document = docx.Document()
    document.add_paragraph("Status report.")
    table = document.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Region"
    table.rows[0].cells[1].text = "Amount"
    table.rows[1].cells[0].text = "North"
    table.rows[1].cells[1].text = "120"
    document.add_paragraph("End of report.")
    return _bytes(document)


def build_beyond_claudia_image() -> bytes:
    document = docx.Document()
    document.add_paragraph("Photo attached.")
    document.add_picture(_red_square_png(), width=Inches(1))
    document.add_paragraph("See above.")
    return _bytes(document)


def _red_square_png() -> BytesIO:
    image = Image.new("RGB", (16, 16), color=(214, 71, 122))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _bytes(document: docx.Document) -> bytes:
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def _box(x: int, y: int, w: int, h: int) -> tuple[Emu, Emu, Emu, Emu]:
    """A claudia-unit box as the EMU box python-pptx wants, at this file's fixed 16:9 scale."""
    return Emu(x * _UNIT_EMU), Emu(y * _UNIT_EMU), Emu(w * _UNIT_EMU), Emu(h * _UNIT_EMU)


def _new_presentation() -> pptx.Presentation:
    """A blank 16:9 deck, same size ``claudia_creates_io.pptx.slides_to_pptx`` itself produces."""
    prs = pptx.Presentation()
    prs.slide_width, prs.slide_height = Emu(1600 * _UNIT_EMU), Emu(900 * _UNIT_EMU)
    return prs


def build_shapes_and_text() -> bytes:
    prs = _new_presentation()
    layout = prs.slide_layouts[6]  # blank
    slide1 = prs.slides.add_slide(layout)
    slide1.shapes.add_textbox(*_box(100, 80, 500, 120)).text_frame.text = "Welcome to Claudia"
    circle = slide1.shapes.add_shape(MSO_SHAPE.OVAL, *_box(700, 80, 200, 200))
    circle.text_frame.text = "Idea"
    slide2 = prs.slides.add_slide(layout)
    rectangle = slide2.shapes.add_shape(MSO_SHAPE.RECTANGLE, *_box(100, 500, 400, 200))
    rectangle.text_frame.text = "Box"
    return _pptx_bytes(prs)


def build_pptx_beyond_claudia_table() -> bytes:
    prs = _new_presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(*_box(100, 80, 600, 120)).text_frame.text = "Status report."
    table_shape = slide.shapes.add_table(2, 2, *_box(100, 300, 600, 300))
    table_shape.table.cell(0, 0).text = "Region"
    table_shape.table.cell(0, 1).text = "Amount"
    table_shape.table.cell(1, 0).text = "North"
    table_shape.table.cell(1, 1).text = "120"
    return _pptx_bytes(prs)


def build_pptx_beyond_claudia_image() -> bytes:
    prs = _new_presentation()
    layout = prs.slide_layouts[6]
    slide1 = prs.slides.add_slide(layout)
    slide1.shapes.add_textbox(*_box(100, 80, 600, 120)).text_frame.text = "Photo attached."
    slide2 = prs.slides.add_slide(layout)
    slide2.shapes.add_picture(_red_square_png(), *_box(100, 100, 300, 300))
    return _pptx_bytes(prs)


def _pptx_bytes(prs: pptx.Presentation) -> bytes:
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


def build_cells_and_formulas() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["Region", "Product", "Amount"])
    for region, product, amount in (
        ("North", "Widget", 100),
        ("North", "Gadget", 150),
        ("South", "Widget", 200),
        ("South", "Gadget", 120),
        ("East", "Widget", 130),
        ("West", "Gadget", 140),
    ):
        ws.append([region, product, amount])
    ws.append(["Total", None, "=SUM(C2:C7)"])
    notes = wb.create_sheet("Notes")
    notes["A1"] = "Six regions, two products."
    return _xlsx_bytes(wb)


def build_xlsx_beyond_claudia_chart() -> bytes:
    wb = openpyxl.Workbook()
    data = wb.active
    data.title = "Data"
    data.append(["Region", "Amount"])
    for region, amount in (("North", 100), ("South", 200), ("East", 130)):
        data.append([region, amount])
    chart_sheet = wb.create_sheet("Chart")
    chart = BarChart()
    chart.add_data(Reference(data, min_col=2, min_row=1, max_row=4), titles_from_data=True)
    chart.set_categories(Reference(data, min_col=1, min_row=2, max_row=4))
    chart_sheet.add_chart(chart, "A1")
    return _xlsx_bytes(wb)


def build_xlsx_beyond_claudia_image() -> bytes:
    wb = openpyxl.Workbook()
    data = wb.active
    data.title = "Data"
    data["A1"] = "North"
    pics = wb.create_sheet("Pics")
    pics.add_image(XLImage(_red_square_png()), "A1")
    return _xlsx_bytes(wb)


_X = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_XR = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PR = "http://schemas.openxmlformats.org/package/2006/relationships"
_SHEET_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml."
_EXCEL_TODAY_PLAN = (
    "<sheetData>"
    '<row r="1"><c r="A1"><v>1</v></c><c r="B1"><f t="shared" ref="B1:B3" si="0">A1*2</f><v>2</v></c>'
    '<c r="C1" cm="1"><f t="array" ref="C1:C3">_xlfn.SEQUENCE(3)</f><v>1</v></c>'
    '<c r="D1" t="inlineStr"><is><t>Apple</t></is></c></row>'
    '<row r="2"><c r="A2"><v>2</v></c><c r="B2"><f t="shared" si="0"/><v>4</v></c><c r="C2"><v>2</v></c></row>'
    '<row r="3"><c r="A3"><v>3</v></c><c r="B3"><f t="shared" si="0"/><v>6</v></c><c r="C3"><v>3</v></c></row>'
    "</sheetData>"
    '<extLst><ext uri="{78C0D931-6437-407d-A8EE-F0AAD7539E65}" '
    'xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"><x14:conditionalFormattings>'
    '<x14:conditionalFormatting xmlns:xm="http://schemas.microsoft.com/office/excel/2006/main">'
    '<x14:cfRule type="iconSet" priority="1" id="{6F1C2A3B-0000-4000-8000-000000000001}">'
    '<x14:iconSet iconSet="3Triangles"><x14:cfvo type="percent"><xm:f>0</xm:f></x14:cfvo>'
    '<x14:cfvo type="percent"><xm:f>33</xm:f></x14:cfvo><x14:cfvo type="percent"><xm:f>67</xm:f></x14:cfvo>'
    "</x14:iconSet></x14:cfRule><xm:sqref>A1:A3</xm:sqref></x14:conditionalFormatting></x14:conditionalFormattings>"
    '</ext><ext uri="{CCE6A557-97BC-4b89-ADB6-D9C93CAAB3DF}" '
    'xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">'
    '<x14:dataValidations count="1" xmlns:xm="http://schemas.microsoft.com/office/excel/2006/main">'
    '<x14:dataValidation type="list" allowBlank="1"><x14:formula1><xm:f>Lists!$A$1:$A$3</xm:f></x14:formula1>'
    "<xm:sqref>D1</xm:sqref></x14:dataValidation></x14:dataValidations></ext></extLst>"
)
_EXCEL_TODAY_METADATA = (
    f'<metadata xmlns="{_X}" xmlns:xda="http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray">'
    '<metadataTypes count="1"><metadataType name="XLDAPR" minSupportedVersion="120000" copy="1" pasteAll="1" '
    'pasteValues="1" merge="1" splitFirst="1" rowColShift="1" clearFormats="1" clearComments="1" assign="1" '
    'coerce="1" cellMeta="1"/></metadataTypes><futureMetadata name="XLDAPR" count="1"><bk><extLst>'
    '<ext uri="{bdbb8cdc-fa1e-496e-a857-3c3f30c029c3}"><xda:dynamicArrayProperties fDynamic="1" fCollapsed="0"/>'
    '</ext></extLst></bk></futureMetadata><cellMetadata count="1"><bk><rc t="1" v="0"/></bk></cellMetadata></metadata>'
)


def build_xlsx_beyond_claudia_excel_today() -> bytes:
    """What Excel writes today and openpyxl leaves out when it saves (D341): a spilled formula with its mark and the
    workbook's metadata part, a list in a cell that takes its choices from another sheet, an icon set, a shared
    formula. Written part by part, since no library writes them."""
    lists = "".join(
        f'<row r="{n}"><c r="A{n}" t="inlineStr"><is><t>{fruit}</t></is></c></row>'
        for n, fruit in enumerate(("Apple", "Pear", "Plum"), start=1)
    )
    sheets = {"Plan": _EXCEL_TODAY_PLAN, "Lists": f"<sheetData>{lists}</sheetData>"}
    parts: dict[str, bytes] = {}
    entries, rels, overrides = [], [], []
    for n, (name, inside) in enumerate(sheets.items(), start=1):
        entries.append(f'<sheet name="{name}" sheetId="{n}" r:id="rId{n}"/>')
        rels.append(f'<Relationship Id="rId{n}" Type="{_XR}/worksheet" Target="worksheets/sheet{n}.xml"/>')
        overrides.append(f'<Override PartName="/xl/worksheets/sheet{n}.xml" ContentType="{_SHEET_TYPE}worksheet+xml"/>')
        parts[f"xl/worksheets/sheet{n}.xml"] = (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="{_X}" xmlns:r="{_XR}">'
            f"{inside}</worksheet>"
        ).encode()
    rels.append(f'<Relationship Id="rId9" Type="{_XR}/sheetMetadata" Target="metadata.xml"/>')
    overrides.append(f'<Override PartName="/xl/metadata.xml" ContentType="{_SHEET_TYPE}sheetMetadata+xml"/>')
    overrides.append(f'<Override PartName="/xl/workbook.xml" ContentType="{_SHEET_TYPE}sheet.main+xml"/>')
    parts["xl/metadata.xml"] = _EXCEL_TODAY_METADATA.encode()
    parts["xl/workbook.xml"] = (
        f'<workbook xmlns="{_X}" xmlns:r="{_XR}"><sheets>{"".join(entries)}</sheets>'
        '<calcPr calcId="191029"/></workbook>'
    ).encode()
    parts["xl/_rels/workbook.xml.rels"] = f'<Relationships xmlns="{_PR}">{"".join(rels)}</Relationships>'.encode()
    parts["_rels/.rels"] = (
        f'<Relationships xmlns="{_PR}"><Relationship Id="rId1" Type="{_XR}/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    ).encode()
    parts["[Content_Types].xml"] = (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        f'<Default Extension="xml" ContentType="application/xml"/>{"".join(overrides)}</Types>'
    ).encode()
    return write_parts({"[Content_Types].xml": parts.pop("[Content_Types].xml"), **parts})


def _xlsx_bytes(wb: openpyxl.Workbook) -> bytes:
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


_ODT_DECLS = " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in NS.items() if prefix != "xml")
_ODT_STYLES = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    f'<office:document-styles {_ODT_DECLS} office:version="1.3"><office:styles>'
    '<style:style style:name="Standard" style:family="paragraph" style:class="text"/>'
    '<style:style style:name="Text_20_body" style:display-name="Text body" style:family="paragraph" '
    'style:parent-style-name="Standard" style:class="text"/>'
    '<style:style style:name="Heading_20_1" style:display-name="Heading 1" style:family="paragraph" '
    'style:parent-style-name="Standard" style:default-outline-level="1" style:class="text"/>'
    '<style:style style:name="Strong" style:display-name="Strong" style:family="text"/>'
    "</office:styles></office:document-styles>"
).encode()


def _odt(body: str, *, automatic: str = "", extra: dict[str, tuple[bytes, str]] | None = None) -> bytes:
    """An odt written by hand, the way LibreOffice lays a file out, for what no library here can build: a paragraph
    full of links, notes and bookmarks, a list, a section. (The three LibreOffice-written odt fixtures were made by
    ``soffice --convert-to odt`` from the docx ones above and checked in as they came out: its files carry the
    time they were made in, so this script cannot make them again.)"""
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<office:document-content {_ODT_DECLS} office:version="1.3"><office:scripts/><office:font-face-decls/>'
        f"<office:automatic-styles>{automatic}</office:automatic-styles>"
        f"<office:body><office:text>{body}</office:text></office:body></office:document-content>"
    )
    return new_package("text", content.encode(), _ODT_STYLES, extra=extra)


def build_odt_rich_paragraph() -> bytes:
    return _odt(
        '<text:h text:style-name="Heading_20_1" text:outline-level="1">Reading list</text:h>'
        '<text:p text:style-name="Text_20_body">Read the <text:a xlink:href="https://example.org/manual" '
        'xlink:type="simple">manual</text:a> and <text:span text:style-name="Strong">note</text:span> '
        'the examples<text:bookmark text:name="examples"/> carefully'
        '<text:note text:id="ftn1" text:note-class="footnote"><text:note-citation>1</text:note-citation>'
        "<text:note-body><text:p>See chapter two.</text:p></text:note-body></text:note>.</text:p>"
        '<text:p text:style-name="Text_20_body">Nothing here changes.</text:p>'
    )


def build_odt_tracked_change_suggestion() -> bytes:
    return _odt('<text:p text:style-name="Standard">The committee rejected the proposal.</text:p>')


def build_odt_lists_and_sections() -> bytes:
    return _odt(
        '<text:p text:style-name="Standard">Shopping.</text:p>'
        '<text:list text:style-name="L1"><text:list-item><text:p text:style-name="Standard">Bread</text:p>'
        '</text:list-item><text:list-item><text:p text:style-name="Standard">Milk</text:p></text:list-item></text:list>'
        '<text:section text:style-name="Sect1" text:name="Notes"><text:p text:style-name="Standard">'
        "Remember the bag.</text:p></text:section>"
        '<text:p text:style-name="Standard">Done.</text:p>',
        automatic='<style:style style:name="Sect1" style:family="section"/>'
        '<text:list-style style:name="L1"><text:list-level-style-bullet text:level="1" text:bullet-char="•"/>'
        "</text:list-style>",
    )


_ODP_STYLES = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    f'<office:document-styles {_ODT_DECLS} office:version="1.3"><office:automatic-styles>'
    '<style:page-layout style:name="PM1"><style:page-layout-properties fo:page-width="28cm" fo:page-height="15.75cm"/>'
    "</style:page-layout></office:automatic-styles><office:master-styles>"
    '<style:master-page style:name="Default" style:page-layout-name="PM1"/></office:master-styles>'
    "</office:document-styles>"
).encode()


def build_odp_groups_notes_transitions() -> bytes:
    """An odp written by hand for what a PowerPoint conversion does not give: a group, a line, speaker notes with
    words, a slide transition and an animation, around a text box and a circle the model does hold."""
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<office:document-content {_ODT_DECLS} office:version="1.3"><office:scripts/><office:font-face-decls/>'
        '<office:automatic-styles><style:style style:name="dp1" style:family="drawing-page">'
        '<style:drawing-page-properties presentation:transition-type="automatic" presentation:duration="PT00H00M05S"/>'
        "</style:style></office:automatic-styles><office:body><office:presentation>"
        '<draw:page draw:name="page1" draw:style-name="dp1" draw:master-page-name="Default">'
        '<draw:frame svg:x="2cm" svg:y="1cm" svg:width="14cm" svg:height="2cm"><draw:text-box>'
        "<text:p>Quarterly plan</text:p></draw:text-box></draw:frame>"
        '<draw:g><draw:rect svg:x="2cm" svg:y="5cm" svg:width="3cm" svg:height="2cm"/>'
        '<draw:rect svg:x="6cm" svg:y="5cm" svg:width="3cm" svg:height="2cm"/></draw:g>'
        '<draw:line svg:x1="2cm" svg:y1="9cm" svg:x2="12cm" svg:y2="9cm"/>'
        '<draw:ellipse svg:x="18cm" svg:y="4cm" svg:width="4cm" svg:height="4cm"><text:p>Goal</text:p></draw:ellipse>'
        '<anim:par smil:begin="next"><anim:set smil:targetElement="x" smil:attributeName="visibility" '
        'smil:to="visible"/>'
        "</anim:par>"
        "<presentation:notes><draw:page-thumbnail/><draw:frame><draw:text-box>"
        "<text:p>Mention the budget first.</text:p></draw:text-box></draw:frame></presentation:notes>"
        "</draw:page></office:presentation></office:body></office:document-content>"
    )
    return new_package("presentation", content.encode(), _ODP_STYLES)


_ODS_STYLES = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    f'<office:document-styles {_ODT_DECLS} office:version="1.3"><office:styles/></office:document-styles>'
).encode()


def build_ods_repeated_and_styled() -> bytes:
    """An ods written by hand for what a file keeps and the model does not show: runs of equal rows and cells, a
    merged title, styled cells, a date, a comment, a formula the model cannot read (a union), a named range and a
    validation -- around the numbers and formulas the model does hold."""
    automatic = (
        '<style:style style:name="co1" style:family="table-column"><style:table-column-properties '
        'style:column-width="2.5cm"/></style:style>'
        '<style:style style:name="ro1" style:family="table-row"><style:table-row-properties style:row-height="0.5cm"/>'
        "</style:style>"
        '<style:style style:name="ce1" style:family="table-cell"><style:text-properties fo:font-weight="bold"/>'
        "</style:style>"
        '<style:style style:name="ce2" style:family="table-cell"><style:text-properties fo:font-size="16pt"/>'
        "</style:style>"
        '<number:date-style style:name="N37"><number:day number:style="long"/><number:text>.</number:text>'
        '<number:month number:style="long"/><number:text>.</number:text><number:year/></number:date-style>'
        '<style:style style:name="ce3" style:family="table-cell" style:data-style-name="N37"/>'
    )

    def number(value: int, formula: str | None = None, extra: str = "") -> str:
        attribute = f' table:formula="{formula}"' if formula else ""
        return (
            f'<table:table-cell{attribute} office:value-type="float" office:value="{value}"{extra}>'
            f"<text:p>{value}</text:p></table:table-cell>"
        )

    def words(text: str, extra: str = "") -> str:
        return f'<table:table-cell office:value-type="string"{extra}><text:p>{text}</text:p></table:table-cell>'

    blank = "<table:table-cell/>"
    rows = (
        '<table:table-row table:style-name="ro1">'
        + words(
            "Household budget",
            ' table:style-name="ce2" table:number-columns-spanned="4" table:number-rows-spanned="1"',
        )
        + '<table:covered-table-cell table:number-columns-repeated="3"/></table:table-row>'
        + '<table:table-row table:style-name="ro1">'
        + "".join(words(label, ' table:style-name="ce1"') for label in ("Item", "Q1", "Q2", "Total"))
        + "</table:table-row>"
        + "<table:table-row>"
        + words("Rent")
        + number(1000)
        + number(1000)
        + number(2000, "of:=SUM([.B3:.C3])")
        + "</table:table-row>"
        + '<table:table-row table:number-rows-repeated="3">'
        + words("Reserve")
        + number(50)
        + number(50)
        + blank
        + "</table:table-row>"
        + "<table:table-row>"
        + '<table:table-cell office:value-type="string"><office:annotation><dc:creator>Ana</dc:creator>'
        "<text:p>The sum of the lines above.</text:p></office:annotation><text:p>Total</text:p></table:table-cell>"
        + number(1150, "of:=SUM([.B3:.B6])")
        + number(1150, "of:=SUM([.C3:.C6])")
        + number(2300, "of:=SUM([.B7:.C7])")
        + "</table:table-row>"
        + "<table:table-row>"
        + words("Due")
        + '<table:table-cell table:style-name="ce3" office:value-type="date" office:date-value="2026-12-31">'
        "<text:p>31.12.2026</text:p></table:table-cell>"
        + "</table:table-row>"
        + "<table:table-row>"
        + words("Second quarter")
        + number(1150, "of:=SUM(([.C3:.C4]~[.C5:.C6]))")
        + '<table:table-cell table:formula="of:=1/0" office:value-type="string" office:string-value="" '
        'calcext:value-type="error"><text:p>#DIV/0!</text:p></table:table-cell>'
        + "</table:table-row>"
        + '<table:table-row table:number-rows-repeated="1000"><table:table-cell table:number-columns-repeated="4"/>'
        "</table:table-row>"
    )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<office:document-content {_ODT_DECLS} office:version="1.3"><office:scripts/><office:font-face-decls/>'
        f"<office:automatic-styles>{automatic}</office:automatic-styles><office:body><office:spreadsheet>"
        '<table:content-validations><table:content-validation table:name="val1" '
        'table:condition="of:cell-content-is-whole-number()" table:allow-empty-cell="true"/>'
        "</table:content-validations>"
        '<table:table table:name="Budget" table:style-name="ta1">'
        '<table:table-column table:style-name="co1" table:number-columns-repeated="4"/>'
        f"{rows}</table:table>"
        '<table:table table:name="Notes"><table:table-column/><table:table-row>'
        + words("Amounts in euros.")
        + "</table:table-row></table:table>"
        '<table:named-expressions><table:named-range table:name="Total_Q1" '
        'table:base-cell-address="$Budget.$B$7" table:cell-range-address="$Budget.$B$7"/></table:named-expressions>'
        "</office:spreadsheet></office:body></office:document-content>"
    )
    return new_package("spreadsheet", content.encode(), _ODS_STYLES)


FIXTURES = {
    "docx/heading-styles/source.docx": build_heading_styles,
    "docx/tracked-change-suggestion/source.docx": build_tracked_change_suggestion,
    "docx/beyond-claudia/table/source.docx": build_beyond_claudia_table,
    "docx/beyond-claudia/image/source.docx": build_beyond_claudia_image,
    "pptx/shapes-and-text/source.pptx": build_shapes_and_text,
    "pptx/beyond-claudia/table/source.pptx": build_pptx_beyond_claudia_table,
    "pptx/beyond-claudia/image/source.pptx": build_pptx_beyond_claudia_image,
    "odt/rich-paragraph/source.odt": build_odt_rich_paragraph,
    "odt/tracked-change-suggestion/source.odt": build_odt_tracked_change_suggestion,
    "odt/lists-and-sections/source.odt": build_odt_lists_and_sections,
    "odp/groups-notes-transitions/source.odp": build_odp_groups_notes_transitions,
    "ods/repeated-and-styled/source.ods": build_ods_repeated_and_styled,
    "xlsx/cells-and-formulas/source.xlsx": build_cells_and_formulas,
    "xlsx/beyond-claudia/chart/source.xlsx": build_xlsx_beyond_claudia_chart,
    "xlsx/beyond-claudia/image/source.xlsx": build_xlsx_beyond_claudia_image,
    "xlsx/beyond-claudia/excel-today/source.xlsx": build_xlsx_beyond_claudia_excel_today,
}


def main() -> None:
    for relative_path, build in FIXTURES.items():
        path = ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(build())
        print(f"wrote {relative_path}")


if __name__ == "__main__":
    main()
