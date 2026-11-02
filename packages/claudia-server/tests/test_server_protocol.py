"""The wire protocol without a web framework: which requests exist, what they accept, what they do (E3.1).

Ported from the demo's protocol tests and rewritten for the kernel: one generic method table that every app extends,
edits carry the revision they were made against, and the errors of the kernel have their own codes.
"""

import json

import pytest

from claudia_core import Revision
from claudia_core.testing import Insert, Interval, Remove
from claudia_server.protocol import (
    ERROR_CODES,
    Context,
    Limits,
    RequestError,
    core_methods,
    parse_request,
)


def ctx_for(doc, account, *, users=("ann", "ben"), limits=None):
    return Context(doc, account, limits or Limits(), users=lambda: list(users), lock_seconds=30.0)


def call(doc, account, name, params=None, *, table=core_methods, **options):
    return table.dispatch(ctx_for(doc, account, **options), name, params)


INSERT = {"k": "list.Insert", "s": 1, "d": {"index": 0, "value": 5}}


# ------------------------------------------------------------------------------------------ the table
def test_every_method_is_documented_and_described():
    description = core_methods.describe(Limits())
    assert description["protocol"] == 1 and description["errors"].keys() == ERROR_CODES.keys()
    for name, info in description["methods"].items():
        assert info["doc"], f"{name} has no description"
    assert {
        "ping",
        "snapshot",
        "changes_since",
        "apply",
        "undo",
        "redo",
        "save_checkpoint",
        "checkpoints",
        "lines",
        "history",
        "presence",
        "lock",
        "unlock",
        "chat",
        "users",
    } <= set(description["methods"])
    json.dumps(description)  # it is served as JSON


def test_restoring_and_switching_are_not_on_the_wire_yet():
    """Who may restore a checkpoint or switch the line in a live session is not decided (E3.1 notes)."""
    assert "restore" not in core_methods.names() and "switch" not in core_methods.names()


# ---------------------------------------------------------------------------------------- reading
def test_ping_snapshot_and_lines(doc, ann):
    doc.execute(Insert(0, 7), author="ben")
    assert call(doc, ann, "ping") == {"revision": "main:1", "line": "main"}
    snap = call(doc, ann, "snapshot")
    assert snap["state"] == {"items": [7]} and snap["revision"] == "main:1" and snap["app"] == "test-list"
    assert call(doc, ann, "lines") == [{"name": "main", "head": "main:1", "active": True, "forked_from": None}]


def test_the_empty_document_has_no_revision(doc, ann):
    assert call(doc, ann, "ping")["revision"] is None


def test_changes_since_brings_a_replica_up_to_date(doc, ann):
    for i in range(3):
        doc.execute(Insert(i, i), author="ben")
    entries = call(doc, ann, "changes_since", {"revision": "main:1"})
    assert [e["rev"] for e in entries] == ["main:2", "main:3"] and entries[0]["command"]["k"] == "list.Insert"
    assert len(call(doc, ann, "changes_since", {})) == 3  # nothing known yet: everything


def test_changes_since_a_revision_of_an_abandoned_line_says_reload(doc, ann):
    doc.execute(Insert(0, 1), author="ben")
    doc.save_checkpoint("ben", "good")
    doc.execute(Insert(0, 2), author="ben")  # main:3
    doc.restore_checkpoint(1, author="ben")
    with pytest.raises(RequestError) as caught:
        call(doc, ann, "changes_since", {"revision": "main:3"})
    assert caught.value.code == "stale"


# ---------------------------------------------------------------------------------------- writing
def test_apply_executes_a_command_as_the_account(doc, ann):
    result = call(doc, ann, "apply", {"command": INSERT})
    assert result == {"revision": "main:1"} and doc.model.items == [5]
    assert doc.log.get(Revision("main", 1)).author == "ann"


def test_apply_with_the_base_the_client_saw(doc, ann):
    doc.execute(Insert(0, 1), author="ben")
    call(doc, ann, "apply", {"command": INSERT, "base": "main:1"})
    assert doc.model.items == [5, 1]


def test_an_edit_in_flight_during_a_restore_is_refused_with_stale(doc, ann):
    doc.execute(Insert(0, 1), author="ben")  # main:1
    doc.save_checkpoint("ben", "good")  # main:2
    doc.execute(Insert(0, 2), author="ben")  # main:3
    doc.restore_checkpoint(1, author="ben")
    before = doc.model.serialize()
    with pytest.raises(RequestError) as caught:
        call(doc, ann, "apply", {"command": INSERT, "base": "main:3"})
    assert caught.value.code == "stale" and "reload" in caught.value.message.lower()
    assert doc.model.serialize() == before


def test_a_command_the_model_refuses_changes_nothing(doc, ann):
    with pytest.raises(RequestError) as caught:
        call(doc, ann, "apply", {"command": {"k": "list.Remove", "s": 1, "d": {"index": 9}}})
    assert caught.value.code == "command_error" and doc.revision is None


def test_unknown_and_too_new_commands_are_bad_requests(doc, ann):
    with pytest.raises(RequestError, match="ext.Thing") as unknown:
        call(doc, ann, "apply", {"command": {"k": "ext.Thing", "s": 1, "d": {}}})
    assert unknown.value.code == "bad_request"
    with pytest.raises(RequestError, match="newer") as new:
        call(doc, ann, "apply", {"command": {"k": "list.Insert", "s": 9, "d": {"index": 0, "value": 1}}})
    assert new.value.code == "bad_request"
    for broken in ({}, {"k": "list.Insert"}, {"k": "list.Insert", "s": 1, "d": {"index": 0}}):
        with pytest.raises(RequestError) as caught:
            call(doc, ann, "apply", {"command": broken})
        assert caught.value.code == "bad_request"


def test_a_lock_held_by_a_colleague_refuses_the_edit(doc, ann, ben):
    doc.lock("ben", [Interval(0, 1)], ttl=30)
    with pytest.raises(RequestError) as caught:
        call(doc, ann, "apply", {"command": INSERT})
    assert caught.value.code == "locked" and "ben" in caught.value.message
    call(doc, ben, "apply", {"command": INSERT})  # his own lock does not stop him


def test_viewers_may_read_but_not_write(doc, vera):
    assert call(doc, vera, "snapshot")["state"] == {"items": []}
    for name, params in (
        ("apply", {"command": INSERT}),
        ("undo", None),
        ("redo", None),
        ("chat", {"text": "hi"}),
        ("save_checkpoint", None),
        ("lock", {"regions": []}),
        ("unlock", None),
    ):
        with pytest.raises(RequestError) as caught:
            call(doc, vera, name, params)
        assert caught.value.code == "forbidden", name


# --------------------------------------------------------------------------------------- undo / redo
def test_undo_and_redo_are_per_account(doc, ann, ben):
    call(doc, ann, "apply", {"command": INSERT})
    call(doc, ben, "apply", {"command": {"k": "list.Insert", "s": 1, "d": {"index": 1, "value": 6}}})
    assert call(doc, ann, "history") == {
        "can_undo": True,
        "can_redo": False,
        "undo_label": "Insert 5",
        "redo_label": "",
    }
    assert call(doc, ann, "undo")["applied"] is True and doc.model.items == [6]
    assert call(doc, ann, "history")["can_redo"] is True
    assert call(doc, ann, "redo")["applied"] is True and doc.model.items == [5, 6]
    assert call(doc, ann, "undo")["applied"] is True and call(doc, ann, "undo") == {"applied": False, "revision": None}


def test_undo_that_would_overwrite_a_colleague_is_a_conflict(doc, ann, ben):
    call(doc, ann, "apply", {"command": INSERT})
    doc.execute(Remove(0), author="ben")  # ben removed the element ann inserted
    with pytest.raises(RequestError) as caught:
        call(doc, ann, "undo")
    assert caught.value.code == "conflict" and "ben" in caught.value.message


def test_undo_into_a_lock_is_refused(doc, ann, ben):
    call(doc, ann, "apply", {"command": INSERT})
    doc.lock("ben", [Interval(0, 1)], ttl=30)
    with pytest.raises(RequestError) as caught:
        call(doc, ann, "undo")
    assert caught.value.code == "locked"


# ---------------------------------------------------------------------------------------- checkpoints
def test_checkpoints_are_saved_and_listed(doc, ann):
    call(doc, ann, "apply", {"command": INSERT})
    assert call(doc, ann, "save_checkpoint", {"label": "first"})["saved"] is True
    assert call(doc, ann, "save_checkpoint", {})["saved"] is False  # nothing changed
    listed = call(doc, ann, "checkpoints")
    assert [(c["number"], c["label"], c["author"]) for c in listed] == [(1, "first", "ann")]


# --------------------------------------------------------------------------------- presence and locks
def test_presence_is_allowed_for_viewers_and_shows_where_one_is(doc, vera, ann):
    seen = []
    doc.subscribe(seen.append)
    call(doc, vera, "presence", {"regions": [{"kind": "interval", "start": 0, "end": 2}]})
    assert doc.presence.of("vera").regions == (Interval(0, 2),)
    assert any(getattr(e, "message", None) and e.message.kind == "presence" for e in seen)


def test_presence_regions_are_validated(doc, ann):
    for bad in ("x", [1], [{"kind": "interval"}], [{"kind": "interval", "start": 0, "end": 1}] * 17):
        with pytest.raises(RequestError) as caught:
            call(doc, ann, "presence", {"regions": bad})
        assert caught.value.code == "bad_request", bad


def test_a_lock_is_taken_held_and_released(doc, ann, ben):
    call(doc, ann, "lock", {"regions": [{"kind": "interval", "start": 0, "end": 1}]})
    with pytest.raises(RequestError) as caught:
        call(doc, ben, "lock", {"regions": [{"kind": "interval", "start": 0, "end": 3}]})
    assert caught.value.code == "locked"
    call(doc, ann, "unlock")
    call(doc, ben, "lock", {"regions": [{"kind": "interval", "start": 0, "end": 3}]})
    assert doc.presence.of("ben") is not None


# --------------------------------------------------------------------------------------------- chat
def test_chat_is_posted_with_the_connected_users_for_addressing(doc, ann):
    result = call(doc, ann, "chat", {"text": "@ben please check 3"}, users=("ann", "ben"))
    assert result["to"] == "ben" and result["text"] == "please check 3" and doc.chat[0].author == "ann"
    with pytest.raises(RequestError) as caught:
        call(doc, ann, "chat", {"text": "@zoe hello"}, users=("ann", "ben"))
    assert caught.value.code == "command_error" and "zoe is not here" in caught.value.message
    assert call(doc, ann, "users", users=("ben", "ann")) == ["ben", "ann"]


# ----------------------------------------------------------------------------------- parameter checks
def test_malformed_params_are_bad_requests(doc, ann):
    for name, params in (
        ("apply", {"command": "x"}),
        ("apply", {}),
        ("apply", {"command": INSERT, "base": 5}),
        ("apply", {"command": INSERT, "base": "nonsense"}),
        ("apply", {"command": INSERT, "extra": 1}),
        ("ping", {"unexpected": 1}),
        ("ping", [1]),
        ("chat", {"text": 5}),
    ):
        with pytest.raises(RequestError) as caught:
            call(doc, ann, name, params)
        assert caught.value.code == "bad_request", (name, params)


def test_defaults_and_nulls(doc, ann):
    call(doc, ann, "apply", {"command": INSERT, "base": None})
    call(doc, ann, "save_checkpoint", {"label": None})
    assert doc.checkpoints[0].label == "Checkpoint 1"
    assert call(doc, ann, "ping", None)["line"] == "main"


def test_unknown_method_and_non_string_method(doc, ann):
    with pytest.raises(RequestError) as caught:
        call(doc, ann, "launch_missiles")
    assert caught.value.code == "unknown_method"
    with pytest.raises(RequestError) as caught:
        call(doc, ann, 7)
    assert caught.value.code == "bad_request"


def test_limits(doc, ann):
    limits = Limits(max_text=10)
    with pytest.raises(RequestError, match="at most 10 characters"):
        call(doc, ann, "chat", {"text": "x" * 11}, limits=limits)
    call(doc, ann, "chat", {"text": "x" * 10}, limits=limits)


def test_parse_request():
    limits = Limits(max_message_bytes=100)
    assert parse_request('{"id": 3, "method": "ping", "params": {"a": 1}}', limits) == (3, "ping", {"a": 1})
    assert parse_request(b'{"id": "abc", "method": "ping"}', limits) == ("abc", "ping", None)
    for raw in (
        "not json",
        "[1]",
        '{"id": true}',
        '{"id": 1.5}',
        '{"id": 1e30}',
        '{"id": "' + "x" * 101 + '"}',
        "x" * 101,
    ):
        with pytest.raises(RequestError) as caught:
            parse_request(raw, limits)
        assert caught.value.code == "bad_request", raw


# --------------------------------------------------------------------------------------- extension
def test_an_app_extends_a_copy_of_the_table_with_its_own_methods_and_types(doc, ann):
    table = core_methods.extended()

    @table.kind("even")
    def _even(value, limits):
        if not isinstance(value, int) or value % 2:
            raise ValueError("must be an even number")
        return value

    @table.method("double", "n:even", write=True)
    def _double(ctx, n):
        """Twice n, for the test."""
        return {"result": n * 2}

    assert call(doc, ann, "double", {"n": 4}, table=table) == {"result": 8}
    with pytest.raises(RequestError, match="even"):
        call(doc, ann, "double", {"n": 3}, table=table)
    assert "double" in table.describe(Limits())["methods"] and "even" in table.describe(Limits())["param_types"]
    assert "double" not in core_methods.names(), "the core table must not change when an app extends its copy"
