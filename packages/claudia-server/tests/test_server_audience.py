"""What a viewer's connection receives and may ask for (D1261, SEC-17).

The file gives a viewer the content key only (D101); the live session must not give more. Three layers are tested:
the table that says what each event and method belongs to, the hub that delivers by it, and the check that a new event
or method cannot be added without somebody classifying it (an unlisted one goes to owners and editors only).
"""

import asyncio
import json
import re
from pathlib import Path

import pytest

from claudia_core.testing import ListModel
from claudia_server import audience
from claudia_server.apps import _METHODS
from claudia_server.audience import EPHEMERAL_RULES, EVENT_RULES, shape_for
from claudia_server.auth import Account
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.protocol import RequestError, core_methods

INSERT = {"k": "list.Insert", "s": 1, "d": {"index": 0, "value": 5}}
PACKAGES = Path(__file__).resolve().parents[2]
SERVER_SRC = PACKAGES / "claudia-server" / "src"


# ------------------------------------------------------------------------------------------ the table
COMMAND = {
    "type": "command",
    "revision": {"branch": "main", "number": 3},
    "author": "ann",
    "origin": "do",
    "time": "2026-11-19T10:00:00Z",
    "label": "Insert 5",
    "summary": "ann inserted 5",
}


@pytest.mark.parametrize("role", ["owner", "editor"])
def test_owners_and_editors_receive_everything_unchanged(role):
    for event, data in (("command", COMMAND), ("chat", {"type": "chat", "text": "hi"}), ("never_heard_of", {"x": 1})):
        assert shape_for(role, event, data) == data


def test_a_viewer_gets_a_command_as_its_revision_alone():
    assert shape_for("viewer", "command", COMMAND) == {"type": "command", "revision": COMMAND["revision"]}


@pytest.mark.parametrize("event", ["history", "checkpoint", "chat", "redacted", "restore_proposed", "restore_resolved"])
def test_a_viewer_gets_nothing_from_the_history_or_the_chat(event):
    assert shape_for("viewer", event, {"type": event, "anything": 1}) is None


def test_a_viewer_is_told_that_the_document_moved_but_not_where_from_or_to():
    data = {"type": "branch", "old": "main", "new": "side-2", "fork_point": {"branch": "main", "number": 4}}
    assert shape_for("viewer", "branch", data) == {"type": "branch"}


@pytest.mark.parametrize("event", ["rebuilt", "stale", "thing_renamed", "joined", "left", "render_result", "cells"])
def test_a_viewer_gets_content_names_and_presence_as_they_are(event):
    data = {"type": event, "id": 1}
    assert shape_for("viewer", event, data) == data


@pytest.mark.parametrize(
    ("kind", "passes"),
    [
        ("presence", True),
        ("person_left", True),
        ("owner_changed", True),
        ("document_deleted", True),
        ("details_changed", True),
        ("typing", False),
        ("something_new", False),
    ],
)
def test_a_viewer_gets_the_ephemeral_kinds_that_are_not_chat_and_no_unknown_one(kind, passes):
    data = {"type": "ephemeral", "kind": kind, "sender": "ann", "data": {}}
    assert (shape_for("viewer", "ephemeral", data) == data) is passes


def test_an_event_nobody_classified_goes_to_owners_and_editors_only():
    assert shape_for("viewer", "brand_new", {"type": "brand_new"}) is None
    assert shape_for("editor", "brand_new", {"type": "brand_new"}) == {"type": "brand_new"}


def test_a_role_nobody_knows_is_treated_as_a_viewer():
    assert shape_for("guest", "chat", {"type": "chat"}) is None


# ------------------------------------------------------- nothing can be added without being classified
def _literals(pattern: str, *roots: Path) -> set[str]:
    found: set[str] = set()
    for root in roots:
        for path in root.rglob("*.py"):
            if "tests" in path.parts or "__pycache__" in path.parts:
                continue
            found |= set(re.findall(pattern, path.read_text(encoding="utf-8")))
    return found


# "bar" is a chart kind that happens to sit under a "type" key; the others under it are all events.
# "bar" is a chart kind; the others are Anthropic's streaming frames, which the fake Anthropic in
# claudia_ai.testing writes and which never reach a document's audience.
NOT_AN_EVENT = {"bar", "content_block_delta", "text_delta", "message_stop", "error"}


def test_every_kind_of_event_the_packages_can_send_is_classified():
    types = _literals(r'"type": "([a-z_]+)"', *PACKAGES.glob("claudia-*/src")) - NOT_AN_EVENT
    assert types - set(EVENT_RULES) == set(), "classify these in claudia_server/audience.py (EVENT_RULES)"


def test_every_event_the_server_names_is_classified():
    named = _literals(r'"event": "([a-z_]+)"', SERVER_SRC)
    assert named - set(EVENT_RULES) == set(), "classify these in claudia_server/audience.py (EVENT_RULES)"


def test_every_documented_event_is_classified():
    from claudia_server.protocol import EVENTS

    assert set(EVENTS) - set(EVENT_RULES) == set()


def test_every_ephemeral_kind_the_server_publishes_is_classified():
    kinds = _literals(r'publish\("([a-z_]+)"', *PACKAGES.glob("claudia-*/src"))
    assert kinds - set(EPHEMERAL_RULES) == set(), "classify these in claudia_server/audience.py (EPHEMERAL_RULES)"


def test_the_table_only_names_parts_a_document_has():
    from claudia_document_file import Part

    parts = {rule.part for rule in EVENT_RULES.values()} | set(EPHEMERAL_RULES.values())
    assert parts <= set(Part)


# ------------------------------------------------------------------------------------------ the hub
class Client:
    def __init__(self, hosted, account):
        self.frames: list[dict] = []
        self.connection = hosted.connect(account, lambda text: self.frames.append(json.loads(text)))
        self._next = 0

    def request(self, method, params=None):
        self._next += 1
        self.connection.handle(json.dumps({"id": self._next, "method": method, "params": params}))
        return self.frames[-1]

    def events(self, name):
        return [f["data"] for f in self.frames if f.get("event") == name]

    def names(self):
        return [f["event"] for f in self.frames if "event" in f]

    def forget(self):
        self.frames.clear()


@pytest.fixture
def hosted(clock):
    provider = MemoryProvider(ListModel, clock=clock.time, lock_clock=clock.lock_time)
    return asyncio.run(Hub(provider, clock=clock.lock_time).open("plan", create=True))


@pytest.fixture
def room(hosted):
    """Ann (owner), Ben (editor) and Vera (viewer) are in the document."""
    ann, ben, vera = (
        Client(hosted, Account(n, r)) for n, r in (("ann", "owner"), ("ben", "editor"), ("vera", "viewer"))
    )
    for client in (ann, ben, vera):
        client.forget()
    return ann, ben, vera


def test_a_viewer_sees_the_change_but_not_who_made_it_or_when(room):
    ann, ben, vera = room
    ann.request("apply", {"command": INSERT})
    assert vera.events("command"), "she hears of the change"
    assert all(set(e) == {"type", "revision"} for e in vera.events("command"))
    assert {"author", "time", "label", "summary", "origin"} <= set(ben.events("command")[0]), "the editor is unchanged"


def test_a_viewer_hears_nothing_of_undo_state_checkpoints_or_chat(room):
    ann, ben, vera = room
    ann.request("apply", {"command": INSERT})
    ann.request("save_checkpoint", {"label": "good"})
    ann.request("chat", {"text": "for everybody"})
    ann.request("chat", {"text": "@ben private"})
    ann.request("undo")
    assert {"history", "checkpoint", "chat"}.isdisjoint(vera.names())
    assert {"history", "checkpoint", "chat"} <= set(ann.names())
    assert [c["text"] for c in ben.events("chat")] == ["for everybody", "private"]


def test_a_viewer_sees_who_is_here_and_where_they_look(room):
    ann, ben, vera = room
    ben.request("presence", {"regions": [{"kind": "interval", "start": 0, "end": 2}]})
    late = Client(ann.connection.hosted, Account("cleo", "editor"))
    assert [e["kind"] for e in vera.events("ephemeral")] == ["presence"]
    assert vera.events("joined") == [late.connection.person()]
    late.connection.close()
    assert vera.events("left")


def test_a_viewer_does_not_see_that_the_ai_is_typing(room, hosted):
    ann, ben, vera = room
    hosted.document.publish("typing", "ai", {"on": True})
    assert vera.events("ephemeral") == []
    assert [e["kind"] for e in ann.events("ephemeral")] == ["typing"]


def test_a_restore_reaches_a_viewer_as_a_reload_only(hosted):
    ann, vera = Client(hosted, Account("ann", "owner")), Client(hosted, Account("vera", "viewer"))
    ann.request("apply", {"command": INSERT})
    ann.request("save_checkpoint", {"label": "good"})
    ann.request("apply", {"command": INSERT})
    ann.forget(), vera.forget()
    assert ann.request("propose_restore", {"checkpoint": 1})["result"]["applied"] is True
    assert vera.events("branch") == [{"type": "branch"}] and vera.events("rebuilt")
    assert ann.events("branch")[0]["new"], "the owner is told which line"
    assert {"restore_proposed", "restore_resolved", "checkpoint", "history"}.isdisjoint(vera.names())


def test_the_welcome_of_a_viewer_carries_no_history(hosted):
    ann = Client(hosted, Account("ann", "owner"))
    ann.request("apply", {"command": INSERT})
    ann.request("save_checkpoint", {"label": "good"})
    vera = Client(hosted, Account("vera", "viewer"))
    welcome = vera.connection.welcome()
    assert welcome["checkpoints"] == [] and welcome["branches"] == [] and welcome["proposal"] is None
    assert welcome["returned"] is None
    assert welcome["revision"] is not None, "the revision of the content is what the snapshot is of"
    assert welcome["role"] == "viewer"
    assert ann.connection.welcome()["checkpoints"], "an owner's welcome is as before"


# ---------------------------------------------------------------------------------------- the methods
HISTORY_METHODS = [
    ("log", {"limit": 5}),
    ("checkpoints", None),
    ("branches", None),
    ("history", None),
    ("changes_since", {"revision": None}),
    ("peek_revision", {"revision": "main:1"}),
    ("peek_branch", {"branch": "main"}),
    ("redaction_plan", {"revisions": []}),
    ("restore_policy", None),
]


@pytest.mark.parametrize(("method", "params"), HISTORY_METHODS)
def test_a_viewer_is_refused_what_reads_the_history(room, method, params):
    ann, ben, vera = room
    answer = vera.request(method, params)
    assert answer["ok"] is False and answer["error"]["code"] == "forbidden", method
    assert "editors" in answer["error"]["message"]


def test_a_viewer_is_refused_the_chat_log(room):
    ann, ben, vera = room
    ann.request("chat", {"text": "hello"})
    answer = vera.request("chat_log", {})
    assert answer["ok"] is False and answer["error"]["code"] == "forbidden"


def test_owners_and_editors_still_read_both(room):
    ann, ben, vera = room
    ann.request("apply", {"command": INSERT})
    ann.request("chat", {"text": "hello"})
    for client in (ann, ben):
        assert client.request("log", {"limit": 5})["ok"]
        assert client.request("chat_log", {})["ok"]
        assert client.request("checkpoints")["ok"]


def test_a_viewer_still_reads_the_content_and_the_names(room):
    ann, ben, vera = room
    ann.request("apply", {"command": INSERT})
    assert vera.request("snapshot")["result"]["state"] == {"items": [5]}
    assert (
        vera.request("ping")["ok"] and vera.request("users")["ok"] and vera.request("presence", {"regions": []})["ok"]
    )


def test_looking_back_reads_the_history():
    """``as_of`` shows the document as it was after a step, which is what the history paragraphs hold."""
    tables = [table for table in _METHODS.values() if "as_of" in table.names()]
    assert tables and all(table.describe()["methods"]["as_of"]["reads"] == "history" for table in tables)


# ---------------------------------------------------- nothing can be added to the protocol unclassified
GOLDEN = Path(__file__).with_name("method_reads.json")


def _all_methods():
    seen = {}
    for table in (core_methods, *_METHODS.values()):
        for name, method in table.describe()["methods"].items():  # what /api/protocol says
            seen.setdefault(name, method["reads"])
    return seen


def test_every_method_is_in_the_reviewed_list_with_the_part_it_reads():
    reviewed = json.loads(GOLDEN.read_text(encoding="utf-8"))
    actual = _all_methods()
    assert set(actual) - set(reviewed) == set(), (
        "a new method: decide which part it reads (content, history or chat), declare it with "
        "`reads=` and add it to tests/method_reads.json"
    )
    assert set(reviewed) - set(actual) == set(), "a method was removed: remove it from tests/method_reads.json"
    assert {n: d for n, d in actual.items() if d != reviewed[n]} == {}, "declared and reviewed parts differ"


def test_a_method_cannot_declare_a_part_there_is_not():
    from claudia_server.protocol import MethodTable

    with pytest.raises(ValueError, match="reads"):
        MethodTable().method("x", reads="gossip")


def test_the_protocol_description_says_what_each_method_reads():
    described = core_methods.describe()["methods"]
    assert described["log"]["reads"] == "history" and described["snapshot"]["reads"] == "content"


def test_a_viewer_is_refused_before_the_method_runs():
    called = []

    from claudia_server.protocol import Context, MethodTable

    table = MethodTable()

    @table.method("spy", reads="history")
    def spy(ctx):
        called.append(1)

    context = Context.__new__(Context)
    context.account = Account("vera", "viewer")
    with pytest.raises(RequestError) as refused:
        table.dispatch(context, "spy", {})
    assert refused.value.code == "forbidden" and called == []


def test_the_role_table_is_the_files(monkeypatch):
    """The live session follows claudia-document-file's table of which role holds which key (one source of truth)."""
    from claudia_document_file import ROLE_PARTS, Part, Role

    assert audience.may_read("viewer", Part.CONTENT)
    assert not audience.may_read("viewer", Part.HISTORY)
    assert all(audience.may_read(r, part) for r in ("owner", "editor") for part in Part)
    assert ROLE_PARTS[Role.VIEWER] == {Part.CONTENT}
