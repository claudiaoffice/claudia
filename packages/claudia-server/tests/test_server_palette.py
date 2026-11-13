"""The style and palette methods every app shares (E1.10, D200–D203), over the protocol.

The implementations live in ``claudia_server.styles`` and are registered into each app's table, so they are
exercised here through a presentation and a text — one table that has no rule of its own about who may write, and
one that does (composes: the assistant suggests, it does not write).
"""

import pytest

from claudia_composes import TextModel
from claudia_core import Document, MemoryStore
from claudia_creates import SlideModel
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.creates import creates_methods
from claudia_server.protocol import Context, Limits, RequestError

ANN = Account("ann", "owner")
VERA = Account("vera", "viewer")
ASSISTANT = Account("claudia", "editor", system=True)


@pytest.fixture
def deck():
    return Document(SlideModel.empty(), store=MemoryStore())


@pytest.fixture
def text():
    return Document(TextModel.empty(), store=MemoryStore())


def call(doc, name, params=None, account=ANN, methods=creates_methods):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann"], lock_seconds=30.0)
    return methods.dispatch(ctx, name, params)


def add_text(doc, **params):
    given = {"slide": "s1", "kind": "text", "x": 10, "y": 10, "w": 300, "h": 120, **params}
    return call(doc, "add_object", given)["object"]


def add_shape(doc, **params):
    given = {"slide": "s1", "kind": "shape", "shape": "rectangle", "x": 10, "y": 10, "w": 300, "h": 200, **params}
    return call(doc, "add_object", given)["object"]


# ----------------------------------------------------------------------------- reading
def test_the_palette_travels_with_its_roles_and_its_readings(deck):
    answer = call(deck, "palette")
    roles = {role["id"]: role for role in answer["roles"]}
    assert roles["accent"]["colour"] == "#5B4BC4"
    assert roles["accent"]["name"] == "Accent" and roles["accent"]["purpose"]
    assert all(reading["ok"] for reading in answer["readings"]), "a new document passes its own checks"
    (one,) = [r for r in answer["readings"] if (r["foreground"], r["background"]) == ("accent-text", "accent")]
    assert (one["floor"], one["words"]) == (4.5, True)


def test_a_style_arrives_with_the_role_it_names_and_the_colour_it_resolves_to(deck):
    styles = {style["id"]: style for style in call(deck, "styles")}
    assert styles["body-text"]["computed"]["color"] == "@text", "what the style menu shows"
    assert styles["body-text"]["resolved"]["color"] == "#1F1A33", "what a client draws with"
    assert styles["plain-shape"]["resolved"]["fill"] == "rgba(91, 75, 196, 0.14)"


def test_every_app_answers_the_same_questions(deck, text):
    # ``styles``, ``palette`` and the rest used to exist in composes alone (D203).
    for name in ("styles", "palette"):
        assert call(deck, name) is not None
        assert call(text, name, methods=composes_methods) is not None


# ----------------------------------------------------------------------------- changing a role
def test_changing_a_role_recolours_every_style_that_meant_it(deck):
    call(deck, "set_role", {"role": "accent", "colour": "#008080"})
    styles = {style["id"]: style for style in call(deck, "styles")}
    assert styles["plain-shape"]["resolved"]["stroke"] == "#008080"
    assert styles["plain-shape"]["resolved"]["fill"] == "rgba(0, 128, 128, 0.14)", "the tint followed its role"
    assert styles["plain-shape"]["computed"]["stroke"] == "@accent", "the style itself did not change"


def test_a_colour_that_breaks_contrast_is_accepted_and_reported(deck):
    call(deck, "set_role", {"role": "accent", "colour": "#F5D76E"})
    answer = call(deck, "palette")
    (reading,) = [r for r in answer["readings"] if (r["foreground"], r["background"]) == ("accent-text", "accent")]
    assert not reading["ok"], "the server says the words will be hard to read"
    assert reading["ratio"] == pytest.approx(1.42, abs=0.01)
    assert "verdict" not in reading, "the client says what it means, in its own words (D202)"


@pytest.mark.parametrize(
    ("params", "message"),
    [({"role": "nope", "colour": "#000000"}, "colour role"), ({"role": "accent", "colour": "mauve"}, "hexadecimal")],
)
def test_an_unknown_role_or_a_colour_that_is_not_one_is_a_command_error(deck, params, message):
    with pytest.raises(RequestError, match=message):
        call(deck, "set_role", params)
    assert call(deck, "palette")["roles"][5]["colour"] == "#5B4BC4"


def test_a_viewer_may_read_the_palette_and_not_change_it(deck):
    assert call(deck, "palette", account=VERA)["roles"]
    with pytest.raises(RequestError):
        call(deck, "set_role", {"role": "accent", "colour": "#008080"}, account=VERA)


def test_in_a_text_the_assistant_may_read_the_palette_and_not_change_it(text):
    # composes' own rule, kept by the ``guard`` hook when the methods moved into the shared module (D63, D203).
    assert call(text, "palette", account=ASSISTANT, methods=composes_methods)["roles"]
    with pytest.raises(RequestError, match="suggestions"):
        call(text, "set_role", {"role": "accent", "colour": "#008080"}, account=ASSISTANT, methods=composes_methods)


# ----------------------------------------------------------------------------- replacing the palette
def _roles(*ids):
    return [{"id": name, "name": name.title(), "purpose": "", "colour": "#101010"} for name in ids]


def test_a_whole_palette_can_be_put_in_place_of_another(deck):
    wanted = _roles(*[role["id"] for role in call(deck, "palette")["roles"]])
    call(deck, "replace_palette", {"roles": wanted})
    assert all(role["colour"] == "#101010" for role in call(deck, "palette")["roles"])


def test_a_palette_that_a_style_points_past_is_refused(deck):
    with pytest.raises(RequestError, match="colour role"):
        call(deck, "replace_palette", {"roles": _roles("page", "surface")})
    assert len(call(deck, "palette")["roles"]) == 9


@pytest.mark.parametrize("roles", [["not an object"], [{"id": "x", "name": "X"}]])
def test_a_malformed_role_is_a_bad_request(deck, roles):
    with pytest.raises(RequestError):
        call(deck, "replace_palette", {"roles": roles})


# ----------------------------------------------------------------------------- an object's own style
def test_an_object_can_be_put_under_another_style(deck):
    # A text box's box takes a paragraph style too: the box slot reads only the box part of it (D316).
    box = add_text(deck)
    call(deck, "set_object_style", {"id": box, "style": "body-text"})
    (obj,) = [o for o in call(deck, "slide", {"slide": "s1"})["objects"] if o["id"] == box]
    assert obj["style"] == "body-text"


def test_putting_an_object_under_another_style_can_be_undone(deck):
    box = add_text(deck)
    call(deck, "set_object_style", {"id": box, "style": "body-text"})
    call(deck, "undo")
    (obj,) = [o for o in call(deck, "slide", {"slide": "s1"})["objects"] if o["id"] == box]
    assert obj["style"] == "plain-box"


def test_a_shape_cannot_be_put_under_a_style_its_outline_cannot_read(deck):
    """A shape's own slot is its outline: a paragraph style holds no outline, so it does not fit (D304, D316)."""
    shape = add_shape(deck)
    with pytest.raises(RequestError, match="cannot be put into the outline"):
        call(deck, "set_object_style", {"id": shape, "style": "body-text"})


@pytest.mark.parametrize(("key", "value"), [("id", "nope"), ("style", "nope")])
def test_an_unknown_object_or_style_changes_nothing(deck, key, value):
    shape = add_shape(deck)
    params = {"id": shape, "style": "body-text", key: value}
    with pytest.raises(RequestError):
        call(deck, "set_object_style", params)
    (obj,) = [o for o in call(deck, "slide", {"slide": "s1"})["objects"] if o["id"] == shape]
    assert obj["style"] == "plain-shape"
