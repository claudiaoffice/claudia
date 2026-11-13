"""The AI participant of creates (E7.9, D265): model-driven like computes, writing slides and the objects that need no
binary data; without a model it says so. A ``FakeModel`` plays the language model."""

import asyncio
import json

from test_server_assistant import ANN, Person

from claudia_ai import ModelRunner
from claudia_ai.testing import FakeModel
from claudia_creates import SlideModel
from claudia_server.apps import MODEL_METHODS, NO_MODEL, model_assistant_for, stand_in_assistant_for
from claudia_server.creates import creates_methods
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.slide_lens import SlideLens, describe_object


def commands(*items):
    return "```commands\n" + json.dumps(list(items)) + "\n```"


def script(*answers):
    queue = list(answers)
    return lambda messages: queue.pop(0) if len(queue) > 1 else queue[0]


def scenario(test, model=None, assistant=None):
    """Run ``test(hosted, model)`` with a presentation that has the AI attached (the model-driven one by default)."""
    model = model or FakeModel()
    runner = ModelRunner(model, timeout=5)

    async def run():
        factory = assistant or model_assistant_for(SlideModel, runner)
        hub = Hub(MemoryProvider(SlideModel), methods=creates_methods, assistant=factory)
        hosted = await hub.open("deck", create=True)
        hosted.assistant.pause = 0
        try:
            await test(hosted, model)
        finally:
            await asyncio.to_thread(runner.close)

    asyncio.run(run())


def slide_of(person):
    """A new presentation has one empty slide."""
    (slide,) = person.request("slides", {})["result"]
    return slide["id"]


def objects(person, slide):
    return person.request("slide", {"slide": slide})["result"]["objects"]


def system_prompt(model):
    return model.calls[-1][0]["content"]


def test_creates_has_a_model_driven_ai_with_the_writes_of_d265():
    assert model_assistant_for(SlideModel, ModelRunner(FakeModel(), timeout=1)) is not None
    assert set(MODEL_METHODS["creates"]) == {
        "add_slide",
        "add_object",
        "set_text",
        "set_paragraph_style",
        "move_object",
        "resize_object",
        "remove_object",
    }
    assert not {"add_image", "export_office", "set_snap", "rotate_object"} & set(MODEL_METHODS["creates"])


def test_the_model_is_shown_the_slides_and_puts_a_text_box_on_one():
    added = {
        "method": "add_object",
        "params": {"slide": "S", "kind": "text", "x": 160, "y": 120, "w": 1280, "h": 160, "text": "Agenda"},
    }

    async def test(hosted, model):
        ann = Person(hosted, ANN)
        slide = slide_of(ann)
        added["params"]["slide"] = slide
        model.answer = script(commands(added), "I put the title on the slide.")
        ann.request("chat", {"text": "@ai give the slide a title"})
        await hosted.assistant.idle()
        assert ann.said() == ["I put the title on the slide."]
        (box,) = objects(ann, slide)
        assert box["kind"] == "text" and box["paragraph"]["text"] == "Agenda"
        first_prompt = model.calls[0][0]["content"]
        assert "1600 units wide" in first_prompt and slide in first_prompt
        report = model.calls[1][-1]["content"]
        assert "done. What changed" in report and box["id"] in report and '"Agenda"' in report

    scenario(test)


def test_in_suggest_mode_it_changes_nothing_on_a_slide_and_says_why():
    async def test(hosted, model):
        ann = Person(hosted, ANN, ai_mode="suggest")
        ann.request("chat", {"text": "@ai add a slide"})
        await hosted.assistant.idle()
        assert len(ann.request("slides", {})["result"]) == 1, "suggest: nothing written (E7.8 comes first)"
        assert ann.said(), "the asker is answered"

    scenario(test, FakeModel(lambda messages: commands({"method": "add_slide", "params": {}})))


def test_without_a_model_creates_ai_says_so_instead_of_being_absent():
    async def test(hosted, model):
        ann = Person(hosted, ANN)
        ann.request("chat", {"text": "@ai add a slide called Agenda"})
        await hosted.assistant.idle()
        assert ann.said() == [NO_MODEL]
        assert "--ai" in NO_MODEL
        assert len(ann.request("slides", {})["result"]) == 1, "only the slide a new presentation has"

    scenario(test, assistant=stand_in_assistant_for(SlideModel))


def test_an_object_is_described_with_its_id_place_size_and_words():
    data = {
        "id": "o1",
        "kind": "shape",
        "shape": "circle",
        "w": 300,
        "h": 300,
        "style": "plain-shape",
        "rotation": 0,
        "paragraph": {"style": "shape-label", "text": "Hi\nthere"},
        "anchor": {"x": 10, "y": 20},
    }
    assert (
        describe_object(data)
        == 'o1 shape (circle) at (10, 20) 300×300, style plain-shape, words shape-label: "Hi there"'
    )


def test_read_answers_are_fenced_and_leave_out_outline_paths():
    lens = SlideLens()
    shapes = lens.show("shapes", {}, {"library": [{"id": "circle", "name": "Circle", "path": "M0 0Z" * 50}]})
    assert "circle (Circle)" in shapes and "M0 0Z" not in shapes and shapes.startswith("```data")
    styles = lens.show(
        "styles", {}, [{"id": "body-text", "name": "Body text", "kind": "paragraph", "purpose": "words"}]
    )
    assert "body-text: Body text (paragraph) words" in styles
