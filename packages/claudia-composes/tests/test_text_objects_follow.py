"""An object in a text follows the words it hangs from (E10.16, D179; ``claudia_composes.anchors``).

``TextModel.move_objects`` had no test of its own (QA 2026-11-12): a picture that stays at character 3 while somebody
types in front of it ends up next to a different word, and one left on a paragraph that was joined away belongs to
nothing. These walk an object through each kind of text command and back with undo.
"""

import pytest

from claudia_composes import BlockAnchor, DeleteText, InsertText, JoinBlocks, SplitBlock, TextModel
from claudia_core import Document, MemoryStore, ObjectBody, VisualObject, paragraph_for


def text_with_a_box(words: str = "Hello world", offset: int = 6) -> Document:
    d = Document(TextModel(), store=MemoryStore())
    d.execute(InsertText("b1", 0, words), author="ann")
    box = ObjectBody("o1", "text", 200, 80, "plain-box", paragraph_for("o1", "body", "a note"))
    d.model.insert_object(VisualObject(box, BlockAnchor("b1", offset)))
    return d


def anchor(d: Document) -> tuple[str, int]:
    a = d.model.objects["o1"].anchor
    return a.block, a.offset


def test_typing_before_the_object_moves_it_with_its_word_and_after_it_does_not():
    d = text_with_a_box()
    d.execute(InsertText("b1", 0, "Oh. "), author="ben")
    assert anchor(d) == ("b1", 10), "still in front of 'world'"
    d.execute(InsertText("b1", 15, "!"), author="ben")
    assert anchor(d) == ("b1", 10)
    d.undo("ben")
    d.undo("ben")
    assert anchor(d) == ("b1", 6), "undo takes it back with the words"


def test_deleting_the_text_before_it_pulls_it_back():
    d = text_with_a_box()
    d.execute(DeleteText("b1", 0, 6), author="ann")
    assert anchor(d) == ("b1", 0)
    assert d.model.block("b1").text == "world"


def test_splitting_the_paragraph_before_it_carries_it_into_the_new_one():
    d = text_with_a_box()
    d.execute(SplitBlock("b1", 3, "b2", "body"), author="ann")
    assert anchor(d) == ("b2", 3), "'world' now starts at 3 of the new paragraph"
    assert [o.id for o in d.model.objects_on("b2")] == ["o1"]
    assert d.model.objects_on("b1") == []


def test_joining_its_paragraph_away_takes_it_to_the_one_that_survives():
    d = text_with_a_box()
    d.execute(SplitBlock("b1", 6, "b2", "body"), author="ann")
    assert anchor(d) == ("b2", 0)
    d.execute(JoinBlocks("b2", "b1", 6), author="ann")
    assert anchor(d) == ("b1", 6)
    assert [o.id for o in d.model.objects_on("b1")] == ["o1"]


def test_an_anchor_round_trips_and_refuses_what_is_not_one():
    a = BlockAnchor("b1", 4)
    assert BlockAnchor.from_data(a.to_data()) == a
    assert a.container == "b1" and a.span == ("b1", 4, 4)
    for bad in (
        {"kind": "slide", "container": "b1", "offset": 0},
        {"kind": "block", "container": "b1", "offset": True},
    ):
        with pytest.raises(ValueError):
            BlockAnchor.from_data(bad)


# D1331: a paragraph after what hangs at the end of a paragraph (a table at the end of the text), not before it
def test_a_split_that_keeps_leaves_what_hangs_at_the_cut_where_it_is():
    d = text_with_a_box("Hello", offset=5)
    d.execute(SplitBlock("b1", 5, "b2", "body", keep=True), author="ann")
    assert anchor(d) == ("b1", 5), "the object stays with the paragraph it hung from"
    assert [b.id for b in d.model.blocks] == ["b1", "b2"]
    assert d.model.block("b2").text == ""
    assert d.model.objects_on("b2") == []


def test_a_split_that_keeps_still_carries_what_hangs_after_the_cut():
    d = text_with_a_box("Hello world", offset=8)
    d.execute(SplitBlock("b1", 6, "b2", "body", keep=True), author="ann")
    assert anchor(d) == ("b2", 2), "only what hangs exactly at the cut stays"


def test_undo_and_redo_of_a_split_that_keeps_leave_the_object_where_it_was():
    d = text_with_a_box("Hello", offset=5)
    d.execute(SplitBlock("b1", 5, "b2", "body", keep=True), author="ann")
    d.undo("ann")
    assert [b.id for b in d.model.blocks] == ["b1"]
    assert anchor(d) == ("b1", 5)
    d.redo("ann")
    assert [b.id for b in d.model.blocks] == ["b1", "b2"]
    assert anchor(d) == ("b1", 5), "redo must not carry the object into the new paragraph"


def test_undoing_the_join_of_a_paragraph_without_objects_does_not_carry_the_others_away():
    d = text_with_a_box("Hello", offset=5)
    d.execute(SplitBlock("b1", 5, "b2", "body", keep=True), author="ann")
    d.execute(InsertText("b2", 0, "next"), author="ann")
    d.execute(JoinBlocks("b2", "b1", 5), author="ann")
    assert d.model.block("b1").text == "Hellonext"
    d.undo("ann")
    assert anchor(d) == ("b1", 5), "the object hung from b1 before the join and does after its undo"
    assert d.model.block("b2").text == "next"


def test_keep_is_written_only_when_it_is_set():
    assert "keep" not in SplitBlock("b1", 5, "b2", "body").to_data()
    data = SplitBlock("b1", 5, "b2", "body", keep=True).to_data()
    assert data["keep"] is True
    assert SplitBlock.from_data(data, None) == SplitBlock("b1", 5, "b2", "body", keep=True)
    assert SplitBlock.from_data({"block": "b1", "offset": 5, "new_id": "b2", "style": "body"}, None).keep is False
