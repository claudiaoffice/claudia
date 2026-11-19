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


def test_a_viewer_may_not_look_back(deck):
    """The document as it was is built from the history, which a viewer's key does not open (D1261)."""
    add_text(deck)
    with pytest.raises(RequestError) as refused:
        as_of(deck, "main:1", "slides", account=VERA)
    assert refused.value.code == "forbidden"


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


# -- thing_last_seen: where a deleted thing was last there (D551) --------------------------------------------------
def test_a_thing_that_is_there_is_present_at_the_head(deck):
    thing = add_text(deck)  # main:1
    seen = call(deck, "thing_last_seen", {"id": thing})
    assert seen == {"present": True, "revision": "main:1"}


def test_a_removed_object_was_last_seen_before_it_went(deck):
    keep = add_text(deck)  # main:1
    gone = add_shape(deck)  # main:2
    call(deck, "add_slide")  # main:3
    call(deck, "remove_object", {"id": gone})  # main:4
    assert call(deck, "thing_last_seen", {"id": gone}) == {"present": False, "revision": "main:3"}
    assert call(deck, "thing_last_seen", {"id": keep})["present"] is True


def test_a_removed_unnamed_object_is_found_too(deck):
    gone = add_text(deck)
    call(deck, "remove_object", {"id": gone})
    assert call(deck, "thing_last_seen", {"id": gone}) == {"present": False, "revision": "main:1"}


def test_an_id_that_never_existed_has_no_revision(deck):
    add_text(deck)
    assert call(deck, "thing_last_seen", {"id": "nothing-like-this"}) == {"present": False, "revision": None}


def test_the_last_look_is_one_of_the_reads_a_replay_may_ask_live(deck):
    from claudia_server.replay import VIEW_READS

    assert "thing_last_seen" not in VIEW_READS  # it looks at the whole history, so it is never "as of" a step


# -- changes_since: where the document has moved on from a step (D553) -------------------------------------------
def test_the_objects_changed_since_a_step_are_named(deck):
    first = add_text(deck)  # main:1
    second = add_shape(deck)  # main:2
    call(deck, "remove_object", {"id": first})  # main:3
    found = call(deck, "changes_since", {"revision": "main:1"})
    assert found["truncated"] is False
    named = {i for r in found["regions"] if r["kind"] == "objects" for i in r["ids"]}
    assert second in named and first in named


def test_nothing_changed_since_the_latest_step(deck):
    add_text(deck)
    assert call(deck, "changes_since", {"revision": "main:1"}) == {"regions": [], "truncated": False}


def test_a_step_that_is_not_there_is_a_command_error(deck):
    with pytest.raises(RequestError) as caught:
        call(deck, "changes_since", {"revision": "main:9"})
    assert caught.value.code == "command_error"


# -- as_planned: the views read the state a redaction would leave, for its preview (D721) ----------------------------
def test_a_preview_answers_the_cells_as_the_redaction_would_leave_them():
    book = Document(WorkbookModel(), store=MemoryStore())
    book.execute(AddSheet("s1", "Sheet1"), author="ann")
    typed(book, "s1", [(0, 0, "4711")])  # main:2
    plan = on_book(book, "redaction_plan", {"revisions": ["main:2"], "state": False})
    assert plan["plan"] and "state" not in plan and plan["regions"]
    window = {"sheet": "s1", "row0": 0, "row1": 3, "col0": 0, "col1": 3}
    seen = on_book(book, "as_planned", {"plan": plan["plan"], "method": "cells", "params": window})
    assert "4711" not in str(seen) and "4711" in str(on_book(book, "cells", window))
    assert not book.log.get(book.log.path(book.revision)[1].rev).redacted


def test_a_preview_that_is_gone_or_a_request_that_is_not_a_look_is_refused():
    book = Document(WorkbookModel(), store=MemoryStore())
    book.execute(AddSheet("s1", "Sheet1"), author="ann")
    with pytest.raises(RequestError) as gone:
        on_book(book, "as_planned", {"plan": "nonsense", "method": "cells", "params": {}})
    assert gone.value.code == "command_error"
    with pytest.raises(RequestError) as other:
        on_book(book, "as_planned", {"plan": "nonsense", "method": "delete_document", "params": {}})
    assert other.value.code == "forbidden"
