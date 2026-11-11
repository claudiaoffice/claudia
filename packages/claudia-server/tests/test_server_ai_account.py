"""The AI works under the account of the person who asked, and in the mode she chose (D261, D262; E7.4, E7.7).

Each question has its own effective account: the AI's allow-list narrowed by what the asker may do and by the asker's
mode, checked at dispatch. The mode travels with each ``@ai`` request (``chat``'s ``ai_mode``); a client that sends
none is an older one and gets what it always got (*act*). The server stores nothing about it.
"""

import pytest
from test_server_assistant import ANN, BEN, Person, scenario
from test_server_model_engine import commands, set_cell, system_prompt
from test_server_model_engine import scenario as model_scenario

from claudia_ai.testing import FakeModel
from claudia_server.ai_mode import ACT, DEFAULT_MODE, SUGGEST, parse_mode
from claudia_server.apps import MODEL_METHODS, SUGGEST_METHODS
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.standin_text import TextEngine


def sheet_with_a1(person):
    person.request("add_sheet", {"name": "S"})


def cell(person, row=0, col=0):
    cells = person.request("cells", {"sheet": "s1", "row0": 0, "row1": 9, "col0": 0, "col1": 3})["result"]["cells"]
    return {(r, c): v["v"] for r, c, v in cells}.get((row, col))


# -- the mode itself
def test_the_default_is_suggest_and_a_request_that_names_no_mode_gets_it():
    assert DEFAULT_MODE == SUGGEST, "D262: what a person gets who never touches the switch"
    assert parse_mode(None) == SUGGEST
    assert parse_mode("act") == ACT and parse_mode("suggest") == SUGGEST


def test_a_mode_that_is_neither_is_refused():
    with pytest.raises(ValueError, match="act.*suggest"):
        parse_mode("yolo")


def test_chat_refuses_an_unknown_mode_and_posts_nothing():
    async def test(hosted, assistant):
        ann = Person(hosted, ANN)
        reply = ann.request("chat", {"text": "@ai hi", "ai_mode": "yolo"})
        assert reply["ok"] is False and reply["error"]["code"] == "bad_request"
        assert ann.events("chat") == []

    scenario(test)


# -- act or suggest, per person and per request
def test_in_act_mode_the_ai_changes_the_sheet():
    async def test(hosted, assistant):
        ann = Person(hosted, ANN)
        sheet_with_a1(ann)
        ann.request("chat", {"text": "@ai fill A1 with 5", "ai_mode": "act"})
        await assistant.idle()
        assert cell(ann) == 5

    scenario(test)


def test_in_suggest_mode_it_writes_nothing_in_computes_and_says_why():
    async def test(hosted, assistant):
        ann = Person(hosted, ANN)
        sheet_with_a1(ann)
        before = len(ann.request("log")["result"])
        ann.request("chat", {"text": "@ai fill A1 with 5", "ai_mode": "suggest"})
        await assistant.idle()
        assert cell(ann) is None
        assert len(ann.request("log")["result"]) == before, "not even a presence entry or a failed attempt in the log"
        (answer,) = ann.said()
        assert "suggest" in answer and "act" in answer, "it says which mode stopped it and where to change that"

    scenario(test)


def test_two_people_in_one_document_can_choose_differently():
    async def test(hosted, assistant):
        ann, ben = Person(hosted, ANN), Person(hosted, BEN)
        sheet_with_a1(ann)
        ben.request("chat", {"text": "@ai fill A1 with 1", "ai_mode": "suggest"})
        ann.request("chat", {"text": "@ai fill B1 with 2", "ai_mode": "act"})
        await assistant.idle()
        assert cell(ann, 0, 0) is None, "ben chose suggest: his request changed nothing"
        assert cell(ann, 0, 1) == 2, "ann chose act: hers did"

    scenario(test)


def test_the_mode_belongs_to_the_request_not_to_the_person_for_ever():
    async def test(hosted, assistant):
        ann = Person(hosted, ANN, ai_mode=None)
        sheet_with_a1(ann)
        ann.request("chat", {"text": "@ai fill A1 with 1", "ai_mode": "act"})
        ann.request("chat", {"text": "@ai fill B1 with 2", "ai_mode": "suggest"})
        ann.request("chat", {"text": "@ai fill C1 with 3"})  # no mode: suggest, like a client that has no switch yet
        await assistant.idle()
        assert (cell(ann, 0, 0), cell(ann, 0, 1), cell(ann, 0, 2)) == (1, None, None)

    scenario(test)


def test_a_message_that_is_not_for_the_ai_leaves_no_mode_behind():
    async def test(hosted, assistant):
        ann = Person(hosted, ANN, ai_mode=None)
        sheet_with_a1(ann)
        ann.request("chat", {"text": "hello everybody", "ai_mode": "suggest"})
        ann.request("chat", {"text": "@ai fill A1 with 1", "ai_mode": "act"})
        await assistant.idle()
        assert cell(ann) == 1
        ann.request("chat", {"text": "hello again", "ai_mode": "act"})
        ann.request("chat", {"text": "@ai fill B1 with 2"})
        await assistant.idle()
        assert cell(ann, 0, 1) is None, "the earlier message was not for the AI; its mode must not govern the next one"

    scenario(test)


def test_composes_keeps_its_suggestions_in_both_modes():
    async def test(hosted, assistant):
        assert SUGGEST_METHODS["composes"] == ("suggest",)
        assert set(MODEL_METHODS["composes"]) == {"suggest"}, "no direct text edit is allowed to the AI yet"

    scenario(test, TextEngine(), methods=composes_methods, allowed_methods=MODEL_METHODS["composes"])


# -- the effective account
def test_the_effective_account_is_never_stronger_than_the_asker_nor_than_the_ai():
    ai = Account.assistant(("set_cells", "add_sheet"))
    owner = ai.acting_for("owner", ("set_cells",))
    assert owner.role == "editor", "the AI never becomes an owner, whoever asks"
    viewer = ai.acting_for("viewer", ("set_cells",))
    assert viewer.role == "viewer" and not viewer.can_write
    assert owner.system and owner.user == ai.user


def test_the_effective_allow_list_is_the_intersection():
    ai = Account.assistant(("set_cells", "add_sheet"))
    assert ai.acting_for("editor", ("set_cells", "resize_lines")).allowed_methods == frozenset({"set_cells"})
    assert ai.acting_for("editor", ()).allowed_methods == frozenset()
    unrestricted = Account.assistant()
    assert unrestricted.acting_for("editor", ("set_cells",)).allowed_methods == frozenset({"set_cells"})
    assert unrestricted.acting_for("editor", None).allowed_methods is None


def test_a_person_who_left_before_the_answer_gets_a_read_only_ai():
    async def test(hosted, assistant):
        ann = Person(hosted, ANN)
        sheet_with_a1(ann)
        ann.request("chat", {"text": "@ai fill A1 with 5", "ai_mode": "act"})
        ann.connection.close()  # gone before the worker runs
        await assistant.idle()
        reader = Person(hosted, BEN)
        assert cell(reader) is None, "nobody is there to ask for it any more: nothing is written"

    scenario(test)


# -- what the model is offered
def test_the_model_is_not_offered_tools_the_asker_may_not_use_in_her_mode():
    async def test(hosts, model, runner):
        (hosted,) = hosts
        ann = Person(hosted, ANN)
        ann.request("add_sheet", {"name": "Budget"})
        ann.request("chat", {"text": "@ai put 7 in A1", "ai_mode": "suggest"})
        await hosted.assistant.idle()
        assert "set_cells" not in system_prompt(model), "a tool that would be refused is not shown to the model"
        assert cell(ann) is None, "and if the model asks for it anyway, dispatch refuses it"
        ann.request("chat", {"text": "@ai put 7 in A1", "ai_mode": "act"})
        await hosted.assistant.idle()
        assert "set_cells" in system_prompt(model)
        assert cell(ann) == 7

    model_scenario(test, FakeModel(lambda messages: commands(set_cell(0, 0, "7"))))
