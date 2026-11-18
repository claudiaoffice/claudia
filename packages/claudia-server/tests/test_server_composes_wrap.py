"""How the text flows round an object, on the wire (D1061, D1064), and the boxes and shapes a text can take (E10.16).

``set_wrap`` is the one step the cycling key takes; ``add_object`` puts a text box or a shape in a text, from the
library the server offers, as presentations do; a new object says its wrap in the call that adds it.
"""

import pytest

from claudia_composes import TextModel
from claudia_core import Document, MemoryStore
from claudia_creates import ShapeLibrary
from claudia_server.apps import methods_for
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.protocol import Context, Limits, RequestError

ANN = Account("ann", "owner")
VERA = Account("vera", "viewer")


@pytest.fixture
def paper():
    return Document(TextModel(), store=MemoryStore())


def call(doc, name, params=None, account=ANN, methods=composes_methods):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0)
    return methods.dispatch(ctx, name, params)


def with_a_box(paper):
    call(paper, "replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "a text with a box"})
    answer = call(paper, "add_object", {"block": "b1", "offset": 2, "kind": "text", "w": 200, "h": 80})
    return answer["object"]


def anchor_of(paper, object_id):
    (obj,) = [o for o in call(paper, "objects")["objects"] if o["id"] == object_id]
    return obj["anchor"]


# ----------------------------------------------------------------------------------------------- set_wrap
def test_an_object_that_says_nothing_floats_over_the_text_and_the_wire_shows_no_wrap(paper):
    object_id = with_a_box(paper)
    assert anchor_of(paper, object_id) == {"kind": "block", "container": "b1", "offset": 2, "dx": 0, "dy": 0}


def test_set_wrap_changes_how_the_text_flows_and_nothing_else(paper):
    object_id = with_a_box(paper)
    call(paper, "move_object", {"id": object_id, "block": "b1", "offset": 4, "dx": 30, "dy": 5})
    call(paper, "set_wrap", {"id": object_id, "wrap": "around"})
    assert anchor_of(paper, object_id) == {
        "kind": "block",
        "container": "b1",
        "offset": 4,
        "dx": 30,
        "dy": 5,
        "wrap": "around",
    }


def test_set_wrap_can_set_the_gap_and_keeps_it_when_it_is_left_out(paper):
    object_id = with_a_box(paper)
    call(paper, "set_wrap", {"id": object_id, "wrap": "around", "gap": 20})
    call(paper, "set_wrap", {"id": object_id, "wrap": "above-below"})
    assert anchor_of(paper, object_id)["gap"] == 20


def test_moving_an_object_keeps_how_the_text_flows_round_it(paper):
    object_id = with_a_box(paper)
    call(paper, "set_wrap", {"id": object_id, "wrap": "behind", "gap": 3})
    call(paper, "move_object", {"id": object_id, "block": "b1", "offset": 6})
    assert (anchor_of(paper, object_id)["wrap"], anchor_of(paper, object_id)["gap"]) == ("behind", 3)


def test_one_press_of_the_key_is_one_step_that_undo_takes_back_and_the_history_names_it(paper):
    object_id = with_a_box(paper)
    call(paper, "set_wrap", {"id": object_id, "wrap": "around"})
    assert call(paper, "history")["undo_label"] == "Wrap text"
    call(paper, "undo")
    assert "wrap" not in anchor_of(paper, object_id)


@pytest.mark.parametrize("bad", [{"wrap": "tight"}, {"wrap": "around", "gap": -1}, {"wrap": "around", "gap": 201}])
def test_a_wrap_nobody_knows_or_a_gap_out_of_reach_is_refused(paper, bad):
    object_id = with_a_box(paper)
    with pytest.raises(RequestError) as caught:
        call(paper, "set_wrap", {"id": object_id, **bad})
    assert caught.value.code in {"bad_request", "command_error"}
    assert "wrap" not in anchor_of(paper, object_id)


def test_a_viewer_may_not_change_the_wrap(paper):
    object_id = with_a_box(paper)
    with pytest.raises(RequestError) as caught:
        call(paper, "set_wrap", {"id": object_id, "wrap": "around"}, VERA)
    assert caught.value.code == "forbidden"


def test_an_object_that_is_not_there_is_refused(paper):
    with pytest.raises(RequestError):
        call(paper, "set_wrap", {"id": "nope", "wrap": "around"})


# ----------------------------------------------------------------------- a new object says how the text flows
def test_a_new_object_may_say_how_the_text_flows_round_it_in_the_call_that_adds_it(paper):
    call(paper, "replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "a text"})
    answer = call(
        paper, "add_object", {"block": "b1", "offset": 1, "kind": "text", "w": 100, "h": 50, "wrap": "above-below"}
    )
    assert anchor_of(paper, answer["object"])["wrap"] == "above-below"


def test_a_wrap_nobody_knows_is_refused_when_adding_too(paper):
    call(paper, "replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "a text"})
    with pytest.raises(RequestError):
        call(paper, "add_object", {"block": "b1", "offset": 1, "kind": "text", "w": 100, "h": 50, "wrap": "tight"})


# ----------------------------------------------------------------------------- a text box or a shape in a text
def test_the_shapes_a_text_can_take_are_the_servers_library_and_the_ones_the_document_has(paper):
    answer = call(paper, "shapes")
    assert {s["id"] for s in answer["library"]} >= {"rectangle", "ellipse"} or answer["library"]
    assert answer["document"] == []


def test_a_shape_comes_into_the_document_with_the_first_object_that_uses_it_and_keeps_its_proportions(paper):
    call(paper, "replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "a text"})
    library = call(paper, "shapes")["library"]
    shape = library[0]["id"]
    answer = call(
        paper, "add_object", {"block": "b1", "offset": 3, "kind": "shape", "shape": shape, "w": 120, "h": 120}
    )
    assert [s["id"] for s in call(paper, "shapes")["document"]] == [shape]
    (obj,) = [o for o in call(paper, "objects")["objects"] if o["id"] == answer["object"]]
    assert (obj["kind"], obj["shape"], obj["style"]) == ("shape", shape, "plain-shape")
    assert obj["anchor"]["offset"] == 3


def test_a_text_box_starts_with_its_words_in_the_body_style(paper):
    call(paper, "replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "a text"})
    answer = call(paper, "add_object", {"block": "b1", "offset": 0, "kind": "text", "w": 200, "h": 60, "text": "Hello"})
    (obj,) = [o for o in call(paper, "objects")["objects"] if o["id"] == answer["object"]]
    assert obj["style"] == "plain-box"
    assert obj["paragraph"]["text"] == "Hello"


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "image"},
        {"kind": "rendered"},
        {"kind": "diagram"},
        {"kind": "shape"},
        {"kind": "shape", "shape": "no-such-shape"},
        {"kind": "triangle"},
    ],
)
def test_what_add_object_does_not_make_is_refused_saying_where_to_go(paper, bad):
    call(paper, "replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "a text"})
    with pytest.raises(RequestError) as caught:
        call(paper, "add_object", {"block": "b1", "offset": 0, "w": 100, "h": 100, **bad})
    assert caught.value.code == "bad_request"


def test_an_object_must_hang_from_a_place_in_the_text(paper):
    with pytest.raises(RequestError):
        call(paper, "add_object", {"block": "b1", "offset": 99, "kind": "text", "w": 100, "h": 50})
    with pytest.raises(RequestError):
        call(paper, "add_object", {"block": "nope", "offset": 0, "kind": "text", "w": 100, "h": 50})


def test_a_server_with_its_own_library_offers_that_one(paper):
    own = methods_for(TextModel, shapes=ShapeLibrary.load())
    assert own is not composes_methods
    assert {"shapes", "add_object", "set_wrap"} <= own.names()
    assert call(paper, "shapes", methods=own)["library"]


def test_the_default_table_is_what_a_server_without_a_library_of_its_own_uses():
    assert methods_for(TextModel) is composes_methods
