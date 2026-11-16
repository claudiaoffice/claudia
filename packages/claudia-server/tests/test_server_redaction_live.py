"""Redaction over the wire (E1.8, D229, D726): an owner asks what a redaction does, sees it, and confirms that plan."""

import asyncio
import json

import pytest

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


def test_only_an_owner_plans_or_redacts(people):
    _, _, ben = people
    assert ben.request("redaction_plan", {"revisions": ["main:2"]})["error"]["code"] == "forbidden"
    assert ben.request("redact", {"revisions": ["main:2"], "dependents": []})["error"]["code"] == "forbidden"


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
