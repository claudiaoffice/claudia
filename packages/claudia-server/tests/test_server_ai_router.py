"""Who answers @ai in a document, decided for each question (E7.11, X1).

The seam is the document's assistant as the hub makes it (``routed_assistant_for``) and the ``ProviderDesk`` the
administrator's page changes. The models are fakes; the fake Anthropic is the one of ``claudia_ai.testing``.
"""

import asyncio
import json

import pytest
from test_server_assistant import ANN, Person

from claudia_ai import ClaudeModel, ModelRunner
from claudia_ai.testing import FakeAnthropic, FakeModel
from claudia_computes import WorkbookModel
from claudia_server.ai_consent import CLAUDE
from claudia_server.ai_desk import NOTE_NOT_ALLOWED, ProviderDesk
from claudia_server.apps import routed_assistant_for
from claudia_server.computes import computes_methods
from claudia_server.hub import Hub, MemoryProvider

KEY = "sk-ant-test-a7Q2"


class KeepsConsent:
    """The directory of a server that keeps the owners' consent, in memory."""

    def __init__(self):
        self.consent = {}

    def consent_rows(self, doc_id):
        return list(self.consent.get(doc_id, []))

    def record_consent(self, doc_id, record):
        self.consent.setdefault(doc_id, []).append(record)


def served(test, desk=None):
    """Run ``test(hosted, ann, desk)`` with a workbook whose assistant asks ``desk``."""
    desk = desk or ProviderDesk()

    async def run():
        hub = Hub(
            MemoryProvider(WorkbookModel),
            methods=computes_methods,
            assistant=routed_assistant_for(WorkbookModel, desk),
            directory=KeepsConsent(),
        )
        hosted = await hub.open("plan", create=True)
        hosted.assistant.pause = 0
        try:
            await test(hosted, Person(hosted, ANN), desk)
        finally:
            await asyncio.to_thread(desk.close)

    asyncio.run(run())


async def ask(hosted, ann, text="@ai hello"):
    """The answer of the ai to ``text`` and who the chat says gave it."""
    before = len(ann.events("chat"))
    ann.request("chat", {"text": text})
    await hosted.assistant.idle()
    answer = [m for m in ann.events("chat")[before:] if m["author"] == "ai"][-1]
    return answer["text"], answer.get("via")


def runner_of(text, name="Qwen2.5-7B"):
    model = FakeModel(lambda messages: text)
    model.name = name
    return ModelRunner(model, timeout=5)


# -- X1: a document that was open when the administrator changed the provider
def test_a_document_that_was_open_when_the_provider_changed_follows_the_change():
    async def test(hosted, ann, desk):
        text, via = await ask(hosted, ann)
        assert via == {"provider": "stand-in", "label": "Scripted stand-in", "remote": False, "note": ""}

        desk.install(provider="local", local=runner_of("first model"))
        text, via = await ask(hosted, ann)
        assert text.endswith("first model")
        assert via == {"provider": "local", "label": "Qwen2.5-7B", "remote": False, "note": ""}

        for runner in desk.install(provider="local", local=runner_of("second model")):
            runner.close()  # as AiRuntime.apply does: the one that was replaced is closed
        text, _ = await ask(hosted, ann)
        assert text.endswith("second model")

    served(test)


# -- Claude answers where the administrator approved and the owners allowed it
@pytest.fixture
def anthropic():
    with FakeAnthropic(key=KEY, answer=lambda messages: "B7 divides by C7, which is empty.") as fake:
        yield fake


def claude_runner(fake, timeout=5):
    return ModelRunner(ClaudeModel(KEY, "claude-sonnet-5-5", base_url=fake.url), timeout=timeout)


def claude_desk(fake, *, local=None):
    desk = ProviderDesk()
    desk.install(provider=CLAUDE, claude=claude_runner(fake), local=local, approved=True)
    return desk


CLAUDE_VIA = {"provider": "claude", "label": "Claude", "remote": True, "note": ""}


def test_claude_answers_and_the_chat_says_so_where_the_owners_allowed_it(anthropic):
    async def test(hosted, ann, desk):
        assert ann.request("set_ai_consent", {"allowed": True})["ok"]
        text, via = await ask(hosted, ann, "@ai why is B7 an error?")
        assert text.endswith("B7 divides by C7, which is empty.")
        assert via == CLAUDE_VIA
        assert anthropic.requests[-1].messages[-1] == {"role": "user", "content": "why is B7 an error?"}

    served(test, claude_desk(anthropic))


def test_where_the_owners_did_not_allow_it_the_servers_own_provider_answers_and_says_so(anthropic):
    async def test(hosted, ann, desk):
        text, via = await ask(hosted, ann)
        assert text.endswith("the local model")
        assert via == {"provider": "local", "label": "Qwen2.5-7B", "remote": False, "note": NOTE_NOT_ALLOWED}
        assert anthropic.requests == []

    served(test, claude_desk(anthropic, local=runner_of("the local model")))


def test_the_stand_in_answers_where_claude_is_not_allowed_and_there_is_no_local_model(anthropic):
    async def test(hosted, ann, desk):
        _, via = await ask(hosted, ann)
        assert (via["provider"], via["note"]) == ("stand-in", NOTE_NOT_ALLOWED)
        assert anthropic.requests == []

    served(test, claude_desk(anthropic))


def test_the_owners_consent_alone_is_not_enough_and_not_an_error(anthropic):
    async def test(hosted, ann, desk):
        ann.request("set_ai_consent", {"allowed": True})
        text, via = await ask(hosted, ann)
        assert text.endswith("the local model") and via["note"] == "" and via["remote"] is False
        assert anthropic.requests == []

    desk = ProviderDesk()
    desk.install(provider="local", local=runner_of("the local model"), claude=claude_runner(anthropic), approved=True)
    served(test, desk)


def test_the_earlier_chat_goes_to_whoever_answers_next(anthropic):
    async def test(hosted, ann, desk):
        await ask(hosted, ann, "@ai what is in B7?")  # not allowed yet: the local model answers
        ann.request("set_ai_consent", {"allowed": True})
        await ask(hosted, ann, "@ai and why is that?")
        sent = anthropic.requests[-1].messages
        assert [m["content"] for m in sent] == ["what is in B7?", "the local model", "and why is that?"]

    served(test, claude_desk(anthropic, local=runner_of("the local model")))


# -- Claude fails: one sentence, nobody else answers, and the reason is for the administrator
UNAVAILABLE = "Claude is not available at the moment. The administrator can see why."


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        ("key_refused", "key_refused"),
        ("credit_used_up", "credit_used_up"),
        ("rate_limited", "rate_limited"),
        ("overloaded", "overloaded"),
        ("unknown_model", "unknown_model"),
    ],
)
def test_when_claude_fails_the_person_reads_one_sentence_and_the_page_knows_why(anthropic, kind, reason):
    local = runner_of("the local model")

    async def test(hosted, ann, desk):
        ann.request("set_ai_consent", {"allowed": True})
        anthropic.fail(kind)
        text, via = await ask(hosted, ann)
        assert text.endswith(UNAVAILABLE) and "credit" not in text and "key" not in text
        assert via == {**CLAUDE_VIA, "note": "no answer was made"}
        assert local.model.calls == []  # nobody else answers instead
        assert desk.health.last.reason.value == reason and desk.health.last.provider == CLAUDE

    served(test, claude_desk(anthropic, local=local))


def test_the_failure_is_forgotten_when_claude_answers_again_and_she_can_ask_again(anthropic):
    async def test(hosted, ann, desk):
        ann.request("set_ai_consent", {"allowed": True})
        anthropic.fail("overloaded")
        await ask(hosted, ann)
        assert desk.health.last is not None
        anthropic.recover()
        text, via = await ask(hosted, ann)
        assert text.endswith("B7 divides by C7, which is empty.") and via == CLAUDE_VIA
        assert desk.health.last is None

    served(test, claude_desk(anthropic))


def test_a_stalled_anthropic_ends_the_question_in_time_and_is_its_own_cause(anthropic):
    async def test(hosted, ann, desk):
        ann.request("set_ai_consent", {"allowed": True})
        anthropic.go_quiet()
        text, _ = await ask(hosted, ann)
        assert text.endswith(UNAVAILABLE)
        assert desk.health.last.reason.value == "timed_out"

    desk = ProviderDesk()
    desk.install(provider=CLAUDE, claude=claude_runner(anthropic, timeout=0.5), approved=True)
    served(test, desk)


# -- switching Claude off while it works
STOPPED = "Stopped: Claude was switched off."
STOPPED_VIA = {**CLAUDE_VIA, "note": "stopped at its next step"}


def commands(*items):
    return "```commands\n" + json.dumps(list(items)) + "\n```"


def test_when_the_owners_withdraw_consent_a_running_question_stops_at_its_next_step_and_keeps_its_work(anthropic):
    put_52 = {"method": "set_cells", "params": {"sheet": "s1", "cells": [{"row": 6, "col": 2, "input": "52"}]}}

    async def test(hosted, ann, desk):
        ann.request("add_sheet", {"name": "Budget"})
        ann.request("set_ai_consent", {"allowed": True})

        def claude_says(messages):
            hosted.consent.decide(CLAUDE, False, "Jonas", "2026-11-22T10:00:00Z")  # while it is working
            return "Typing.\n" + commands(put_52)

        anthropic.answer = claude_says
        text, via = await ask(hosted, ann, "@ai fix B7")
        assert text.endswith(STOPPED) and via == STOPPED_VIA
        assert len(anthropic.requests) == 1  # nothing more was sent for this question
        cells = ann.request("cells", {"sheet": "s1", "row0": 6, "row1": 7, "col0": 2, "col1": 3})["result"]["cells"]
        assert [(r, c, v["v"]) for r, c, v in cells] == [(6, 2, 52)]  # what was done stays

    served(test, claude_desk(anthropic))


def test_when_the_administrator_switches_provider_a_running_question_stops_the_same_way(anthropic):
    async def test(hosted, ann, desk):
        ann.request("set_ai_consent", {"allowed": True})
        anthropic.delay = 0.5
        question = asyncio.create_task(ask(hosted, ann))
        await asyncio.sleep(0.2)  # Claude is working
        for runner in desk.install(provider="local", local=runner_of("the local model")):
            await asyncio.to_thread(runner.close)
        text, via = await question
        assert text.endswith(STOPPED) and via == STOPPED_VIA
        assert desk.health.last is None  # a switch-off is not a fault of Claude's
        text, via = await ask(hosted, ann, "@ai and now?")
        assert text.endswith("the local model") and via["provider"] == "local"

    served(test, claude_desk(anthropic))


def test_after_the_stop_the_next_question_goes_to_the_servers_own_provider(anthropic):
    async def test(hosted, ann, desk):
        ann.request("set_ai_consent", {"allowed": True})
        ann.request("set_ai_consent", {"allowed": False})
        text, via = await ask(hosted, ann, "@ai and now?")
        assert text.endswith("the local model") and via["note"] == NOTE_NOT_ALLOWED
        assert anthropic.requests == []

    served(test, claude_desk(anthropic, local=runner_of("the local model")))


# -- the windows are told who answers here now
def test_the_consent_says_who_answers_here_now_and_why_it_is_not_claude(anthropic):
    async def test(hosted, ann, desk):
        before = ann.request("ai_consent")["result"]
        assert before["answering"] == {
            "provider": "local",
            "label": "Qwen2.5-7B",
            "remote": False,
            "note": NOTE_NOT_ALLOWED,
        }
        after = ann.request("set_ai_consent", {"allowed": True})["result"]
        assert after["answering"] == CLAUDE_VIA
        assert ann.request("ai_consent")["result"]["answering"] == CLAUDE_VIA

    served(test, claude_desk(anthropic, local=runner_of("the local model")))
