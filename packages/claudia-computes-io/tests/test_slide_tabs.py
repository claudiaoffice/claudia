"""A workbook's slides in ods and xlsx (E6.31 step 5, D1477): a slide is a tab of its own in its place among the
sheets, without cells, and its objects are where they were on the slide: one unit of the slide is one pixel of the tab
(``SlideSize``, a setting of the export). Writing a slide this way is not reported."""

from __future__ import annotations

import json
from io import BytesIO

import openpyxl
import pytest
from claudia_computes_io import (
    SlideSize,
    UnsupportedEdit,
    apply_edits_to_ods,
    apply_edits_to_xlsx,
    ods_export_losses,
    ods_import_losses,
    ods_to_workbook,
    workbook_to_ods,
    workbook_to_xlsx,
    xlsx_export_losses,
    xlsx_import_losses,
    xlsx_to_workbook,
)
from lxml import etree
from test_ods_charts import a_range, a_workbook
from test_pictures import a_png, an_import

from claudia_computes import CellAnchor, ChartSpec, ObjectBody, VisualObject, WorkbookModel
from claudia_computes.model import Sheet
from claudia_core import Slide, SlideAnchor, paragraph_for, primitive
from claudia_odf_io import NS as ODF
from claudia_odf_io import Loss, problems, user_defined
from claudia_opc_io import read_parts, write_parts

FORMATS = {
    "xlsx": (workbook_to_xlsx, xlsx_to_workbook, xlsx_export_losses),
    "ods": (workbook_to_ods, ods_to_workbook, ods_export_losses),
}
XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
EMU = 9525  # in a pixel


def with_a_slide(name: str = "Sales chart", *, at: int = 1) -> WorkbookModel:
    """Sheet "Data" with three regions, a slide ``name`` after it with the chart "Sales" at 100, 50, 800 by 450, the
    text box "East leads" at 1000, 100, 400 by 100 and the picture "Logo" at 1200, 700, 200 by 100, and a sheet
    "Costs" last."""
    model = a_workbook()
    model.add_slide(Slide("p1", name), at)
    model.add_sheet(Sheet("s2", "Costs"), None)
    model.charts.define(ChartSpec(id="c1", kind="bar", range=a_range()))
    chart = ObjectBody("o1", "chart", 800, 450, "plain-image", ref="c1", name="Sales")
    model.insert_object(VisualObject(chart, SlideAnchor("p1", 100, 50)))
    words = ObjectBody(
        "t1", "text", 400, 100, "plain-box", paragraph_for("t1", "body-text", "East leads"), name="East leads"
    )
    model.insert_object(VisualObject(words, SlideAnchor("p1", 1000, 100)))
    asset = a_png()
    model.images.define(asset)
    picture = ObjectBody(
        "o2", "image", 200, 100, "plain-image", ref=asset.id, imported=an_import(asset.id), name="Logo"
    )
    model.insert_object(VisualObject(picture, SlideAnchor("p1", 1200, 700)))
    return model


def tab_names(model: WorkbookModel) -> list[tuple[str, str]]:
    return [(tab.kind, model.thing_name(tab.id)) for tab in model.tabs]


def xlsx_anchors(data: bytes, drawing: str = "xl/drawings/drawing1.xml") -> list[tuple[int, int, int, int, int, int]]:
    """``(col, colOff, row, rowOff, cx, cy)`` of every anchor of a drawing, in pixels."""
    root = etree.fromstring(read_parts(data)[drawing])
    found = []
    for anchor in root:
        start = anchor.find(f"{{{XDR}}}from")
        numbers = [int(start.findtext(f"{{{XDR}}}{tag}")) for tag in ("col", "colOff", "row", "rowOff")]
        extent = anchor.find(f"{{{XDR}}}ext")
        found.append(
            (
                numbers[0],
                numbers[1] // EMU,
                numbers[2],
                numbers[3] // EMU,
                *(int(extent.get(side)) // EMU for side in ("cx", "cy")),
            )
        )
    return found


def ods_frames(data: bytes, tab: str) -> list[tuple[str, str, str, str]]:
    """``(x, y, width, height)`` of every frame on the tab ``tab``, as the file writes them."""
    content = etree.fromstring(read_parts(data)["content.xml"])
    table = content.find(f".//{{{ODF['table']}}}table[@{{{ODF['table']}}}name='{tab}']")
    svg = ODF["svg"]
    return [
        tuple(frame.get(f"{{{svg}}}{side}") for side in ("x", "y", "width", "height"))
        for frame in table.iter(f"{{{ODF['draw']}}}frame")
    ]


def cm(pixels: float) -> str:
    return f"{pixels * 2.54 / 96:.4f}cm"


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_a_slide_is_a_tab_of_its_own_in_its_place_without_cells(fmt):
    write, _, _ = FORMATS[fmt]
    data = write(with_a_slide())
    if fmt == "ods":
        assert problems(data) == []
        content = etree.fromstring(read_parts(data)["content.xml"])
        tables = content.findall(f".//{{{ODF['table']}}}table")
        assert [t.get(f"{{{ODF['table']}}}name") for t in tables] == ["Data", "Sales chart", "Costs"]
        assert not [cell for cell in tables[1].iter(f"{{{ODF['table']}}}table-cell") if len(cell)]
    else:
        book = openpyxl.load_workbook(BytesIO(data))
        assert book.sheetnames == ["Data", "Sales chart", "Costs"]
        assert book["Sales chart"].max_row == 1 and book["Sales chart"]["A1"].value is None


def test_the_objects_of_a_slide_are_where_they_were_in_xlsx():
    # a column is 96 pixels and a row 26 (the model's own sizes, which the file says): 100, 50 is 4, 24 into B2
    anchors = xlsx_anchors(workbook_to_xlsx(with_a_slide()))
    assert anchors == [(1, 4, 1, 24, 800, 450), (10, 40, 3, 22, 400, 100), (12, 48, 26, 24, 200, 100)]


def test_the_objects_of_a_slide_are_where_they_were_in_ods():
    frames = ods_frames(workbook_to_ods(with_a_slide()), "Sales chart")
    assert frames == [
        (cm(100), cm(50), cm(800), cm(450)),
        (cm(1000), cm(100), cm(400), cm(100)),
        (cm(1200), cm(700), cm(200), cm(100)),
    ]


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_writing_a_slide_as_a_tab_is_not_reported(fmt):
    _, _, losses = FORMATS[fmt]
    assert losses(with_a_slide()) == losses(a_workbook())


def test_how_big_a_slide_is_on_its_tab_is_a_setting_of_the_export():
    half = SlideSize(px_per_unit=0.5)
    anchors = xlsx_anchors(workbook_to_xlsx(with_a_slide(), slide_size=half))
    assert anchors == [(0, 50, 0, 25, 400, 225), (5, 20, 1, 24, 200, 50), (6, 24, 13, 12, 100, 50)]
    frames = ods_frames(workbook_to_ods(with_a_slide(), slide_size=half), "Sales chart")
    assert frames[0] == (cm(50), cm(25), cm(400), cm(225))


def test_an_object_on_a_sheet_is_pinned_to_its_cell_as_before():
    model = a_workbook()
    model.charts.define(ChartSpec(id="c1", kind="bar", range=a_range()))
    model.insert_object(VisualObject(ObjectBody("o1", "chart", 300, 200, "plain-image", ref="c1"), _cell(4, 2)))
    assert xlsx_anchors(workbook_to_xlsx(model)) == [(2, 0, 4, 0, 300, 200)]
    assert ods_frames(workbook_to_ods(model), "Data") == [(cm(2 * 96), cm(4 * 26), cm(300), cm(200))]


def _cell(row: int, col: int):
    from claudia_computes import CellAnchor

    return CellAnchor("s1", row, col)


def placements(model: WorkbookModel, tab_id: str) -> list[tuple[str, int, int, int, int]]:
    """``(kind, x, y, w, h)`` of the objects on the slide ``tab_id``, bottom first."""
    return [(obj.body.kind, obj.anchor.x, obj.anchor.y, obj.body.w, obj.body.h) for obj in model.objects_on(tab_id)]


@pytest.mark.parametrize("fmt", sorted(FORMATS))
@pytest.mark.parametrize("size", [1.0, 0.5])
def test_a_slide_comes_back_as_a_slide_with_its_objects_where_they_were(fmt, size):
    write, read, _ = FORMATS[fmt]
    again = read(write(with_a_slide(), slide_size=SlideSize(size)))
    assert tab_names(again) == [("sheet", "Data"), ("slide", "Sales chart"), ("sheet", "Costs")]
    slide = again.tabs[1].id
    assert placements(again, slide) == [
        ("chart", 100, 50, 800, 450),
        ("text", 1000, 100, 400, 100),
        ("image", 1200, 700, 200, 100),
    ]
    chart, words, picture = again.objects_on(slide)
    assert (chart.body.name, words.body.name, picture.body.name) == ("Sales", "East leads", "Logo")
    assert (words.body.style, words.body.paragraph.style, words.body.paragraph.text) == (
        "plain-box",
        "body-text",
        "East leads",
    )


def test_the_file_says_which_tabs_are_slides_in_its_custom_properties():
    xlsx = openpyxl.load_workbook(BytesIO(workbook_to_xlsx(with_a_slide())))
    (mark,) = [prop for prop in xlsx.custom_doc_props if prop.name == "Claudia slides"]
    said = {"slides": ["Sales chart"], "px_per_unit": 1.0, "styles": {"East leads": ["plain-box", "body-text"]}}
    assert json.loads(mark.value) == said
    meta = read_parts(workbook_to_ods(with_a_slide()))["meta.xml"]
    assert json.loads(user_defined(meta)["Claudia slides"]) == said
    assert "Claudia slides" not in user_defined(read_parts(workbook_to_ods(a_workbook()))["meta.xml"])


def test_a_tab_renamed_in_another_program_is_a_sheet_with_the_objects_at_their_cells():
    parts = read_parts(workbook_to_xlsx(with_a_slide()))
    parts["xl/workbook.xml"] = parts["xl/workbook.xml"].replace(b'name="Sales chart"', b'name="Chart tab"')
    again = xlsx_to_workbook(write_parts(parts))
    assert tab_names(again) == [("sheet", "Data"), ("sheet", "Chart tab"), ("sheet", "Costs")]
    chart, picture = again.objects_on(again.tabs[1].id)
    assert [(o.body.kind, o.anchor.row, o.anchor.col) for o in (chart, picture)] == [("chart", 1, 1), ("image", 26, 12)]
    assert Loss("shape", "", 1) in xlsx_import_losses(write_parts(parts))  # (the text box, as on any sheet)


def test_a_tab_someone_typed_into_is_a_sheet():
    data = workbook_to_ods(with_a_slide())
    parts = read_parts(data)
    content = etree.fromstring(parts["content.xml"])
    table = content.find(f".//{{{ODF['table']}}}table[@{{{ODF['table']}}}name='Sales chart']")
    cell = next(table.iter(f"{{{ODF['table']}}}table-cell"))
    cell.set(f"{{{ODF['office']}}}value-type", "string")
    etree.SubElement(cell, f"{{{ODF['text']}}}p").text = "note"
    parts["content.xml"] = etree.tostring(content, xml_declaration=True, encoding="UTF-8")
    again = ods_to_workbook(write_parts(parts))
    assert tab_names(again)[1] == ("sheet", "Sales chart")
    sheet = again.sheets[again.tabs[1].id]
    assert sheet.cells[(0, 0)] == {"t": "text", "v": "note"}
    assert [obj.body.kind for obj in again.objects_on(sheet.id)] == ["chart", "image"]


def test_a_slide_name_a_sheet_cannot_have_is_written_the_way_a_sheet_can_be_called():
    model = with_a_slide("Q1/Q2 [draft]")
    assert openpyxl.load_workbook(BytesIO(workbook_to_xlsx(model))).sheetnames == ["Data", "Q1-Q2 -draft-", "Costs"]


def test_a_slide_named_like_a_sheet_gets_a_name_of_its_own():
    model = with_a_slide("Costs")
    assert openpyxl.load_workbook(BytesIO(workbook_to_xlsx(model))).sheetnames == ["Data", "Costs (2)", "Costs"]


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_a_kept_file_is_not_patched_with_a_slide_it_cannot_hold(fmt):
    write, read, _ = FORMATS[fmt]
    patch = {"xlsx": apply_edits_to_xlsx, "ods": apply_edits_to_ods}[fmt]
    original = write(a_workbook())
    baseline, current = read(original), read(original)
    current.add_slide(Slide("p1", "Sales chart"), None)
    with pytest.raises(UnsupportedEdit, match="slide"):
        patch(original, baseline, current)


# -- text boxes and shapes (D1479) -------------------------------------------------------------------------------------
XLSX_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def test_a_text_box_is_a_shape_with_its_words_in_the_look_of_their_style_in_xlsx():
    root = etree.fromstring(read_parts(workbook_to_xlsx(with_a_slide()))["xl/drawings/drawing1.xml"])
    (box,) = root.iter(f"{{{XDR}}}sp")
    assert box.find(f"{{{XDR}}}nvSpPr/{{{XDR}}}cNvSpPr").get("txBox") == "1"
    assert box.find(f"{{{XDR}}}nvSpPr/{{{XDR}}}cNvPr").get("name") == "East leads"
    assert box.find(f".//{{{XLSX_A}}}prstGeom").get("prst") == "rect"
    assert [t.text for t in box.iter(f"{{{XLSX_A}}}t")] == ["East leads"]
    run = box.find(f".//{{{XLSX_A}}}rPr")
    assert run.get("sz") == "975"  # Body text is 13 pixels: 9.75 points
    assert box.find(f".//{{{XLSX_A}}}pPr").get("algn") == "l"


def test_a_text_box_is_a_frame_with_a_text_box_and_its_words_in_a_named_style_in_ods():
    data = workbook_to_ods(with_a_slide())
    assert problems(data) == []
    content = etree.fromstring(read_parts(data)["content.xml"])
    (box,) = content.iter(f"{{{ODF['draw']}}}text-box")
    paragraph = box.find(f"{{{ODF['text']}}}p")
    assert paragraph.text == "East leads"
    style = paragraph.get(f"{{{ODF['text']}}}style-name")
    styles = etree.fromstring(read_parts(data)["styles.xml"])
    named = styles.find(f".//{{{ODF['style']}}}style[@{{{ODF['style']}}}name='{style}']")
    assert named.get(f"{{{ODF['style']}}}display-name") == "Body text"
    assert named.find(f"{{{ODF['style']}}}text-properties").get(f"{{{ODF['fo']}}}font-size") == "9.75pt"


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_a_shape_on_a_slide_comes_back_with_its_outline_and_words(fmt):
    write, read, _ = FORMATS[fmt]
    model = with_a_slide()
    words = paragraph_for("s9", "shape-label", "Go")
    shape = ObjectBody("s9", "shape", 150, 120, "plain-shape", words, ref="triangle", name="Arrow", rotation=30)
    model.shapes.define(primitive("triangle"))
    model.insert_object(VisualObject(shape, SlideAnchor("p1", 300, 600)))
    again = read(write(model))
    (back,) = [obj for obj in again.objects.values() if obj.body.kind == "shape"]
    assert (back.anchor.x, back.anchor.y, back.body.w, back.body.h, back.body.rotation) == (300, 600, 150, 120, 30)
    assert (back.body.shape, back.body.style, back.body.paragraph.style, back.body.paragraph.text) == (
        "triangle",
        "plain-shape",
        "shape-label",
        "Go",
    )


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_a_box_on_a_slide_is_written_and_one_on_a_sheet_is_still_reported(fmt):
    _, _, losses = FORMATS[fmt]
    assert not [loss for loss in losses(with_a_slide()) if loss.kind == "object"]
    model = a_workbook()
    words = ObjectBody("t1", "text", 400, 100, "plain-box", paragraph_for("t1", "body-text", "x"))
    model.insert_object(VisualObject(words, CellAnchor("s1", 0, 0)))
    assert Loss("object", "", 1) in losses(model)


def test_a_box_restyled_in_another_program_has_the_plain_style_and_says_its_look_is_lost():
    parts = read_parts(workbook_to_xlsx(with_a_slide()))
    drawing = parts["xl/drawings/drawing1.xml"]
    parts["xl/drawings/drawing1.xml"] = drawing.replace(
        b'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/>',
        b'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill>',
    )
    data = write_parts(parts)
    again = xlsx_to_workbook(data)
    (words,) = [obj for obj in again.objects.values() if obj.body.kind == "text"]
    assert words.body.style == "plain-box"
    assert Loss("look", "", 1) in xlsx_import_losses(data)


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_a_box_without_a_name_is_written_with_one_and_keeps_its_styles(fmt):
    write, read, _ = FORMATS[fmt]
    model = with_a_slide()
    words = ObjectBody("t2", "text", 300, 80, "plain-box", paragraph_for("t2", "shape-label", "Centred"))
    model.insert_object(VisualObject(words, SlideAnchor("p1", 100, 700)))
    again = read(write(model))
    (back,) = [obj for obj in again.objects.values() if obj.body.paragraph and obj.body.paragraph.text == "Centred"]
    assert (back.body.name, back.body.style, back.body.paragraph.style) == ("Text box 1", "plain-box", "shape-label")


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_the_objects_of_a_slide_come_back_stacked_as_they_were(fmt):
    write, read, _ = FORMATS[fmt]
    model = with_a_slide()
    picture, chart = model.get_object("o2"), model.get_object("o1")
    for obj in (picture, chart):
        model.delete_object(obj.id)
    model.insert_object(picture, 0)  # the picture at the back, the chart in front
    model.insert_object(chart)
    again = read(write(model))
    assert [obj.body.kind for obj in again.objects_on(again.tabs[1].id)] == ["image", "text", "chart"]


def test_a_box_restyled_in_another_program_says_its_look_is_lost_in_ods():
    parts = read_parts(workbook_to_ods(with_a_slide()))
    content = parts["content.xml"]
    parts["content.xml"] = content.replace(b'draw:fill="none"', b'draw:fill="solid" draw:fill-color="#ff0000"', 1)
    data = write_parts(parts)
    (words,) = [obj for obj in ods_to_workbook(data).objects.values() if obj.body.kind == "text"]
    assert words.body.style == "plain-box"
    assert Loss("look", "", 1) in ods_import_losses(data)
