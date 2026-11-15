"""``as_of``: the read requests a view makes, answered for the document as it was after one step (D551).

A replay shows the past with the views the three apps already have, so the views ask what they always ask — `slides`,
`slide`, `cells` — and the server answers it for that step. Only reading is possible: anything else is refused, and so
is every method that is not a view's way of reading (`delete_document`, `change_password`, ... are not marked as
writing, but they are not for a look either)."""

import pytest
from test_server_computes import call as on_book
from test_server_computes import typed
from test_server_creates import VERA, add_shape, add_text, call

from claudia_computes import AddSheet, WorkbookModel
from claudia_core import Document, MemoryStore
from claudia_creates import SlideModel
from claudia_server.protocol import RequestError


@pytest.fixture
def deck():
    return Document(SlideModel.empty(), store=MemoryStore())


def as_of(doc, revision, method, params=None, **kw):
    return call(doc, "as_of", {"revision": revision, "method": method, "params": params or {}}, **kw)


def test_the_slide_is_answered_as_it_was(deck):
    first = add_text(deck)  # main:1
    second = add_shape(deck)  # main:2

    then = as_of(deck, "main:1", "slide", {"slide": "s1"})
    now = call(deck, "slide", {"slide": "s1"})

    assert [o["id"] for o in then["objects"]] == [first]
    assert [o["id"] for o in now["objects"]] == [first, second]


def test_the_list_of_slides_follows_too(deck):
    call(deck, "add_slide")  # main:1
    call(deck, "add_slide")  # main:2
    assert [s["id"] for s in as_of(deck, "main:1", "slides")] == ["s1", as_of(deck, "main:1", "slides")[1]["id"]]
    assert len(as_of(deck, "main:1", "slides")) == 2
    assert len(call(deck, "slides")) == 3


def test_what_is_asked_is_checked_like_any_request(deck):
    with pytest.raises(RequestError) as caught:
        as_of(deck, "main:9", "slide", {"slide": "s1"})
    assert caught.value.code == "command_error"
    with pytest.raises(RequestError) as caught:
        as_of(deck, "main:0", "slide", {"slide": "s1"})  # there is no step 0
    assert caught.value.code == "bad_request"
    add_text(deck)
    with pytest.raises(RequestError) as caught:
        as_of(deck, "main:1", "slide", {})
    assert caught.value.code == "bad_request"


@pytest.mark.parametrize(
    "method", ["add_text", "add_object", "set_text", "undo", "delete_document", "change_password", "leave", "as_of"]
)
def test_nothing_but_looking_is_possible(deck, method):
    add_text(deck)
    with pytest.raises(RequestError) as caught:
        as_of(deck, "main:1", method, {})
    assert caught.value.code in {"forbidden", "bad_request", "unknown_method"}
    assert len(call(deck, "slide", {"slide": "s1"})["objects"]) == 1


def test_a_viewer_may_look_back(deck):
    add_text(deck)
    assert as_of(deck, "main:1", "slides", account=VERA)


def test_the_log_is_the_history_up_to_that_step(deck):
    add_text(deck)
    add_shape(deck)
    assert [e["revision"] for e in as_of(deck, "main:1", "log", {"limit": 50})] == ["main:1"]


def test_looking_back_changes_nothing_that_is_live(deck):
    add_text(deck)
    add_shape(deck)
    before = (deck.revision, deck.model.serialize())
    as_of(deck, "main:1", "slide", {"slide": "s1"})
    assert (deck.revision, deck.model.serialize()) == before


def test_a_table_answers_its_cells_as_they_were():
    book = Document(WorkbookModel(), store=MemoryStore())
    book.execute(AddSheet("s1", "Sheet1"), author="ann")
    typed(book, "s1", [(0, 0, "1")])  # main:2
    typed(book, "s1", [(0, 0, "2")])  # main:3

    window = {"sheet": "s1", "row0": 0, "row1": 3, "col0": 0, "col1": 3}
    then = on_book(book, "as_of", {"revision": "main:2", "method": "cells", "params": window})
    now = on_book(book, "cells", window)

    assert str(then) != str(now)
    assert "1" in str(then)
