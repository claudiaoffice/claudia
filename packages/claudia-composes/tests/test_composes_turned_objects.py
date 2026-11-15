"""Turning an object in a text (rotation-ui): it turns about its centre and its anchor does not move.

A text has no edge an object could fall off, so a turn is never nudged and there is no place to carry; the offset
from the anchor character stays what it was.
"""

import pytest

from claudia_composes import BlockAnchor, InsertText, RotateObject, TextModel
from claudia_core import Document, MemoryStore, ObjectBody, VisualObject, paragraph_for


@pytest.fixture
def text() -> Document:
    d = Document(TextModel(), store=MemoryStore())
    d.execute(InsertText("b1", 0, "Hello world"), author="ann")
    box = ObjectBody("o1", "text", 200, 80, "plain-box", paragraph_for("o1", "body", "a note"))
    d.model.insert_object(VisualObject(box, BlockAnchor("b1", 6, dx=40, dy=-10)))
    return d


def test_turning_an_object_in_a_text_keeps_its_anchor_and_its_offset(text):
    text.execute(text.model.turn_command("o1", 30), author="ann")
    obj = text.model.objects["o1"]
    assert obj.body.rotation == 30
    assert obj.anchor == BlockAnchor("b1", 6, dx=40, dy=-10)


def test_the_command_for_a_turn_in_a_text_carries_no_place(text):
    assert text.model.turn_command("o1", -90) == RotateObject("o1", 270)


def test_one_undo_takes_the_turn_back(text):
    text.execute(text.model.turn_command("o1", 30), author="ann")
    text.undo("ann")
    assert text.model.objects["o1"].body.rotation == 0
