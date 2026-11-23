"""What a remote provider is first sent (CODE-80, D1568).

The first message of a question describes the document so that a model need not ask for everything. For the local model
that stays on the machine. For a remote provider it is content that leaves the server before the model has asked for
anything, so it has to say how much there is (counts and ids) and never what a person wrote (a sheet's name, a cell, a
heading, a word of a paragraph or a slide). The model *looks* for what it needs, and what it looked at is what went out.

The seams: each lens's ``orient`` (``remote=True``), and the document's assistant as the hub makes it, with the fake
Anthropic recording what it received.
"""

import asyncio

import pytest
from test_server_assistant import ANN, Person

from claudia_ai import ClaudeModel, ModelRunner
from claudia_ai.testing import FakeAnthropic, FakeModel
from claudia_composes import TextModel
from claudia_computes import AddSheet, SetCells, WorkbookModel, parse_input
from claudia_core import Document, MemoryStore
from claudia_creates import SlideModel
from claudia_server.ai_desk import ProviderDesk
from claudia_server.apps import routed_assistant_for
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.computes import computes_methods
from claudia_server.creates import creates_methods
from claudia_server.document_lens import DocumentLens
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.protocol import Context, Limits
from claudia_server.server_settings import CLAUDE
from claudia_server.slide_lens import SlideLens
from claudia_server.workbook_lens import WorkbookLens

SECRETS = ("Salaries", "Mueller", "48000", "Quarterly pay review", "Confidential plan")


def a_workbook():
    doc = Document(WorkbookModel())
    doc.execute(AddSheet("s1", "Budget"), author="ann")
    doc.execute(AddSheet("s2", "Salaries"), author="ann")
    doc.execute(SetCells("s1", ((0, 0, parse_input("Item")), (1, 1, parse_input("900")))), author="ann")
    doc.execute(SetCells("s2", ((0, 0, parse_input("Mueller")), (0, 1, parse_input("48000")))), author="ann")
    return doc


def a_text():
    doc = Document(TextModel(), store=MemoryStore())
    ctx = Context(doc, Account("ann", "owner"), Limits(), users=lambda: ["ann"], lock_seconds=30.0)
    text = "Quarterly pay review\nMueller earns 48000.\nMore"
    params = {"paragraph": "b1", "start": 0, "end_paragraph": "b1", "end": 0, "text": text}
    composes_methods.dispatch(ctx, "replace_text", params)
    composes_methods.dispatch(ctx, "set_style", {"paragraph": "b1", "style": "heading-1"})
    return doc


def a_deck():
    doc = Document(SlideModel(), store=MemoryStore())
    ctx = Context(doc, Account("ann", "owner"), Limits(), users=lambda: ["ann"], lock_seconds=30.0)
    creates_methods.dispatch(ctx, "add_slide", {})
    (slide,) = composes_slides(ctx)
    text = {"slide": slide, "kind": "text", "x": 160, "y": 120, "w": 1280, "h": 160, "text": "Confidential plan"}
    creates_methods.dispatch(ctx, "add_object", text)
    return doc


def composes_slides(ctx):
    return [s["id"] for s in creates_methods.dispatch(ctx, "slides", {})]


LENSES = {"workbook": (WorkbookLens(), a_workbook), "text": (DocumentLens(), a_text), "deck": (SlideLens(), a_deck)}


@pytest.mark.parametrize("app", LENSES)
def test_the_first_message_for_a_remote_provider_holds_no_word_a_person_wrote(app):
    lens, make = LENSES[app]
    text = lens.outline(make(), can_write=True)
    assert not [secret for secret in SECRETS + ("Budget", "Item") if secret in text]


@pytest.mark.parametrize("app", LENSES)
def test_the_first_message_for_the_local_model_is_what_it_was(app):
    lens, make = LENSES[app]
    text = lens.orient(make(), can_write=True)
    assert any(secret in text for secret in SECRETS), "the local model is still shown the start of the document"


@pytest.mark.parametrize("app", LENSES)
def test_a_remote_provider_is_told_how_much_there_is_and_how_to_look(app):
    lens, make = LENSES[app]
    text = lens.outline(make(), can_write=True)
    assert "look" in text.lower(), "it is told that it has to look, and how"
    assert any(char.isdigit() for char in text)


def test_a_workbook_is_counted_and_its_cells_are_still_explained():
    text = WorkbookLens().outline(a_workbook(), can_write=True)
    assert "2 sheets" in text and "A1 is row 0, column 0" in text
    assert "s1" in text and "s2" in text, "ids carry no meaning of their own, so the model can ask for them"


def test_one_sheet_is_one_sheet_and_a_long_list_of_sheets_is_cut_with_its_number():
    doc = Document(WorkbookModel())
    doc.execute(AddSheet("s1", "Budget"), author="ann")
    assert "1 sheet (s1)" in WorkbookLens().outline(doc, can_write=True)
    for n in range(2, 60):
        doc.execute(AddSheet(f"s{n}", f"Sheet {n}"), author="ann")
    text = WorkbookLens().outline(doc, can_write=True)
    assert "59 sheets" in text and "and 9 more" in text and "Sheet 7" not in text


def test_the_text_outline_does_not_name_the_asker_and_does_not_point_at_text_below():
    doc = a_text()
    text = DocumentLens().outline(doc, can_write=True, asker="ann")
    assert "ann" not in text and "text below" not in text
    assert "3 paragraphs, 1 heading, 0 tables" in text


def test_an_empty_workbook_is_still_told_to_add_a_sheet():
    text = WorkbookLens().outline(Document(WorkbookModel()), can_write=True)
    assert "add_sheet" in text


# -- the router: only Claude gets the short first message
KEY = "sk-ant-test-a7Q2"


class KeepsConsent:
    def __init__(self):
        self.rows = {}

    def consent_rows(self, doc_id):
        return list(self.rows.get(doc_id, []))

    def record_consent(self, doc_id, record):
        self.rows.setdefault(doc_id, []).append(record)


def served_workbook(test, desk):
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
            await test(hosted, Person(hosted, ANN))
        finally:
            await asyncio.to_thread(desk.close)

    asyncio.run(run())


def fill_in(ann):
    ann.request("add_sheet", {"name": "Budget"})
    ann.request("add_sheet", {"name": "Salaries"})
    ann.request("set_cells", {"sheet": "s2", "cells": [{"row": 0, "col": 0, "input": "Mueller"}]})
    ann.request("set_cells", {"sheet": "s1", "cells": [{"row": 0, "col": 0, "input": "Item"}]})


async def ask(hosted, ann, text):
    ann.request("chat", {"text": text})
    await hosted.assistant.idle()


def test_claude_is_sent_no_content_before_it_asks_and_what_it_asks_for_is_sent():
    answers = iter(
        [
            "```commands\n"
            '[{"method": "cells", "params": {"sheet": "s1", "row0": 0, "row1": 3, "col0": 0, "col1": 3}}]\n```',
            "Item is the header.",
        ]
    )
    with FakeAnthropic(key=KEY, answer=lambda messages: next(answers)) as fake:
        desk = ProviderDesk()
        claude = ModelRunner(ClaudeModel(KEY, "claude-sonnet-5-5", base_url=fake.url), timeout=5)
        desk.install(provider=CLAUDE, claude=claude, approved=True)

        async def test(hosted, ann):
            fill_in(ann)
            assert ann.request("set_ai_consent", {"allowed": True})["ok"]
            await ask(hosted, ann, "@ai what is in the first sheet?")

        served_workbook(test, desk)
        first, second = fake.requests
        assert "2 sheets" in first.system
        assert "Mueller" not in first.system and "Salaries" not in first.system and "Item" not in first.system
        assert "Mueller" not in second.messages[-1]["content"] and "Salaries" not in second.messages[-1]["content"]
        assert "Item" in second.messages[-1]["content"], "what it asked to look at is sent"


def test_the_local_model_is_still_shown_the_start_of_the_document():
    seen = []

    def answer(messages):
        seen.append(messages[0]["content"])
        return "ok"

    desk = ProviderDesk()
    local = ModelRunner(FakeModel(answer), timeout=5)
    desk.install(provider="local", local=local)

    async def test(hosted, ann):
        fill_in(ann)
        await ask(hosted, ann, "@ai what is in the first sheet?")

    served_workbook(test, desk)
    assert "Item" in seen[0] and "Salaries" in seen[0]


def test_whoever_builds_an_engine_gets_the_outline_for_a_remote_runner_without_saying_so():
    seen = []

    def answer(messages):
        seen.append(messages[0]["content"])
        return "ok"

    model = FakeModel(answer)
    model.remote = True
    desk = ProviderDesk()
    desk.install(provider="local", local=ModelRunner(model, timeout=5))  # a remote model in the local place

    async def test(hosted, ann):
        fill_in(ann)
        await ask(hosted, ann, "@ai what is in the first sheet?")

    served_workbook(test, desk)
    assert "2 sheets" in seen[0] and "Item" not in seen[0] and "Salaries" not in seen[0]
