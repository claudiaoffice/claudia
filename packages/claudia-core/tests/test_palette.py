"""The document's palette (E1.10, D200–D202): colours named by what they mean, and the contrast that follows."""

from __future__ import annotations

from typing import ClassVar, Self

import pytest

from claudia_core import (
    BUILTIN_ROLES,
    MAX_ROLES,
    PAIRINGS,
    TEXT_FLOOR,
    UI_FLOOR,
    ColourRole,
    CommandRegistry,
    CssError,
    Document,
    DocumentModel,
    MemoryStore,
    Palette,
    PaletteChanged,
    ReplacePalette,
    SetRole,
    StyleBook,
    StyleDef,
    UndoConflict,
    builtin_palette,
    contrast,
    luminance,
    new_registry,
    resolve_css,
    rgb_of,
    roles_used,
    validate_css,
)

OTHER = (
    ColourRole("text", "Text", "the words you read", "#101010"),
    ColourRole("page", "Page", "the page itself", "#FFFFFF"),
    ColourRole("accent", "Accent", "the one thing to notice", "#008080"),
)


# ----------------------------------------------------------------------------- the roles
def test_a_new_document_starts_with_the_nine_roles_the_builtin_styles_need():
    palette = builtin_palette()
    assert palette.ids() == [
        "text",
        "muted",
        "page",
        "surface",
        "structure",
        "accent",
        "accent-text",
        "attention",
        "highlight",
    ]
    assert len(palette) == len(BUILTIN_ROLES)
    assert palette.get("accent").colour == "#5B4BC4"
    assert palette.colours()["accent"] == "#5B4BC4"


def test_a_role_carries_what_it_means_not_only_what_it_looks_like():
    role = builtin_palette().get("accent")
    assert (role.name, role.purpose) == ("Accent", "the one thing to notice")


@pytest.mark.parametrize("ident", ["", "Has Space", "UPPER", "-lead", "x" * 70])
def test_role_ids_are_lower_case_words_with_hyphens(ident):
    with pytest.raises(ValueError, match="role id"):
        Palette().add(ColourRole(ident, "Fine", "", "#000000"))


@pytest.mark.parametrize("name", ["", "   ", "x" * 61, "two\nlines"])
def test_role_names_are_one_short_line(name):
    with pytest.raises(ValueError, match="role name"):
        Palette().add(ColourRole("x", name, "", "#000000"))


def test_a_duplicate_id_or_name_is_refused():
    palette = builtin_palette()
    with pytest.raises(ValueError, match="exists already"):
        palette.add(ColourRole("accent", "Another", "", "#000000"))
    with pytest.raises(ValueError, match="already a colour role named"):
        palette.add(ColourRole("second", "  ACCENT ", "", "#000000"))


@pytest.mark.parametrize("colour", ["red", "rgb(1, 2, 3)", "@accent", "", "#12345", "nonsense"])
def test_a_role_holds_one_definite_hexadecimal_colour(colour):
    with pytest.raises(ValueError, match="hexadecimal"):
        Palette().add(ColourRole("x", "X", "", colour))


def test_a_colour_is_kept_in_one_form_however_it_was_written():
    palette = Palette([ColourRole("x", "X", "", "#abc")])
    assert palette.get("x").colour == "#AABBCC"
    palette.set_colour("x", "  #5b4bc4  ")
    assert palette.get("x").colour == "#5B4BC4"


def test_a_palette_is_bounded():
    palette = Palette(ColourRole(f"r{n}", f"R{n}", "", "#000000") for n in range(MAX_ROLES))
    with pytest.raises(ValueError, match="at most"):
        palette.add(ColourRole("one-more", "One more", "", "#000000"))


def test_the_palette_round_trips_as_plain_data_and_keeps_its_order():
    palette = builtin_palette()
    again = Palette.from_data(palette.to_data())
    assert again.to_data() == palette.to_data()
    assert again.ids() == palette.ids()


def test_an_unknown_role_says_so():
    with pytest.raises(KeyError, match="no colour role"):
        builtin_palette().get("nope")
    with pytest.raises(KeyError, match="no colour role"):
        builtin_palette().remove("nope")


def test_replacing_every_role_at_once_changes_nothing_when_one_of_them_is_refused():
    palette = builtin_palette()
    before = palette.to_data()
    with pytest.raises(ValueError, match="hexadecimal"):
        palette.replace_all([*OTHER, ColourRole("bad", "Bad", "", "wrong")])
    assert palette.to_data() == before
    palette.replace_all(OTHER)
    assert palette.ids() == ["text", "page", "accent"]


# ----------------------------------------------------------------------------- contrast
def test_luminance_and_contrast_are_the_wcag_figures():
    assert luminance("#000000") == pytest.approx(0.0)
    assert luminance("#FFFFFF") == pytest.approx(1.0)
    assert contrast("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast("#5B4BC4", "#5B4BC4") == pytest.approx(1.0)
    assert contrast("#FFFFFF", "#5B4BC4") == pytest.approx(contrast("#5B4BC4", "#FFFFFF"))


def test_the_builtin_palette_passes_every_check_it_makes():
    readings = builtin_palette().readings()
    assert readings, "a palette with no reading cannot warn anybody about anything"
    assert [r for r in readings if not r.ok] == []


def test_a_reading_says_which_pairing_it_is_and_what_the_floor_was():
    (reading,) = [r for r in builtin_palette().readings() if (r.foreground, r.background) == ("accent-text", "accent")]
    assert reading.ratio == pytest.approx(6.46, abs=0.01)
    assert (reading.floor, reading.ok, reading.words) == (TEXT_FLOOR, True, True)
    assert reading.to_data() == {
        "foreground": "accent-text",
        "background": "accent",
        "ratio": 6.46,
        "floor": TEXT_FLOOR,
        "ok": True,
        "words": True,
    }


def test_a_reading_never_carries_a_verdict_in_words():
    # The client says what it means, in its own language, and never shows the ratio to a reader (D202).
    data = builtin_palette().readings()[0].to_data()
    assert not any(isinstance(value, str) and " " in value for value in data.values())


def test_a_colour_a_person_chooses_is_allowed_and_only_reported():
    palette = builtin_palette()
    palette.set_colour("accent", "#F5D76E")  # the mock's yellow: white on it is 1.42:1
    (reading,) = [r for r in palette.readings() if (r.foreground, r.background) == ("accent-text", "accent")]
    assert reading.ratio == pytest.approx(1.42, abs=0.01)
    assert not reading.ok
    assert palette.get("accent").colour == "#F5D76E", "the palette states the cost, it does not refuse the colour"


def test_a_role_with_no_pairing_is_simply_not_checked():
    palette = Palette([ColourRole("ornament", "Ornament", "", "#F2A057")])
    assert palette.readings() == []
    assert "highlight" not in {fore for fore, _, _ in PAIRINGS}
    assert UI_FLOOR < TEXT_FLOOR


# ----------------------------------------------------------------------------- roles in CSS
def test_a_colour_may_be_a_role_wherever_a_colour_belongs():
    clean = validate_css(
        {
            "color": "@text",
            "background-color": "@attention/7",
            "fill": "@surface",
            "stroke": "@accent",
            "border-left": "3px SOLID @highlight",
        }
    )
    assert clean == {
        "color": "@text",
        "background-color": "@attention/7",
        "fill": "@surface",
        "stroke": "@accent",
        "border-left": "3px solid @highlight",
    }


@pytest.mark.parametrize(
    ("prop", "value"),
    [
        ("font-family", "@text"),
        ("font-size", "@text"),
        ("font-weight", "@text"),
        ("line-height", "@text"),
        ("text-align", "@text"),
        ("margin-top", "@text"),
        ("stroke-width", "@text"),
        ("text-decoration", "@text"),
    ],
)
def test_a_role_is_refused_everywhere_a_colour_does_not_belong(prop, value):
    with pytest.raises(CssError):
        validate_css({prop: value})


@pytest.mark.parametrize("value", ["@", "@-lead", "@UPPER", "@accent/0", "@accent/101", "@accent/5.5", "@a@b"])
def test_only_a_well_formed_role_token_is_a_colour(value):
    with pytest.raises(CssError):
        validate_css({"color": value})


def test_the_ban_on_reaching_outside_the_page_is_untouched():
    for value in ("url(http://example.com)", "var(--x)", "calc(1px + 1px)", "red !important", "red; color: blue"):
        with pytest.raises(CssError):
            validate_css({"color": value})


def test_which_roles_a_style_names():
    assert roles_used({"color": "@text", "border-left": "3px solid @accent/55", "font-size": "9pt"}) == {
        "text",
        "accent",
    }
    assert roles_used({"color": "#5B4BC4"}) == set()


def test_resolving_turns_a_role_into_a_literal_colour_and_an_opacity_into_rgba():
    colours = builtin_palette().colours()
    assert resolve_css({"color": "@text"}, colours) == {"color": "#1F1A33"}
    assert resolve_css({"background-color": "@attention/7"}, colours) == {
        "background-color": "rgba(214, 71, 122, 0.07)"
    }
    assert resolve_css({"border-left": "3px solid @accent/55"}, colours) == {
        "border-left": "3px solid rgba(91, 75, 196, 0.55)"
    }
    assert resolve_css({"font-size": "9pt", "color": "#ABCDEF"}, colours) == {"font-size": "9pt", "color": "#ABCDEF"}


def test_a_declaration_whose_role_is_gone_is_left_out_rather_than_passed_on():
    # Nothing a browser cannot read ever reaches it; the parent style's value shows through instead.
    assert resolve_css({"color": "@nope", "font-size": "9pt"}, {"text": "#000000"}) == {"font-size": "9pt"}


@pytest.mark.parametrize(
    ("colour", "rgb"),
    [("#000", (0, 0, 0)), ("#FFF", (255, 255, 255)), ("#5B4BC4", (91, 75, 196)), ("#5B4BC480", (91, 75, 196))],
)
def test_a_hexadecimal_colour_reads_in_every_form_it_is_written(colour, rgb):
    assert rgb_of(colour) == rgb


# ----------------------------------------------------------------------------- the commands
class Painted(DocumentModel):
    """A model that is a palette and a style book, which is all the palette commands ask of an app."""

    app: ClassVar[str] = "test-painted"
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(self):
        self.palette = builtin_palette()
        self.styles = StyleBook([StyleDef("body", "Body text", "running text", None, {"color": "@text"})])

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self) -> dict:
        return {"palette": self.palette.to_data(), "styles": self.styles.to_data()}

    @classmethod
    def restore(cls, state: dict) -> Self:
        model = cls()
        model.palette = Palette.from_data(state["palette"])
        model.styles = StyleBook.from_data(state["styles"])
        return model


@pytest.fixture
def painted():
    return Document(Painted(), store=MemoryStore())


def seen(doc):
    events: list[PaletteChanged] = []
    doc.subscribe(lambda e: events.append(e) if isinstance(e, PaletteChanged) else None)
    return events


def test_setting_a_role_tells_the_clients_the_whole_palette_and_can_be_undone(painted):
    events = seen(painted)
    painted.execute(SetRole("accent", "#F5D76E"), author="ann")
    assert painted.model.palette.get("accent").colour == "#F5D76E"
    (event,) = events
    data = event.to_data()
    assert data["type"] == "palette"
    assert [r["id"] for r in data["roles"]] == painted.model.palette.ids()
    assert any(not r["ok"] for r in data["readings"]), "the clients learn what the change costs"
    painted.undo("ann")
    assert painted.model.palette.get("accent").colour == "#5B4BC4"
    painted.redo("ann")
    assert painted.model.palette.get("accent").colour == "#F5D76E"


def test_setting_a_role_that_is_not_there_or_a_colour_that_is_not_one_changes_nothing(painted):
    before = painted.model.serialize()
    with pytest.raises(ValueError, match="no colour role"):
        painted.execute(SetRole("nope", "#000000"), author="ann")
    with pytest.raises(ValueError, match="hexadecimal"):
        painted.execute(SetRole("accent", "mauve"), author="ann")
    assert painted.model.serialize() == before and painted.revision is None


def test_the_history_says_what_happened():
    assert SetRole("accent", "#F5D76E").summary == "set the colour accent to #F5D76E"
    assert SetRole("accent", "#F5D76E").label == "Change colour"
    assert ReplacePalette(OTHER).summary == "replaced the palette (3 colours)"


def test_a_whole_palette_can_be_put_in_place_of_another_and_undone(painted):
    painted.execute(ReplacePalette(OTHER), author="ann")
    assert painted.model.palette.ids() == ["text", "page", "accent"]
    painted.undo("ann")
    assert painted.model.palette.ids() == builtin_palette().ids()


def test_a_palette_that_a_style_already_points_past_is_refused(painted):
    painted.execute(SetRole("accent", "#123456"), author="ann")  # a style uses @text, not @accent
    without_text = (ColourRole("page", "Page", "", "#FFFFFF"),)
    with pytest.raises(ValueError, match="colour role"):
        painted.execute(ReplacePalette(without_text), author="ann")
    assert painted.model.palette.ids() == builtin_palette().ids()


def test_undoing_a_role_a_colleague_has_since_changed_is_refused_rather_than_silently_overwriting(painted):
    painted.execute(SetRole("accent", "#111111"), author="ann")
    painted.execute(SetRole("accent", "#222222"), author="ben")
    with pytest.raises(UndoConflict, match="ben changed this"):
        painted.undo("ann")
    assert painted.model.palette.get("accent").colour == "#222222"
    painted.undo("ben")  # ben may undo his own, and ann's colour is underneath it
    assert painted.model.palette.get("accent").colour == "#111111"


def test_a_role_change_before_a_whole_palette_went_in_cannot_be_undone_on_its_own(painted):
    painted.execute(SetRole("text", "#111111"), author="ann")
    painted.execute(ReplacePalette(OTHER), author="ben")
    with pytest.raises(UndoConflict, match="ben changed this"):
        painted.undo("ann")


def test_a_style_travels_with_both_the_roles_it_names_and_the_colours_they_resolve_to(painted):
    (view,) = painted.model.styles.views(painted.model.palette.colours())
    assert view["css"] == {"color": "@text"}, "what the style menu shows a person"
    assert view["computed"] == {"color": "@text"}
    assert view["resolved"] == {"color": "#1F1A33"}, "what a client draws with"


def test_a_book_without_a_palette_leaves_a_role_out_of_the_resolved_css():
    book = StyleBook([StyleDef("body", "Body text", "", None, {"color": "@text", "font-size": "9pt"})])
    (view,) = book.views()
    assert view["resolved"] == {"font-size": "9pt"}


def test_changing_the_palette_tells_the_clients_the_styles_too(painted):
    # A client is deliberately unable to resolve a role itself, so a palette change has to resend the styles.
    styles: list = []
    painted.subscribe(lambda e: styles.append(e) if type(e).__name__ == "StylesChanged" else None)
    painted.execute(SetRole("text", "#008080"), author="ann")
    assert styles, "the styles did not follow the palette"
    assert styles[-1].styles[0]["resolved"] == {"color": "#008080"}
    assert styles[-1].styles[0]["computed"] == {"color": "@text"}, "the role itself is unchanged"


def test_a_role_change_survives_a_snapshot(painted):
    painted.execute(SetRole("accent", "#F5D76E"), author="ann")
    again = Painted.restore(painted.model.serialize())
    assert again.palette.get("accent").colour == "#F5D76E"
    assert again.palette.readings()[0].ok
