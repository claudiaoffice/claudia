"""The methods a text view needs: the paragraphs, editing a range, styles, cursors and zones, suggestions (composes)."""

import pytest

from claudia_composes import TextModel
from claudia_core import Document, MemoryStore
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.protocol import Context, Limits, RequestError, core_methods

ANN = Account("ann", "owner")
BEN = Account("ben", "editor")
VERA = Account("vera", "viewer")
AI = Account.assistant()


@pytest.fixture
def paper():
    return Document(TextModel(), store=MemoryStore())


def call(doc, name, params=None, account=ANN):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0)
    return composes_methods.dispatch(ctx, name, params)


def type_(doc, text, at=0, *, block="b1", account=ANN, end=None, end_block=None):
    params = {
        "block": block,
        "start": at,
        "end_block": end_block or block,
        "end": at if end is None else end,
        "text": text,
    }
    return call(doc, "replace_text", params, account)


def texts(doc):
    return [b["text"] for b in call(doc, "blocks")["blocks"]]


# ----------------------------------------------------------------------------- reading
def test_composes_has_everything_the_core_has_and_more():
    assert core_methods.names() <= composes_methods.names()
    assert {"blocks", "replace_text", "set_style", "look", "hold", "suggestions"} <= composes_methods.names()


def test_a_new_document_has_one_empty_body_paragraph_and_the_styles(paper):
    answer = call(paper, "blocks")
    assert [(b["id"], b["style"], b["text"]) for b in answer["blocks"]] == [("b1", "body", "")]
    assert [s["id"] for s in answer["styles"]][:3] == ["body", "title", "heading-1"]
    assert all({"name", "purpose", "next"} <= set(s) for s in answer["styles"])
    assert answer["revision"] is None


# ----------------------------------------------------------------------------- typing
def test_typing_returns_where_the_cursor_ends_up(paper):
    answer = type_(paper, "Hello")
    assert answer["revision"] == "main:1" and (answer["block"], answer["offset"]) == ("b1", 5)
    assert texts(paper) == ["Hello"]
    assert call(paper, "blocks")["blocks"][0]["runs"] == [[5, "ann", None]]


def test_a_newline_in_the_text_starts_a_new_paragraph(paper):
    type_(paper, "one\ntwo\n\nthree")
    assert texts(paper) == ["one", "two", "", "three"]
    answer = call(paper, "blocks")
    assert [b["id"] for b in answer["blocks"]] == ["b1", "b2", "b3", "b4"]


def test_enter_in_the_middle_splits_and_keeps_the_style_enter_at_the_end_follows_the_style_rule(paper):
    type_(paper, "Title words")
    call(paper, "set_style", {"block": "b1", "style": "title"})
    type_(paper, "\n", at=5)  # in the middle: both halves are a title
    assert [b["style"] for b in call(paper, "blocks")["blocks"]] == ["title", "title"]
    type_(paper, "\n", at=len(" words"), block="b2")  # at the end: what follows a title is body text
    assert [b["style"] for b in call(paper, "blocks")["blocks"]] == ["title", "title", "body"]


def test_replacing_a_range_inside_one_paragraph(paper):
    type_(paper, "the quick fox")
    answer = type_(paper, "slow", at=4, end=9)
    assert texts(paper) == ["the slow fox"] and answer["offset"] == 8


def test_deleting_across_paragraphs_joins_what_is_left(paper):
    type_(paper, "one\ntwo\nthree\nfour")
    answer = type_(paper, "", at=2, end=2, end_block="b4")  # from "on|e" to "fo|ur"
    assert texts(paper) == ["onur"] and (answer["block"], answer["offset"]) == ("b1", 2)


def test_backspace_at_the_start_of_a_paragraph_joins_it_to_the_one_before(paper):
    type_(paper, "one\ntwo")
    type_(paper, "", at=3, end=0, end_block="b2")
    assert texts(paper) == ["onetwo"]


def test_pasting_several_lines_over_a_selection(paper):
    type_(paper, "alpha beta\ngamma")
    type_(paper, "X\nY\nZ", at=6, end=5, end_block="b2")  # replaces "beta\ngamma"
    assert texts(paper) == ["alpha X", "Y", "Z"]


def test_one_edit_is_one_undo_step(paper):
    type_(paper, "one\ntwo\nthree")
    type_(paper, "", at=1, end=2, end_block="b3")
    assert texts(paper) == ["oree"]
    call(paper, "undo")
    assert texts(paper) == ["one", "two", "three"]


def test_nothing_to_do_is_not_an_edit(paper):
    answer = type_(paper, "", at=0)
    assert answer["revision"] is None and paper.revision is None


def test_bad_ranges_are_refused_and_change_nothing(paper):
    type_(paper, "one\ntwo")
    for params in (
        {"block": "b9", "start": 0, "end_block": "b9", "end": 0, "text": "x"},
        {"block": "b1", "start": 9, "end_block": "b1", "end": 9, "text": "x"},
        {"block": "b2", "start": 0, "end_block": "b1", "end": 0, "text": "x"},  # backwards
        {"block": "b1", "start": 2, "end_block": "b1", "end": 1, "text": "x"},
    ):
        with pytest.raises(RequestError) as caught:
            call(paper, "replace_text", params)
        assert caught.value.code in {"command_error", "bad_request"}
    assert texts(paper) == ["one", "two"]


def test_a_viewer_cannot_edit_but_can_read_and_look(paper):
    type_(paper, "abc")
    with pytest.raises(RequestError) as caught:
        type_(paper, "x", account=VERA)
    assert caught.value.code == "forbidden"
    assert call(paper, "blocks", account=VERA)["blocks"][0]["text"] == "abc"
    call(paper, "look", {"block": "b1", "offset": 1}, VERA)


def test_a_stale_view_is_refused(paper):
    type_(paper, "abc")
    call(paper, "save_checkpoint", {"label": "first"})
    type_(paper, "d", at=3)
    paper.restore_checkpoint(1, author="ann")
    params = {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "x", "base": "main:3"}
    with pytest.raises(RequestError) as caught:
        call(paper, "replace_text", params)
    assert caught.value.code == "stale"


# ----------------------------------------------------------------------------- styles
def test_setting_a_style(paper):
    type_(paper, "Intro")
    call(paper, "set_style", {"block": "b1", "style": "heading-1"})
    assert call(paper, "blocks")["blocks"][0]["style"] == "heading-1"
    for bad in ({"block": "b1", "style": "sparkly"}, {"block": "b9", "style": "title"}):
        with pytest.raises(RequestError) as caught:
            call(paper, "set_style", bad)
        assert caught.value.code == "command_error"


# ----------------------------------------------------------------------------- cursors and zones
def test_looking_shows_the_zone_and_the_caret_but_locks_nothing(paper):
    type_(paper, "the quick brown fox jumps")
    call(paper, "look", {"block": "b1", "offset": 12, "words": 1})
    zone, caret = paper.presence.of("ann").regions
    assert (zone.start, zone.end, caret.start, caret.end) == (4, 19, 12, 12)
    type_(paper, "!", at=5, account=BEN)  # nothing is held, so the edit goes through


def test_holding_locks_the_zone_for_the_others_and_says_why(paper):
    type_(paper, "the quick brown fox jumps")
    call(paper, "hold", {"block": "b1", "offset": 12, "words": 1})
    with pytest.raises(RequestError) as caught:
        type_(paper, "!", at=5, account=BEN)
    assert caught.value.code == "locked" and "ann" in caught.value.message
    type_(paper, "!", at=0, account=BEN)  # outside the zone
    type_(paper, "?", at=6, account=ANN)  # the holder's own edits are fine
    assert texts(paper) == ["!the q?uick brown fox jumps"]


def test_two_people_cannot_hold_overlapping_zones(paper):
    type_(paper, "the quick brown fox jumps")
    call(paper, "hold", {"block": "b1", "offset": 12, "words": 1})
    with pytest.raises(RequestError) as caught:
        call(paper, "hold", {"block": "b1", "offset": 14, "words": 1}, BEN)
    assert caught.value.code == "locked"


def test_the_zone_width_is_limited_and_the_place_must_exist(paper):
    type_(paper, "abc")
    for bad in ({"block": "b1", "offset": 1, "words": 99}, {"block": "b1", "offset": 9}, {"block": "b9", "offset": 0}):
        with pytest.raises(RequestError):
            call(paper, "look", bad)


# ----------------------------------------------------------------------------- suggestions
def suggest(doc, start=4, end=9, replacement="fast", account=AI):
    return call(
        doc,
        "suggest",
        {"block": "b1", "start": start, "end": end, "replacement": replacement, "reason": "shorter"},
        account,
    )


def test_only_the_assistant_suggests_and_people_do_not_get_edited_by_it(paper):
    type_(paper, "the quick brown fox")
    for account in (ANN, BEN):
        with pytest.raises(RequestError) as caught:
            suggest(paper, account=account)
        assert caught.value.code == "forbidden"
    for name, params in (
        ("replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "x"}),
        ("set_style", {"block": "b1", "style": "title"}),
    ):
        with pytest.raises(RequestError) as caught:
            call(paper, name, params, AI)
        assert caught.value.code == "forbidden", "the AI has no direct write path into the text (D63)"


def test_a_suggestion_is_listed_and_changes_no_text(paper):
    type_(paper, "the quick brown fox")
    answer = suggest(paper)
    assert answer["suggestion"] == "s1"
    (item,) = call(paper, "suggestions")
    assert (item["author"], item["original"], item["replacement"], item["outdated"]) == ("ai", "quick", "fast", False)
    assert texts(paper) == ["the quick brown fox"]


def test_a_remark_has_no_replacement(paper):
    type_(paper, "the quick brown fox")
    call(paper, "suggest", {"block": "b1", "start": 0, "end": 9, "reason": "long"}, AI)
    assert call(paper, "suggestions")[0]["replacement"] is None


def test_accepting_edits_as_the_accepter(paper):
    type_(paper, "the quick brown fox")
    suggest(paper)
    call(paper, "accept_suggestion", {"id": "s1"}, BEN)
    block = call(paper, "blocks")["blocks"][0]
    assert block["text"] == "the fast brown fox" and [4, "ben", "ai"] in block["runs"]
    assert call(paper, "suggestions") == []


def test_an_outdated_suggestion_cannot_be_accepted(paper):
    type_(paper, "the quick brown fox")
    suggest(paper)
    type_(paper, "X", at=6, account=BEN)
    assert call(paper, "suggestions")[0]["outdated"] is True
    with pytest.raises(RequestError) as caught:
        call(paper, "accept_suggestion", {"id": "s1"})
    assert caught.value.code == "command_error" and "changed" in caught.value.message


def test_rejecting_and_dismissing(paper):
    type_(paper, "the quick brown fox")
    suggest(paper)
    call(paper, "suggest", {"block": "b1", "start": 0, "end": 9, "reason": "long"}, AI)
    call(paper, "reject_suggestion", {"id": "s1"})
    call(paper, "reject_suggestion", {"id": "s2"})
    assert call(paper, "suggestions") == []
    summaries = [e["summary"] for e in call(paper, "log")][-2:]
    assert summaries == ["rejected a suggestion", "dismissed a remark"]


def test_unknown_suggestions_and_ranges_are_refused(paper):
    type_(paper, "abc")
    for name, params, account in (
        ("accept_suggestion", {"id": "s9"}, ANN),
        ("reject_suggestion", {"id": "s9"}, ANN),
        ("suggest", {"block": "b1", "start": 2, "end": 9, "replacement": "x", "reason": "r"}, AI),
        ("suggest", {"block": "b9", "start": 0, "end": 1, "replacement": "x", "reason": "r"}, AI),
    ):
        with pytest.raises(RequestError) as caught:
            call(paper, name, params, account)
        assert caught.value.code == "command_error"
