"""The paragraphs of a presentation as the shared text structure reads them (step C, E10.21).

A presentation is a ParagraphHost: its slides in order, on each slide the words of its objects in stacking order
(bottom first: what PowerPoint reads to a screen reader, decided by the owner on 2026-11-16), and each slide's number
as the place a reader finds them. A list continues from one text box to the next across slides."""

from dataclasses import replace

import pytest
from conftest import SLIDE, add, text_box

from claudia_core import (
    CreateList,
    Document,
    LabelsChanged,
    ListDef,
    ListItem,
    MemoryStore,
    RemoveObject,
    TextStructure,
)
from claudia_creates import AddSlide, SlideModel


def item(obj, list_id="l1", level=0):
    """``obj`` with its words an item of a list."""
    return replace(obj, body=replace(obj.body, paragraph=replace(obj.body.paragraph, item=ListItem(list_id, level))))


@pytest.fixture
def deck():
    d = Document(SlideModel.empty(), store=MemoryStore())
    d.execute(AddSlide("s2"), author="ann")
    d.execute(CreateList(ListDef("l1", "numbers")), author="ann")
    return d


def markers(deck):
    return {k: v.marker for k, v in deck.model.labels().items()}


def test_the_words_are_read_slide_by_slide_in_stacking_order_with_the_slide_number_as_their_place(deck):
    deck.execute(add(text_box("a", text="A")), author="ann")
    deck.execute(add(text_box("b", text="B"), at=0), author="ann")  # under "a": read first
    deck.execute(add(text_box("c", slide="s2", text="C")), author="ann")
    read = [(p.paragraph.id, p.container, p.main, p.place) for p in deck.model.reading_order()]
    assert read == [("b", SLIDE, True, "1"), ("a", SLIDE, True, "1"), ("c", "s2", True, "2")]
    assert isinstance(deck.model.structure, TextStructure)


def test_a_list_continues_from_one_text_box_to_the_next_across_slides(deck):
    events = []
    deck.subscribe(lambda e: events.append(e) if isinstance(e, LabelsChanged) else None)
    deck.execute(add(item(text_box("a", text="first"))), author="ann")
    deck.execute(add(item(text_box("c", slide="s2", text="third"))), author="ann")
    deck.execute(add(item(text_box("b", text="second"), level=1)), author="ann")
    assert markers(deck) == {"a": "1.", "b": "a.", "c": "2."}
    assert events[-1].to_data()["labels"] == {"b": {"marker": "a.", "path": [1, 1]}}
    deck.execute(RemoveObject("a"), author="ann")
    assert markers(deck) == {"b": "a.", "c": "1."}


def test_the_lists_are_part_of_the_presentation_and_survive_a_snapshot(deck):
    deck.execute(add(item(text_box("a", text="first"))), author="ann")
    again = SlideModel.restore(deck.model.serialize())
    assert "l1" in again.lists and {k: v.marker for k, v in again.labels().items()} == {"a": "1."}
    assert again.list_in_use("l1") and not again.list_in_use("l2")


def test_a_snapshot_from_before_lists_opens_without_any():
    state = SlideModel.empty().serialize()
    del state["lists"]
    assert len(SlideModel.restore(state).lists) == 0
