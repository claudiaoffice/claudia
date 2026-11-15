"""How far a turned object reaches, in whole units and without a floating-point sine (D910, rotation-ui).

A slide keeps its objects on the slide (E10.1). An object that is turned reaches further than its frame, so the
rule has to look at its turned outline; and because every server must reach the same verdict about the same
document, the arithmetic is integer, from a table, never ``math.sin``.
"""

import math

import pytest

from claudia_core import SINE_MILLIONTHS, nudge_into, turned_extent


def test_the_sine_table_holds_one_entry_per_degree_from_0_to_90():
    assert len(SINE_MILLIONTHS) == 91
    assert SINE_MILLIONTHS[0] == 0
    assert SINE_MILLIONTHS[30] == 500_000
    assert SINE_MILLIONTHS[90] == 1_000_000


def test_the_sine_table_agrees_with_the_real_sine_to_a_millionth():
    for degrees, millionths in enumerate(SINE_MILLIONTHS):
        assert abs(millionths - math.sin(math.radians(degrees)) * 1_000_000) <= 0.5


@pytest.mark.parametrize(
    ("w", "h", "rotation", "extent"),
    [
        (300, 100, 0, (300, 100)),
        (300, 100, 90, (100, 300)),
        (300, 100, 180, (300, 100)),
        (300, 100, 270, (100, 300)),
        (100, 100, 45, (142, 142)),  # 141.42, rounded up: the outline never reaches further than this says
        (300, 100, 30, (310, 237)),  # 309.8 and 236.6, rounded up
    ],
)
def test_the_extent_of_a_turned_frame(w, h, rotation, extent):
    assert turned_extent(w, h, rotation) == extent


def test_a_turn_is_read_modulo_a_whole_turn():
    assert turned_extent(300, 100, 360) == (300, 100)
    assert turned_extent(300, 100, 450) == turned_extent(300, 100, 90)
    assert turned_extent(300, 100, -90) == turned_extent(300, 100, 270)


def test_a_turn_and_its_mirror_reach_the_same_distance():
    assert turned_extent(300, 100, 20) == turned_extent(300, 100, 340)
    assert turned_extent(300, 100, 20) == turned_extent(300, 100, 160)


def test_an_object_that_fits_after_its_turn_stays_where_it_is():
    assert nudge_into(600, 400, 300, 100, 90, 1600, 900) == (600, 400)


def test_a_turn_that_would_push_the_outline_off_the_slide_nudges_the_object_inward():
    # turned upright, 300 x 100 at the top left is 100 wide and 300 tall around the same centre: 100 above the slide
    assert nudge_into(0, 0, 300, 100, 90, 1600, 900) == (0, 100)
    assert nudge_into(1300, 800, 300, 100, 90, 1600, 900) == (1300, 700)


def test_an_object_is_moved_no_further_than_it_must_be():
    # at 45 degrees 300 x 100 reaches 283 x 283: only the right edge is in the way
    assert nudge_into(1500, 100, 300, 100, 45, 1600, 900) == (1308, 100)


def test_the_frame_of_a_turned_object_may_lie_outside_the_slide_while_its_outline_does_not():
    x, _ = nudge_into(-150, 400, 400, 100, 90, 1600, 900)
    assert x == -150  # an outline 100 wide around the centre x = 50 is on the slide


def test_an_object_that_cannot_fit_turned_is_refused():
    assert nudge_into(0, 0, 1600, 100, 90, 1600, 900) is None  # a bar 1600 long, upright, is taller than the slide
