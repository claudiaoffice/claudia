"""The methods a text view needs: the paragraphs, editing a range, styles, cursors and zones, suggestions (composes)."""

import base64

import pytest

from claudia_composes import TextModel
from claudia_core import Document, MemoryStore
from claudia_opc_io import read_parts
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
    assert all({"name", "purpose", "css", "computed", "based_on", "to_name"} <= set(s) for s in answer["styles"])
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


# ----------------------------------------------------------------------------- styles (E9.7, E9.8)
def style(doc, style_id):
    return next(s for s in call(doc, "styles") if s["id"] == style_id)


def test_the_styles_come_with_their_css_and_the_blocks_answer_lists_the_same(paper):
    listed = call(paper, "styles")
    assert [s["id"] for s in listed][:3] == ["body", "title", "heading-1"]
    heading = style(paper, "heading-1")
    assert heading["based_on"] == "body" and heading["css"]["font-size"] == "19pt"
    assert heading["computed"]["color"] == style(paper, "body")["css"]["color"]  # inherited from Body text
    assert heading["to_name"] is False and heading["purpose"]
    assert call(paper, "blocks")["styles"] == listed


def test_changing_a_style_by_properties(paper):
    answer = call(paper, "change_style", {"style": "heading-1", "set": {"color": "#5B4BC4"}, "unset": ["font-weight"]})
    assert answer["revision"] == "main:1"
    heading = style(paper, "heading-1")
    assert heading["css"]["color"] == "#5B4BC4" and "font-weight" not in heading["css"]
    assert style(paper, "heading-2")["computed"]["color"] == style(paper, "body")["computed"]["color"]


def test_changing_a_style_by_its_css_text_replaces_its_own_declarations(paper):
    call(paper, "change_style", {"style": "quote", "text": "font-size: 15pt;\ncolor: #333333;"})
    assert style(paper, "quote")["css"] == {"font-size": "15pt", "color": "#333333"}
    log = [e["summary"] for e in call(paper, "log")]
    assert log[-1].startswith("changed the style quote")


def test_changing_a_style_to_what_it_is_already_is_not_an_edit(paper):
    same = style(paper, "quote")["css"]
    answer = call(paper, "change_style", {"style": "quote", "set": dict(list(same.items())[:2])})
    assert answer["revision"] is None and paper.revision is None


def test_bad_css_is_refused_and_changes_nothing(paper):
    for params in (
        {"style": "quote", "set": {"color": "url(http://example.com/x)"}},
        {"style": "quote", "set": {"position": "absolute"}},
        {"style": "quote", "text": "color: red;\nfont-size: huge"},
        {"style": "quote", "set": {"color": "red"}, "text": "color: blue"},  # one way or the other, not both
        {"style": "nope", "set": {"color": "red"}},
    ):
        with pytest.raises(RequestError) as caught:
            call(paper, "change_style", params)
        assert caught.value.code in {"command_error", "bad_request"}
    assert paper.revision is None


def test_checking_css_names_the_lines_and_changes_nothing_so_viewers_may_do_it(paper):
    answer = call(paper, "check_css", {"text": "color: red;\nfont-size: huge;\nposition: absolute"}, VERA)
    assert answer["css"] == {"color": "red"}
    assert [(p["line"], p["property"]) for p in answer["problems"]] == [(2, "font-size"), (3, "position")]
    good = call(paper, "check_css", {"text": "FONT-WEIGHT: BOLD;color:#fff"})
    assert good["problems"] == [] and good["text"] == "font-weight: bold;\ncolor: #fff;"
    assert paper.revision is None


def test_deviating_makes_a_style_with_a_provisional_name_and_applies_it_in_one_step(paper):
    type_(paper, "Intro")
    answer = call(paper, "deviate_style", {"parent": "heading-1", "blocks": ["b1"], "set": {"color": "#D6477A"}})
    assert answer["style"] == "heading-1-changed" and answer["name"] == "Heading 1 (changed)"
    made = style(paper, answer["style"])
    assert (made["based_on"], made["to_name"], made["css"]) == ("heading-1", True, {"color": "#D6477A"})
    assert call(paper, "blocks")["blocks"][0]["style"] == answer["style"]
    call(paper, "undo")
    assert call(paper, "blocks")["blocks"][0]["style"] == "body"
    assert all(s["id"] != answer["style"] for s in call(paper, "styles"))


def test_a_second_deviation_from_the_same_style_gets_the_next_free_name(paper):
    first = call(paper, "deviate_style", {"parent": "quote", "blocks": [], "set": {"font-size": "16pt"}})
    second = call(paper, "deviate_style", {"parent": "quote", "blocks": [], "set": {"font-size": "17pt"}})
    third = call(paper, "deviate_style", {"parent": first["style"], "blocks": [], "text": "color: red"})
    assert [first["name"], second["name"], third["name"]] == [
        "Quote (changed)",
        "Quote (changed 2)",
        "Quote (changed 3)",
    ]
    assert first["style"] != second["style"] != third["style"]


def test_a_deviation_must_differ_from_its_parent(paper):
    parent = style(paper, "quote")["computed"]
    for params in (
        {"parent": "quote", "blocks": [], "set": {}},
        {"parent": "quote", "blocks": [], "set": {"font-size": parent["font-size"]}},
        {"parent": "nope", "blocks": [], "set": {"color": "red"}},
        {"parent": "quote", "blocks": ["b9"], "set": {"color": "red"}},
    ):
        with pytest.raises(RequestError) as caught:
            call(paper, "deviate_style", params)
        assert caught.value.code == "command_error"
    assert paper.revision is None


def test_naming_a_style_ends_the_invitation(paper):
    made = call(paper, "deviate_style", {"parent": "quote", "blocks": [], "set": {"font-size": "16pt"}})
    call(paper, "rename_style", {"style": made["style"], "name": "Epigraph"})
    assert (style(paper, made["style"])["name"], style(paper, made["style"])["to_name"]) == ("Epigraph", False)
    with pytest.raises(RequestError) as caught:
        call(paper, "rename_style", {"style": "quote", "name": "epigraph"})
    assert caught.value.code == "command_error" and "already a style named" in caught.value.message


def test_viewers_and_the_assistant_do_not_change_styles(paper):
    calls = (
        ("change_style", {"style": "quote", "set": {"color": "red"}}),
        ("deviate_style", {"parent": "quote", "blocks": [], "set": {"color": "red"}}),
        ("rename_style", {"style": "quote", "name": "Cite"}),
    )
    for name, params in calls:
        with pytest.raises(RequestError) as caught:
            call(paper, name, params, VERA)
        assert caught.value.code == "forbidden"
        with pytest.raises(RequestError) as caught:
            call(paper, name, params, AI)
        assert caught.value.code == "forbidden"
    assert paper.revision is None


def test_enter_at_the_end_of_a_deviated_heading_starts_body_text(paper):
    type_(paper, "Intro")
    made = call(paper, "deviate_style", {"parent": "heading-1", "blocks": ["b1"], "set": {"color": "#D6477A"}})
    type_(paper, "\n", at=5)
    assert [b["style"] for b in call(paper, "blocks")["blocks"]] == [made["style"], "body"]


# ----------------------------------------------------------------------------- export to Word (D212)
def test_export_office_returns_docx_bytes_that_round_trip(paper):
    from claudia_composes_io import docx_to_text

    type_(paper, "Hello there")
    answer = call(paper, "export_office", {"format": "docx"})
    assert answer["format"] == "docx"
    assert answer["content_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    raw = base64.b64decode(answer["data"])
    assert raw[:2] == b"PK"  # a docx is a zip
    assert [b.text for b in docx_to_text(raw).blocks] == ["Hello there"]


def test_export_office_drops_open_suggestions_rather_than_tracking_them(paper):
    from claudia_composes_io import docx_to_text

    type_(paper, "Hello there")
    call(paper, "suggest", {"block": "b1", "start": 0, "end": 5, "reason": "greeting", "replacement": "Hi"}, AI)
    raw = base64.b64decode(call(paper, "export_office", {"format": "docx"})["data"])
    assert [b.text for b in docx_to_text(raw).blocks] == ["Hello there"]


def test_export_office_returns_an_odt_that_round_trips_and_says_what_it_lost(paper):
    from claudia_composes_io import odt_to_text

    from claudia_odf_io import problems

    type_(paper, "Hello there")
    answer = call(paper, "export_office", {"format": "odt"})
    assert answer["format"] == "odt"
    assert answer["content_type"] == "application/vnd.oasis.opendocument.text"
    raw = base64.b64decode(answer["data"])
    assert problems(raw) == []
    assert [b.text for b in odt_to_text(raw).blocks] == ["Hello there"]
    # who typed which words is not something an odt keeps: the one thing this text loses
    assert answer["losses"] == [{"kind": "authorship", "detail": "", "count": 1}]


def test_export_office_to_odt_names_a_style_it_cannot_write(paper):
    type_(paper, "Hello there")
    call(paper, "set_style", {"block": "b1", "style": "remark"})
    losses = call(paper, "export_office", {"format": "odt"})["losses"]
    assert {"kind": "style", "detail": "remark", "count": 1} in losses


def test_export_office_to_docx_has_no_loss_list(paper):
    type_(paper, "Hello there")
    assert "losses" not in call(paper, "export_office", {"format": "docx"})


def test_export_office_to_odt_drops_open_suggestions_rather_than_tracking_them(paper):
    from claudia_composes_io import odt_to_text

    type_(paper, "Hello there")
    call(paper, "suggest", {"block": "b1", "start": 0, "end": 5, "reason": "greeting", "replacement": "Hi"}, AI)
    raw = base64.b64decode(call(paper, "export_office", {"format": "odt"})["data"])
    assert [b.text for b in odt_to_text(raw).blocks] == ["Hello there"]
    assert b"tracked-changes" not in read_parts(raw)["content.xml"]


def test_export_office_rejects_an_unknown_format(paper):
    with pytest.raises(RequestError):
        call(paper, "export_office", {"format": "pdf"})


# ---------------------------------------------------------------- tracked changes and dates in an export (D411)
@pytest.fixture
def dated_paper():
    """A text with known times: typed 2026-01-02, a suggestion 2026-03-04, typed again 2026-11-11."""
    times = iter(["2026-01-02T03:04:05Z", "2026-03-04T05:06:07Z", "2026-11-11T17:13:05Z"])
    doc = Document(TextModel(), store=MemoryStore(), clock=lambda: next(times))
    type_(doc, "Hello there")
    call(doc, "suggest", {"block": "b1", "start": 0, "end": 5, "reason": "greeting", "replacement": "Hi"}, AI)
    type_(doc, "!", at=11)
    return doc


def exported(doc, fmt, **params):
    return base64.b64decode(call(doc, "export_office", {"format": fmt, **params})["data"])


def test_tracked_changes_are_written_when_asked_for_and_dated_when_the_suggestion_was_made(dated_paper):
    from lxml import etree

    from claudia_odf_io import NS

    raw = exported(dated_paper, "odt", tracked_changes=True)
    root = etree.fromstring(read_parts(raw)["content.xml"])
    dates = {d.text for d in root.iterfind(".//office:change-info/dc:date", NS)}
    assert dates == {"2026-03-04T05:06:07Z"}
    authors = {a.text for a in root.iterfind(".//office:change-info/dc:creator", NS)}
    assert authors == {AI.user}


def test_an_odt_says_when_it_was_made_and_last_changed_and_by_whom(dated_paper):
    from claudia_odf_io import read_info

    info = read_info(read_parts(exported(dated_paper, "odt"))["meta.xml"])
    assert (info.created, info.creator) == ("2026-01-02T03:04:05Z", ANN.user)
    assert (info.modified, info.modifier) == ("2026-11-11T17:13:05Z", ANN.user)


def test_tracked_changes_in_an_odt_leave_no_suggestion_loss(dated_paper):
    losses = call(dated_paper, "export_office", {"format": "odt", "tracked_changes": True})["losses"]
    assert not [loss for loss in losses if loss["kind"] == "suggestion"]


def test_without_tracked_changes_the_open_suggestion_is_a_loss(dated_paper):
    losses = call(dated_paper, "export_office", {"format": "odt"})["losses"]
    assert {"kind": "suggestion", "detail": "", "count": 1} in losses


def test_a_docx_with_tracked_changes_dates_them_too(dated_paper):
    import re

    raw = exported(dated_paper, "docx", tracked_changes=True)
    xml = read_parts(raw)["word/document.xml"].decode()
    assert set(re.findall(r'w:date="([^"]*)"', xml)) == {"2026-03-04T05:06:07Z"}
    assert "<w:ins " in xml


def test_tracked_changes_default_to_off(dated_paper):
    assert b"tracked-changes" not in read_parts(exported(dated_paper, "odt"))["content.xml"]
    assert "<w:ins " not in read_parts(exported(dated_paper, "docx"))["word/document.xml"].decode()
