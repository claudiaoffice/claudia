"""A turned object keeps its outline on the slide (rotation-ui, open point 3).

The frame of an object is its unturned rectangle; turning it about its centre makes it reach further. The slide
keeps what is on it on the slide, so the rule is about the outline, and a turn that would push a corner off is
carried out together with the move that keeps it on, as one command and one undo step.
"""

import pytest
from conftest import SLIDE, add, frame, move, text_box

from claudia_core import RotateObject
from claudia_creates import SLIDE_HEIGHT, SLIDE_WIDTH, SlideAnchor


def test_an_upright_object_must_still_have_its_frame_on_the_slide(doc):
    with pytest.raises(ValueError, match="stay on the slide"):
        doc.execute(add(text_box(x=SLIDE_WIDTH - 399, w=400)), author="ann")


def test_a_turned_object_is_judged_by_its_outline(doc):
    # 300 x 100 turned upright stands 100 wide and 300 tall around its centre: at the very top it sticks out above
    with pytest.raises(ValueError, match="stay on the slide"):
        doc.execute(add(text_box(x=0, y=0, w=300, h=100, rotation=90)), author="ann")
    doc.execute(add(text_box(x=0, y=100, w=300, h=100, rotation=90)), author="ann")


def test_the_frame_of_a_turned_object_may_lie_beyond_the_slide(doc):
    # 400 x 100 upright is 100 wide around x = 50, so its (unturned) frame starts at -150
    doc.execute(add(text_box(x=-150, y=400, w=400, h=100, rotation=90)), author="ann")
    assert frame(doc, "t1") == (-150, 400, 400, 100)


def test_turning_without_a_new_place_is_refused_when_the_outline_would_leave_the_slide(doc):
    doc.execute(add(text_box(x=0, y=0, w=300, h=100)), author="ann")
    with pytest.raises(ValueError, match="stay on the slide"):
        doc.execute(RotateObject("t1", 90), author="ann")
    assert doc.model.get("t1").body.rotation == 0


def test_a_turn_can_carry_the_place_that_keeps_the_outline_on_the_slide(doc):
    doc.execute(add(text_box(x=0, y=0, w=300, h=100)), author="ann")
    doc.execute(RotateObject("t1", 90, SlideAnchor(SLIDE, 0, 100).to_data()), author="ann")
    obj = doc.model.get("t1")
    assert (obj.body.rotation, obj.anchor.x, obj.anchor.y) == (90, 0, 100)


def test_one_undo_takes_back_both_the_turn_and_the_nudge(doc):
    doc.execute(add(text_box(x=0, y=0, w=300, h=100)), author="ann")
    doc.execute(RotateObject("t1", 90, SlideAnchor(SLIDE, 0, 100).to_data()), author="ann")
    doc.undo("ann")
    obj = doc.model.get("t1")
    assert (obj.body.rotation, obj.anchor.x, obj.anchor.y) == (0, 0, 0)


def test_a_turn_without_a_place_undoes_as_it_always_did(doc):
    doc.execute(add(text_box(x=600, y=400, w=300, h=100)), author="ann")
    doc.execute(RotateObject("t1", 90), author="ann")
    doc.undo("ann")
    assert doc.model.get("t1").body.rotation == 0


def test_a_turn_command_without_a_place_is_stored_as_it_always_was():
    assert RotateObject("t1", 90).to_data() == {"id": "t1", "rotation": 90}
    carried = RotateObject("t1", 90, {"kind": "slide", "holder": SLIDE, "x": 0, "y": 100})
    assert RotateObject.from_data(carried.to_data(), registry=None) == carried  # type: ignore[arg-type]


def test_a_move_after_a_turn_is_judged_by_the_outline_too(doc):
    doc.execute(add(text_box(x=600, y=400, w=300, h=100, rotation=90)), author="ann")
    doc.execute(move("t1", 0, 200), author="ann")  # outline x 100..200 is fine although the frame is at 0
    with pytest.raises(ValueError, match="stay on the slide"):
        doc.execute(move("t1", 0, SLIDE_HEIGHT - 100), author="ann")


def test_the_model_nudges_a_turn_to_the_nearest_place_that_fits(doc):
    doc.execute(add(text_box(x=0, y=0, w=300, h=100)), author="ann")
    anchor = doc.model.turned_anchor(doc.model.get("t1"), 90)
    assert anchor == SlideAnchor(SLIDE, 0, 100)


def test_the_model_refuses_a_turn_that_can_never_fit(doc):
    doc.execute(add(text_box(x=0, y=0, w=SLIDE_WIDTH, h=100)), author="ann")
    with pytest.raises(ValueError, match="too large to turn"):
        doc.model.turned_anchor(doc.model.get("t1"), 90)


# -- the command a client's "turn it to this angle" becomes ----------------------------------------------------
def test_turning_to_an_angle_that_needs_no_nudge_is_a_plain_turn(doc):
    doc.execute(add(text_box(x=600, y=400, w=300, h=100)), author="ann")
    assert doc.model.turn_command("t1", 37) == RotateObject("t1", 37)


def test_turning_to_an_angle_that_needs_a_nudge_carries_the_new_place(doc):
    doc.execute(add(text_box(x=0, y=0, w=300, h=100)), author="ann")
    command = doc.model.turn_command("t1", 90)
    assert command == RotateObject("t1", 90, SlideAnchor(SLIDE, 0, 100).to_data())
    doc.execute(command, author="ann")
    assert frame(doc, "t1") == (0, 100, 300, 100)


@pytest.mark.parametrize(("asked", "stored"), [(-20, 340), (360, 0), (725, 5), (0, 0)])
def test_any_whole_number_of_degrees_is_read_modulo_a_whole_turn(doc, asked, stored):
    doc.execute(add(text_box(x=600, y=400, w=300, h=100)), author="ann")
    assert doc.model.turn_command("t1", asked).rotation == stored


@pytest.mark.parametrize("bad", [1.5, "90", None, True])
def test_a_turn_is_whole_degrees(doc, bad):
    doc.execute(add(text_box()), author="ann")
    with pytest.raises(ValueError, match="whole degrees"):
        doc.model.turn_command("t1", bad)


def test_an_unknown_object_cannot_be_turned(doc):
    with pytest.raises(ValueError, match="no object"):
        doc.model.turn_command("nothing", 90)
