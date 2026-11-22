"""Slides in computes on the wire (E6.31 step 2, D1473): the tabs in one order, and the objects of a slide placed with
the words creates uses for them (`slide`, `x`, `y`). Nothing on the wire adds a slide yet: a chart brings one (step 3),
so these tests put it there through the document."""

import pytest
from test_server_computes import ANN, VERA, add_image, call, tiny_gif

from claudia_computes import AddSheet, AddSlide, TabsChanged, WorkbookModel
from claudia_core import Document, MemoryStore
from claudia_server.protocol import RequestError


@pytest.fixture
def book():
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet("s1", "Sheet1"), author="ann")
    doc.execute(AddSlide("p1", "Sales chart"), author="ann")
    doc.execute(AddSheet("s2", "Costs"), author="ann")
    return doc


def box_on_slide(doc, **params):
    given = {"slide": "p1", "kind": "text", "x": 100, "y": 80, "w": 400, "h": 120, "text": "East leads", **params}
    return call(doc, "add_object", given)["object"]


def test_the_tabs_are_one_list_of_sheets_and_slides_in_order(book):
    assert call(book, "tabs") == [
        {"kind": "sheet", "id": "s1", "name": "Sheet1"},
        {"kind": "slide", "id": "p1", "name": "Sales chart"},
        {"kind": "sheet", "id": "s2", "name": "Costs"},
    ]
    assert [sheet["id"] for sheet in call(book, "sheets")] == ["s1", "s2"]
    assert call(book, "tabs", account=VERA) == call(book, "tabs")


def test_the_clients_hear_of_a_new_tab_and_of_a_new_name():
    doc = Document(WorkbookModel(), store=MemoryStore())
    seen: list = []
    doc.subscribe(seen.append)
    call(doc, "add_sheet", {"name": "Budget"})
    assert [event.to_data() for event in seen if isinstance(event, TabsChanged)] == [{"type": "tabs"}]


def test_a_text_box_is_put_on_a_slide_moved_and_resized_with_the_words_of_creates(book):
    object_id = box_on_slide(book)
    shown = call(book, "slide", {"slide": "p1"})
    assert shown["slide"] == "p1"
    (box,) = shown["objects"]
    anchor = {"kind": "slide", "holder": "p1", "x": 100, "y": 80}
    assert (box["id"], box["anchor"], box["w"], box["h"]) == (object_id, anchor, 400, 120)
    call(book, "move_object", {"id": object_id, "x": 300, "y": 200})
    call(book, "resize_object", {"id": object_id, "x": 280, "y": 180, "w": 500, "h": 160})
    (box,) = call(book, "slide", {"slide": "p1"})["objects"]
    assert (box["anchor"]["x"], box["anchor"]["y"], box["w"], box["h"]) == (280, 180, 500, 160)


def test_a_picture_goes_on_a_slide_and_one_on_a_sheet_still_hangs_at_a_cell(book):
    picture = call(
        book,
        "add_image",
        {
            "slide": "p1",
            "x": 0,
            "y": 0,
            "w": 400,
            "h": 200,
            "data": tiny_gif(400, 200),
            "alt": "a picture",
            "source_name": "a.gif",
        },
    )["object"]
    assert call(book, "slide", {"slide": "p1"})["objects"][0]["id"] == picture
    on_sheet = add_image(book)
    assert book.model.get_object(on_sheet).anchor.to_data() == {"kind": "cell", "holder": "s1", "row": 2, "col": 2}


def picture(**params) -> dict:
    return {"w": 400, "h": 200, "data": tiny_gif(400, 200), "alt": "a picture", "source_name": "a.gif", **params}


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"slide": "p1", "row": 1, "col": 1}, "bad_request"),  # a slide is placed on with x and y
        ({"sheet": "s1", "x": 1, "y": 1}, "bad_request"),  # a sheet with row and col
        ({"sheet": "s1", "slide": "p1", "x": 1, "y": 1}, "bad_request"),  # one of them
        ({"x": 1, "y": 1}, "bad_request"),
        ({"slide": "p9", "x": 1, "y": 1}, "command_error"),  # no such slide
        ({"slide": "s1", "x": 1, "y": 1}, "command_error"),  # a sheet named as a slide
        ({"slide": "p1", "x": 1300, "y": 1}, "command_error"),  # off the slide
    ],
)
def test_a_place_that_is_not_one_is_refused(book, params, code):
    with pytest.raises(RequestError) as refused:
        call(book, "add_image", picture(**params))
    assert refused.value.code == code


def test_a_text_box_or_a_shape_goes_on_a_slide_and_not_on_a_sheet(book):
    with pytest.raises(RequestError) as refused:
        call(book, "add_object", {"sheet": "s1", "row": 1, "col": 1, "kind": "text", "w": 400, "h": 120})
    assert refused.value.code == "bad_request"
    circle = box_on_slide(book, kind="shape", shape="circle", w=200, h=200)
    assert book.model.get_object(circle).body.kind == "shape"


def test_a_moved_object_stays_on_its_own_kind_of_tab(book):
    object_id = box_on_slide(book)
    with pytest.raises(RequestError) as refused:
        call(book, "move_object", {"id": object_id, "row": 1, "col": 1})
    assert refused.value.code == "bad_request"


def test_a_slide_is_named_and_described_like_any_other_thing(book):
    call(book, "name_and_describe", {"id": "p1", "name": "East", "description": "Where the money is"})
    assert call(book, "tabs")[1] == {"kind": "slide", "id": "p1", "name": "East"}
    assert book.model.thing_description("p1") == "Where the money is"


def test_a_viewer_sees_a_slide_and_its_objects_and_changes_nothing(book):
    box_on_slide(book)
    assert len(call(book, "slide", {"slide": "p1"}, account=VERA)["objects"]) == 1
    with pytest.raises(RequestError):
        box_on_slide_as(book, VERA)
    assert call(book, "slide", {"slide": "p1"}, account=ANN)["objects"][0]["paragraph"]["text"] == "East leads"


def box_on_slide_as(doc, account):
    given = {"slide": "p1", "kind": "text", "x": 100, "y": 80, "w": 400, "h": 120}
    return call(doc, "add_object", given, account=account)


def test_asking_for_a_slide_that_is_not_one_is_refused(book):
    with pytest.raises(RequestError) as refused:
        call(book, "slide", {"slide": "s1"})
    assert refused.value.code == "command_error"


@pytest.mark.parametrize("fmt", ["xlsx", "ods"])
def test_an_export_says_that_a_slide_became_a_sheet(book, fmt):
    losses = call(book, "export_office", {"format": fmt})["losses"]
    assert {"kind": "slide", "detail": "Sales chart", "count": 1} in losses


def test_a_new_sheet_does_not_take_the_id_of_a_slide():
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet("s1", "Sheet1"), author="ann")
    doc.execute(AddSlide("s2", "Sales chart"), author="ann")
    added = call(doc, "add_sheet", {"name": "Costs"})["sheet"]
    assert added not in ("s1", "s2")
    assert [tab["kind"] for tab in call(doc, "tabs")] == ["sheet", "slide", "sheet"]
