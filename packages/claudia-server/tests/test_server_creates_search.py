"""Search and replace in a presentation over the wire (E10.19, D284-D289): the three search methods."""

import pytest

from claudia_core import Document, MemoryStore
from claudia_creates import SlideModel
from claudia_server.auth import Account
from claudia_server.creates import creates_methods
from claudia_server.protocol import Context, Limits, RequestError

ANN = Account("ann", "owner")
BEN = Account("ben", "editor")


def call(doc, name, params=None, account=BEN):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0)
    return creates_methods.dispatch(ctx, name, params)


@pytest.fixture
def deck():
    d = Document(SlideModel.empty(), store=MemoryStore())
    second = call(d, "add_slide", None, ANN)["slide"]
    frame = {"x": 100, "y": 100, "w": 400, "h": 120}
    box = call(d, "add_object", {"slide": "s1", "kind": "text", "text": "A red plan", **frame}, ANN)["object"]
    shape = call(
        d, "add_object", {"slide": second, "kind": "shape", "shape": "rectangle", "text": "red label", **frame}, ANN
    )["object"]
    call(d, "set_slide_notes", {"slide": "s1", "notes": "Say **red** twice."}, ANN)
    d.ids = {"box": box, "shape": shape, "s2": second}  # type: ignore[attr-defined]
    return d


def text(find, replace=None, **options):
    query = {"mode": "text", "text": find, **options}
    if replace is not None:
        query["replace"] = [{"text": replace}]
    return query


def search(doc, query, **more):
    return call(doc, "search_find", {"query": query, **more})


def words(doc, object_id):
    return doc.model.get(object_id).body.paragraph.text


def test_creates_has_the_three_search_methods():
    assert {"search_find", "search_preview", "search_replace"} <= creates_methods.names()


def test_the_methods_are_documented_in_creates_words():
    doc = creates_methods.describe()["methods"]["search_find"]["doc"]
    assert "slide" in doc and "notes" in doc and "section" not in doc


def test_a_search_names_every_match_by_slide_object_and_source(deck):
    found = search(deck, text("red"), kinds=["text", "label", "notes"])
    box, shape = deck.ids["box"], deck.ids["shape"]
    assert [(m["at"], m["kind"]) for m in found["matches"]] == [
        ({"slide": "s1", "object": box, "source": "box"}, "text"),
        ({"slide": "s1", "source": "notes"}, "notes"),
        ({"slide": deck.ids["s2"], "object": shape, "source": "label"}, "label"),
    ]
    assert found["counts"] == {"text": 1, "label": 1, "notes": 1, "description": 0}


def test_this_slide_narrows_the_search_and_a_slide_that_is_not_there_is_refused(deck):
    found = search(deck, text("red"), kinds=["text", "label", "notes"], scope={"slide": deck.ids["s2"]})
    assert [m["at"]["slide"] for m in found["matches"]] == [deck.ids["s2"]]
    for scope in ({"slide": "s9"}, {"page": 1}):
        with pytest.raises(RequestError) as caught:
            search(deck, text("red"), scope=scope)
        assert caught.value.code == "bad_request"


def test_unknown_kinds_are_a_bad_request(deck):
    with pytest.raises(RequestError) as caught:
        search(deck, text("red"), kinds=["heading"])
    assert caught.value.code == "bad_request" and "notes" in caught.value.message


def test_a_preview_shows_the_effect_and_changes_nothing(deck):
    shown = call(deck, "search_preview", {"query": text("red", "blue"), "kinds": ["text", "notes"]})
    assert [c["after"] for c in shown["changes"]] == ["A blue plan", "Say **blue** twice."]
    assert shown["total"] == 2 and words(deck, deck.ids["box"]) == "A red plan"


def test_a_replacement_is_one_step_that_undo_takes_back(deck):
    answer = call(deck, "search_replace", {"query": text("red", "blue"), "kinds": ["text", "label", "notes"]})
    assert answer["replaced"] == 3 and answer["skipped"] == []
    assert words(deck, deck.ids["box"]) == "A blue plan" and words(deck, deck.ids["shape"]) == "blue label"
    assert deck.model.notes_of("s1") == "Say **blue** twice."
    call(deck, "undo")
    assert words(deck, deck.ids["box"]) == "A red plan" and deck.model.notes_of("s1") == "Say **red** twice."


def test_the_words_around_a_replacement_keep_their_author(deck):
    call(deck, "search_replace", {"query": text("red", "grey")})
    runs = deck.model.get(deck.ids["box"]).body.paragraph.runs
    assert [(r.length, r.author) for r in runs] == [(2, "ann"), (4, "ben"), (5, "ann")]


def test_an_object_somebody_selected_is_skipped_and_named(deck):
    box = deck.ids["box"]
    call(deck, "lock", {"regions": [{"kind": "objects", "holder": "s1", "ids": [box]}]}, ANN)
    answer = call(deck, "search_replace", {"query": text("red", "blue"), "kinds": ["text", "label"]})
    assert answer["replaced"] == 1
    assert [(s["at"]["object"], s["reason"], s["by"]) for s in answer["skipped"]] == [(box, "locked", "ann")]
    assert words(deck, box) == "A red plan" and words(deck, deck.ids["shape"]) == "blue label"


def test_a_text_typed_into_since_the_person_looked_is_skipped(deck):
    box = deck.ids["box"]
    stale = [{"at": {"slide": "s1", "object": box, "source": "box"}, "match": 0, "said": "fox"}]
    answer = call(deck, "search_replace", {"query": text("red", "x"), "leave": stale})
    assert answer["replaced"] == 0 and [s["reason"] for s in answer["skipped"]] == ["changed"]


def test_a_replacement_that_would_change_too_much_is_refused(deck, monkeypatch):
    monkeypatch.setattr("claudia_server.creates_search.MAX_REPLACED_TEXTS", 1)
    with pytest.raises(RequestError) as caught:
        call(deck, "search_replace", {"query": text("red", "blue"), "kinds": ["text", "notes"]})
    assert caught.value.code == "bad_request" and words(deck, deck.ids["box"]) == "A red plan"


def test_a_search_that_runs_out_of_time_says_so_and_a_replacement_refuses(deck, monkeypatch):
    monkeypatch.setattr("claudia_server.search_methods.SEARCH_SECONDS", 0.0)
    assert search(deck, text("red"))["timed_out"]
    with pytest.raises(RequestError) as caught:
        call(deck, "search_replace", {"query": text("red", "blue")})
    assert caught.value.code == "command_error"


def test_a_place_that_is_not_one_is_a_bad_request(deck):
    for bad in ({"at": {"sheet": "s1"}, "match": 0}, {"at": {"slide": "s1", "source": "box"}, "match": 0}):
        with pytest.raises(RequestError) as caught:
            call(deck, "search_preview", {"query": text("red", "x"), "leave": [bad]})
        assert caught.value.code == "bad_request"
