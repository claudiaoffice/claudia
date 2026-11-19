"""``peek_revision`` over the wire: the document after one step of its history, and where the step touched it (D551).

What the web client replays when the wheel turns over the history panel: it is a look, so a viewer may ask too."""

import pytest
from test_server_creates import VERA, add_shape, add_text, call

from claudia_core import Document, MemoryStore
from claudia_creates import SlideModel
from claudia_server.protocol import RequestError


@pytest.fixture
def deck():
    return Document(SlideModel.empty(), store=MemoryStore())


def test_a_step_shows_the_state_after_it_and_who_did_it(deck):
    first = add_text(deck)  # main:1
    second = add_shape(deck)  # main:2

    look = call(deck, "peek_revision", {"revision": "main:1"})

    assert look["revision"] == "main:1"
    assert look["app"] == "creates"
    assert [o["id"] for o in look["state"]["objects"]] == [first]
    assert second not in str(look["state"]["objects"])
    assert look["entry"]["author"] == "ann"
    assert look["entry"]["label"] and look["entry"]["summary"]


def test_the_focus_names_the_slide_and_the_object_the_step_touched(deck):
    add_text(deck)
    shape = add_shape(deck)

    look = call(deck, "peek_revision", {"revision": "main:2"})

    assert look["focus"] == [{"kind": "objects", "container": "s1", "ids": [shape]}]


def test_the_state_may_be_left_out_when_only_the_place_is_wanted(deck):
    add_text(deck)
    look = call(deck, "peek_revision", {"revision": "main:1", "state": False})
    assert "state" not in look
    assert look["focus"]


def test_a_step_that_is_not_there_is_a_command_error(deck):
    add_text(deck)
    with pytest.raises(RequestError) as caught:
        call(deck, "peek_revision", {"revision": "main:9"})
    assert caught.value.code == "command_error"
    assert "main:9" in str(caught.value.message)


def test_a_viewer_may_not_look(deck):
    """The steps of the history are behind the history key, which a viewer does not hold (D1261)."""
    add_text(deck)
    with pytest.raises(RequestError) as refused:
        call(deck, "peek_revision", {"revision": "main:1"}, account=VERA)
    assert refused.value.code == "forbidden"


def test_looking_changes_nothing(deck):
    add_text(deck)
    add_text(deck, y=300)
    before = (deck.revision, deck.model.serialize())
    call(deck, "peek_revision", {"revision": "main:1"})
    assert (deck.revision, deck.model.serialize()) == before


def test_the_log_and_the_look_say_the_same_about_a_step(deck):
    add_text(deck)
    entry = call(deck, "log")[0]
    assert call(deck, "peek_revision", {"revision": "main:1"})["entry"] == entry


# -- a table: the focus is cells ----------------------------------------------------------------------------------
def test_a_step_in_a_table_names_the_cells_it_touched():
    from test_server_computes import call as on_book
    from test_server_computes import typed

    from claudia_computes import AddSheet, WorkbookModel

    book = Document(WorkbookModel(), store=MemoryStore())
    book.execute(AddSheet("s1", "Sheet1"), author="ann")
    typed(book, "s1", [(2, 3, "42")])

    look = on_book(book, "peek_revision", {"revision": "main:2"})

    (region,) = look["focus"]
    assert region["kind"] == "cells"
    assert "s1" in str(region) and look["entry"]["label"]
