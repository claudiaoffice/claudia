"""What the model is told in each app (CODE-81, E7.2).

The seam is the system message a model receives when somebody writes ``@ai ...`` in a document of each app, built from
the real parts of the server (the app's lens, its requests, its persona and skills), with a scripted model recording
what it was sent. These tests say what reaches the model, not whether a model obeys it.
"""

import asyncio
import json
import re

import pytest
from test_server_assistant import ANN, BEN, Person

from claudia_ai import ModelRunner
from claudia_ai.testing import FakeModel
from claudia_composes import TextModel
from claudia_computes import WorkbookModel
from claudia_creates import SlideModel
from claudia_server.ai_guidance import load_guidance
from claudia_server.apps import model_assistant_for
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.computes import computes_methods
from claudia_server.creates import creates_methods
from claudia_server.hub import Hub, MemoryProvider

APPS = {
    "computes": (WorkbookModel, computes_methods),
    "composes": (TextModel, composes_methods),
    "creates": (SlideModel, creates_methods),
}


def system_message(app: str, who: Account = ANN, mode: str = "act") -> str:
    """The system message the model gets for a question in a new document of ``app`` from ``who``, in ``mode``."""
    return asked(app, "@ai hello", FakeModel(lambda messages: "ok"), who, mode).calls[0][0]["content"]


def asked(app: str, text: str, model: FakeModel, who: Account = ANN, mode: str = "act", then=None) -> FakeModel:
    """Write ``text`` in the chat of a new document of ``app`` as ``who`` and let the scripted ``model`` answer.

    ``then`` is called with the document and the person once the question is answered."""
    model_cls, methods = APPS[app]
    runner = ModelRunner(model, timeout=5)

    async def run():
        hub = Hub(MemoryProvider(model_cls), methods=methods, assistant=model_assistant_for(model_cls, runner))
        hosted = await hub.open("plan", create=True)
        hosted.assistant.pause = 0
        try:
            person = Person(hosted, who, ai_mode=mode)
            person.request("chat", {"text": text})
            await hosted.assistant.idle()
            if then is not None:
                then(hosted, person)
        finally:
            await asyncio.to_thread(runner.close)

    asyncio.run(run())
    return model


def requests_shown(text: str) -> list[dict]:
    """Every request the text shows as an example, read as JSON (an example that cannot be read raises)."""
    text = text.replace("{...}", "{}")
    decoder = json.JSONDecoder()
    found, at = [], text.find('{"method"')
    while at != -1:
        request, end = decoder.raw_decode(text, at)
        found.append(request)
        at = text.find('{"method"', end)
    return found


@pytest.mark.parametrize("app", APPS)
def test_the_requests_shown_to_the_model_are_written_as_json_in_every_app(app):
    """CODE-81: a doubled brace in the prompt is what the model copies, and then nothing parses."""
    text = system_message(app)
    assert "{{" not in text
    assert requests_shown(text), "the form of a request is shown"


# -- the persona and the skills (E7.2)
# A viewer cannot write in the chat at all (it needs the editor role), so the person who "may only look" is an editor in
# suggest mode in an app where nothing can be proposed yet (computes, creates).
TITLES = {app: [skill.title for skill in load_guidance(model).skills] for app, (model, _) in APPS.items()}


@pytest.mark.parametrize("app", APPS)
def test_the_model_is_given_the_persona_of_the_app_it_works_in(app):
    persona = load_guidance(APPS[app][0]).persona
    assert persona and persona in system_message(app)


@pytest.mark.parametrize("app", APPS)
def test_an_owner_who_may_change_things_is_given_every_skill_of_the_app(app):
    text = system_message(app)
    assert [title for title in TITLES[app] if f"{title}:" not in text] == []


@pytest.mark.parametrize("app", ["computes", "creates"])
def test_a_person_who_may_only_look_is_taught_no_skill_for_changing_but_still_who_the_ai_is(app):
    text = system_message(app, BEN, "suggest")
    assert "can only look" in text and "Requests that change" not in text
    assert [title for title in TITLES[app] if f"{title}:" in text] == []
    assert load_guidance(APPS[app][0]).persona in text


@pytest.mark.parametrize("app", APPS)
def test_an_app_is_not_taught_the_skills_of_another(app):
    text = system_message(app)
    assert [t for other, titles in TITLES.items() if other != app for t in titles if f"\n{t}:" in text] == []


def test_in_suggest_mode_a_text_is_taught_to_propose_and_not_to_rewrite():
    text = system_message("composes", mode="suggest")
    assert "Propose a rewrite:" in text and "\nRewrite a passage:" not in text


@pytest.mark.parametrize("app", APPS)
def test_the_help_is_offered_as_a_way_to_look_in_every_app_to_an_owner_and_to_somebody_who_may_only_look(app):
    for who, mode in ((ANN, "act"), (BEN, "suggest")):
        text = system_message(app, who, mode)
        looks = text.split("Requests that only look", 1)[1].split("Requests that change", 1)[0]
        assert "help_search(" in looks and "help_topic(" in looks


def commands_block(method: str, **params) -> str:
    return "```commands\n" + json.dumps([{"method": method, "params": params}]) + "\n```"


def test_the_help_is_read_from_the_topic_and_is_not_fenced_as_data():
    seen: list[str] = []

    def answer(messages):
        seen.append(messages[-1]["content"])
        if len(seen) == 1:
            return "Let me look.\n" + commands_block("help_search", query="style")
        if len(seen) == 2:
            found = next(line for line in seen[1].splitlines() if " — " in line)
            return commands_block("help_topic", id=found.removeprefix("- ").split(" — ")[0])
        return "Insert it from the menu."

    seen_after: dict = {}

    def check(hosted, person):
        seen_after["said"] = person.said()
        seen_after["text"] = [p["text"] for p in person.request("read_paragraphs")["result"]["paragraphs"]]

    model = asked("composes", "@ai how do I change how a heading looks?", FakeModel(answer), BEN, "suggest", then=check)
    assert seen_after == {"said": ["Insert it from the menu."], "text": [""]}, (
        "the answer came, the text did not change"
    )
    assert len(model.calls) == 3
    assert "```data" not in seen[1] and "```data" not in seen[2], "the help is the product's own text"
    assert "composes.editing-a-style" in seen[1] and "how a style looks" in seen[2].lower()


# -- a request made in the form the model was shown is carried out, in the apps where it failed on 2026-11-23 (CODE-81)
def test_a_text_gets_a_long_story_as_paragraphs_in_the_document():
    story = " ".join(f"word{n}" for n in range(300))
    script = iter([commands_block("add_paragraphs", text=story), "I wrote it."])
    seen = {}

    def check(hosted, person):
        paragraphs = person.request("read_paragraphs", {"count": 50})["result"]["paragraphs"]
        seen["words"] = len(" ".join(p["text"] for p in paragraphs).split())
        seen["said"] = person.said()

    asked("composes", "@ai write me a story about a boy, 300 words", FakeModel(lambda m: next(script)), then=check)
    assert seen == {"words": 300, "said": ["I wrote it."]}


def test_a_presentation_gets_the_text_box_and_the_chat_shows_no_list_of_requests():
    script = iter([commands_block("add_slide"), None, "Added."])
    seen = {}

    def reply(messages):
        step = next(script)
        if step is not None:
            return step
        slide = re.search(r"\bs[0-9a-f]+\b", messages[-1]["content"]).group(0)  # the id the report of add_slide gave
        return commands_block("add_object", slide=slide, kind="text", x=160, y=120, w=1280, h=160, text="Hello")

    def check(hosted, person):
        slide = person.request("slides")["result"][0]["id"]
        seen["texts"] = [o["paragraph"]["text"] for o in person.request("slide", {"slide": slide})["result"]["objects"]]
        seen["said"] = person.said()

    asked("creates", "@ai add a textbox and write Hello in it", FakeModel(reply), then=check)
    assert seen == {"texts": ["Hello"], "said": ["Added."]}
