"""A workbook's slides in ods and xlsx (E6.31 step 5, D1477): a slide is a tab of its own in its place among the
sheets, without cells, and its objects are where they were on the slide: one unit of the slide is one pixel of the tab
(``SlideSize``, a setting of the export). Writing a slide this way is not reported."""

from __future__ import annotations

from io import BytesIO

import openpyxl
import pytest
from claudia_computes_io import (
    SlideSize,
    UnsupportedEdit,
    apply_edits_to_ods,
    apply_edits_to_xlsx,
    ods_export_losses,
    ods_to_workbook,
    workbook_to_ods,
    workbook_to_xlsx,
    xlsx_export_losses,
    xlsx_to_workbook,
)
from lxml import etree
from test_ods_charts import a_range, a_workbook
from test_pictures import a_png, an_import

from claudia_computes import ChartSpec, ObjectBody, VisualObject, WorkbookModel
from claudia_computes.model import Sheet
from claudia_core import Slide, SlideAnchor
from claudia_odf_io import NS as ODF
from claudia_odf_io import problems
from claudia_opc_io import read_parts

FORMATS = {
    "xlsx": (workbook_to_xlsx, xlsx_to_workbook, xlsx_export_losses),
    "ods": (workbook_to_ods, ods_to_workbook, ods_export_losses),
}
XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
EMU = 9525  # in a pixel


def with_a_slide(name: str = "Sales chart", *, at: int = 1) -> WorkbookModel:
    """Sheet "Data" with three regions, a slide ``name`` after it with the chart "Sales" at 100, 50, 800 by 450 and
    the picture "Logo" at 1200, 700, 200 by 100, and a sheet "Costs" last."""
    model = a_workbook()
    model.add_slide(Slide("p1", name), at)
    model.add_sheet(Sheet("s2", "Costs"), None)
    model.charts.define(ChartSpec(id="c1", kind="bar", range=a_range()))
    chart = ObjectBody("o1", "chart", 800, 450, "plain-image", ref="c1", name="Sales")
    model.insert_object(VisualObject(chart, SlideAnchor("p1", 100, 50)))
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
        assert not list(tables[1].iter(f"{{{ODF['text']}}}p"))
    else:
        book = openpyxl.load_workbook(BytesIO(data))
        assert book.sheetnames == ["Data", "Sales chart", "Costs"]
        assert book["Sales chart"].max_row == 1 and book["Sales chart"]["A1"].value is None


def test_the_objects_of_a_slide_are_where_they_were_in_xlsx():
    # a column is 96 pixels and a row 26 (the model's own sizes, which the file says): 100, 50 is 4, 24 into B2
    anchors = xlsx_anchors(workbook_to_xlsx(with_a_slide()))
    assert anchors == [(1, 4, 1, 24, 800, 450), (12, 48, 26, 24, 200, 100)]


def test_the_objects_of_a_slide_are_where_they_were_in_ods():
    frames = ods_frames(workbook_to_ods(with_a_slide()), "Sales chart")
    assert frames == [(cm(100), cm(50), cm(800), cm(450)), (cm(1200), cm(700), cm(200), cm(100))]


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_writing_a_slide_as_a_tab_is_not_reported(fmt):
    _, _, losses = FORMATS[fmt]
    assert losses(with_a_slide()) == losses(a_workbook())


def test_how_big_a_slide_is_on_its_tab_is_a_setting_of_the_export():
    half = SlideSize(px_per_unit=0.5)
    anchors = xlsx_anchors(workbook_to_xlsx(with_a_slide(), slide_size=half))
    assert anchors == [(0, 50, 0, 25, 400, 225), (6, 24, 13, 12, 100, 50)]
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


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_read_back_a_slide_tab_is_a_sheet_with_its_chart(fmt):
    write, read, _ = FORMATS[fmt]
    again = read(write(with_a_slide()))
    assert tab_names(again) == [("sheet", "Data"), ("sheet", "Sales chart"), ("sheet", "Costs")]
    (chart,) = again.objects_on(again.tabs[1].id)
    assert (chart.body.kind, chart.anchor.row, chart.anchor.col) == ("chart", 1, 1)


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
