"""A theme is styles and colours that exist outside a document, and what giving it to a document comes to (E10.4,
E10.23, D1531): built-in styles are matched by what they are for (their id), the others by name; nothing the document
has of its own is taken away."""

from __future__ import annotations

from claudia_core import (
    ChangeStyle,
    ColourRole,
    CreateStyle,
    Palette,
    ReplacePalette,
    StyleBook,
    StyleDef,
    Theme,
    theme_commands,
)


def body(**css: str) -> StyleDef:
    return StyleDef("body-text", "Body text", "running text", None, css or {"font-size": "40px"}, origin="builtin")


def role(role_id: str, colour: str, name: str | None = None) -> ColourRole:
    return ColourRole(role_id, name or role_id.title(), "a role", colour)


def theme(styles: list[StyleDef], roles: list[ColourRole], name: str = "Talk") -> Theme:
    return Theme(name, StyleBook(styles), Palette(roles))


def commands(deck_styles, deck_roles, styles, roles):
    return theme_commands(StyleBook(deck_styles), Palette(deck_roles), theme(styles, roles))


def test_a_built_in_style_gets_the_look_of_the_style_with_the_same_id():
    deck = body(**{"font-size": "40px", "font-family": "Inter", "text-align": "left"})
    given = body(**{"font-size": "28px", "color": "@text"})
    assert commands([deck], [], [given], []) == (
        ChangeStyle("body-text", {"font-size": "28px", "color": "@text"}, ("font-family", "text-align")),
    )


def test_a_style_that_already_looks_like_the_theme_is_left_alone():
    assert commands([body()], [], [body()], []) == ()


def test_another_style_is_matched_by_its_name_whatever_its_id_or_the_letters():
    mine = StyleDef("quote", "Quote", "", "body-text", {"font-style": "italic"})
    theirs = StyleDef("citation", "QUOTE", "", "body-text", {"font-style": "oblique", "margin-left": "2em"})
    assert commands([body(), mine], [], [body(), theirs], []) == (
        ChangeStyle("quote", {"font-style": "oblique", "margin-left": "2em"}, ()),
    )


def test_a_style_only_the_theme_has_is_added_as_a_style_of_the_template_based_on_the_matching_style():
    theirs = StyleDef("big-number", "Big number", "one number", "body-text", {"font-size": "120px"})
    (create,) = commands([body()], [], [body(), theirs], [])
    assert isinstance(create, CreateStyle)
    assert (create.style.id, create.style.name, create.style.based_on, create.style.origin) == (
        "big-number",
        "Big number",
        "body-text",
        "template",
    )


def test_an_added_style_takes_another_id_when_the_document_has_one_with_that_id_under_another_name():
    mine = StyleDef("big-number", "Mine", "", "body-text", {"font-size": "10px"})
    theirs = StyleDef("big-number", "Big number", "one number", "body-text", {"font-size": "120px"})
    (create,) = commands([body(), mine], [], [body(), theirs], [])
    assert (create.style.id, create.style.name) == ("big-number-2", "Big number")


def test_an_added_style_is_based_on_the_style_its_parent_became_here():
    parent = StyleDef("quote", "Quote", "", "body-text", {"font-style": "italic"})
    mine = StyleDef("zitat", "quote", "", "body-text", {"font-style": "normal"})  # the same name, another id
    child = StyleDef("small-quote", "Small quote", "", "quote", {"font-size": "20px"})
    steps = commands([body(), mine], [], [body(), parent, child], [])
    create = next(step for step in steps if isinstance(step, CreateStyle))
    assert create.style.based_on == "zitat"


def test_what_only_the_document_has_is_not_touched():
    steps = commands(
        [body(), StyleDef("mine", "Mine", "", "body-text", {"color": "red"})], [role("a", "#111111")], [body()], []
    )
    assert steps == ()


def test_the_colours_of_the_theme_replace_the_roles_with_the_same_id_and_the_others_stay():
    steps = commands(
        [],
        [role("accent", "#111111"), role("brand", "#222222")],
        [],
        [role("accent", "#aa0000"), role("sky", "#0000aa")],
    )
    (replace,) = steps
    assert isinstance(replace, ReplacePalette)
    assert [(r.id, r.colour) for r in replace.roles] == [
        ("accent", "#AA0000"),
        ("brand", "#222222"),
        ("sky", "#0000AA"),
    ]


def test_the_same_colours_are_no_change():
    roles = [role("accent", "#111111")]
    assert commands([], roles, [], list(roles)) == ()
