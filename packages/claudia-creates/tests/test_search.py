"""Search and replace in a presentation (E10.19, D284-D289): which texts the slides offer, where they are, what a
replacement changes, and what it must leave alone. The engine is claudia-search's; this is creates' part of it."""

import pytest
from conftest import SLIDE, put, shape_object, text_box

from claudia_core import DescribeObject, ObjectSet
from claudia_creates import AddSlide, SetSlideNotes
from claudia_creates.search import (
    EXTRA_PARTS,
    KINDS,
    notes_at,
    object_at,
    plan_replacement,
    replace_command,
    scan_slides,
    slide_texts,
)
from claudia_search import Query


def search(text, replace=None, **options):
    data = {"mode": "text", "text": text, **options}
    if replace is not None:
        data["replace"] = [{"text": replace}]
    return Query.from_data(data).compile(EXTRA_PARTS)


@pytest.fixture
def deck(doc):
    """Two slides: s1 with a text box, a shape with a label and notes; s2 with a box and a described shape."""
    doc.execute(AddSlide("s2"), author="ana")
    put(doc, text_box("t1", text="A red plan"))
    put(doc, shape_object("r1", text="red label"))
    doc.execute(SetSlideNotes("s1", "Say **red** twice."), author="ana")
    put(doc, text_box("t2", slide="s2", text="more red"))
    put(doc, shape_object("r2", slide="s2", text=""))
    doc.execute(DescribeObject("r2", "a red server"), author="ana")
    return doc


def no_conflicts(regions):
    return []


def replaced(doc, query, author="ben", **options):
    made = plan_replacement(doc.model, query, kinds=options.pop("kinds", KINDS), conflicts=no_conflicts, **options)
    command = replace_command(doc.model, made, author)
    if command is not None:
        doc.execute(command, author=author)
    return made


# ---------------------------------------------------------------------------------------------- what is offered
def test_a_slide_offers_its_boxes_its_labels_its_notes_and_its_descriptions_in_that_order(deck):
    items = [(t.at, t.kind, t.text) for t in slide_texts(deck.model, KINDS)]
    assert items == [
        (object_at("s1", "t1", "box"), "text", "A red plan"),
        (object_at("s1", "r1", "label"), "label", "red label"),
        (notes_at("s1"), "notes", "Say **red** twice."),
        (object_at("s2", "t2", "box"), "text", "more red"),
        (object_at("s2", "r2", "description"), "description", "a red server"),
    ]


def test_only_the_kinds_asked_for_are_offered(deck):
    assert [t.kind for t in slide_texts(deck.model, ["notes", "label"])] == ["label", "notes"]


def test_a_kind_that_does_not_exist_is_refused(deck):
    with pytest.raises(ValueError, match="cannot look in 'words'"):
        list(slide_texts(deck.model, ["words"]))


def test_this_slide_is_a_scope_and_an_unknown_slide_is_refused(deck):
    assert {t.at["slide"] for t in slide_texts(deck.model, KINDS, {"slide": "s2"})} == {"s2"}
    with pytest.raises(ValueError, match="no such slide"):
        scan_slides(deck.model, search("red"), kinds=KINDS, scope={"slide": "s9"})
    with pytest.raises(ValueError, match="a scope is"):
        scan_slides(deck.model, search("red"), kinds=KINDS, scope={"page": 1})


def test_counts_say_how_many_texts_of_each_kind_hold_a_match(deck):
    found = scan_slides(deck.model, search("red"), kinds=KINDS)
    assert found.counts == {"text": 2, "label": 1, "notes": 1, "description": 1}
    assert found.total == 5


def test_a_word_is_a_part_of_the_builder(deck):
    query = Query.from_data({"mode": "builder", "parts": [{"what": "word"}]}).compile(EXTRA_PARTS)
    found = scan_slides(deck.model, query, kinds=["text"], scope={"slide": "s2"})
    assert [(m.start, m.end) for m in found.matches] == [(0, 4), (5, 8)]


# ------------------------------------------------------------------------------------------------- replacing
def test_a_replacement_is_one_step_that_undo_takes_back_whole(deck):
    made = replaced(deck, search("red", "blue"))
    assert len(made.changes) == 5
    model = deck.model
    assert model.get("t1").body.paragraph.text == "A blue plan"
    assert model.get("r1").body.paragraph.text == "blue label"
    assert model.notes_of("s1") == "Say **blue** twice."
    assert model.get("t2").body.paragraph.text == "more blue"
    assert model.get("r2").body.description == "a blue server"
    deck.undo("ben")
    assert model.get("t1").body.paragraph.text == "A red plan"
    assert model.notes_of("s1") == "Say **red** twice."
    assert model.get("r2").body.description == "a red server"


def test_the_replacement_is_named_by_its_size(deck):
    made = plan_replacement(deck.model, search("red", "x"), kinds=KINDS, conflicts=no_conflicts)
    assert replace_command(deck.model, made, "ben").label == "Replace in 5 texts"


def test_only_this_slide_is_replaced_when_asked(deck):
    replaced(deck, search("red", "blue"), scope={"slide": "s2"})
    assert deck.model.get("t1").body.paragraph.text == "A red plan"
    assert deck.model.get("t2").body.paragraph.text == "more blue"


def test_only_the_kinds_chosen_are_replaced(deck):
    replaced(deck, search("red", "blue"), kinds=["notes"])
    assert deck.model.notes_of("s1") == "Say **blue** twice."
    assert deck.model.get("t1").body.paragraph.text == "A red plan"


def test_the_words_around_a_replacement_keep_their_author_and_the_new_words_are_the_replacers(deck):
    replaced(deck, search("red", "grey"), kinds=["text"], scope={"slide": "s1"}, author="ben")
    words = deck.model.get("t1").body.paragraph
    assert words.text == "A grey plan"
    assert [(r.length, r.author) for r in words.runs] == [(2, "ana"), (4, "ben"), (5, "ana")]


def test_a_pattern_with_kept_parts_is_stored_as_text_not_as_a_pattern(deck):
    query = Query.from_data({"mode": "pattern", "find": "(r)ed", "replace": r"\1ose"}).compile()
    replaced(deck, query, kinds=["notes"])
    assert deck.model.notes_of("s1") == "Say **rose** twice."


def test_nothing_to_change_makes_no_command(deck):
    made = plan_replacement(deck.model, search("purple", "x"), kinds=KINDS, conflicts=no_conflicts)
    assert made.changes == [] and replace_command(deck.model, made, "ben") is None


def test_matches_a_person_left_alone_stay(deck):
    made = replaced(deck, search("red", "blue"), kinds=["notes"], leave=[(notes_at("s1"), 0)])
    assert deck.model.notes_of("s1") == "Say **red** twice."
    assert made.changes == []


def test_a_text_typed_into_since_the_person_looked_is_skipped(deck):
    made = replaced(deck, search("red|plan", "x"), kinds=["text"], leave=[(object_at("s1", "t1", "box"), 1, "red")])
    assert deck.model.get("t1").body.paragraph.text == "A red plan"
    assert [(s.at, s.reason) for s in made.skipped] == [(object_at("s1", "t1", "box"), "changed")]


# -------------------------------------------------------------------------------------------------- the locks
def test_an_object_somebody_holds_is_skipped_and_named(deck):
    held = ObjectSet(SLIDE, frozenset({"t1"}))
    deck.lock("ana", [held], ttl=5)
    made = plan_replacement(
        deck.model,
        search("red", "blue"),
        kinds=["text"],
        conflicts=lambda regions: deck.presence.conflicts("ben", regions),
    )
    assert [(s.at, s.reason, s.by) for s in made.skipped] == [(object_at("s1", "t1", "box"), "locked", "ana")]
    assert [c.at["object"] for c in made.changes] == ["t2"]


def test_the_notes_of_a_slide_are_not_locked_by_a_selection(deck):
    deck.lock("ana", [ObjectSet(SLIDE, frozenset({"t1", "r1"}))], ttl=5)
    made = plan_replacement(
        deck.model,
        search("red", "blue"),
        kinds=["notes"],
        conflicts=lambda regions: deck.presence.conflicts("ben", regions),
    )
    assert made.skipped == [] and len(made.changes) == 1


def test_a_result_that_is_too_long_is_skipped(deck):
    made = plan_replacement(deck.model, search("red", "x" * 30), kinds=["text"], conflicts=no_conflicts, max_length=15)
    assert {s.reason for s in made.skipped} == {"too_long"}


def test_notes_that_would_outgrow_their_limit_are_skipped(deck, monkeypatch):
    monkeypatch.setattr("claudia_creates.search.MAX_NOTES_LENGTH", 20)
    made = plan_replacement(deck.model, search("red", "x" * 30), kinds=["notes"], conflicts=no_conflicts)
    assert [s.reason for s in made.skipped] == ["too_long"] and made.changes == []
