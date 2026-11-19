"""Every thing can be described (D1317), a paragraph's description is stored the way an object's is (D1318): a plain
string beside the name, changed by a logged command, undone with it, seen by everybody, kept through a snapshot."""

import pytest
from composes_helpers import SENTENCE

from claudia_composes import BlockAnchor, InsertText, JoinBlocks, SplitBlock, TextModel
from claudia_core import (
    DescribeObject,
    DescribeThing,
    Document,
    MemoryStore,
    ObjectBody,
    ThingDescribed,
    VisualObject,
    paragraph_for,
)
from claudia_core.assets import MAX_ALT_CHARS


@pytest.fixture
def text(clock):
    d = Document(TextModel(), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)
    d.execute(InsertText("b1", 0, SENTENCE), author="ann")
    d.execute(SplitBlock("b1", 9, "b2", "body", name="Paragraph 2"), author="ann")
    return d


def test_a_paragraph_has_no_description_until_somebody_writes_one(text):
    assert text.model.thing_description("b2") == ""


def test_a_description_is_written_told_and_undone(text):
    events: list = []
    text.subscribe(lambda e: events.append(e) if isinstance(e, ThingDescribed) else None)
    text.execute(DescribeThing("b2", "Check the date with legal"), author="ann")
    assert text.model.thing_description("b2") == "Check the date with legal"
    assert events == [ThingDescribed("b2", "Check the date with legal")]
    text.undo("ann")
    assert text.model.thing_description("b2") == ""
    text.redo("ann")
    assert text.model.thing_description("b2") == "Check the date with legal"


def test_describing_again_replaces_and_undo_gives_the_earlier_words_back(text):
    text.execute(DescribeThing("b2", "first"), author="ann")
    text.execute(DescribeThing("b2", "second"), author="ann")
    text.undo("ann")
    assert text.model.thing_description("b2") == "first"


def test_empty_words_take_the_description_away(text):
    text.execute(DescribeThing("b2", "first"), author="ann")
    text.execute(DescribeThing("b2", ""), author="ann")
    assert text.model.thing_description("b2") == ""
    assert "b2" not in text.model.block_descriptions


def test_it_stays_with_the_paragraph_through_edits_and_a_join_that_is_undone(text):
    text.execute(DescribeThing("b2", "kept"), author="ann")
    text.execute(InsertText("b2", 0, "Look: "), author="ben")
    text.execute(JoinBlocks("b2", "b1", 9), author="ben")
    text.undo("ben")
    assert text.model.thing_description("b2") == "kept"


def test_the_other_person_reads_the_same_words(text):
    text.execute(DescribeThing("b2", "for Ben"), author="ann")
    again = TextModel.restore(text.model.serialize())
    assert again.thing_description("b2") == "for Ben"


def test_a_state_from_before_descriptions_has_none():
    old = TextModel().serialize()
    del old["descriptions"]
    assert TextModel.restore(old).thing_description("b1") == ""


def test_a_description_is_short_text_and_of_something_there_is(text):
    with pytest.raises(ValueError, match="at most"):
        text.execute(DescribeThing("b2", "x" * (MAX_ALT_CHARS + 1)), author="ann")
    with pytest.raises(ValueError, match="nothing with the id"):
        text.execute(DescribeThing("b99", "words"), author="ann")


def test_a_redacted_description_is_gone():
    assert DescribeThing("b2", "secret").redacted() == DescribeThing("b2", "")


def test_the_command_survives_the_log():
    data = DescribeThing("b2", "words").to_data()
    assert DescribeThing.from_data(data, None) == DescribeThing("b2", "words")


def test_an_object_is_described_by_describe_object_which_says_whether_it_is_decoration(text):
    box = ObjectBody("o1", "text", 200, 80, "plain-box", paragraph_for("o1", "body", "a note"))
    text.model.insert_object(VisualObject(box, BlockAnchor("b2", 3)))
    assert text.model.thing_description("o1") == ""
    with pytest.raises(ValueError, match="DescribeObject"):
        text.execute(DescribeThing("o1", "words"), author="ann")
    text.execute(DescribeObject("o1", "a note about the fox", False), author="ann")
    assert text.model.thing_description("o1") == "a note about the fox"


def test_redacting_an_import_takes_the_words_written_about_a_blanked_paragraph(text):
    text.execute(DescribeThing("b2", "secret"), author="ann")
    text.execute(DescribeThing("b1", "kept"), author="ann")
    text.model.blank(frozenset({"b2"}))
    assert (text.model.thing_description("b2"), text.model.thing_description("b1")) == ("", "kept")
    text.model.blank(None)
    assert text.model.thing_description("b1") == ""
