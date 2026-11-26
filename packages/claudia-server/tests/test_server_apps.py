"""Which method table and which stand-in assistant a model gets."""

import asyncio

from test_server_assistant import ANN, Person

from claudia_composes import TextModel
from claudia_computes import WorkbookModel
from claudia_core.testing import ListModel
from claudia_creates import ShapeLibrary, SlideModel
from claudia_server.apps import NO_MODEL, methods_for, model_assistant_for, stand_in_assistant_for
from claudia_server.composes import composes_methods
from claudia_server.computes import computes_methods
from claudia_server.creates import creates_methods
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.protocol import core_methods
from claudia_server.standin import ScriptedEngine
from claudia_server.standin_text import TextEngine


def test_each_app_gets_its_own_methods_and_unknown_apps_get_the_core():
    assert methods_for(WorkbookModel) is computes_methods
    assert methods_for(TextModel) is composes_methods
    assert methods_for(ListModel) is core_methods


def test_workbooks_and_texts_get_their_own_stand_in_and_others_none():
    assert stand_in_assistant_for(ListModel) is None
    engines = {type(stand_in_assistant_for(m)().engine) for m in (WorkbookModel, TextModel)}
    assert engines == {ScriptedEngine, TextEngine}


def test_presentations_get_their_methods_and_a_server_can_bring_its_own_shapes(tmp_path):
    assert methods_for(SlideModel) is creates_methods
    (tmp_path / "bar.json").write_text(
        '{"format": 1, "id": "bar", "name": "Bar", "path": "M0 0 L100 0 L100 100 L0 100 Z"}'
    )
    custom = methods_for(SlideModel, shapes=ShapeLibrary.load([tmp_path]))
    assert custom is not creates_methods and "add_object" in custom.names()
    workbooks = methods_for(WorkbookModel, shapes=ShapeLibrary.load([tmp_path]))
    assert workbooks is not computes_methods and "add_object" in workbooks.names(), "a workbook's slides have shapes"


def test_a_presentation_has_the_model_driven_ai_and_without_a_model_one_that_says_so():
    """D265 (supersedes D85): creates' AI is model-driven; with no model, `@ai` is answered that there is none."""
    assert model_assistant_for(SlideModel, runner=None) is not None

    async def ask_without_a_model():
        hosted = await Hub(MemoryProvider(SlideModel), methods=creates_methods).open("deck", create=True)
        stand_in_assistant_for(SlideModel)().attach(hosted)
        ann = Person(hosted, ANN)
        ann.request("chat", {"text": "@ai make a title slide"})
        await hosted.assistant.idle()
        return ann.said()

    assert asyncio.run(ask_without_a_model()) == [NO_MODEL]  # what it says, not which class says it
