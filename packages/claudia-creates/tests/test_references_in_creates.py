"""References in the words of a text box (step H): a reference to a slide title shows its number, its words or its
slide; one to a picture shows the picture's name."""

import pytest
from conftest import add, text_box

from claudia_core import (
    FIELD_CHAR,
    Document,
    InsertText,
    MemoryStore,
    RefField,
    SetField,
    Shown,
)
from claudia_creates import AddSlide, SlideModel


@pytest.fixture
def deck():
    d = Document(SlideModel.empty(), store=MemoryStore())
    d.execute(AddSlide("s2"), author="ann")
    d.execute(add(text_box("t2", slide="s2", text="Results")), author="ann")
    d.execute(add(text_box("a", text="see slide ")), author="ann")
    return d


def test_a_reference_to_a_box_on_another_slide_shows_its_slide_number_or_its_words(deck):
    deck.execute(InsertText("a", 10, FIELD_CHAR, fields=(RefField("t2", "page"),)), author="ann")
    assert deck.model.structure.shown()["a"] == (Shown("2"),)
    deck.execute(SetField("a", 0, RefField("t2", "text")), author="ann")
    assert deck.model.structure.shown()["a"] == (Shown("Results"),)
    assert deck.model.object_fields("a") == (RefField("t2", "text"),)
    deck.undo("ann")
    assert deck.model.object_fields("a") == (RefField("t2", "page"),)


def test_a_reference_to_a_thing_without_words_shows_its_name_and_a_missing_one_is_broken(deck):
    deck.execute(add(text_box("pic", text="")), author="ann")
    deck.execute(InsertText("a", 0, FIELD_CHAR * 2, fields=(RefField("nothing"), RefField("s2", "name"))), author="ann")
    assert deck.model.structure.shown()["a"][0] == Shown("", "broken")
    assert deck.model.structure.shown()["a"][1].state == "ok"  # a slide is a thing with a name (or its id)
