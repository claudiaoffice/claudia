"""What a style looks like in the words of a file: lengths, colours, fonts, and what a file cannot say (D455)."""

from __future__ import annotations

import pytest
from claudia_composes_io._style_look import Border, colour_of, look_of, over_white, points


@pytest.mark.parametrize(
    ("value", "expected"),
    [("12pt", 12), ("12", 12), ("16px", 12), ("2em", 24), ("1rem", 12), ("2.54cm", 72), ("25.4mm", 72), ("1in", 72)],
)
def test_a_length_is_given_in_points(value: str, expected: float):
    assert points(value, font_size=12) == pytest.approx(expected)


def test_a_percentage_is_a_share_of_what_it_is_of_and_no_length_where_it_is_of_nothing():
    assert points("110%", font_size=12, percent_of=10) == pytest.approx(11)
    assert points("110%", font_size=12) is None
    assert points("wide", font_size=12) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#abc", ("#AABBCC", 1.0)),
        ("#11223380", ("#112233", 128 / 255)),
        ("rgb(10, 20, 30)", ("#0A141E", 1.0)),
        ("rgba(255 0 0 / 50%)", ("#FF0000", 0.5)),
        ("rgb(100%, 0%, 0%)", ("#FF0000", 1.0)),
        ("hsl(0, 100%, 50%)", ("#FF0000", 1.0)),
        ("red", ("#FF0000", 1.0)),
    ],
)
def test_a_colour_is_a_hex_colour_and_how_opaque_it_is(value: str, expected: tuple[str, float]):
    found = colour_of(value)
    assert found is not None and found[0] == expected[0] and found[1] == pytest.approx(expected[1])


@pytest.mark.parametrize(
    "value", ["#12", "#gggggg", "rgb(1, 2)", "rgb(a, b, c)", "rgb(300, 0, 0)", "salmon", "transparent"]
)
def test_what_is_no_colour_we_know_is_none(value: str):
    assert colour_of(value) is None
    assert over_white(value) is None


def test_a_translucent_colour_shows_as_the_colour_it_has_on_white_paper():
    assert over_white("rgba(0, 0, 0, 0.5)") == "#808080"


def look(**css: str):
    return look_of({key.replace("_", "-"): value for key, value in css.items()}, font_size=12, parent_size=12)


def test_a_font_family_is_the_first_one_a_file_can_name():
    assert look(font_family="system-ui, 'Segoe UI', sans-serif").family == "Segoe UI"
    assert look(font_family="Georgia, serif").family == "Georgia"
    assert look(font_family="serif").family == "Liberation Serif"
    assert look(font_family="system-ui").unsaid == ["font-family"]


def test_a_weight_is_a_number_or_a_keyword_and_nothing_else_is_said():
    assert (look(font_weight="bold").weight, look(font_weight="500").weight) == (700, 500)
    assert look(font_weight="bolder").unsaid == ["font-weight"]


def test_decoration_says_underline_and_strike_but_not_a_line_over_the_text():
    said = look(text_decoration="underline line-through")
    assert (said.underline, said.strike, said.unsaid) == (True, True, [])
    assert look(text_decoration="overline").unsaid == ["text-decoration"]


def test_the_spacing_of_letters_and_of_the_box_is_in_points():
    said = look(letter_spacing="0.1em", margin_left="1em", padding_top="6pt", background_color="rgba(0, 0, 0, 0.5)")
    assert said.spacing == pytest.approx(1.2) and said.margins == {"left": 12}
    assert said.padding == {"top": 6} and said.background == "#808080"
    assert look(letter_spacing="normal").spacing == 0
    assert look(margin_top="wide").unsaid == ["margin-top"]


@pytest.mark.parametrize(
    ("value", "line", "fixed"),
    [("normal", 1.0, False), ("1.5", 1.5, False), ("150%", 1.5, False), ("1.25em", 1.25, False), ("18pt", 18.0, True)],
)
def test_a_line_height_is_a_multiple_of_the_size_or_a_height(value: str, line: float, fixed: bool):
    said = look(line_height=value)
    assert (said.line, said.line_fixed) == (line, fixed)
    assert look(line_height="tall").unsaid == ["line-height"]


def test_a_border_has_a_width_a_line_and_a_colour_or_is_none():
    said = look(border_left="2pt dashed #112233", border_top="none")
    assert said.borders == {"left": Border(2, "dashed", "#112233"), "top": None}
    assert look(border_left="thick solid red").unsaid == ["border-left"]
    assert look(border_left="2pt solid salmon").unsaid == ["border-left"]


def test_text_that_a_style_aligns_and_hyphenates_is_said_and_what_has_no_place_in_a_file_is_not():
    said = look(
        text_align="end", hyphens="auto", color="#112233", font_style="italic", white_space="pre", opacity="0.5"
    )
    assert (said.align, said.hyphenate, said.colour, said.italic) == ("right", True, "#112233", True)
    assert said.unsaid == ["white-space", "opacity"]
