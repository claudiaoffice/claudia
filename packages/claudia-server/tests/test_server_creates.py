"""The methods a slide view needs: slides, their objects, the shapes to insert, and the edits (creates)."""

import json

import pytest

from claudia_core import Document, MemoryStore
from claudia_creates import ShapeLibrary, SlideModel
from claudia_server.auth import Account
from claudia_server.creates import creates_methods, creates_methods_with
from claudia_server.protocol import Context, Limits, RequestError

ANN = Account("ann", "owner")
BEN = Account("ben", "editor")
VERA = Account("vera", "viewer")


@pytest.fixture
def deck():
    return Document(SlideModel.empty(), store=MemoryStore())


def call(doc, name, params=None, account=ANN, methods=creates_methods):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0)
    return methods.dispatch(ctx, name, params)


def add_text(doc, **params):
    given = {"slide": "s1", "kind": "text", "x": 100, "y": 100, "w": 400, "h": 120, **params}
    return call(doc, "add_object", given)["object"]


def add_shape(doc, shape="rectangle", **params):
    given = {"slide": "s1", "kind": "shape", "shape": shape, "x": 200, "y": 200, "w": 300, "h": 200, **params}
    return call(doc, "add_object", given)["object"]


def objects(doc, slide="s1"):
    return call(doc, "slide", {"slide": slide})["objects"]


def test_a_new_presentation_has_one_empty_slide(deck):
    assert call(deck, "slides") == [{"id": "s1", "objects": 0}]
    assert call(deck, "slide", {"slide": "s1"}) == {"revision": None, "slide": "s1", "objects": []}


def test_a_text_box_is_added_with_the_body_text_style(deck):
    added = call(deck, "add_object", {"slide": "s1", "kind": "text", "x": 100, "y": 80, "w": 400, "h": 120})
    assert added["revision"] == "main:1"
    (box,) = objects(deck)
    assert box["id"] == added["object"]
    assert (box["kind"], box["x"], box["y"], box["w"], box["h"]) == ("text", 100, 80, 400, 120)
    assert box["style"] == "body-text" and box["text"] == "" and box["shape"] is None
    assert call(deck, "slides") == [{"id": "s1", "objects": 1}]


def test_text_can_be_given_when_the_box_is_added(deck):
    add_text(deck, text="Quarterly goals")
    assert objects(deck)[0]["text"] == "Quarterly goals"


def test_a_shape_brings_its_outline_into_the_document_once(deck):
    first = add_shape(deck)
    second = add_shape(deck, x=600)
    assert first != second
    shapes = call(deck, "shapes")
    assert [s["id"] for s in shapes["document"]] == ["rectangle"]
    assert shapes["document"][0]["path"].startswith("M")
    assert [o["style"] for o in objects(deck)] == ["plain-shape", "plain-shape"]


def test_adding_a_shape_is_one_step_in_the_history(deck):
    add_shape(deck)
    assert deck.history_for("ann").undo_label == "Add shape"
    deck.undo("ann")
    assert objects(deck) == [] and call(deck, "shapes")["document"] == []


def test_the_library_lists_the_shapes_to_insert_and_the_styles(deck):
    shapes = call(deck, "shapes")
    assert [s["id"] for s in shapes["library"]] == ["circle", "rectangle", "triangle"]
    assert shapes["library"][0]["aspect"] == 1
    assert [s["id"] for s in call(deck, "styles")] == ["body-text", "plain-shape"]
    assert call(deck, "styles")[0]["css"]["font-size"]


def test_a_user_defined_shape_is_offered_and_used(deck, tmp_path):
    star = {
        "format": 1,
        "id": "star",
        "name": "Star",
        "path": "M50 0 L61 38 L100 38 L69 62 L80 100 L50 77 L20 100 L31 62 L0 38 L39 38 Z",
    }
    (tmp_path / "star.json").write_text(json.dumps(star))
    methods = creates_methods_with(ShapeLibrary.load([tmp_path]))
    assert "star" in [s["id"] for s in call(deck, "shapes", methods=methods)["library"]]
    call(
        deck,
        "add_object",
        {"slide": "s1", "kind": "shape", "shape": "star", "x": 0, "y": 0, "w": 200, "h": 200},
        methods=methods,
    )
    assert [s["id"] for s in call(deck, "shapes", methods=methods)["document"]] == ["star"]
    other = Document(SlideModel.empty(), store=MemoryStore())
    with pytest.raises(RequestError) as caught:
        add_shape(other, "star")  # a server without the star in its library cannot use it
    assert caught.value.code == "bad_request"


def test_a_document_keeps_working_with_a_shape_its_server_has_lost(deck, tmp_path):
    star = {"format": 1, "id": "star", "name": "Star", "path": "M50 0 L100 100 L0 100 Z"}
    (tmp_path / "star.json").write_text(json.dumps(star))
    call(
        deck,
        "add_object",
        {"slide": "s1", "kind": "shape", "shape": "star", "x": 0, "y": 0, "w": 200, "h": 200},
        methods=creates_methods_with(ShapeLibrary.load([tmp_path])),
    )
    add_shape(deck, "star", x=500)  # the document carries the outline itself
    assert len(objects(deck)) == 2


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"kind": "picture"}, "bad_request"),
        ({"kind": "shape"}, "bad_request"),  # a shape needs a shape
        ({"kind": "text", "shape": "circle"}, "command_error"),  # a text box has no outline
        ({"kind": "shape", "shape": "hexagon"}, "bad_request"),
        ({"slide": "nowhere"}, "command_error"),
        ({"x": -5}, "command_error"),
        ({"x": 1500}, "command_error"),
        ({"w": 3}, "command_error"),
        ({"x": 1.5}, "bad_request"),
        ({"text": 7}, "bad_request"),
    ],
)
def test_a_bad_object_is_refused_and_changes_nothing(deck, params, code):
    given = {"slide": "s1", "kind": "text", "x": 100, "y": 100, "w": 400, "h": 120, **params}
    with pytest.raises(RequestError) as caught:
        call(deck, "add_object", given)
    assert caught.value.code == code
    assert objects(deck) == [] and call(deck, "shapes")["document"] == []


def test_a_circle_must_keep_its_proportions(deck):
    add_shape(deck, "circle", w=200, h=200)
    with pytest.raises(RequestError, match="proportions") as caught:
        add_shape(deck, "circle", w=300, h=200)
    assert caught.value.code == "command_error"


def test_an_object_moves_resizes_and_is_edited(deck):
    box = add_text(deck)
    assert call(deck, "move_object", {"id": box, "x": 300, "y": 50})["revision"] == "main:2"
    call(deck, "resize_object", {"id": box, "x": 300, "y": 50, "w": 500, "h": 200})
    call(deck, "set_text", {"id": box, "text": "Hello"})
    (found,) = objects(deck)
    assert (found["x"], found["y"], found["w"], found["h"], found["text"]) == (300, 50, 500, 200, "Hello")
    assert deck.history_for("ann").undo_label == "Edit text"


def test_an_object_is_removed_and_comes_back_on_undo(deck):
    first, second = add_text(deck), add_text(deck, x=700)
    call(deck, "remove_object", {"id": first})
    assert [o["id"] for o in objects(deck)] == [second]
    deck.undo("ann")
    assert [o["id"] for o in objects(deck)] == [first, second], "it is back where it was in the stacking order"


def test_moving_something_that_is_not_there_is_an_error_not_a_crash(deck):
    for name, params in (
        ("move_object", {"id": "ghost", "x": 1, "y": 1}),
        ("resize_object", {"id": "ghost", "x": 1, "y": 1, "w": 50, "h": 50}),
        ("set_text", {"id": "ghost", "text": "x"}),
        ("remove_object", {"id": "ghost"}),
    ):
        with pytest.raises(RequestError) as caught:
            call(deck, name, params)
        assert caught.value.code == "command_error"


def test_ids_of_removed_objects_are_not_handed_out_again(deck):
    seen = set()
    for _ in range(30):
        box = add_text(deck)
        assert box not in seen
        seen.add(box)
        call(deck, "remove_object", {"id": box})


def test_slides_are_added_at_the_end(deck):
    added = call(deck, "add_slide")
    assert added["slide"] != "s1" and added["revision"] == "main:1"
    assert [s["id"] for s in call(deck, "slides")] == ["s1", added["slide"]]
    add_text(deck, slide=added["slide"])
    assert call(deck, "slides")[1]["objects"] == 1


def test_viewers_may_look_but_not_change(deck):
    box = add_text(deck)
    assert call(deck, "slides", account=VERA) and call(deck, "slide", {"slide": "s1"}, account=VERA)
    assert call(deck, "shapes", account=VERA) and call(deck, "styles", account=VERA)
    for name, params in (
        ("add_object", {"slide": "s1", "kind": "text", "x": 0, "y": 0, "w": 100, "h": 50}),
        ("move_object", {"id": box, "x": 1, "y": 1}),
        ("set_text", {"id": box, "text": "x"}),
        ("remove_object", {"id": box}),
        ("add_slide", {}),
    ):
        with pytest.raises(RequestError) as caught:
            call(deck, name, params, account=VERA)
        assert caught.value.code == "forbidden"


def test_a_selection_can_be_held_and_then_only_the_holder_changes_the_object(deck):
    box = add_text(deck)
    selection = {"kind": "objects", "slide": "s1", "ids": [box]}
    call(deck, "lock", {"regions": [selection]})
    with pytest.raises(RequestError) as caught:
        call(deck, "move_object", {"id": box, "x": 5, "y": 5}, account=BEN)
    assert caught.value.code == "locked"
    call(deck, "move_object", {"id": box, "x": 5, "y": 5})
    call(deck, "unlock")
    call(deck, "move_object", {"id": box, "x": 9, "y": 9}, account=BEN)
    assert objects(deck)[0]["x"] == 9


def test_a_selection_must_look_like_one(deck):
    with pytest.raises(RequestError) as caught:
        call(deck, "presence", {"regions": [{"kind": "objects", "slide": "s1", "ids": "all"}]})
    assert caught.value.code == "bad_request"


def test_the_methods_are_described_for_client_developers(deck):
    described = creates_methods.describe()["methods"]
    for name in ("slides", "slide", "shapes", "styles", "add_object", "move_object", "resize_object", "set_text"):
        assert described[name]["doc"], name
    assert described["add_object"]["write"] and not described["slide"]["write"]
    assert {"ping", "apply", "undo", "lock"} <= set(described), "the core methods are all there"


def test_a_stale_base_is_refused_like_everywhere(deck):
    box = add_text(deck)
    call(deck, "move_object", {"id": box, "x": 2, "y": 2, "base": "main:1"})
    with pytest.raises(RequestError) as caught:
        call(deck, "move_object", {"id": box, "x": 3, "y": 3, "base": "other:9"})
    assert caught.value.code == "stale"


def test_a_presentation_comes_back_after_a_restart_with_its_shapes_and_order(tmp_path):
    from claudia_server.filestore import FileProvider

    deck = FileProvider(tmp_path, SlideModel).create("talk")
    text = add_text(deck, text="Agenda")
    circle = add_shape(deck, "circle", w=200, h=200)
    call(deck, "move_object", {"id": text, "x": 30, "y": 40})
    call(deck, "remove_object", {"id": circle})
    deck.undo("ann")
    before = {"objects": objects(deck), "shapes": call(deck, "shapes")["document"], "slides": call(deck, "slides")}

    back = FileProvider(tmp_path, SlideModel).open("talk")
    assert objects(back) == before["objects"] and [o["id"] for o in objects(back)] == [text, circle]
    assert call(back, "shapes")["document"] == before["shapes"] and call(back, "slides") == before["slides"]
    assert objects(back)[0]["x"] == 30 and objects(back)[0]["text"] == "Agenda"
