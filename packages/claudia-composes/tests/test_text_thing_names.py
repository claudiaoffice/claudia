"""Paragraphs are things (D554): a heading, a list item or a plain paragraph can have a name in the one namespace of
the document (D550), so a tag in the chat can point at it, as named ranges became things in computes (D552).

A paragraph is named when it is made (D1310): the server puts the first free "Paragraph N", in the language of the
person who makes it, in the command that makes it (``SplitParagraph.name``). A heading is the exception (D1311, A3 of
the E1 architecture): it is called by its title, worked out whenever it is asked, so it cannot go stale. The name is
kept by the paragraph's id, which a text never gives twice, so it follows the paragraph through every edit, and undo of
a join gives the paragraph that came back its name back. A text from before paragraphs had names has paragraphs without
one, until ``name_unnamed`` gives them one.
"""

from dataclasses import replace

import pytest
from composes_helpers import SENTENCE

from claudia_composes import (
    DeleteText,
    InsertText,
    JoinParagraphs,
    ParagraphAnchor,
    SetStyle,
    SplitParagraph,
    TextModel,
)
from claudia_core import (
    CreateList,
    Document,
    ListDef,
    ListItem,
    MemoryStore,
    ObjectBody,
    RenameThing,
    SetListItem,
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
    d.execute(SplitParagraph("b1", 12, "b2", "body"), author="ann")
    d.execute(InsertText("b2", 0, "first point"), author="ann")
    d.execute(CreateList(ListDef("l1", "bullets")), author="ann")
    d.execute(SetListItem("b2", ListItem("l1")), author="ann")
    d.execute(SplitParagraph("b2", 11, "b3", "body"), author="ann")
    d.execute(SetListItem("b3", None), author="ann")  # (a split continues the list; this one leaves it)
    d.execute(InsertText("b3", 0, SENTENCE), author="ann")
    return d


def test_a_paragraph_made_before_names_is_a_thing_without_a_name(three):
    model = three.model
    assert all(model.has_thing(paragraph) for paragraph in ("b1", "b2", "b3"))
    assert model.thing_name("b3") == ""
    assert [thing for _kind, thing, _name in model.named_things() if thing != "b1"] == []


def test_a_paragraph_without_a_name_is_among_the_things_name_unnamed_names(three):
    """The heading is not: its title is its name."""
    assert sorted(three.model.unnamed_things()) == [("item", "b2"), ("paragraph", "b3")]


def test_a_named_paragraph_says_what_kind_of_paragraph_it_is(three):
    for paragraph, name in (("b2", "Point A"), ("b3", "Fox")):
        three.execute(RenameThing(paragraph, name), author="ann")
    assert sorted(three.model.named_things()) == [
        ("heading", "b1", "Introduction"),
        ("item", "b2", "Point A"),
        ("paragraph", "b3", "Fox"),
    ]


def test_a_paragraph_shares_the_namespace_with_everything_else(three):
    three.execute(RenameThing("b2", "Point A"), author="ann")
    with pytest.raises(ValueError, match="There is already a list item called “Point A”"):
        three.execute(RenameThing("b3", "point a"), author="ann")
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
    assert three.model.thing_name("b3") == "Look: " + SENTENCE, "a heading is its title"
    three.execute(SetStyle("b3", "body"), author="ben")
    assert ("paragraph", "b3", "Fox") in three.model.named_things(), "its own name was waiting"

    three.execute(JoinParagraphs("b3", "b2", 11), author="ben")
    assert not three.model.has_thing("b3")
    assert "Fox" not in three.model.names_in_use(), "a paragraph that is gone holds no name"
    three.undo("ben")
    assert three.model.thing_name("b3") == "Fox"


# -- a new paragraph has a name from the start (D1310) -------------------------------------------------------------
def test_a_split_that_carries_a_name_gives_it_to_the_new_paragraph(three):
    three.execute(SplitParagraph("b3", 9, "b4", "body", name="Paragraph 1"), author="ann")
    assert three.model.thing_name("b4") == "Paragraph 1"
    assert ("paragraph", "b4", "Paragraph 1") in three.model.named_things()


def test_a_split_without_a_name_is_what_an_older_log_wrote(three):
    three.execute(SplitParagraph("b3", 9, "b4", "body"), author="ann")
    assert three.model.thing_name("b4") == ""


def test_the_name_of_a_split_is_taken_back_with_the_split(three):
    three.execute(SplitParagraph("b3", 9, "b4", "body", name="Paragraph 1"), author="ann")
    three.undo("ann")
    assert "Paragraph 1" not in three.model.names_in_use()
    three.redo("ann")
    assert three.model.thing_name("b4") == "Paragraph 1"


def test_two_people_who_name_a_paragraph_at_once_do_not_make_two_of_one_name(three):
    """The second split arrives with a name that was free for its maker and is not any more."""
    three.execute(SplitParagraph("b3", 9, "b4", "body", name="Paragraph 1"), author="ann")
    three.execute(SplitParagraph("b3", 5, "b5", "body", name="Paragraph 1"), author="ben")
    assert three.model.thing_name("b4") == "Paragraph 1"
    assert three.model.thing_name("b5") == "Paragraph 1 (2)"


def test_the_first_paragraph_of_a_new_text_is_an_unnamed_thing():
    assert list(TextModel().unnamed_things()) == [("paragraph", "b1")]


# -- a heading is called by its title (D1311) ----------------------------------------------------------------------
def test_a_heading_is_called_by_its_title_and_follows_it(three):
    assert three.model.thing_name("b1") == "Introduction"
    three.execute(InsertText("b1", 12, " and aims"), author="ann")
    assert three.model.thing_name("b1") == "Introduction and aims"


def test_a_heading_that_is_only_spaces_has_no_title_to_be_called_by(three):
    three.execute(DeleteText("b1", 0, 12), author="ann")
    assert three.model.thing_name("b1") == ""
    assert ("b1", "heading") not in [(i, k) for k, i, _n in three.model.named_things()]


def test_two_headings_with_one_title_are_told_apart_in_the_order_of_the_text(three):
    three.execute(SplitParagraph("b3", 9, "b4", "body", name="Paragraph 1"), author="ann")
    three.execute(DeleteText("b4", 0, len(three.model.paragraph("b4").text)), author="ann")
    three.execute(InsertText("b4", 0, "introduction"), author="ann")
    three.execute(SetStyle("b4", "heading-1"), author="ann")
    assert three.model.thing_name("b1") == "Introduction"
    assert three.model.thing_name("b4") == "introduction (2)"


def test_a_heading_does_not_take_the_name_somebody_gave_a_paragraph(three):
    three.execute(RenameThing("b3", "Summary"), author="ann")
    three.execute(DeleteText("b1", 0, 12), author="ann")
    three.execute(InsertText("b1", 0, "Summary"), author="ann")
    assert three.model.thing_name("b3") == "Summary"
    assert three.model.thing_name("b1") == "Summary (2)"


def test_nobody_can_give_a_paragraph_the_title_of_a_heading(three):
    with pytest.raises(ValueError, match="There is already a heading called “Introduction”"):
        three.execute(RenameThing("b3", "introduction"), author="ann")


def test_a_heading_keeps_the_name_it_had_as_a_paragraph_for_when_it_is_one_again(three):
    three.execute(RenameThing("b3", "Fox"), author="ann")
    three.execute(SetStyle("b3", "heading-2"), author="ann")
    assert three.model.thing_name("b3") != "Fox"
    three.execute(SetStyle("b3", "body"), author="ann")
    assert three.model.thing_name("b3") == "Fox"


def test_names_survive_a_snapshot(three):
    three.execute(RenameThing("b3", "Fox"), author="ann")
    again = TextModel.restore(three.model.serialize())
    assert again.thing_name("b3") == "Fox"
    assert ("paragraph", "b3", "Fox") in again.named_things()


def test_a_state_from_before_named_paragraphs_has_none():
    old = TextModel().serialize()
    del old["names"]
    assert TextModel.restore(old).thing_name("b1") == ""  # (a paragraph, not a heading)


def test_an_unknown_paragraph_is_no_thing(three):
    with pytest.raises(ValueError):
        three.model.thing_name("b99")


def test_a_paragraph_whose_style_the_text_lacks_is_judged_by_its_own_style_id(three):
    """A paragraph of a file can name a style the text does not have; it is still a thing of some kind."""
    paragraph = next(b for b in three.model.paragraphs if b.id == "b3")
    assert three.model.paragraph_kind(replace(paragraph, style="no-such-style")) == "paragraph"
    assert three.model.paragraph_kind(replace(paragraph, style="heading-1")) == "heading"


def test_an_object_is_named_in_the_same_namespace_as_the_paragraphs(three):
    box = ObjectBody("o1", "text", 200, 80, "plain-box", paragraph_for("o1", "body", "a note"))
    three.model.insert_object(VisualObject(box, ParagraphAnchor("b3", 3)))
    three.execute(RenameThing("b3", "Fox"), author="ann")
    three.execute(RenameThing("o1", "Note"), author="ann")
    assert three.model.thing_name("o1") == "Note"
    with pytest.raises(ValueError):
        three.execute(RenameThing("o1", "fox"), author="ann")
    three.undo("ann")
    assert three.model.thing_name("o1") == ""


# dock-text (2026-11-20): a paragraph made a heading was still offered as "Paragraph 1" in the # list, since nobody told
# the clients that its name had become its words (D1311)
def renamings(document):
    told: list = []
    document.subscribe(lambda e: told.append(e) if isinstance(e, ThingRenamed) else None)
    return told


def test_a_paragraph_that_becomes_a_heading_is_told_by_its_words(clock):
    d = Document(TextModel(), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)
    d.execute(InsertText("b1", 0, "Introduction"), author="ann")
    d.execute(RenameThing("b1", "Paragraph 1"), author="ann")  # as a paragraph made by Enter is called (D1310)
    told = renamings(d)
    d.execute(SetStyle("b1", "heading-1"), author="ann")
    assert ThingRenamed("b1", "Introduction") in told


def test_retyping_a_heading_tells_its_new_name_and_a_paragraph_again_its_old_one(three):
    told = renamings(three)
    three.execute(InsertText("b1", 0, "An "), author="ann")
    assert told[-1] == ThingRenamed("b1", "An Introduction")
    three.execute(SetStyle("b1", "body"), author="ann")
    assert told[-1].id == "b1" and told[-1].name == three.model.thing_name("b1")


def test_typing_in_a_paragraph_tells_no_name(three):
    told = renamings(three)
    three.execute(InsertText("b3", 0, "Well, "), author="ann")
    assert told == []
