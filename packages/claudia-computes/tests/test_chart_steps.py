"""What a chart step takes along (E6.31 step 3, D1472, D1475): one place decides it, and each step is one undo step.

A chart is made on a new slide, on the slide shown or on a sheet; "Move to Slide" puts a chart of a sheet on a new
slide; removing objects takes each chart's definition along and every slide left empty. A slide made for a chart is
"Slide n" and the chart keeps its own name (owner, 2026-11-23).
"""

import pytest
from conftest import S1, chart_spec

from claudia_computes import AddSheet, AddSlide, CellAnchor, RemoveSlide, SheetId, WorkbookModel, chart_steps
from claudia_computes.chart_steps import NewChart
from claudia_core import (
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    AddObject,
    ObjectBody,
    SlideAnchor,
    paragraph_for,
)


def tabs(doc) -> list[tuple[str, str]]:
    return [(tab.kind, tab.id) for tab in doc.model.tabs]


def new_chart(object_id: str = "o1", name: str = "Sales", spec_id: str = "c1") -> NewChart:
    return NewChart(spec_id, object_id, name, chart_spec(spec_id).to_data())


def frame(doc, object_id: str):
    obj = doc.model.get_object(object_id)
    return obj.anchor, obj.body.w, obj.body.h


def a_chart_on_the_sheet(doc, object_id: str = "o1", name: str = "Sales") -> None:
    step = chart_steps.on_sheet(doc.model, new_chart(object_id, name), CellAnchor(SheetId(S1), 4, 2), 480, 300)
    doc.execute(step, author="ana")


def text_box(object_id: str, slide: str) -> AddObject:
    body = ObjectBody(object_id, "text", 400, 200, "plain-box", paragraph=paragraph_for(object_id, "body-text", "Note"))
    return AddObject(body, SlideAnchor(slide, 100, 100).to_data())


# -- a chart on a new slide -------------------------------------------------------------------------------------------
def test_a_chart_on_a_new_slide_comes_right_after_the_tab_and_fills_the_frame(doc):
    doc.execute(AddSheet("s2", "Costs"), author="ana")
    step = chart_steps.as_new_slide(doc.model, new_chart(), slide_id="p1", slide_name="Slide 1", after=S1)
    doc.execute(step, author="ana")
    assert tabs(doc) == [("sheet", "s1"), ("slide", "p1"), ("sheet", "s2")]
    assert doc.model.thing_name("p1") == "Slide 1"
    assert doc.model.thing_name("o1") == "Sales"
    assert frame(doc, "o1") == (SlideAnchor("p1", 0, 0), SLIDE_WIDTH, SLIDE_HEIGHT)
    assert doc.model.get_object("o1").body.chart == "c1"
    assert "c1" in doc.model.charts


def test_one_undo_takes_the_slide_its_chart_and_the_definition_away(doc):
    step = chart_steps.as_new_slide(doc.model, new_chart(), slide_id="p1", slide_name="Slide 1", after=S1)
    doc.execute(step, author="ana")
    doc.undo("ana")
    assert tabs(doc) == [("sheet", "s1")]
    assert "o1" not in doc.model.objects
    assert "c1" not in doc.model.charts


# -- a chart on the slide shown, or on a sheet ------------------------------------------------------------------------
def test_a_second_chart_on_a_slide_takes_half_the_frame_in_its_middle(doc):
    doc.execute(
        chart_steps.as_new_slide(doc.model, new_chart(), slide_id="p1", slide_name="Slide 1", after=S1), author="ana"
    )
    doc.execute(chart_steps.on_slide(doc.model, new_chart("o2", "Sales 2", "c2"), "p1"), author="ana")
    assert tabs(doc) == [("sheet", "s1"), ("slide", "p1")]
    assert frame(doc, "o2") == (
        SlideAnchor("p1", SLIDE_WIDTH // 4, SLIDE_HEIGHT // 4),
        SLIDE_WIDTH // 2,
        SLIDE_HEIGHT // 2,
    )
    assert doc.model.get_object("o2").body.chart == "c2"


def test_a_chart_on_a_sheet_is_one_step_with_its_definition(doc):
    a_chart_on_the_sheet(doc)
    assert frame(doc, "o1") == (CellAnchor(SheetId(S1), 4, 2), 480, 300)
    doc.undo("ana")
    assert "o1" not in doc.model.objects and "c1" not in doc.model.charts


# -- Move to Slide ----------------------------------------------------------------------------------------------------
def test_moving_a_chart_to_a_slide_makes_the_slide_after_its_sheet_and_the_chart_keeps_its_name(doc):
    doc.execute(AddSheet("s2", "Costs"), author="ana")
    a_chart_on_the_sheet(doc)
    doc.execute(chart_steps.to_new_slide(doc.model, "o1", slide_id="p1", slide_name="Slide 1"), author="ana")
    assert tabs(doc) == [("sheet", "s1"), ("slide", "p1"), ("sheet", "s2")]
    assert frame(doc, "o1") == (SlideAnchor("p1", 0, 0), SLIDE_WIDTH, SLIDE_HEIGHT)
    assert doc.model.thing_name("o1") == "Sales"
    assert doc.model.stack_of(S1) == ()


def test_one_undo_puts_the_chart_back_where_it_was_and_takes_the_slide_away(doc):
    a_chart_on_the_sheet(doc)
    doc.execute(chart_steps.to_new_slide(doc.model, "o1", slide_id="p1", slide_name="Slide 1"), author="ana")
    doc.undo("ana")
    assert frame(doc, "o1") == (CellAnchor(SheetId(S1), 4, 2), 480, 300)
    assert tabs(doc) == [("sheet", "s1")]


def test_undoing_the_move_keeps_the_slide_when_a_colleague_put_something_on_it(doc):
    a_chart_on_the_sheet(doc)
    doc.execute(chart_steps.to_new_slide(doc.model, "o1", slide_id="p1", slide_name="Slide 1"), author="ana")
    doc.execute(text_box("t1", "p1"), author="ben")
    doc.undo("ana")
    assert frame(doc, "o1") == (CellAnchor(SheetId(S1), 4, 2), 480, 300)
    assert tabs(doc) == [("sheet", "s1"), ("slide", "p1")]
    assert doc.model.stack_of("p1") == ("t1",)


def test_only_a_chart_on_a_sheet_moves_to_a_slide(doc):
    doc.execute(
        chart_steps.as_new_slide(doc.model, new_chart(), slide_id="p1", slide_name="Slide 1", after=S1), author="ana"
    )
    with pytest.raises(ValueError, match="on a sheet"):
        chart_steps.to_new_slide(doc.model, "o1", slide_id="p2", slide_name="Slide 2")


# -- removal ----------------------------------------------------------------------------------------------------------
def test_removing_the_only_chart_of_a_slide_takes_the_slide_and_the_definition_along(doc):
    doc.execute(
        chart_steps.as_new_slide(doc.model, new_chart(), slide_id="p1", slide_name="Slide 1", after=S1), author="ana"
    )
    doc.execute(chart_steps.removal(doc.model, ["o1"]), author="ana")
    assert tabs(doc) == [("sheet", "s1")]
    assert "c1" not in doc.model.charts
    doc.undo("ana")
    assert tabs(doc) == [("sheet", "s1"), ("slide", "p1")]
    assert frame(doc, "o1") == (SlideAnchor("p1", 0, 0), SLIDE_WIDTH, SLIDE_HEIGHT)
    assert doc.model.thing_name("p1") == "Slide 1"


def test_a_slide_with_something_left_stays(doc):
    doc.execute(
        chart_steps.as_new_slide(doc.model, new_chart(), slide_id="p1", slide_name="Slide 1", after=S1), author="ana"
    )
    doc.execute(text_box("t1", "p1"), author="ana")
    doc.execute(chart_steps.removal(doc.model, ["o1"]), author="ana")
    assert tabs(doc) == [("sheet", "s1"), ("slide", "p1")]
    doc.execute(chart_steps.removal(doc.model, ["t1"]), author="ana")
    assert tabs(doc) == [("sheet", "s1")]


def test_removing_a_chart_on_a_sheet_keeps_the_sheet(doc):
    a_chart_on_the_sheet(doc)
    doc.execute(chart_steps.removal(doc.model, ["o1"]), author="ana")
    assert tabs(doc) == [("sheet", "s1")]
    assert "c1" not in doc.model.charts


# -- a slide is not made or taken by hand -----------------------------------------------------------------------------
def test_the_undo_of_a_slide_made_for_a_chart_leaves_a_slide_a_colleague_uses(doc):
    """The inverse of adding a slide takes it away only while it is empty: a slide goes with its last object."""
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    doc.execute(text_box("t1", "p1"), author="ben")
    doc.undo("ana")
    assert tabs(doc) == [("sheet", "s1"), ("slide", "p1")]


def test_a_slide_is_still_refused_to_be_removed_while_it_has_objects(doc):
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    doc.execute(text_box("t1", "p1"), author="ana")
    with pytest.raises(ValueError):
        doc.execute(RemoveSlide("p1"), author="ana")


# -- no chart tabs ----------------------------------------------------------------------------------------------------
def test_a_workbook_stores_no_chart_tabs_and_its_charts_survive_a_snapshot(doc):
    doc.execute(
        chart_steps.as_new_slide(doc.model, new_chart(), slide_id="p1", slide_name="Slide 1", after=S1), author="ana"
    )
    state = doc.model.serialize()
    # "charts" holds the charts' definitions (D1476), the object is of the kind "chart"; no tab is a chart
    assert [spec["id"] for spec in state["charts"]] == ["c1"]
    assert doc.model.get_object("o1").body.kind == "chart"
    assert "diagrams" not in state
    assert {tab.kind for tab in doc.model.tabs} == {"sheet", "slide"}
    assert WorkbookModel.restore(state).serialize() == state
