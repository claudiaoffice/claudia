"""An object in a text can be moved to another paragraph (D1351; the ``@unit`` scenarios of
``specs/composes/object-anchor.feature``).

B8 (2026-11-20): a drop near another paragraph was refused with "an object cannot change its container", since the
kernel kept every object in its holder. A text lets its objects change paragraph; a slide or a sheet does not.
"""

import pytest

from claudia_composes import BlockAnchor, InsertText, SplitBlock, TextModel, TextRange
from claudia_core import (
    Document,
    MemoryStore,
    MoveObject,
    ObjectBody,
    ObjectsChanged,
    RegionHeld,
    VisualObject,
    paragraph_for,
)
from claudia_creates import AddSlide, SlideAnchor, SlideModel


def box(object_id: str, words_style: str = "body") -> ObjectBody:
    return ObjectBody(object_id, "text", 200, 80, "plain-box", paragraph_for(object_id, words_style, "a note"))


@pytest.fixture
def text():
    """Three paragraphs; two objects hang from the first, o1 behind o2."""
    d = Document(TextModel(), store=MemoryStore())
    d.execute(InsertText("b1", 0, "The gardens"), author="ann")
    d.execute(SplitBlock("b1", 11, "b2", "body"), author="ann")
    d.execute(InsertText("b2", 0, "The courtyard"), author="ann")
    d.execute(SplitBlock("b2", 13, "b3", "body"), author="ann")
    d.execute(InsertText("b3", 0, "The allotment"), author="ann")
    d.model.insert_object(VisualObject(box("o1"), BlockAnchor("b1", 4)))
    d.model.insert_object(VisualObject(box("o2"), BlockAnchor("b1", 8)))
    return d


def move(document, object_id: str, block: str, offset: int, author: str = "ann") -> None:
    document.execute(MoveObject(object_id, BlockAnchor(block, offset).to_data()), author=author)


def test_an_object_moved_to_another_paragraph_hangs_from_it_on_top_of_its_stack(text):
    text.model.insert_object(VisualObject(box("o3"), BlockAnchor("b3", 0)))
    move(text, "o1", "b3", 4)
    anchor = text.model.objects["o1"].anchor
    assert (anchor.block, anchor.offset) == ("b3", 4)
    assert text.model.stack_of("b1") == ("o2",)
    assert text.model.stack_of("b3") == ("o3", "o1"), "on top of what hangs there already"


def test_the_clients_hear_both_paragraphs_and_the_object_is_never_removed(text):
    events: list = []
    text.subscribe(lambda e: events.append(e) if isinstance(e, ObjectsChanged) else None)
    move(text, "o1", "b3", 4)
    by_holder = {e.holder: e for e in events}
    assert by_holder["b1"].order == ("o2",) and by_holder["b1"].removed == ()
    assert [o.id for o in by_holder["b3"].changed] == ["o1"]


def test_undo_puts_it_back_in_its_place_in_the_old_stack_and_redo_moves_it_again(text):
    move(text, "o1", "b3", 4)
    text.undo("ann")
    assert text.model.objects["o1"].anchor.block == "b1"
    assert text.model.stack_of("b1") == ("o1", "o2"), "behind o2 again, as it was"
    assert text.model.stack_of("b3") == ()
    text.redo("ann")
    assert text.model.objects["o1"].anchor.block == "b3"
    assert text.model.stack_of("b1") == ("o2",)


def test_a_move_inside_its_paragraph_keeps_its_place_in_the_stack(text):
    move(text, "o1", "b1", 9)
    assert text.model.stack_of("b1") == ("o1", "o2")


def test_a_move_into_a_paragraph_a_colleague_is_writing_in_is_refused(text):
    text.lock("ben", [TextRange("b3", 0, 13)], ttl=5)
    with pytest.raises(RegionHeld):
        move(text, "o1", "b3", 4)
    assert text.model.objects["o1"].anchor.block == "b1", "it stays where it was"
    move(text, "o1", "b2", 4)  # elsewhere is free


def test_the_move_is_written_and_read_with_its_place_in_the_stack():
    plain = MoveObject("o1", {"kind": "block", "block": "b1", "offset": 2})
    assert "at" not in plain.to_data()
    placed = MoveObject("o1", {"kind": "block", "block": "b1", "offset": 2}, at=1)
    assert MoveObject.from_data(placed.to_data(), None) == placed
    assert MoveObject.from_data(plain.to_data(), None).at is None


def test_on_a_slide_an_object_still_cannot_change_its_container():
    deck = Document(SlideModel.empty(), store=MemoryStore())
    deck.execute(AddSlide("s2"), author="ann")
    deck.model.insert_object(VisualObject(box("o1", "body-text"), SlideAnchor("s1", 10, 10)))
    with pytest.raises(ValueError, match="cannot change its holder"):
        deck.execute(MoveObject("o1", SlideAnchor("s2", 10, 10).to_data()), author="ann")
