"""Names over the wire (D550): the server gives every new thing a name of its own, anybody may rename it, and a
document from before names gets them on request."""

import pytest
from test_server_computes import tiny_gif
from test_server_creates import add_image, add_shape, add_text, call

from claudia_computes import AddSheet, WorkbookModel
from claudia_core import Document, MemoryStore, RenameThing
from claudia_creates import SlideModel
from claudia_server.auth import Account
from claudia_server.computes import computes_methods
from claudia_server.i18n import translate
from claudia_server.protocol import Context, Limits, RequestError

BEN = Account("ben", "editor")
VERA = Account("vera", "viewer")


@pytest.fixture
def deck():
    return Document(SlideModel.empty(), store=MemoryStore())


@pytest.fixture
def book():
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet("s1", "Sheet1"), author="ann")
    return doc


ANN = Account("ann", "owner")


def on_book(doc, name, params=None, account=ANN, locale="en"):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0, locale=locale)
    return computes_methods.dispatch(ctx, name, params)


def name_of(doc, thing: str) -> str:
    return doc.model.thing_name(thing)


# -- slides and their objects -------------------------------------------------------------------------------------
def test_a_new_slide_gets_the_first_free_default_name(deck):
    first = call(deck, "add_slide")["slide"]
    second = call(deck, "add_slide")["slide"]
    assert (name_of(deck, first), name_of(deck, second)) == ("Slide 1", "Slide 2")


def test_the_slide_list_says_each_slides_name(deck):
    call(deck, "add_slide")
    assert [s["name"] for s in call(deck, "slides")] == ["", "Slide 1"]


def test_new_objects_are_named_by_what_they_are_and_counted_per_name(deck):
    text = add_text(deck)
    shape = add_shape(deck)
    again = add_text(deck, y=300)
    picture = add_image(deck)
    assert [name_of(deck, o) for o in (text, shape, again, picture)] == [
        "Text box 1",
        "Shape 1",
        "Text box 2",
        "Picture 1",
    ]


def test_a_default_name_skips_a_name_somebody_took(deck):
    first = add_text(deck)
    call(deck, "rename_thing", {"id": first, "name": "Text box 2"})
    second = add_text(deck, y=300)
    assert name_of(deck, second) == "Text box 1"
    third = add_text(deck, y=500)
    assert name_of(deck, third) == "Text box 3"


def test_a_removed_things_default_name_comes_free_again(deck):
    first = add_text(deck)
    call(deck, "remove_object", {"id": first})
    assert name_of(deck, add_text(deck, y=300)) == "Text box 1"


def test_default_names_are_said_in_the_language_of_the_one_who_made_the_thing(deck):
    ctx = Context(deck, Account("ann", "owner"), Limits(), users=lambda: ["ann"], lock_seconds=30.0, locale="de")
    from claudia_server.creates import creates_methods

    made = creates_methods.dispatch(
        ctx, "add_object", {"slide": "s1", "kind": "text", "x": 1, "y": 1, "w": 400, "h": 100}
    )["object"]
    assert name_of(deck, made) == f"{translate('Text box', 'de')} 1"


# -- renaming -----------------------------------------------------------------------------------------------------
def test_anyone_who_may_edit_renames_a_thing_and_the_old_name_is_free_again(deck):
    box = add_text(deck)
    done = call(deck, "rename_thing", {"id": box, "name": "  Intro  "}, account=BEN)
    assert done["revision"] is not None
    assert name_of(deck, box) == "Intro"
    other = add_text(deck, y=300)
    call(deck, "rename_thing", {"id": other, "name": "Text box 1"})
    assert name_of(deck, other) == "Text box 1"


def test_a_slide_is_renamed_like_an_object(deck):
    call(deck, "rename_thing", {"id": "s1", "name": "Title"})
    assert call(deck, "slides")[0]["name"] == "Title"


def test_a_viewer_cannot_rename(deck):
    box = add_text(deck)
    with pytest.raises(RequestError) as caught:
        call(deck, "rename_thing", {"id": box, "name": "Mine"}, account=VERA)
    assert caught.value.code == "forbidden"
    assert name_of(deck, box) == "Text box 1"


def test_a_clash_is_refused_with_the_name_of_the_one_who_has_it(deck):
    one = add_text(deck)
    two = add_text(deck, y=300)
    with pytest.raises(RequestError) as caught:
        call(deck, "rename_thing", {"id": two, "name": "TEXT BOX 1"})
    assert caught.value.code == "command_error"
    assert "There is already a text called “Text box 1”" in str(caught.value.message)
    assert name_of(deck, one) == "Text box 1"


@pytest.mark.parametrize("bad", ["", "   ", "x" * 61])
def test_a_name_must_have_some_text_and_not_too_much(deck, bad):
    box = add_text(deck)
    with pytest.raises(RequestError) as caught:
        call(deck, "rename_thing", {"id": box, "name": bad})
    assert caught.value.code == "bad_request"
    assert name_of(deck, box) == "Text box 1"


def test_renaming_something_that_is_not_there_is_an_error(deck):
    with pytest.raises(RequestError) as caught:
        call(deck, "rename_thing", {"id": "nothing", "name": "Name"})
    assert caught.value.code == "command_error"


def test_a_rename_by_somebody_else_does_not_stop_the_first_from_undoing_their_own_work(deck):
    box = add_text(deck)
    call(deck, "rename_thing", {"id": box, "name": "Intro"})
    deck.undo("ann")
    assert name_of(deck, box) == "Text box 1"


# -- documents from before names ----------------------------------------------------------------------------------
def test_name_unnamed_names_what_has_no_name_and_leaves_the_rest(deck):
    # a document made before names: a slide and two objects without any
    box = add_text(deck)
    other = add_text(deck, y=300)
    for thing in (box, other, "s1"):
        deck.execute(RenameThing(thing, ""), author="ann")
    deck.execute(RenameThing(other, "Keep"), author="ann")

    done = call(deck, "name_unnamed")
    assert done["named"] == 2
    assert name_of(deck, box) == "Text box 1"
    assert name_of(deck, "s1") == "Slide 1"
    assert name_of(deck, other) == "Keep"


def test_name_unnamed_with_nothing_to_name_does_not_touch_the_log(deck):
    add_text(deck)
    call(deck, "name_unnamed")  # the first slide of a new deck has no name yet
    before = deck.revision
    assert call(deck, "name_unnamed") == {"named": 0, "revision": before.to_data() if before else None}
    assert deck.revision == before


def test_name_unnamed_is_one_step_in_the_history(deck):
    for thing in (add_text(deck), add_shape(deck), "s1"):
        deck.execute(RenameThing(thing, ""), author="ann")
    before = deck.revision
    call(deck, "name_unnamed")
    assert deck.revision.seq == before.seq + 1


# -- computes -----------------------------------------------------------------------------------------------------
def test_a_picture_on_a_sheet_gets_a_default_name_that_the_sheets_names_do_not_take(book):
    first = on_book(book, "add_image", _image_params())["object"]
    assert name_of(book, first) == "Picture 1"


def test_a_sheet_is_renamed_and_the_formulas_that_read_it_follow(book):
    on_book(book, "add_sheet", {"name": "Data"})
    on_book(book, "set_cells", {"sheet": "s1", "cells": [{"row": 0, "col": 0, "input": "=Data!A1"}]})
    on_book(book, "rename_thing", {"id": "s1", "name": "Takings"})
    assert name_of(book, "s1") == "Takings"
    on_book(book, "rename_thing", {"id": next(i for i in book.model.sheets if i != "s1"), "name": "Figures"})
    cells = on_book(book, "cells", {"sheet": "s1", "row0": 0, "row1": 0, "col0": 0, "col1": 0})["cells"]
    assert "Figures!A1" in str(cells)
    assert [s["name"] for s in on_book(book, "sheets")] == ["Takings", "Figures"]


def test_a_sheet_cannot_take_the_name_of_a_named_range(book):
    on_book(book, "add_sheet", {"name": "Data"})
    area = {"sheet": "s1", "row0": 0, "col0": 0, "row1": 1, "col1": 1}
    on_book(book, "define_name", {"definition": {"name": "Revenue", "range": area}})
    with pytest.raises(RequestError) as caught:
        on_book(book, "rename_thing", {"id": "s1", "name": "revenue"})
    assert "There is already a range called “Revenue”" in str(caught.value.message)


def test_a_new_sheet_may_not_take_the_name_of_a_picture(book):
    picture = on_book(book, "add_image", _image_params())["object"]
    on_book(book, "rename_thing", {"id": picture, "name": "Logo"})
    with pytest.raises(RequestError) as caught:
        on_book(book, "add_sheet", {"name": "logo"})
    assert "There is already an image called “Logo”" in str(caught.value.message)


def _image_params() -> dict:
    return {
        "sheet": "s1",
        "row": 2,
        "col": 2,
        "w": 400,
        "h": 200,
        "data": tiny_gif(400, 200),
        "alt": "a sample picture",
        "source_name": "pic.gif",
    }
