"""A table of contents in a text (E9.31, step E): a generated paragraph that takes no typing, whose entries follow the
headings."""

import pytest

from claudia_composes import Block, BlockAnchor, BlockGenerated, InsertText, JoinBlocks, SplitBlock, TextModel
from claudia_core import Document, MemoryStore, ObjectBody, SetGenerated, Toc, VisualObject, paragraph_for


@pytest.fixture
def text():
    blocks = [Block("b1", "heading-1", "Why"), Block("b2", "body", ""), Block("b3", "heading-2", "Asked")]
    return Document(TextModel(blocks), store=MemoryStore())


def test_an_empty_paragraph_becomes_a_table_of_contents_and_undo_makes_it_plain_again(text):
    events = []
    text.subscribe(events.append)
    text.execute(SetGenerated("b2", Toc()), author="ann")
    assert text.model.block("b2").generated == Toc()
    assert BlockGenerated("b2", Toc()) in events
    assert [e.target for e in text.model.structure.entries("b2")] == ["b1", "b3"]
    text.undo("ann")
    assert text.model.block("b2").generated is None


def test_it_takes_no_typing_and_no_join_but_enter_after_it_makes_a_plain_paragraph(text):
    text.execute(SetGenerated("b2", Toc()), author="ann")
    with pytest.raises(ValueError, match="no typing"):
        text.execute(InsertText("b2", 0, "x"), author="ann")
    with pytest.raises(ValueError, match="cannot be joined"):
        text.execute(JoinBlocks("b2", "b1", 3), author="ann")
    with pytest.raises(ValueError, match="joined into a table"):
        text.execute(JoinBlocks("b3", "b2", 0), author="ann")
    text.execute(SplitBlock("b2", 0, "b9", "body"), author="ann")
    assert text.model.block("b9").generated is None and text.model.block("b2").generated == Toc()
    text.undo("ann")
    assert [b.id for b in text.model.blocks] == ["b1", "b2", "b3"]


def test_a_paragraph_with_words_cannot_become_one(text):
    with pytest.raises(ValueError, match="only an empty paragraph"):
        text.execute(SetGenerated("b1", Toc()), author="ann")


def test_it_survives_a_snapshot(text):
    text.execute(SetGenerated("b2", Toc(1, 2, leader="none")), author="ann")
    again = TextModel.restore(text.model.serialize())
    assert again.block("b2").generated == Toc(1, 2, leader="none")
    assert [e.target for e in again.structure.entries("b2")] == ["b1", "b3"]


def test_the_words_of_a_floating_object_can_be_a_table_of_contents_too(text):
    box = ObjectBody("o1", "text", 200, 80, "plain-box", paragraph_for("o1", "body"))
    text.model.insert_object(VisualObject(box, BlockAnchor("b1", 1)))
    text.execute(SetGenerated("o1", Toc(1, 1)), author="ann")
    assert text.model.generated_of("o1") == Toc(1, 1)
    text.undo("ann")
    assert text.model.generated_of("o1") is None


def test_the_clients_hear_which_paragraph_became_a_table_and_which_became_plain_again():
    assert BlockGenerated("b2", Toc(1, 2)).to_data() == {
        "type": "block_generated",
        "block": "b2",
        "generated": Toc(1, 2).to_data(),
    }
    assert BlockGenerated("b2", None).to_data()["generated"] is None


def test_the_words_of_a_floating_object_are_typed_into_like_a_paragraph(text):
    """Step G: the kernel's typing reaches the words of a floating object too, and its zone is the object."""
    from claudia_core import DeleteText, InsertText, ObjectSet

    box = ObjectBody("o1", "text", 200, 80, "plain-box", paragraph_for("o1", "body", "a note"))
    text.model.insert_object(VisualObject(box, BlockAnchor("b1", 1)))
    text.execute(InsertText("o1", 1, " short"), author="ben")
    assert text.model.get_object("o1").body.paragraph.text == "a short note"
    assert all(isinstance(r, ObjectSet) for r in InsertText("o1", 1, "x").regions(text.model))
    text.execute(DeleteText("o1", 8, 4), author="ben")
    assert text.model.get_object("o1").body.paragraph.text == "a short "
    text.undo("ben")
    text.undo("ben")
    assert text.model.get_object("o1").body.paragraph.text == "a note"
