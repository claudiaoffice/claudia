"""Paragraphs are things (D554): a heading, a list item or a plain paragraph can have a name in the one namespace of
the document (D550), so a tag in the chat can point at it, as named ranges became things in computes (D552).

A paragraph is named when somebody first points at it, not when it is made: a text has many paragraphs and a name for
each would only be noise. The name is kept by the paragraph's id, which a text never gives twice, so it follows the
paragraph through every edit, and undo of a join gives the paragraph that came back its name back.
"""

from dataclasses import replace

import pytest
from composes_helpers import SENTENCE

from claudia_composes import BlockAnchor, InsertText, JoinBlocks, SetListItem, SetStyle, SplitBlock, TextModel
from claudia_core import (
    CreateList,
    Document,
    ListDef,
    ListItem,
    MemoryStore,
    ObjectBody,
    RenameThing,
    ThingRenamed,
    VisualObject,
    paragraph_for,
)


@pytest.fixture
def three(clock):
    """b1 a heading, b2 a list item, b3 a plain paragraph."""
    d = Document(TextModel(), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)
    d.execute(InsertText("b1", 0, "Introduction"), author="ann")
    d.execute(SetStyle("b1", "heading-1"), author="ann")
    d.execute(SplitBlock("b1", 12, "b2", "body"), author="ann")
    d.execute(InsertText("b2", 0, "first point"), author="ann")
    d.execute(CreateList(ListDef("l1", "bullets")), author="ann")
    d.execute(SetListItem("b2", ListItem("l1")), author="ann")
    d.execute(SplitBlock("b2", 11, "b3", "body"), author="ann")
    d.execute(SetListItem("b3", None), author="ann")  # (a split continues the list; this one leaves it)
    d.execute(InsertText("b3", 0, SENTENCE), author="ann")
    return d


def test_a_paragraph_is_a_thing_without_a_name_until_somebody_names_it(three):
    model = three.model
    assert all(model.has_thing(block) for block in ("b1", "b2", "b3"))
    assert model.thing_name("b1") == ""
    assert [thing for _kind, thing, _name in model.named_things()] == []


def test_paragraphs_are_not_among_the_things_named_all_at_once(three):
    """`name_unnamed` names what a document from before names holds; a text's every paragraph is not that."""
    assert [thing for _kind, thing in three.model.unnamed_things()] == []


def test_a_named_paragraph_says_what_kind_of_paragraph_it_is(three):
    for block, name in (("b1", "Intro"), ("b2", "Point A"), ("b3", "Fox")):
        three.execute(RenameThing(block, name), author="ann")
    assert sorted(three.model.named_things()) == [
        ("heading", "b1", "Intro"),
        ("item", "b2", "Point A"),
        ("paragraph", "b3", "Fox"),
    ]


def test_a_paragraph_shares_the_namespace_with_everything_else(three):
    three.execute(RenameThing("b1", "Intro"), author="ann")
    with pytest.raises(ValueError, match="There is already a heading called “Intro”"):
        three.execute(RenameThing("b3", "intro"), author="ann")
    assert three.model.thing_name("b3") == ""


def test_a_rename_is_told_and_undone(three):
    events: list = []
    three.subscribe(lambda e: events.append(e) if isinstance(e, ThingRenamed) else None)
    three.execute(RenameThing("b3", "Fox"), author="ann")
    assert events == [ThingRenamed("b3", "Fox")]
    three.undo("ann")
    assert three.model.thing_name("b3") == ""


def test_the_name_follows_the_paragraph_through_edits_and_a_join_that_is_undone(three):
    three.execute(RenameThing("b3", "Fox"), author="ann")
    three.execute(InsertText("b3", 0, "Look: "), author="ben")
    three.execute(SetStyle("b3", "heading-2"), author="ben")
    assert ("heading", "b3", "Fox") in three.model.named_things()

    three.execute(JoinBlocks("b3", "b2", 11), author="ben")
    assert not three.model.has_thing("b3")
    assert "Fox" not in three.model.names_in_use(), "a paragraph that is gone holds no name"
    three.undo("ben")
    assert three.model.thing_name("b3") == "Fox"


def test_a_new_paragraph_of_a_split_has_no_name(three):
    three.execute(RenameThing("b3", "Fox"), author="ann")
    three.execute(SplitBlock("b3", 9, "b4", "body"), author="ann")
    assert (three.model.thing_name("b3"), three.model.thing_name("b4")) == ("Fox", "")


def test_names_survive_a_snapshot(three):
    three.execute(RenameThing("b1", "Intro"), author="ann")
    again = TextModel.restore(three.model.serialize())
    assert again.thing_name("b1") == "Intro"
    assert ("heading", "b1", "Intro") in again.named_things()


def test_a_state_from_before_named_paragraphs_has_none():
    old = TextModel().serialize()
    del old["names"]
    assert TextModel.restore(old).thing_name("b1") == ""


def test_an_unknown_paragraph_is_no_thing(three):
    with pytest.raises(ValueError):
        three.model.thing_name("b99")


def test_a_paragraph_whose_style_the_text_lacks_is_judged_by_its_own_style_id(three):
    """A paragraph of a file can name a style the text does not have; it is still a thing of some kind."""
    block = next(b for b in three.model.blocks if b.id == "b3")
    assert three.model.block_kind(replace(block, style="no-such-style")) == "paragraph"
    assert three.model.block_kind(replace(block, style="heading-1")) == "heading"


def test_an_object_is_named_in_the_same_namespace_as_the_paragraphs(three):
    box = ObjectBody("o1", "text", 200, 80, "plain-box", paragraph_for("o1", "body", "a note"))
    three.model.insert_object(VisualObject(box, BlockAnchor("b3", 3)))
    three.execute(RenameThing("b3", "Fox"), author="ann")
    three.execute(RenameThing("o1", "Note"), author="ann")
    assert three.model.thing_name("o1") == "Note"
    with pytest.raises(ValueError):
        three.execute(RenameThing("o1", "fox"), author="ann")
    three.undo("ann")
    assert three.model.thing_name("o1") == ""
