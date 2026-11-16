"""Search and replace in a text over the wire (E9.28, D284-D289): search_find, search_preview, search_replace."""

import pytest

from claudia_composes import BlockAnchor, InsertText, SetStyle, SplitBlock, TextModel
from claudia_core import Document, MemoryStore, ObjectBody, VisualObject, paragraph_for
from claudia_server.apps import MODEL_METHODS
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.protocol import Context, Limits, RequestError

ANN = Account("ann", "owner")
BEN = Account("ben", "editor")
AI = Account.assistant(MODEL_METHODS["composes"])  # as a server gives it (SEC-10, D640)


@pytest.fixture
def paper():
    d = Document(TextModel(), store=MemoryStore())
    d.execute(SetStyle("b1", "heading-1"), author="ann")
    d.execute(InsertText("b1", 0, "A red start"), author="ann")
    d.execute(SplitBlock("b1", 11, "b2", "body"), author="ann")
    d.execute(InsertText("b2", 0, "The red fox met the red hen."), author="ann")
    d.execute(SplitBlock("b2", 28, "b3", "remark"), author="ann")
    d.execute(InsertText("b3", 0, "check the red facts"), author="ann")
    return d


def call(doc, name, params=None, account=BEN):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0)
    return composes_methods.dispatch(ctx, name, params)


def text(find, replace=None, **options):
    query = {"mode": "text", "text": find, **options}
    if replace is not None:
        query["replace"] = [{"text": replace}]
    return query


def search(doc, query, **more):
    return call(doc, "search_find", {"query": query, **more})


def words(doc):
    return [b["text"] for b in call(doc, "blocks")["blocks"]]


def test_composes_has_the_three_search_methods():
    assert {"search_find", "search_preview", "search_replace"} <= composes_methods.names()


def test_the_methods_are_documented_in_composes_words():
    doc = composes_methods._methods["search_find"].doc
    assert "heading" in doc and "section" in doc and "sheet" not in doc


def test_a_search_names_every_match_by_its_paragraph_and_the_kind_of_text_it_is(paper):
    found = search(paper, text("red"), kinds=["text", "heading", "remark"])
    assert [(m["at"], m["kind"], m["start"]) for m in found["matches"]] == [
        ({"block": "b1"}, "heading", 2),
        ({"block": "b2"}, "text", 4),
        ({"block": "b2"}, "text", 20),
        ({"block": "b3"}, "remark", 10),
    ]
    assert found["counts"] == {"text": 1, "heading": 1, "remark": 1, "object": 0, "description": 0}


def test_by_default_only_the_text_is_searched(paper):
    assert {m["kind"] for m in search(paper, text("red"))["matches"]} == {"text"}


def test_a_section_and_a_selection_narrow_the_search(paper):
    found = search(paper, text("red"), kinds=["text", "heading", "remark"], scope={"section": "b2"})
    assert [m["at"]["block"] for m in found["matches"]] == [
        "b1",
        "b2",
        "b2",
        "b3",
    ]  # the heading is part of its section
    selection = {"range": {"from": {"block": "b2", "offset": 10}, "to": {"block": "b2", "offset": 28}}}
    found = search(paper, text("red"), scope=selection)
    assert [(m["at"], m["start"]) for m in found["matches"]] == [({"block": "b2", "offset": 10}, 10)]


def test_a_scope_that_makes_no_sense_is_a_bad_request(paper):
    for scope in ({"section": "b9"}, {"page": 2}, {"range": {"from": 1}}):
        with pytest.raises(RequestError) as caught:
            search(paper, text("red"), scope=scope)
        assert caught.value.code == "bad_request"


def test_unknown_kinds_are_a_bad_request(paper):
    with pytest.raises(RequestError) as caught:
        search(paper, text("red"), kinds=["notes"])
    assert caught.value.code == "bad_request" and "heading" in caught.value.message


def test_the_words_and_the_description_of_an_object_are_found(paper):
    body = ObjectBody(
        "o1", "text", 200, 80, "plain-box", paragraph_for("o1", "body", "a red note"), description="red box"
    )
    paper.model.insert_object(VisualObject(body, BlockAnchor("b2", 0)))
    found = search(paper, text("red"), kinds=["object", "description"])
    assert [(m["at"], m["kind"]) for m in found["matches"]] == [
        ({"block": "b2", "object": "o1", "source": "box"}, "object"),
        ({"block": "b2", "object": "o1", "source": "description"}, "description"),
    ]


def test_a_preview_shows_the_effect_and_changes_nothing(paper):
    before = words(paper)
    shown = call(paper, "search_preview", {"query": text("red", "blue"), "kinds": ["text", "heading"]})
    assert [(c["at"], c["after"]) for c in shown["changes"]] == [
        ({"block": "b1"}, "A blue start"),
        ({"block": "b2"}, "The blue fox met the blue hen."),
    ]
    assert shown["total"] == 2 and shown["skipped"] == []
    assert words(paper) == before


def test_a_replacement_is_one_step_that_undo_takes_back(paper):
    answer = call(paper, "search_replace", {"query": text("red", "blue"), "kinds": ["text", "heading", "remark"]})
    assert answer["replaced"] == 3 and answer["skipped"] == []
    assert words(paper) == ["A blue start", "The blue fox met the blue hen.", "check the blue facts"]
    call(paper, "undo", None, BEN)
    assert words(paper) == ["A red start", "The red fox met the red hen.", "check the red facts"]


def test_those_who_wrote_the_rest_stay_its_authors(paper):
    call(paper, "search_replace", {"query": text("fox", "cat")})
    runs = paper.model.block("b2").runs
    assert [(r.length, r.author) for r in runs] == [(8, "ann"), (3, "ben"), (17, "ann")]


def test_matches_a_person_left_alone_stay_and_a_changed_text_is_skipped(paper):
    leave = [{"at": {"block": "b2"}, "match": 0, "said": "red"}]
    call(paper, "search_replace", {"query": text("red", "blue"), "leave": leave})
    assert words(paper)[1] == "The red fox met the blue hen."
    stale = [{"at": {"block": "b3"}, "match": 0, "said": "fox"}]
    answer = call(paper, "search_replace", {"query": text("red", "x"), "kinds": ["remark"], "leave": stale})
    assert answer["replaced"] == 0 and [(s["at"], s["reason"]) for s in answer["skipped"]] == [
        ({"block": "b3"}, "changed")
    ]


def test_a_stretch_somebody_holds_is_skipped_and_named(paper):
    call(paper, "hold", {"block": "b2", "offset": 22, "words": 1}, ANN)
    answer = call(paper, "search_replace", {"query": text("red", "blue"), "kinds": ["text", "heading"]})
    assert answer["replaced"] == 1
    assert [(s["at"], s["reason"], s["by"]) for s in answer["skipped"]] == [({"block": "b2"}, "locked", "ann")]
    assert words(paper)[:2] == ["A blue start", "The red fox met the red hen."]


def test_the_assistant_may_look_but_not_replace(paper):
    ctx = Context(paper, AI, Limits(), users=lambda: ["ann"])
    assert composes_methods.dispatch(ctx, "search_find", {"query": text("red")})["total"] == 2
    with pytest.raises(RequestError) as caught:
        composes_methods.dispatch(ctx, "search_replace", {"query": text("red", "blue")})
    assert caught.value.code == "forbidden"


def test_a_viewer_cannot_replace(paper):
    with pytest.raises(RequestError) as caught:
        call(paper, "search_replace", {"query": text("red", "blue")}, Account("vera", "viewer"))
    assert caught.value.code in {"forbidden", "read_only"}


def test_a_replacement_that_would_change_too_much_is_refused(paper, monkeypatch):
    monkeypatch.setattr("claudia_server.composes_search.MAX_REPLACED_TEXTS", 1)
    with pytest.raises(RequestError) as caught:
        call(paper, "search_replace", {"query": text("red", "blue"), "kinds": ["text", "heading"]})
    assert caught.value.code == "bad_request" and words(paper)[0] == "A red start"


def test_a_search_that_runs_out_of_time_says_so_and_a_replacement_refuses(paper, monkeypatch):
    monkeypatch.setattr("claudia_server.search_methods.SEARCH_SECONDS", 0.0)
    assert search(paper, text("red"))["timed_out"]
    with pytest.raises(RequestError) as caught:
        call(paper, "search_replace", {"query": text("red", "blue")})
    assert caught.value.code == "command_error"


def test_a_mistake_in_a_pattern_comes_back_as_a_result(paper):
    found = search(paper, {"mode": "pattern", "find": "a(bc"})
    assert found["error"]["field"] == "find" and found["matches"] == []


def test_a_place_that_is_not_one_is_a_bad_request(paper):
    for bad in ({"at": {"sheet": "s1"}, "match": 0}, {"at": {"block": 4}, "match": 0}, {"at": {"block": "b1"}}):
        with pytest.raises(RequestError) as caught:
            call(paper, "search_preview", {"query": text("red", "x"), "leave": [bad]})
        assert caught.value.code == "bad_request"
