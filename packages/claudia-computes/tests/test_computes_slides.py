"""Slides in computes (E6.31 step 2, D1471): a slide is a tab beside the sheets, a page of objects in the 16:9 frame of
the core's slide (D1470). Sheets and slides are two collections with one tab order."""

import pytest
from conftest import S1

from claudia_computes import AddSheet, AddSlide, RemoveSheet, RemoveSlide, Tab, TabsChanged, WorkbookModel
from claudia_core import (
    AddObject,
    CommandLog,
    DescribeThing,
    Document,
    MemoryStore,
    MoveObject,
    ObjectBody,
    RenameThing,
    SlideAnchor,
    paragraph_for,
)


def tabs(doc) -> list[tuple[str, str]]:
    return [(tab.kind, tab.id) for tab in doc.model.tabs]


def box(object_id: str = "t1", w: int = 400, h: int = 200) -> ObjectBody:
    return ObjectBody(object_id, "text", w, h, "plain-box", paragraph=paragraph_for(object_id, "body-text", "East"))


def text_box(object_id: str = "t1", slide: str = "p1", x: int = 100, y: int = 100) -> AddObject:
    return AddObject(box(object_id), SlideAnchor(slide, x, y).to_data())


def events_of(doc) -> list:
    seen: list = []
    doc.subscribe(seen.append)
    return seen


# -- one tab order -------------------------------------------------------------------------------------------------
def test_a_slide_goes_into_the_tab_order_where_it_is_asked_and_undo_takes_it_away(doc):
    doc.execute(AddSheet("s2", "Costs"), author="ana")
    doc.execute(AddSlide("p1", "Slide 1", index=1), author="ana")
    assert tabs(doc) == [("sheet", "s1"), ("slide", "p1"), ("sheet", "s2")]
    assert doc.model.tabs[1] == Tab("slide", "p1")
    assert doc.model.thing_name("p1") == "Slide 1"
    doc.undo("ana")
    assert tabs(doc) == [("sheet", "s1"), ("sheet", "s2")]
    assert "p1" not in doc.model.slides


def test_a_slide_without_a_place_goes_last(doc):
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    assert tabs(doc) == [("sheet", "s1"), ("slide", "p1")]


def test_a_sheet_added_after_a_slide_counts_the_slide_in_its_place(doc):
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    doc.execute(AddSheet("s2", "Costs", index=1), author="ana")
    assert tabs(doc) == [("sheet", "s1"), ("sheet", "s2"), ("slide", "p1")]
    assert list(doc.model.sheets) == ["s1", "s2"]


def test_removing_a_sheet_and_undoing_it_puts_it_back_between_the_slides(doc):
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    doc.execute(AddSheet("s2", "Costs"), author="ana")
    doc.execute(AddSlide("p2", "Slide 2"), author="ana")
    doc.execute(RemoveSheet("s2"), author="ana")
    assert tabs(doc) == [("sheet", "s1"), ("slide", "p1"), ("slide", "p2")]
    doc.undo("ana")
    assert tabs(doc) == [("sheet", "s1"), ("slide", "p1"), ("sheet", "s2"), ("slide", "p2")]


@pytest.mark.parametrize(
    ("command", "refusal"),
    [
        (AddSlide("s1", "Slide 1"), "exists already"),
        (AddSlide("P 1", "Slide 1"), "slide id"),
        (AddSlide("p1", "Sheet1"), "already a sheet"),
        (AddSlide("p1", ""), "needs a name"),
        (AddSlide("p1", "Slide 1", index=3), "no place 3"),
    ],
)
def test_a_slide_that_cannot_be_is_refused_and_changes_nothing(doc, command, refusal):
    with pytest.raises(ValueError, match=refusal):
        doc.execute(command, author="ana")
    assert tabs(doc) == [("sheet", "s1")]


def test_a_sheet_cannot_take_the_id_of_a_slide(doc):
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    with pytest.raises(ValueError, match="exists"):
        doc.execute(AddSheet("p1", "Costs"), author="ana")


# -- objects on a slide --------------------------------------------------------------------------------------------
def test_a_text_box_sits_on_a_slide_and_must_stay_in_its_frame(doc):
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    doc.execute(text_box(x=1200, y=700), author="ana")
    assert doc.model.get_object("t1").anchor == SlideAnchor("p1", 1200, 700)
    assert [obj.id for obj in doc.model.objects_on("p1")] == ["t1"]
    with pytest.raises(ValueError, match="stay on the slide"):
        doc.execute(MoveObject("t1", SlideAnchor("p1", 1300, 700).to_data()), author="ana")


@pytest.mark.parametrize(
    ("anchor", "refusal"),
    [
        ({"kind": "cell", "holder": "p1", "row": 0, "col": 0}, "is a slide"),
        ({"kind": "slide", "holder": "s1", "x": 0, "y": 0}, "is a sheet"),
    ],
)
def test_an_anchor_must_be_of_the_kind_of_its_tab(doc, anchor, refusal):
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    with pytest.raises(ValueError, match=refusal):
        doc.execute(AddObject(box(), anchor), author="ana")


def test_a_slide_that_still_has_objects_is_not_removed(doc):
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    doc.execute(text_box(), author="ana")
    with pytest.raises(ValueError, match="still has objects"):
        doc.execute(RemoveSlide("p1"), author="ana")


def test_removing_an_empty_slide_and_undoing_it_gives_back_its_place_name_and_description(doc):
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    doc.execute(AddSheet("s2", "Costs"), author="ana")
    doc.execute(DescribeThing("p1", "The numbers"), author="ana")
    doc.execute(RemoveSlide("p1"), author="ana")
    assert tabs(doc) == [("sheet", "s1"), ("sheet", "s2")]
    doc.undo("ana")
    assert tabs(doc) == [("sheet", "s1"), ("slide", "p1"), ("sheet", "s2")]
    assert (doc.model.thing_name("p1"), doc.model.thing_description("p1")) == ("Slide 1", "The numbers")


# -- names and descriptions ----------------------------------------------------------------------------------------
def test_a_slide_is_renamed_and_described_like_a_sheet_and_the_clients_hear_of_it(doc):
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    seen = events_of(doc)
    doc.execute(RenameThing("p1", "Sales chart"), author="ana")
    doc.execute(DescribeThing("p1", "East leads"), author="ana")
    assert (doc.model.thing_name("p1"), doc.model.thing_description("p1")) == ("Sales chart", "East leads")
    assert TabsChanged() in seen
    with pytest.raises(ValueError, match="already a sheet"):
        doc.execute(RenameThing("p1", "Sheet1"), author="ana")
    with pytest.raises(ValueError, match="needs a name"):
        doc.execute(RenameThing("p1", ""), author="ana")


@pytest.mark.parametrize(
    "command",
    [AddSlide("p1", "Slide 1"), AddSheet("s2", "Costs"), RenameThing(S1, "Plan")],
)
def test_the_clients_hear_when_the_tabs_change(doc, command):
    seen = events_of(doc)
    doc.execute(command, author="ana")
    assert seen.count(TabsChanged()) == 1
    assert TabsChanged().to_data() == {"type": "tabs"}


# -- kept ----------------------------------------------------------------------------------------------------------
def test_slides_and_their_objects_survive_being_stored_loaded_and_replayed(doc):
    doc.execute(AddSlide("p1", "Slide 1", index=0), author="ana")
    doc.execute(DescribeThing("p1", "Opening"), author="ana")
    doc.execute(text_box(), author="ana")
    state = doc.model.serialize()
    again = WorkbookModel.restore(state)
    assert [(t.kind, t.id) for t in again.tabs] == [("slide", "p1"), ("sheet", "s1")]
    assert (again.thing_name("p1"), again.thing_description("p1")) == ("Slide 1", "Opening")
    assert again.get_object("t1").anchor == SlideAnchor("p1", 100, 100)
    assert again.serialize() == state
    replayed = Document.open(WorkbookModel, CommandLog.from_data(doc.log.to_data(), WorkbookModel.registry))
    assert replayed.model.serialize() == state
    # 17: tabs, one order of sheets and slides, and the slides as records (E6.31, D1471)
    assert WorkbookModel.state_schema == 17


def test_a_stored_state_whose_tabs_miss_a_sheet_or_a_slide_is_refused(doc):
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    state = doc.model.serialize()
    state["tabs"] = [{"kind": "sheet", "id": "s1"}]
    with pytest.raises(ValueError, match="every sheet and every slide exactly once"):
        WorkbookModel.restore(state)


def test_redacting_takes_what_was_written_about_a_slide_and_keeps_the_slide(doc):
    doc.execute(AddSlide("p1", "Slide 1"), author="ana")
    doc.execute(DescribeThing("p1", "secret"), author="ana")
    doc.model.blank(None)
    assert doc.model.thing_description("p1") == ""
    assert AddSlide("p1", "Quarterly secrets", index=2).redacted() == AddSlide("p1", "p1", index=2)


def test_a_new_document_still_starts_with_one_sheet():
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(WorkbookModel.setup_commands(None)[0], author="ana")
    assert [(t.kind, t.id) for t in doc.model.tabs] == [("sheet", "s1")]
