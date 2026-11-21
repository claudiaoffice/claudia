"""The what-if desk (D1308): a person tries something on a private copy through the app's own methods, looks at it
through the views the app already has, and carries it out as one step -- or is told that it is outdated."""

import pytest
from test_server_composes import AI, ANN, BEN, call

from claudia_composes import TextModel
from claudia_core import Document, MemoryStore
from claudia_server import what_if
from claudia_server.composes import composes_methods
from claudia_server.protocol import Context, Limits, RequestError


@pytest.fixture
def paper():
    doc = Document(TextModel(), store=MemoryStore())
    call(doc, "replace_text", {"paragraph": "b1", "start": 0, "end_paragraph": "b1", "end": 0, "text": "Hello world"})
    return doc


def start(doc, account=ANN, params=None):
    return call(doc, "what_if_start", params or {}, account)["token"]


def replace(doc, token, text, account=ANN, *, at=0, end=5):
    params = {"paragraph": "b1", "start": at, "end_paragraph": "b1", "end": end, "text": text}
    return call(doc, "what_if_apply", {"token": token, "method": "replace_text", "params": params}, account)


def paragraphs_in(doc, token, account=ANN):
    return call(doc, "as_what_if", {"token": token, "method": "paragraphs"}, account)["paragraphs"]


def text_of(doc):
    return doc.model.paragraph("b1").text


def test_what_if_writes_through_the_apps_own_methods_and_the_live_document_does_not_change(paper):
    token = start(paper)
    replace(paper, token, "Howdy")
    assert text_of(paper) == "Hello world"
    assert [b["text"] for b in paragraphs_in(paper, token)] == ["Howdy world"]


def test_the_views_the_app_has_read_the_what_if_with_the_same_requests(paper):
    token = start(paper)
    live = call(paper, "as_what_if", {"token": token, "method": "paragraphs"})
    assert live == call(paper, "paragraphs")


def test_only_the_reads_of_a_view_can_be_asked_of_a_what_if(paper):
    token = start(paper)
    with pytest.raises(RequestError) as refused:
        call(paper, "as_what_if", {"token": token, "method": "undo"})
    assert refused.value.code == "forbidden"


def test_what_would_change_is_named_in_places_and_counted(paper):
    token = start(paper)
    replace(paper, token, "Howdy")
    answer = call(paper, "what_if_changes", {"token": token})
    assert answer["count"] == 1 and answer["regions"][0]["kind"] == "text"


def test_commit_carries_it_out_as_one_step_by_the_person_and_it_is_undone_in_one(paper):
    token = start(paper)
    replace(paper, token, "Howdy")
    replace(paper, token, "Hi", at=0, end=5)
    answer = call(paper, "what_if_commit", {"token": token})
    assert answer["applied"] is True
    assert text_of(paper) == "Hi world"
    entry = paper.log.path(paper.revision)[-1]
    assert (entry.author, entry.via) == ("ann", None)
    call(paper, "undo")
    assert text_of(paper) == "Hello world"


def test_a_proposal_that_is_accepted_for_the_assistant_is_tagged(paper):
    token = start(paper, AI)
    replace(paper, token, "Howdy", AI)
    answer = call(paper, "what_if_commit", {"token": token, "via": "ai"}, AI)
    assert answer["applied"] is True
    assert paper.log.path(paper.revision)[-1].via == "ai"


def test_somebody_else_may_not_use_or_commit_it(paper):
    token = start(paper)
    replace(paper, token, "Howdy")
    for method, params in (
        ("as_what_if", {"token": token, "method": "paragraphs"}),
        ("what_if_apply", {"token": token, "method": "replace_text", "params": {}}),
        ("what_if_changes", {"token": token}),
        ("what_if_commit", {"token": token}),
        ("what_if_drop", {"token": token}),
    ):
        with pytest.raises(RequestError) as refused:
            call(paper, method, params, BEN)
        assert refused.value.code == "command_error"
    assert text_of(paper) == "Hello world"


def test_outdated_is_answered_with_a_sentence_and_the_places_and_changes_nothing(paper):
    token = start(paper)
    replace(paper, token, "Howdy")
    call(paper, "replace_text", {"paragraph": "b1", "start": 0, "end_paragraph": "b1", "end": 5, "text": "Hey"}, BEN)
    answer = call(paper, "what_if_commit", {"token": token})
    assert answer["applied"] is False and answer["reason"] and answer["conflicts"]
    assert text_of(paper) == "Hey world"
    assert call(paper, "as_what_if", {"token": token, "method": "paragraphs"})  # still there to look at


def test_a_viewer_cannot_change_the_copy_either(paper):
    from claudia_server.auth import Account

    viewer = Account("vera", "viewer")
    token = start(paper, viewer)
    with pytest.raises(RequestError) as refused:
        replace(paper, token, "Howdy", viewer)
    assert refused.value.code == "forbidden"


@pytest.mark.parametrize("method", ["undo", "redo", "save_checkpoint", "chat", "redact", "lock"])
def test_what_is_not_an_edit_of_the_document_cannot_be_tried(paper, method):
    token = start(paper)
    with pytest.raises(RequestError) as refused:
        call(paper, "what_if_apply", {"token": token, "method": method, "params": {}})
    assert refused.value.code == "forbidden"


def test_a_person_has_so_many_and_a_document_has_so_many(paper):
    for _ in range(what_if.MAX_PER_PERSON):
        start(paper)
    with pytest.raises(RequestError) as full:
        start(paper)
    assert full.value.code == "unavailable"
    start(paper, BEN)  # somebody else's own


def test_dropping_one_makes_room_and_an_idle_one_is_dropped(paper, monkeypatch):
    first = start(paper)
    call(paper, "what_if_drop", {"token": first})
    with pytest.raises(RequestError):
        call(paper, "as_what_if", {"token": first, "method": "paragraphs"})
    kept = start(paper)
    now = what_if.time.monotonic() + what_if.IDLE_SECONDS + 1
    monkeypatch.setattr(what_if.time, "monotonic", lambda: now)
    with pytest.raises(RequestError):
        call(paper, "as_what_if", {"token": kept, "method": "paragraphs"})


def test_a_person_who_leaves_takes_theirs_with_them(paper):
    token = start(paper)
    what_if.drop_person(paper, "ann")
    with pytest.raises(RequestError):
        call(paper, "as_what_if", {"token": token, "method": "paragraphs"})


def test_a_what_if_can_start_from_an_earlier_step(paper):
    call(paper, "replace_text", {"paragraph": "b1", "start": 0, "end_paragraph": "b1", "end": 5, "text": "Howdy"}, BEN)
    first = paper.log.path(paper.revision)[0].rev.to_data()
    token = start(paper, params={"at": first})
    assert [b["text"] for b in paragraphs_in(paper, token)] == ["Hello world"]


def test_a_viewer_cannot_start_a_what_if_from_an_earlier_step(paper):
    """An earlier step is the history, which a viewer's key does not open (D1261); the document as it is now is hers."""
    from claudia_server.auth import Account

    call(paper, "replace_text", {"paragraph": "b1", "start": 0, "end_paragraph": "b1", "end": 5, "text": "Howdy"}, BEN)
    first = paper.log.path(paper.revision)[0].rev.to_data()
    with pytest.raises(RequestError) as refused:
        start(paper, Account("vera", "viewer"), params={"at": first})
    assert refused.value.code == "forbidden"


def test_the_what_if_methods_are_in_every_apps_table():
    from claudia_server.computes import computes_methods
    from claudia_server.creates import creates_methods

    for table in (composes_methods, computes_methods, creates_methods):
        names = {"what_if_start", "what_if_apply", "as_what_if", "what_if_changes", "what_if_commit", "what_if_drop"}
        assert names <= table.names()


def test_the_context_of_a_what_if_cannot_reach_the_other_windows(paper):
    heard = []
    ctx = Context(paper, ANN, Limits(), broadcast=heard.append)
    token = composes_methods.dispatch(ctx, "what_if_start", {})["token"]
    composes_methods.dispatch(
        ctx,
        "what_if_apply",
        {
            "token": token,
            "method": "replace_text",
            "params": {"paragraph": "b1", "start": 0, "end_paragraph": "b1", "end": 5, "text": "Howdy"},
        },
    )
    assert heard == []
