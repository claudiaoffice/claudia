"""The prompt the model gets and the reading of what it answers."""

import json

import pytest

from claudia_ai import CALL_LIMIT, Agent, Request, ToolSpec
from claudia_ai.testing import FakeModel

SET = ToolSpec("set_cells", "set_cells(sheet: str, cells: list)", "Type into cells.")
ADD = ToolSpec("add_sheet", "add_sheet(name: str)", "Add a sheet.")
TOOLS = (SET, ADD)


def block(*items):
    return "```commands\n" + json.dumps(list(items)) + "\n```"


# ---------------------------------------------------------------- what the model is asked
def test_the_conversation_is_system_then_history_then_the_question():
    history = ({"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"})
    request = Request("ann", "what now?", context="Sheets: s1: Budget", tools=TOOLS, history=history)
    messages = Agent().messages(request)
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[-1]["content"] == "what now?"
    system = messages[0]["content"]
    assert "Sheets: s1: Budget" in system
    assert "set_cells(sheet: str, cells: list)" in system and "Type into cells." in system
    assert "```commands" in system


def test_without_tools_the_model_is_told_it_can_only_answer():
    system = Agent().messages(Request("ann", "hello"))[0]["content"]
    assert "cannot change" in system and "```commands" not in system


# ---------------------------------------------------------------- what the model answered
def test_plain_text_is_just_said():
    turn = Agent().parse("There are two sheets.", TOOLS)
    assert (turn.say, turn.calls, turn.problems) == ("There are two sheets.", [], [])


def test_a_commands_block_becomes_calls_and_leaves_the_text():
    raw = "I put 42 into A1.\n" + block({"method": "set_cells", "params": {"sheet": "s1", "cells": []}})
    turn = Agent().parse(raw, TOOLS)
    assert turn.say == "I put 42 into A1."
    assert [(c.method, c.params) for c in turn.calls] == [("set_cells", {"sheet": "s1", "cells": []})]
    assert turn.problems == []


def test_a_request_without_params_gets_empty_ones():
    turn = Agent().parse(block({"method": "add_sheet"}), TOOLS)
    assert [(c.method, c.params) for c in turn.calls] == [("add_sheet", {})]


def test_thinking_is_not_shown():
    turn = Agent().parse("<think>hmm\nlet me see</think>\nFour.", TOOLS)
    assert turn.say == "Four." and turn.problems == []


def test_running_out_of_room_while_thinking_is_reported():
    turn = Agent().parse("Sure.<think>I should first check", TOOLS)
    assert turn.say == "Sure." and "ran out of room while thinking" in turn.problems[0]


def test_a_cut_off_commands_block_changes_nothing_and_is_reported():
    turn = Agent().parse('Done.\n```commands\n[{"method": "set_cells", "par', TOOLS)
    assert turn.say == "Done." and turn.calls == []
    assert "cut off" in turn.problems[0]


@pytest.mark.parametrize("body", ["not json", '{"method": "add_sheet"}', "[1, 2"])
def test_commands_that_cannot_be_read_change_nothing(body):
    turn = Agent().parse(f"ok\n```commands\n{body}\n```", TOOLS)
    assert turn.calls == [] and "could not be read" in turn.problems[0]


def test_only_the_offered_methods_are_taken():
    raw = block(
        {"method": "add_sheet", "params": {"name": "Plan"}},
        {"method": "chat", "params": {"text": "hi"}},
        {"method": "no_such_thing"},
        "nonsense",
        {"method": "add_sheet", "params": "wrong"},
    )
    turn = Agent().parse(raw, TOOLS)
    assert [c.method for c in turn.calls] == ["add_sheet"]
    assert len(turn.problems) == 4 and any("chat" in p for p in turn.problems)


def test_no_tools_means_no_calls():
    turn = Agent().parse(block({"method": "add_sheet", "params": {"name": "x"}}), ())
    assert turn.calls == [] and turn.problems


def test_one_answer_makes_at_most_so_many_requests():
    raw = block(*[{"method": "add_sheet", "params": {"name": str(i)}} for i in range(CALL_LIMIT + 3)])
    turn = Agent().parse(raw, TOOLS)
    assert len(turn.calls) == CALL_LIMIT and "rest were dropped" in turn.problems[0]


# ---------------------------------------------------------------- asking and reading in one go
def test_respond_asks_the_model_and_reads_the_answer():
    model = FakeModel(lambda messages: "Hi " + messages[-1]["content"])
    turn = Agent().respond(model, Request("ann", "Ann"), max_new_tokens=7, stop=lambda: False)
    assert turn.say == "Hi Ann" and model.calls[0][0]["role"] == "system"
