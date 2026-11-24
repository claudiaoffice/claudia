"""The slide, shared by creates and computes (E6.31, D1470): its anchor, its frame, and the slides of a document."""

import pytest

from claudia_core import ObjectBody, VisualObject
from claudia_core.slides import (
    SLIDE_WIDTH,
    Slide,
    SlideAnchor,
    Slides,
    check_on_slide,
    room_on_slide,
    turned_on_slide,
)


def box(w: int = 400, h: int = 200, rotation: int = 0) -> ObjectBody:
    return ObjectBody("o1", "text", w, h, "", rotation=rotation)


def test_a_slide_anchor_survives_the_trip_through_stored_data():
    anchor = SlideAnchor("s1", 40, 80)
    assert anchor.holder == "s1"
    assert anchor.to_data() == {"kind": "slide", "holder": "s1", "x": 40, "y": 80}
    assert SlideAnchor.from_data(anchor.to_data()) == anchor


@pytest.mark.parametrize(
    "data",
    [
        {"kind": "cell", "holder": "s1", "x": 0, "y": 0},
        {"kind": "slide", "holder": 7, "x": 0, "y": 0},
        {"kind": "slide", "holder": "s1", "x": 1.5, "y": 0},
        {"kind": "slide", "holder": "s1", "x": 0},
    ],
)
def test_what_is_not_a_slide_anchor_is_refused(data):
    with pytest.raises(ValueError):
        SlideAnchor.from_data(data)


def test_an_object_must_stay_on_the_slide():
    check_on_slide(SlideAnchor("s1", 1200, 700), box())  # right to the corner
    with pytest.raises(ValueError, match="stay on the slide"):
        check_on_slide(SlideAnchor("s1", 1201, 700), box())
    with pytest.raises(ValueError, match="whole numbers"):
        check_on_slide(SlideAnchor("s1", 0.5, 0), box())  # type: ignore[arg-type]  # a client may send a fraction


def test_a_turned_object_is_kept_on_the_slide_by_its_outline():
    # a 400 x 200 box turned a quarter is 200 wide and 400 high around the same centre
    check_on_slide(SlideAnchor("s1", 1300, 300), box(rotation=90))  # outline x 1400..1600, y 200..600: on the slide
    with pytest.raises(ValueError, match="stay on the slide"):
        check_on_slide(SlideAnchor("s1", 1300, 300), box())  # upright it reaches x 1700


def test_a_turn_is_nudged_to_the_nearest_place_on_the_slide():
    # in the bottom right corner, upright; turned a quarter its outline would reach y 1000, so it goes up by 100
    obj = VisualObject(box(), SlideAnchor("s1", 1200, 700))
    assert turned_on_slide(obj, 90) == SlideAnchor("s1", 1200, 600)


def test_a_turn_that_cannot_fit_is_refused():
    obj = VisualObject(box(1600, 900), SlideAnchor("s1", 0, 0))
    with pytest.raises(ValueError, match="too large to turn"):
        turned_on_slide(obj, 45)


def test_room_on_a_slide_is_what_is_left_to_the_right():
    assert room_on_slide(SlideAnchor("s1", 600, 0)) == 1000
    assert room_on_slide(None) == SLIDE_WIDTH


def test_slides_are_kept_by_id_with_their_name_and_description():
    slides = Slides()
    slides.add(Slide("s1"))
    slides.add(Slide("s2", "Sales chart", "East leads"))
    assert "s2" in slides and "s3" not in slides
    assert slides["s2"] == Slide("s2", "Sales chart", "East leads")
    assert slides.rename("s1", "Opening") == ""
    assert slides["s1"].name == "Opening"
    assert slides.describe("s1", "The title") == ""
    assert slides["s1"].description == "The title"


def test_a_slide_id_is_given_once_and_must_be_one():
    slides = Slides()
    slides.add(Slide("s1"))
    with pytest.raises(ValueError, match="exists already"):
        slides.add(Slide("s1"))
    with pytest.raises(ValueError, match="slide id"):
        slides.add(Slide("Slide 1"))
    with pytest.raises(ValueError, match="exists already"):
        slides.check_new("s1")  # what an app asks before it changes anything else
    slides.check_new("s2")
    assert "s2" not in slides


def test_removing_a_slide_gives_it_back_whole():
    slides = Slides()
    slides.add(Slide("s2", "Sales chart", "East leads"))
    assert slides.remove("s2") == Slide("s2", "Sales chart", "East leads")
    assert "s2" not in slides
    with pytest.raises(ValueError, match="unknown slide"):
        slides.remove("s2")


def test_slides_are_written_in_the_order_the_app_gives():
    slides = Slides()
    for slide in (Slide("s1"), Slide("s2", "Two"), Slide("s3", "", "Three")):
        slides.add(slide)
    data = slides.to_data(["s3", "s1", "s2"])  # the app's order (creates: the presentation; computes: its tabs)
    assert [item["id"] for item in data] == ["s3", "s1", "s2"]
    back, order = Slides.from_data(data)
    assert order == ["s3", "s1", "s2"]
    assert [back[i] for i in ("s1", "s2", "s3")] == [slides[i] for i in ("s1", "s2", "s3")]


@pytest.mark.parametrize("order", [["s1"], ["s1", "s2", "s2"], ["s1", "s3"]])
def test_an_order_that_does_not_name_every_slide_once_is_refused(order):
    slides = Slides()
    slides.add(Slide("s1"))
    slides.add(Slide("s2"))
    with pytest.raises(ValueError, match="exactly once"):
        slides.to_data(order)


@pytest.mark.parametrize("item", ["s1", {"name": "No id"}, {"id": "s1", "name": 3}, {"id": "s1", "description": None}])
def test_what_is_not_a_stored_slide_is_refused(item):
    with pytest.raises(ValueError, match="a slide has an id"):
        Slides.from_data([item])
