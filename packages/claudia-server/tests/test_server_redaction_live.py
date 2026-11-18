"""Redaction over the wire (E1.8, D229, D727): an owner on anything, an editor on her own work, asks what a redaction
does, sees it, and confirms that plan."""

import asyncio
import json
from dataclasses import dataclass
from typing import ClassVar

import pytest

from claudia_core import Command, new_registry
from claudia_core.testing import ListModel
from claudia_server.auth import Account
from claudia_server.hub import Hub, MemoryProvider

SECRET = 424242


def insert(index, value):
    return {"k": "list.Insert", "s": 1, "d": {"index": index, "value": value}}


class Client:
    def __init__(self, hosted, account):
        self.frames: list[dict] = []
        self.connection = hosted.connect(account, lambda text: self.frames.append(json.loads(text)))
        self._next = 0

    def request(self, method, params=None):
        self._next += 1
        self.connection.handle(json.dumps({"id": self._next, "method": method, "params": params}))
        return next(f for f in reversed(self.frames) if f.get("id") == self._next)

    def events(self, name):
        return [f["data"] for f in self.frames if f.get("event") == name]


@pytest.fixture
def hosted(clock):
    hub = Hub(MemoryProvider(ListModel, clock=clock.time, lock_clock=clock.lock_time), clock=clock.lock_time)
    return asyncio.run(hub.open("plan", create=True))


@pytest.fixture
def people(hosted):
    ana, ben = Client(hosted, Account("ana", "owner")), Client(hosted, Account("ben", "editor"))
    ana.request("apply", {"command": insert(0, 1)})  # main:1
    ben.request("apply", {"command": insert(1, SECRET)})  # main:2
    ben.request("chat", {"text": f"the code is {SECRET}"})  # chat 1
    ben.request("chat", {"text": f"@ana between us: {SECRET}"})  # chat 2, private
    return hosted, ana, ben


def test_an_owner_sees_what_a_redaction_does_before_doing_it(people):
    hosted, ana, _ = people
    plan = ana.request("redaction_plan", {"revisions": ["main:2"], "chat": [1]})["result"]
    assert plan["targets"] == ["main:2"] and plan["dependents"] == [] and plan["chat"] == [1]
    assert plan["changes_now"] is True and plan["state"]["items"] == [1, 0]
    assert [step["revision"] for step in plan["steps"]] == ["main:2"]
    assert plan["steps"][0]["author"] == "ben"
    assert hosted.document.model.items == [1, SECRET]  # nothing happened yet


def test_an_owner_redacts_the_plan_she_saw_and_everybody_hears_of_it(people):
    hosted, ana, ben = people
    result = ana.request("redact", {"revisions": ["main:2"], "chat": [1], "dependents": []})["result"]
    assert result["revision"].startswith("main:")
    assert hosted.document.model.items == [1, 0]
    heard = ben.events("redacted")[-1]
    assert (heard["revisions"], heard["chat"]) == (["main:2"], [1])
    assert ben.events("rebuilt")
    log = ana.request("chat_log")["result"]
    assert log[0]["redacted"] is True and log[0]["text"] == ""
    assert str(SECRET) not in json.dumps(hosted.document.log.to_data())


def test_a_plan_that_changed_since_it_was_shown_is_not_carried_out(people):
    hosted, ana, _ = people
    reply = ana.request("redact", {"revisions": ["main:2"], "dependents": ["main:9"]})
    assert reply["error"]["code"] == "command_error"
    assert not hosted.document.log.get(hosted.document.log.path(hosted.document.revision)[1].rev).redacted


def test_an_editor_redacts_her_own_changes_and_messages(people):
    """D727: an editor redacts what she did herself."""
    hosted, _, ben = people
    plan = ben.request("redaction_plan", {"revisions": ["main:2"], "chat": [1, 2]})["result"]
    assert plan["targets"] == ["main:2"] and plan["chat"] == [1, 2]
    assert ben.request("redact", {"revisions": ["main:2"], "chat": [1, 2], "dependents": []})["result"]
    assert hosted.document.model.items == [1, 0] and hosted.document.chat[1].redacted


def test_an_editor_does_not_redact_the_work_of_others(people):
    _, ana, ben = people
    ana.request("chat", {"text": "noted"})  # chat 3, ana's
    for params in ({"revisions": ["main:1"]}, {"chat": [3]}, {"revisions": ["main:1", "main:2"]}):
        for method in ("redaction_plan", "redact"):
            reply = ben.request(method, {**params, "dependents": []} if method == "redact" else params)
            assert reply["error"]["code"] == "command_error", (method, params)
            assert "ana" in reply["error"]["message"] or "your own" in reply["error"]["message"]


def test_a_viewer_and_the_ai_do_not_redact(people):
    hosted, _, _ = people
    viewer = Client(hosted, Account("cy", "viewer"))
    assert viewer.request("redaction_plan", {"chat": [1]})["error"]["code"] == "forbidden"
    ai = Client(hosted, Account("ai", "editor", system=True))
    assert ai.request("redaction_plan", {"revisions": ["main:2"]})["error"]["code"] == "forbidden"


# --------------------------------------------------------------------------- later steps by somebody else (D727)
naive = new_registry()


@naive.register
@dataclass(frozen=True)
class NaiveInsert(Command):
    """Its tombstone inserts nothing, so a later removal of what it inserted stops working."""

    kind: ClassVar[str] = "naive.Insert"
    index: int
    value: int

    def apply(self, ctx):
        ctx.model.items.insert(self.index, self.value)
        return NaiveRemove(self.index)

    def to_data(self):
        return {"index": self.index, "value": self.value}

    @classmethod
    def from_data(cls, data, registry):
        return cls(data["index"], data["value"])


@naive.register
@dataclass(frozen=True)
class NaiveRemove(Command):
    kind: ClassVar[str] = "naive.Remove"
    index: int

    def apply(self, ctx):
        if not 0 <= self.index < len(ctx.model.items):
            raise IndexError(f"nothing at {self.index}")
        return NaiveInsert(self.index, ctx.model.items.pop(self.index))

    def to_data(self):
        return {"index": self.index}

    @classmethod
    def from_data(cls, data, registry):
        return cls(data["index"])


class NaiveModel(ListModel):
    app: ClassVar[str] = "test-naive"
    registry = naive


def test_an_editor_whose_redaction_would_blank_somebody_elses_later_step_asks_an_owner(clock):
    hub = Hub(MemoryProvider(NaiveModel, clock=clock.time, lock_clock=clock.lock_time), clock=clock.lock_time)
    hosted = asyncio.run(hub.open("plan", create=True))
    ana, ben = Client(hosted, Account("ana", "owner")), Client(hosted, Account("ben", "editor"))
    ben.request("apply", {"command": {"k": "naive.Insert", "s": 1, "d": {"index": 0, "value": SECRET}}})
    ana.request("apply", {"command": {"k": "naive.Remove", "s": 1, "d": {"index": 0}}})  # needs ben's step
    shown = ben.request("redaction_plan", {"revisions": ["main:1"]})["result"]  # he sees why, for the dialog
    assert shown["dependents"] == ["main:2"] and shown["allowed"] is False and shown["others"] == ["ana"]
    assert "state" not in shown
    reply = ben.request("redact", {"revisions": ["main:1"], "dependents": ["main:2"]})
    assert reply["error"]["code"] == "command_error" and "ana" in reply["error"]["message"]
    plan = ana.request("redaction_plan", {"revisions": ["main:1"]})["result"]  # an owner may
    assert plan["allowed"] is True and plan["others"] == [] and "state" in plan


def test_nobody_redacts_while_a_restore_is_suggested(people):
    hosted, ana, ben = people
    ana.request("save_checkpoint", {"label": "start"})
    ben.request("apply", {"command": insert(0, 7)})
    proposed = ana.request("propose_restore", {"checkpoint": 1})["result"]
    assert proposed["proposal"] is not None  # ben is connected too, so it waits for him
    reply = ben.request("redact", {"revisions": ["main:2"], "dependents": []})
    assert reply["error"]["code"] == "command_error"


def test_an_owner_redacts_only_chat_she_can_read(hosted):
    ana, ben = Client(hosted, Account("ana", "owner")), Client(hosted, Account("ben", "editor"))
    Client(hosted, Account("cy", "editor"))
    ben.request("chat", {"text": "@cy just for you"})
    reply = ana.request("redaction_plan", {"chat": [1]})
    assert reply["error"]["code"] == "command_error"


def test_what_cannot_be_redacted_is_a_command_error(people):
    _, ana, _ = people
    for params in ({"revisions": ["main:99"]}, {}, {"revisions": ["nonsense"]}, {"parts": {"main:2": ["0"]}}):
        reply = ana.request("redaction_plan", params)
        assert reply["error"]["code"] in ("command_error", "bad_request"), params


# --------------------------------------------------------------------------- the preview (D721)
def test_the_history_says_which_steps_are_redacted_and_which_is_the_record(people):
    _, ana, _ = people
    ana.request("redact", {"revisions": ["main:2"], "dependents": []})
    log = ana.request("log")["result"]
    assert [(e["revision"], e["redacted"]) for e in log[:2]] == [("main:1", False), ("main:2", True)]
    assert log[-1]["kind"] == "core.Redaction" and log[0]["kind"] == "list.Insert"
