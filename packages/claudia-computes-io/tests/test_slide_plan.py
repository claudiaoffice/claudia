"""A workbook's slides in ods and xlsx (E6.31 step 2, D1473): neither format has slides, so a slide is written as a
sheet of its own in its place among the sheets, with its objects on it, scaled from the slide's 1600 × 900 units to
the size a chart tab is written at, and the export says so. Read back, what was a slide is a sheet."""

from __future__ import annotations

from io import BytesIO

import openpyxl
import pytest
from claudia_computes_io import (
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
from claudia_computes_io._pictures import written_pictures
from claudia_computes_io.slide_plan import SLIDE_SCALE, with_slides_as_sheets
from test_ods_charts import S1, a_range, a_workbook
from test_pictures import a_png, an_import

from claudia_computes import ChartSpec, ObjectBody, VisualObject, WorkbookModel
from claudia_computes.model import DEFAULT_COL_WIDTH, DEFAULT_ROW_HEIGHT, Sheet
from claudia_core import Slide, SlideAnchor, paragraph_for
from claudia_odf_io import Loss, problems

FORMATS = {
    "xlsx": (workbook_to_xlsx, xlsx_to_workbook, xlsx_export_losses),
    "ods": (workbook_to_ods, ods_to_workbook, ods_export_losses),
}


def with_a_slide(name: str = "Sales chart", *, at: int = 1) -> WorkbookModel:
    """Sheet "Data" with three regions, a slide ``name`` after it with a chart filling most of it and a picture, and a
    sheet "Costs" last."""
    model = a_workbook()
    model.add_slide(Slide("p1", name), at)
    model.add_sheet(Sheet("s2", "Costs"), None)
    model.diagrams.define(ChartSpec(id="c1", kind="bar", range=a_range()))
    chart = ObjectBody("o1", "diagram", 1200, 700, "plain-image", ref="c1")
    model.insert_object(VisualObject(chart, SlideAnchor("p1", 200, 100)))
    asset = a_png()
    model.images.define(asset)
    picture = ObjectBody("o2", "image", 400, 200, "plain-image", ref=asset.id, imported=an_import(asset.id))
    model.insert_object(VisualObject(picture, SlideAnchor("p1", 800, 450)))
    return model


def tab_names(model: WorkbookModel) -> list[tuple[str, str]]:
    return [(tab.kind, model.thing_name(tab.id)) for tab in model.tabs]


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_a_slide_becomes_a_sheet_in_its_place_with_its_chart_on_it(fmt):
    write, read, _ = FORMATS[fmt]
    data = write(with_a_slide())
    if fmt == "ods":
        assert problems(data) == []
    again = read(data)
    assert tab_names(again) == [("sheet", "Data"), ("sheet", "Sales chart"), ("sheet", "Costs")]
    assert [obj.body.kind for obj in again.objects_on(again.tabs[1].id)] == ["diagram"]  # (pictures are not read yet)


def test_the_picture_of_a_slide_is_written_on_the_sheet_it_becomes():
    (picture,) = written_pictures(with_slides_as_sheets(with_a_slide()), svg_beside_png=False)
    assert (picture.sheet_name, picture.width, picture.height) == ("Sales chart", 180, 90)


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_downloading_says_that_a_slide_became_a_sheet(fmt):
    _, _, losses = FORMATS[fmt]
    found = losses(with_a_slide())
    assert Loss("slide", "Sales chart", 1) in found
    assert not [loss for loss in losses(a_workbook()) if loss.kind == "slide"]


def test_the_objects_of_a_slide_hang_at_the_cell_nearest_to_where_they_are_scaled_to_a_chart_tab():
    sheets = with_slides_as_sheets(with_a_slide())
    assert SLIDE_SCALE == 0.45  # 1600 × 900 into the 720 × 432 of a chart tab, keeping the proportions
    picture = sheets.get_object("o2")
    assert (picture.body.w, picture.body.h) == (180, 90)
    assert (picture.anchor.row, picture.anchor.col) == (
        round(450 * SLIDE_SCALE / DEFAULT_ROW_HEIGHT),
        round(800 * SLIDE_SCALE / DEFAULT_COL_WIDTH),
    )
    assert sheets.tabs[1].kind == "sheet" and sheets.thing_name("p1") == "Sales chart"
    assert sheets.sheets["p1"].cells == {}


def test_a_slide_name_a_sheet_cannot_have_is_written_the_way_a_sheet_can_be_called():
    model = with_a_slide("Q1/Q2 [draft]")
    assert openpyxl.load_workbook(BytesIO(workbook_to_xlsx(model))).sheetnames == ["Data", "Q1-Q2 -draft-", "Costs"]


def test_a_tiny_object_on_a_slide_is_written_at_the_smallest_size_a_sheet_allows():
    model = with_a_slide()
    words = ObjectBody("t1", "text", 30, 30, "plain-box", paragraph_for("t1", "body-text", "x"))
    model.insert_object(VisualObject(words, SlideAnchor("p1", 0, 0)))
    tiny = with_slides_as_sheets(model).get_object("t1")
    assert (tiny.body.w, tiny.body.h) == (model.min_object_size, model.min_object_size)


def test_a_workbook_without_slides_is_written_as_it_is():
    model = a_workbook()
    assert with_slides_as_sheets(model) is model
    assert S1 in model.sheets


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_a_kept_file_is_not_patched_with_a_slide_it_cannot_hold(fmt):
    write, read, _ = FORMATS[fmt]
    patch = {"xlsx": apply_edits_to_xlsx, "ods": apply_edits_to_ods}[fmt]
    original = write(a_workbook())
    baseline, current = read(original), read(original)
    current.add_slide(Slide("p1", "Sales chart"), None)
    with pytest.raises(UnsupportedEdit, match="slide"):
        patch(original, baseline, current)
