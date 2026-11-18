"""Deleting and hiding a style, over the protocol (E1.10, D226, D785): `style_deletion` says what a deletion would do,
`delete_style` does it in one step, `hide_style` is all a built-in style allows."""

import pytest

from claudia_core import Document, MemoryStore
from claudia_creates import SlideModel
from claudia_server.auth import Account
from claudia_server.creates import creates_methods
from claudia_server.protocol import Context, Limits, RequestError

ANN = Account("ann", "owner")
VERA = Account("vera", "viewer")


@pytest.fixture
def deck():
    d = Document(SlideModel.empty(), store=MemoryStore())
    call(d, "add_object", {"slide": "s1", "kind": "text", "x": 10, "y": 10, "w": 300, "h": 120})
    return d


def call(doc, name, params=None, account=ANN):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann"], lock_seconds=30.0)
    return creates_methods.dispatch(ctx, name, params)


def made_style(doc, name="Loud"):
    """A document style based on Body text that the first text box has, by deviating."""
    object_id = next(iter(doc.model.objects))
    made = call(
        doc, "deviate_object_style", {"parent": "body-text", "objects": [object_id], "set": {"font-size": "90px"}}
    )
    call(doc, "rename_style", {"style": made["style"], "name": name})
    return made["style"]


def test_the_preview_says_how_many_places_have_the_style_what_is_based_on_it_and_where_it_could_go(deck):
    style = made_style(deck)
    answer = call(deck, "style_deletion", {"style": style})
    assert (answer["name"], answer["protected"], answer["hidden"], answer["uses"]) == ("Loud", False, False, 1)
    targets = {t["id"]: t for t in answer["targets"]}
    assert targets["slide-title"]["holds"] is True
    assert targets["body-text"]["changes_look"] is True  # the text is 90px now, Body text is not
    assert targets["body-text"]["reason"] is None
    assert style not in targets and "plain-shape" not in targets  # another kind, and itself


def test_a_built_in_style_is_protected_and_offers_no_targets(deck):
    answer = call(deck, "style_deletion", {"style": "body-text"})
    assert (answer["protected"], answer["targets"]) == (True, [])
    with pytest.raises(RequestError) as refused:
        call(deck, "delete_style", {"style": "body-text", "how": "assign", "target": "slide-title"})
    assert refused.value.code == "command_error" and "can only be hidden" in str(refused.value)


def test_rebasing_keeps_the_look_names_the_stand_in_and_is_one_undo_step(deck):
    style = made_style(deck)
    object_id = next(iter(deck.model.objects))
    look = deck.model.styles.computed(style)
    answer = call(deck, "delete_style", {"style": style, "how": "rebase", "target": "body-text"})
    stand_in = answer["stand_in"]
    assert stand_in and style not in deck.model.styles
    assert deck.model.get_object(object_id).body.style == stand_in
    assert deck.model.styles.computed(stand_in) == look
    assert {s["id"]: s for s in call(deck, "styles")}[stand_in]["to_name"] is True
    deck.undo("ann")
    assert style in deck.model.styles and deck.model.get_object(object_id).body.style == style


def test_deleting_a_style_nothing_has_needs_no_target_and_makes_no_stand_in(deck):
    style = made_style(deck)
    object_id = next(iter(deck.model.objects))
    call(deck, "set_object_style", {"id": object_id, "style": "plain-box"})
    assert call(deck, "delete_style", {"style": style})["stand_in"] is None
    assert style not in deck.model.styles


def test_a_style_that_does_not_exist_or_a_bad_way_or_target_is_a_command_error(deck):
    style = made_style(deck)
    for params in (
        {"style": "nope", "how": "assign", "target": "body-text"},
        {"style": style, "how": "assign", "target": "nope"},
        {"style": style, "how": "assign", "target": "plain-shape"},
        {"style": style, "how": "assign", "target": style},
        {"style": style, "how": "assign"},
        {"style": style, "how": "rebase"},
        {"style": style, "how": "sideways", "target": "body-text"},
        {"style": style, "how": "keep", "target": "body-text"},
    ):
        with pytest.raises(RequestError) as refused:
            call(deck, "delete_style", params)
        assert refused.value.code == "command_error", params
    assert style in deck.model.styles


def test_a_viewer_may_look_at_what_a_deletion_would_do_but_not_do_it(deck):
    style = made_style(deck)
    assert call(deck, "style_deletion", {"style": style}, account=VERA)["uses"] == 1
    for name, params in (
        ("delete_style", {"style": style, "how": "assign", "target": "body-text"}),
        ("hide_style", {"style": style, "hidden": True}),
    ):
        with pytest.raises(RequestError) as refused:
            call(deck, name, params, account=VERA)
        assert refused.value.code == "forbidden"


def test_hiding_marks_the_style_in_what_a_client_gets_and_showing_brings_it_back(deck):
    first = call(deck, "hide_style", {"style": "body-text", "hidden": True})
    assert first["revision"]
    assert {s["id"]: s for s in call(deck, "styles")}["body-text"]["hidden"] is True
    assert call(deck, "hide_style", {"style": "body-text", "hidden": True})["revision"] == first["revision"]  # no step
    call(deck, "hide_style", {"style": "body-text", "hidden": False})
    assert "hidden" not in {s["id"]: s for s in call(deck, "styles")}["body-text"]


def test_hiding_a_style_that_is_not_there_is_a_command_error(deck):
    with pytest.raises(RequestError) as refused:
        call(deck, "hide_style", {"style": "nope", "hidden": True})
    assert refused.value.code == "command_error"


def test_the_preview_suggests_the_plain_style_of_the_kind(deck):
    style = made_style(deck)
    answer = call(deck, "style_deletion", {"style": style})
    assert answer["suggested"] == {"id": "body-text", "name": "Body text"}
    assert call(deck, "style_deletion", {"style": "body-text"})["suggested"] is None  # protected


def test_assigning_puts_what_had_the_style_under_the_other_one_and_makes_no_stand_in(deck):
    style = made_style(deck)
    object_id = next(iter(deck.model.objects))
    answer = call(deck, "delete_style", {"style": style, "how": "assign", "target": "body-text"})
    assert answer["stand_in"] is None and style not in deck.model.styles
    assert deck.model.get_object(object_id).body.style == "body-text"
    assert not any(s.to_name for s in deck.model.styles)
    deck.undo("ann")
    assert deck.model.get_object(object_id).body.style == style


def test_how_is_assign_when_left_out(deck):
    style = made_style(deck)
    call(deck, "delete_style", {"style": style, "target": "body-text"})
    assert next(iter(deck.model.objects.values())).body.style == "body-text"
