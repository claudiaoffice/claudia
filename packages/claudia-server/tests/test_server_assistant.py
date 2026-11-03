"""The AI as one more participant of a document: it joins, hears its name in chat, answers and edits as ``ai``."""

import asyncio
import json

import pytest

from claudia_computes import WorkbookModel
from claudia_server.assistant import Assistant, Call, Say, Task
from claudia_server.auth import Account
from claudia_server.computes import computes_methods
from claudia_server.hub import Hub, HubError, MemoryProvider
from claudia_server.protocol import core_methods
from claudia_server.standin import ScriptedEngine

ANN = Account("ann", "owner")
BEN = Account("ben", "editor")


class Person:
    """A connected person; everything the server sent is in ``frames``."""

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

    def said(self):
        return [m["text"] for m in self.events("chat") if m["author"] == "ai"]


class EchoEngine:
    def plan(self, task: Task):
        return [Say(f"you said: {task.text}")]


class BrokenEngine:
    def plan(self, task: Task):
        raise RuntimeError("the model fell over")


def scenario(test, engine=None, methods=computes_methods):
    """Run ``test(hosted, assistant)`` inside an event loop with a workbook that has the assistant attached."""

    async def run():
        hub = Hub(MemoryProvider(WorkbookModel), methods=methods)
        hosted = await hub.open("plan", create=True)
        assistant = Assistant(engine or ScriptedEngine(), pause=0)
        assistant.attach(hosted)
        await test(hosted, assistant)

    asyncio.run(run())


def test_the_assistant_is_a_participant_but_not_a_person():
    async def test(hosted, assistant):
        ann = Person(hosted, ANN)
        assert hosted.users() == ["ai", "ann"]
        assert [c.account.user for c in hosted.humans()] == ["ann"]
        people = {p["user"]: p for p in ann.connection.welcome()["people"]}
        assert people["ai"]["color"] == "#5b4bc4", "the assistant has its own colour (Iris)"
        assert ann.request("users")["result"] == ["ai", "ann"]

    scenario(test)


def test_a_document_has_one_assistant():
    async def test(hosted, assistant):
        with pytest.raises(HubError):
            Assistant(EchoEngine()).attach(hosted)

    scenario(test)


def test_a_message_to_ai_is_answered_to_its_sender_only():
    async def test(hosted, assistant):
        ann, ben = Person(hosted, ANN), Person(hosted, BEN)
        ann.request("chat", {"text": "@ai hello there"})
        await assistant.idle()
        assert ann.said() == ["you said: hello there"]
        assert [m["to"] for m in ann.events("chat") if m["author"] == "ai"] == ["ann"]
        assert ben.said() == [], "an answer is for the one who asked"

    scenario(test, EchoEngine())


def test_messages_that_are_not_for_ai_are_not_answered():
    async def test(hosted, assistant):
        ann, ben = Person(hosted, ANN), Person(hosted, BEN)
        ann.request("chat", {"text": "@ben are you there?"})
        ann.request("chat", {"text": "good morning everybody"})
        await assistant.idle()
        assert ann.said() == [] and ben.said() == []

    scenario(test, EchoEngine())


def test_questions_are_answered_in_the_order_they_were_asked():
    async def test(hosted, assistant):
        ann, ben = Person(hosted, ANN), Person(hosted, BEN)
        ann.request("chat", {"text": "@ai one"})
        ben.request("chat", {"text": "@ai two"})
        ann.request("chat", {"text": "@ai three"})
        await assistant.idle()
        assert [m["text"] for m in ann.events("chat") if m["author"] == "ai"] == ["you said: one", "you said: three"]
        assert ben.said() == ["you said: two"]

    scenario(test, EchoEngine())


def test_a_failing_engine_is_answered_not_silent():
    async def test(hosted, assistant):
        ann = Person(hosted, ANN)
        ann.request("chat", {"text": "@ai please"})
        await assistant.idle()
        assert ann.said() == ["I could not answer: the model fell over"]

    scenario(test, BrokenEngine())


def test_it_shows_that_it_is_typing_while_it_works():
    async def test(hosted, assistant):
        ann = Person(hosted, ANN)
        ann.request("chat", {"text": "@ai hi"})
        await assistant.idle()
        typing = [e["data"]["on"] for e in ann.events("ephemeral") if e["kind"] == "typing"]
        assert typing == [True, False]

    scenario(test, EchoEngine())


def test_it_edits_with_the_same_methods_as_everybody_and_shows_where():
    async def test(hosted, assistant):
        ann = Person(hosted, ANN)
        ann.request("add_sheet", {"name": "S"})
        ann.request("chat", {"text": "@ai fill A1:A3 with 5"})
        await assistant.idle()
        cells = ann.request("cells", {"sheet": "s1", "row0": 0, "row1": 9, "col0": 0, "col1": 3})["result"]["cells"]
        assert [(r, c, v["v"]) for r, c, v in cells] == [(0, 0, 5), (1, 0, 5), (2, 0, 5)]
        entry = ann.request("log")["result"][-1]
        assert entry["author"] == "ai" and entry["summary"] == "A1 = 5, A2 = 5, A3 = 5"
        places = [e for e in ann.events("ephemeral") if e["kind"] == "presence" and e["sender"] == "ai"]
        assert places, "the others see the assistant's cursor"
        assert ann.said(), "and it says what it did"

    scenario(test)


def test_a_part_a_colleague_holds_stays_untouched_and_the_assistant_says_so():
    async def test(hosted, assistant):
        ann, ben = Person(hosted, ANN), Person(hosted, BEN)
        ann.request("add_sheet", {"name": "S"})
        region = {
            "kind": "cells",
            "range": {"first": {"row": 1, "col": 0, "sheet": "s1"}, "last": {"row": 1, "col": 0, "sheet": "s1"}},
        }
        assert ben.request("lock", {"regions": [region]})["ok"]
        ann.request("chat", {"text": "@ai fill A1:A3 with 5"})
        await assistant.idle()
        assert (
            ann.request("cells", {"sheet": "s1", "row0": 0, "row1": 9, "col0": 0, "col1": 3})["result"]["cells"] == []
        )
        assert "ben" in ann.said()[-1].casefold()

    scenario(test)


def test_a_call_that_fails_stops_the_rest_of_the_plan():
    class TwoCalls:
        def plan(self, task):
            return [Call("nothing_like_this", {}), Say("done")]

    async def test(hosted, assistant):
        ann = Person(hosted, ANN)
        ann.request("chat", {"text": "@ai go"})
        await assistant.idle()
        assert len(ann.said()) == 1 and "could not" in ann.said()[0]

    scenario(test, TwoCalls(), methods=core_methods)


def test_the_hub_gives_every_document_its_own_assistant():
    async def run():
        hub = Hub(MemoryProvider(WorkbookModel), methods=computes_methods, assistant=lambda: Assistant(EchoEngine()))
        one, two = await hub.open("one", create=True), await hub.open("two", create=True)
        assert one.assistant is not two.assistant and "ai" in one.users() and "ai" in two.users()
        assert hub.listing()[0]["online"] == 0, "the assistant is not counted as a person"

    asyncio.run(run())


# ---------------------------------------------------------------- engines that wait for a model (E7.1)
class SlowEngine:
    """Plans with ``await``: it may take long without stopping the event loop."""

    def __init__(self):
        self.running = 0
        self.most_at_once = 0

    async def plan_async(self, task: Task):
        self.running += 1
        self.most_at_once = max(self.most_at_once, self.running)
        await asyncio.sleep(0.05)
        self.running -= 1
        return [Say(f"slowly: {task.text}")]


def test_an_engine_that_plans_with_await_is_awaited():
    async def test(hosted, assistant):
        ann, ben = Person(hosted, ANN), Person(hosted, BEN)
        ann.request("chat", {"text": "@ai one"})
        ben.request("chat", {"text": "@ai two"})
        await assistant.idle()
        assert ann.said() == ["slowly: one"] and ben.said() == ["slowly: two"]
        assert assistant.engine.most_at_once == 1, "questions of one document are still answered one at a time"

    scenario(test, SlowEngine())


def test_the_event_loop_is_free_while_an_engine_waits():
    async def test(hosted, assistant):
        ann, ben = Person(hosted, ANN), Person(hosted, BEN)
        ann.request("chat", {"text": "@ai please"})
        working = asyncio.create_task(assistant.idle())
        await asyncio.sleep(0.01)
        assert ben.request("ping")["ok"] and ann.said() == [], "ben was served while the engine was still working"
        await working
        assert ann.said() == ["slowly: please"]

    scenario(test, SlowEngine())


def test_questions_beyond_the_limit_are_refused_at_once_and_say_so():
    async def test(hosted, assistant):
        ann = Person(hosted, ANN)
        for word in ("one", "two", "three", "four"):
            ann.request("chat", {"text": f"@ai {word}"})
        assert len(ann.said()) == 2 and all("busy" in s for s in ann.said()), "refusals do not wait for the others"
        await assistant.idle()
        assert [s for s in ann.said() if s.startswith("you said")] == ["you said: one", "you said: two"]
        assert sum("busy" in s for s in ann.said()) == 2

    async def run():
        hub = Hub(MemoryProvider(WorkbookModel), methods=computes_methods)
        hosted = await hub.open("plan", create=True)
        assistant = Assistant(EchoEngine(), pause=0, max_waiting=2)
        assistant.attach(hosted)
        await test(hosted, assistant)

    asyncio.run(run())
