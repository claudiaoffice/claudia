"""Styles are named by what they are for, and are CSS from a short allow-list (D62, D73, D75).

Since E10.16 a presentation's styles are core ``StyleDef``s in the document's own ``StyleBook``, exactly as in
composes: they inherit from a parent, they are validated against ``ALLOWED_CSS`` on the way in, and the core
style commands change them. The tests below check the three things that are this app's own: which styles a new
presentation starts with, that they say what they are for, and that a shape's look is in the SVG vocabulary.
"""

import re

import pytest

from claudia_core import ALLOWED_CSS, ChangeStyle, Document, MemoryStore
from claudia_creates import BUILTIN_STYLES, DEFAULT_STYLE, SlideModel, builtin_styles

STYLE_IDS = {"body-text", "plain-shape", "plain-image"}


@pytest.fixture
def doc():
    return Document(SlideModel.empty(), store=MemoryStore())


def test_a_new_presentation_has_one_style_each_for_text_shapes_and_images():
    assert {style.id for style in BUILTIN_STYLES} == STYLE_IDS
    assert set(builtin_styles().ids()) == STYLE_IDS


def test_every_style_has_a_name_people_can_read_and_says_what_it_is_for():
    for style in BUILTIN_STYLES:
        assert style.name and style.name[0].isupper()
        assert style.purpose.strip(), "a style's name must be backed by a sentence about its purpose (D62)"


def test_styles_use_only_allow_listed_css_properties_and_no_way_to_reach_outside():
    for style in BUILTIN_STYLES:
        assert set(style.css) <= ALLOWED_CSS
        for value in style.css.values():
            assert not re.search(r"url\(|@import|expression|javascript:|\\|;|\{|\}", value, re.IGNORECASE), value


def test_the_built_in_styles_pass_the_shared_validator():
    """They never did before E10.16: creates had its own ``Style`` dataclass with no validation, and one font
    name (``-apple-system``) was in fact refused by ``ALLOWED_CSS``. Going through a ``StyleBook`` catches it."""
    book = builtin_styles()  # raises CssError if any built-in style is not allowed
    assert len(book) == len(STYLE_IDS)


def test_every_style_is_based_on_body_text_so_one_change_reaches_them_all():
    book = builtin_styles()
    assert book.get(DEFAULT_STYLE).based_on is None
    for style in book:
        if style.id != DEFAULT_STYLE:
            assert style.based_on == DEFAULT_STYLE
    # a shape inherits the font it never sets itself
    assert book.computed("plain-shape")["font-family"] == book.computed(DEFAULT_STYLE)["font-family"]


def test_a_shape_says_its_background_and_border_in_the_svg_vocabulary():
    """D178: a shape is an outline in a 100 by 100 box, not a rectangle, so only ``fill``/``stroke`` can give a
    circle or a triangle a background and a border."""
    css = builtin_styles().computed("plain-shape")
    assert {"fill", "stroke", "stroke-width"} <= set(css)
    assert "background-color" not in css
    assert not any(name.startswith("border") for name in css)


def test_the_styles_live_in_the_document_and_the_core_commands_change_them(doc):
    """They used to live in the program, read-only (``BUILTIN_STYLES`` as a module-level dict). Now a change is a
    logged command like any other, so it can be undone and everybody sees it."""
    assert doc.model.styles.computed("plain-shape")["fill"] == "@accent/14"  # a role, not a colour (D200)
    doc.execute(ChangeStyle("plain-shape", {"fill": "#FFD9E0"}), author="ana")
    assert doc.model.styles.computed("plain-shape")["fill"] == "#FFD9E0"
    doc.undo("ana")
    assert doc.model.styles.computed("plain-shape")["fill"] == "@accent/14"


def test_a_builtin_style_holds_no_colour_of_its_own_so_the_palette_can_recolour_it():
    # Every colour in a new presentation is a role; what a client draws with is the resolved form (D200).
    for style in builtin_styles():
        for prop, value in style.css.items():
            if prop in ("color", "background-color", "fill", "stroke") or prop.startswith("border"):
                assert "@" in value, f"{style.id} sets {prop} to the literal {value!r}"


def test_the_roles_resolve_to_exactly_the_colours_the_styles_used_to_hold(doc):
    views = {v["id"]: v for v in doc.model.styles.views(doc.model.palette.colours())}
    assert views["body-text"]["resolved"]["color"] == "#1F1A33"
    assert views["plain-shape"]["resolved"]["stroke"] == "#5B4BC4"
    assert views["plain-shape"]["resolved"]["fill"] == "rgba(91, 75, 196, 0.14)"


def test_a_style_travels_as_plain_data():
    data = builtin_styles().get(DEFAULT_STYLE).to_data()
    assert set(data) == {"id", "name", "purpose", "based_on", "css", "to_name"}
    assert data["css"]["font-family"]


def test_the_style_book_survives_a_snapshot(doc):
    doc.execute(ChangeStyle("plain-shape", {"stroke-width": "9px"}), author="ana")
    rebuilt = SlideModel.restore(doc.model.serialize())
    assert rebuilt.styles.computed("plain-shape")["stroke-width"] == "9px"
