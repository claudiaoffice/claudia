"""The size a new picture or container is shown at (D1229, D1332): no larger than the most, no smaller than the body
text's letters, its proportions kept, within the room it has; and the font size of a style read as a length."""

import pytest

from claudia_core import font_size_px, new_object_size


def ratio(size: tuple[int, int]) -> float:
    return size[0] / size[1]


def test_a_picture_smaller_than_the_most_keeps_its_own_size():
    assert new_object_size(420, 240, 100, 50, least=20) == (100, 50)


def test_a_larger_picture_goes_into_the_most_with_its_proportions():
    assert new_object_size(420, 240, 1200, 400, least=20) == (420, 140)
    assert new_object_size(420, 240, 1000, 1000, least=20) == (240, 240)


def test_a_short_formula_is_raised_to_the_body_texts_height_with_its_proportions():
    # XeLaTeX draws E = mc^2 43 by 12 (measured 2026-11-20); it used to become 43 by 20, letterboxed
    assert new_object_size(420, 240, 43, 12, least=20) == (72, 20)
    assert new_object_size(420, 240, 50, 10, least=40) == (200, 40)


def test_the_least_wins_over_the_most():
    # a long one-line formula: 2000 by 10 would be 420 by 2 in the most; the least makes it 20 high
    assert new_object_size(420, 240, 2000, 10, least=20) == (4000, 20)
    assert new_object_size(420, 240, 300, 12, least=20) == (500, 20)


def test_the_room_keeps_it_inside_the_column_or_the_slide():
    # creates: the body text is 40 high, which would make the formula 1000 wide; 600 are left on the slide
    assert new_object_size(420, 240, 300, 12, least=40, room=600) == (600, 24)
    assert new_object_size(420, 240, 300, 12, least=40, room=2000) == (1000, 40)


def test_no_side_is_ever_below_the_smallest_an_object_may_be():
    w, h = new_object_size(420, 240, 4, 40, least=20)
    assert (w, h) == (20, 200), "a thin picture: its narrow side is raised to 20, the other follows"
    assert new_object_size(420, 240, 8, 8, least=12, smallest=20) == (20, 20)


@pytest.mark.parametrize(
    ("picture", "least", "room"),
    [((43, 12), 20, None), ((1200, 400), 20, None), ((640, 480), 40, 300), ((3, 997), 16, None), ((997, 3), 40, 1600)],
)
def test_the_width_keeps_the_pictures_proportions_within_one_unit(picture, least, room):
    w, h = new_object_size(420, 240, *picture, least=least, room=room)
    assert isinstance(w, int) and isinstance(h, int)
    assert abs(w - h * picture[0] / picture[1]) <= 1, "the server refuses a picture whose proportions are off"


@pytest.mark.parametrize(
    ("value", "px"),
    [("12pt", 16.0), ("13px", 13.0), ("40px", 40.0), ("1.5em", 24.0), ("1rem", 16.0), ("125%", 20.0), (" 9pt ", 12.0)],
)
def test_a_font_size_is_read_in_pixels(value, px):
    assert font_size_px(value) == pytest.approx(px)


@pytest.mark.parametrize("value", ["", "large", "12", "calc(1em + 2px)", None])
def test_a_font_size_that_is_not_a_length_is_none(value):
    assert font_size_px(value) is None
