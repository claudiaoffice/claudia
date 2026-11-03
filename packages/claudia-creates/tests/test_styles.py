"""Styles are named by what they are for, and are CSS from a short allow-list (D62, D73)."""

import re

from claudia_creates import ALLOWED_CSS, BUILTIN_STYLES


def test_the_first_draft_has_one_style_for_text_and_one_for_shapes():
    assert set(BUILTIN_STYLES) == {"body-text", "plain-shape"}


def test_every_style_has_a_name_people_can_read_and_says_what_it_is_for():
    for style_id, style in BUILTIN_STYLES.items():
        assert style.id == style_id
        assert style.name and style.name[0].isupper()
        assert style.purpose.strip(), "a style's name must be backed by a sentence about its purpose (D62)"


def test_styles_use_only_allow_listed_css_properties_and_no_way_to_reach_outside():
    for style in BUILTIN_STYLES.values():
        assert set(style.css) <= ALLOWED_CSS
        for value in style.css.values():
            assert not re.search(r"url\(|@import|expression|javascript:|\\|;|\{|\}", value, re.IGNORECASE), value


def test_a_style_travels_as_plain_data():
    data = BUILTIN_STYLES["body-text"].to_data()
    assert set(data) == {"id", "name", "purpose", "css"}
    assert data["css"]["font-family"]
