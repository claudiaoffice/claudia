"""What the model is told in each app (CODE-81, E7.2).

The seam is the system message a model receives when somebody writes ``@ai ...`` in a document of each app, built from
the real parts of the server (the app's lens, its requests, its persona and recipes), with a scripted model recording
what it was sent. These tests say what reaches the model, not whether a model obeys it.
"""

import asyncio
import json

import pytest
from test_server_assistant import ANN, Person

from claudia_ai import ModelRunner
from claudia_ai.testing import FakeModel
from claudia_composes import TextModel
from claudia_computes import WorkbookModel
from claudia_creates import SlideModel
from claudia_server.apps import model_assistant_for
from claudia_server.composes import composes_methods
from claudia_server.computes import computes_methods
from claudia_server.creates import creates_methods
from claudia_server.hub import Hub, MemoryProvider

APPS = {
    "computes": (WorkbookModel, computes_methods),
    "composes": (TextModel, composes_methods),
    "creates": (SlideModel, creates_methods),
}


def system_message(app: str) -> str:
    """The system message the model gets for a question in a new document of ``app``, from an owner who may write."""
    model_cls, methods = APPS[app]
    model = FakeModel(lambda messages: "ok")
    runner = ModelRunner(model, timeout=5)

    async def run():
        hub = Hub(MemoryProvider(model_cls), methods=methods, assistant=model_assistant_for(model_cls, runner))
        hosted = await hub.open("plan", create=True)
        hosted.assistant.pause = 0
        try:
            Person(hosted, ANN).request("chat", {"text": "@ai hello"})
            await hosted.assistant.idle()
        finally:
            await asyncio.to_thread(runner.close)

    asyncio.run(run())
    return model.calls[0][0]["content"]


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
