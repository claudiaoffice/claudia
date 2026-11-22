"""A slide can be described (D1317, D1318): a plain string beside its name, written by a logged command, undone with
it, kept through a snapshot, and gone with the slide."""

import pytest

from claudia_core import DescribeThing, Document, MemoryStore, ThingDescribed
from claudia_creates import AddSlide, RemoveSlide, SlideModel


@pytest.fixture
def deck():
    doc = Document(SlideModel.empty(), store=MemoryStore())
    doc.execute(AddSlide("s2", name="Agenda"), author="ann")
    return doc


def test_a_slide_has_no_description_until_somebody_writes_one(deck):
    assert deck.model.thing_description("s2") == ""


def test_a_description_is_written_told_and_undone(deck):
    events: list = []
    deck.subscribe(lambda e: events.append(e) if isinstance(e, ThingDescribed) else None)
    deck.execute(DescribeThing("s2", "The plan for Q4"), author="ann")
    assert deck.model.thing_description("s2") == "The plan for Q4"
    assert events == [ThingDescribed("s2", "The plan for Q4")]
    deck.undo("ann")
    assert deck.model.thing_description("s2") == ""


def test_it_survives_a_snapshot_and_a_slide_without_one_is_stored_without_one(deck):
    deck.execute(DescribeThing("s2", "kept"), author="ann")
    state = deck.model.serialize()
    assert SlideModel.restore(state).thing_description("s2") == "kept"
    assert state["slides"] == [{"id": "s1"}, {"id": "s2", "name": "Agenda", "description": "kept"}]


def test_it_goes_with_the_slide_and_comes_back_with_an_undo(deck):
    deck.execute(DescribeThing("s2", "gone"), author="ann")
    deck.execute(RemoveSlide("s2"), author="ann")
    assert "s2" not in deck.model.slides
    deck.undo("ann")
    assert deck.model.thing_description("s2") == "gone"
