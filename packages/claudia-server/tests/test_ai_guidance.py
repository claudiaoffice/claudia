"""The persona and the recipes of each app (E7.2, D1560–D1563): how the files are read and what they must hold.

The files are ``ai/persona.md`` and ``ai/skills.md`` in the package of each app. Nobody reads them but a language model,
so what they hold is checked here, not by eye: that they ship with the package, that every recipe names requests the
app really offers, that it has a worked example, that together they fit the size cap, and that one app's recipes do not
tell a model to use another app's requests.
"""

import asyncio
import json
from importlib import resources

import pytest
from test_server_assistant import ANN, Person

from claudia_composes import TextModel
from claudia_computes import WorkbookModel
from claudia_core.testing import ListModel
from claudia_creates import SlideModel
from claudia_server.ai_guidance import MAX_CHARACTERS, Guidance, Recipe, load_guidance, parse_recipes
from claudia_server.apps import MODEL_METHODS, NOT_FOR_A_MODEL, _model_parts, methods_for
from claudia_server.auth import Account
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.model_engine import HIDDEN_PARAMS

APPS = {"computes": WorkbookModel, "composes": TextModel, "creates": SlideModel}


def offered_by(app: str) -> set[str]:
    """Every request a model may be given in ``app``, to look or to change (what an owner in act mode is offered)."""
    parts, _ = _model_parts(APPS[app], None)
    return {tool.name for tool in parts.tools}


# -- reading skills.md
SKILLS = """Notes for the people who write this file; a model is not shown them.

## Write values
Uses: set_cells
Rows count from 0.
```commands
[{"method": "set_cells", "params": {}}]
```

## Add a sheet
Uses: add_sheet, structure
A sheet has a name.
"""


def test_a_recipe_has_a_title_the_requests_it_uses_and_its_words():
    first, second = parse_recipes(SKILLS)
    assert first.title == "Write values" and first.uses == ("set_cells",)
    assert first.text.startswith("Rows count from 0.") and "```commands" in first.text
    assert second == Recipe("Add a sheet", ("add_sheet", "structure"), "A sheet has a name.")


def test_a_recipe_that_names_no_request_is_refused_and_named():
    with pytest.raises(ValueError, match="Add a sheet"):
        parse_recipes("## Add a sheet\nA sheet has a name.\n")


def test_a_recipe_with_an_empty_uses_line_is_refused_too():
    with pytest.raises(ValueError, match="Add a sheet"):
        parse_recipes("## Add a sheet\nUses:\nA sheet has a name.\n")


# -- choosing what a person's question gets
def test_only_the_recipes_whose_requests_are_all_offered_are_given_in_the_order_of_the_file():
    guidance = Guidance("Be brief.", parse_recipes(SKILLS))
    both = guidance.skills_for({"set_cells", "add_sheet", "structure"})
    assert both.index("Write values") < both.index("Add a sheet")
    only_one = guidance.skills_for({"set_cells", "add_sheet"})
    assert "Write values" in only_one and "Add a sheet" not in only_one, "one of its requests is not offered"


def test_nothing_offered_to_change_gives_no_recipes_and_no_heading():
    assert Guidance("Be brief.", parse_recipes(SKILLS)).skills_for({"cells"}) == ""


def test_the_size_is_what_the_model_is_sent_of_persona_and_recipes():
    guidance = Guidance("Be brief.", parse_recipes(SKILLS))
    assert guidance.size() == len("Be brief.") + sum(len(r.title) + len(r.text) for r in guidance.recipes)


# -- finding the files of an app
def test_a_document_model_outside_the_apps_has_no_guidance_and_works_without():
    assert load_guidance(ListModel) == Guidance("", ())


@pytest.mark.parametrize("app", APPS)
def test_each_app_ships_both_files_in_its_own_package(app):
    package = APPS[app].__module__.split(".")[0]
    folder = resources.files(package) / "ai"
    assert (folder / "persona.md").is_file() and (folder / "skills.md").is_file()
    guidance = load_guidance(APPS[app])
    assert guidance.persona and guidance.recipes


# -- what the files must hold
@pytest.mark.parametrize("app", APPS)
def test_the_persona_and_the_recipes_together_fit_the_size_cap(app):
    assert load_guidance(APPS[app]).size() <= MAX_CHARACTERS == 6000


@pytest.mark.parametrize("app", APPS)
def test_every_recipe_names_requests_the_app_really_offers_a_model(app):
    allowed = {name for name in MODEL_METHODS[app] if name not in NOT_FOR_A_MODEL.get(app, ())}
    for recipe in load_guidance(APPS[app]).recipes:
        assert recipe.uses, recipe.title
        unknown = set(recipe.uses) - offered_by(app)
        assert not unknown, f"{app}: {recipe.title} names {sorted(unknown)}, which the model is not offered"
        assert set(recipe.uses) <= allowed, f"{app}: {recipe.title} uses a look request: it teaches how to change"


@pytest.mark.parametrize("app", APPS)
def test_every_recipe_has_a_worked_example_of_a_request(app):
    for recipe in load_guidance(APPS[app]).recipes:
        assert '```commands\n[{"method": "' in recipe.text, f"{app}: {recipe.title} shows no request"


@pytest.mark.parametrize("app", APPS)
def test_the_examples_of_a_recipe_are_requests_it_names_with_json_that_can_be_read(app):
    for recipe in load_guidance(APPS[app]).recipes:
        for block in recipe.text.split("```commands\n")[1:]:
            requests = json.loads(block.split("```", 1)[0])
            assert {r["method"] for r in requests} <= set(recipe.uses), f"{app}: {recipe.title}"


@pytest.mark.parametrize("app", APPS)
def test_an_app_is_not_taught_the_requests_of_the_other_apps(app):
    others = {name for other, names in MODEL_METHODS.items() if other != app for name in names}
    own = set(MODEL_METHODS[app]) | offered_by(app)
    text = load_guidance(APPS[app])
    mentioned = {name for name in others - own if name in text.persona + " ".join(r.text for r in text.recipes)}
    assert not mentioned, f"{app} mentions {sorted(mentioned)}"


def test_the_lines_all_three_personas_share_are_the_same_words_in_each():
    shared = {app: load_guidance(model).persona.split("\n## ", 1)[0] for app, model in APPS.items()}
    assert len(set(shared.values())) == 1, "the text before the first '## ' of each persona is the same"


def test_a_persona_tells_the_model_to_look_in_the_help_first_and_never_to_invent():
    for model in APPS.values():
        persona = load_guidance(model).persona
        assert "help_search" in persona and "help_topic" in persona
        assert "Never invent" in persona


@pytest.mark.parametrize("app", APPS)
def test_the_examples_of_a_recipe_give_the_parameters_the_request_takes_and_all_it_needs(app):
    described = methods_for(APPS[app]).describe()["methods"]
    for recipe in load_guidance(APPS[app]).recipes:
        for block in recipe.text.split("```commands\n")[1:]:
            for request in json.loads(block.split("```", 1)[0]):
                params = {p["name"]: p for p in described[request["method"]]["params"]}
                given = set(request["params"])
                assert given <= set(params), f"{app}: {recipe.title} gives {sorted(given - set(params))}"
                needed = {name for name, p in params.items() if p["required"] and name not in HIDDEN_PARAMS}
                assert needed <= given, f"{app}: {recipe.title} leaves out {sorted(needed - given)}"


# -- the examples really work: each is made as the assistant, on a document that holds what it names
def _workbook(ai):
    ai.request("set_cells", {"sheet": "s1", "cells": [{"row": 0, "col": 0, "input": "EUR"}]})
    return {}


def _text(ai):
    said = "Notes\nWe agreed in order to go in order to stay."
    return {"b3": ai.request("add_paragraphs", {"text": said})["result"]["paragraphs"][1]}


def _slides(ai):
    slide = ai.request("add_slide")["result"]["slide"]
    made = ai.request("add_object", {"slide": slide, "kind": "text", "x": 0, "y": 0, "w": 400, "h": 100, "text": "x"})
    return {"s1": slide, "o1": made["result"]["object"]}


@pytest.mark.parametrize(("app", "prepare"), [("computes", _workbook), ("composes", _text), ("creates", _slides)])
def test_every_example_of_a_recipe_is_accepted_by_the_server_as_it_stands(app, prepare):
    model_cls = APPS[app]

    async def run():
        hub = Hub(MemoryProvider(model_cls), methods=methods_for(model_cls))
        hosted = await hub.open("plan", create=True)
        if app == "computes":
            Person(hosted, ANN).request("add_sheet", {"name": "First"})
        ai = Person(hosted, Account("ai", "editor", system=True))
        ids = prepare(ai)
        refused = []
        for recipe in load_guidance(model_cls).recipes:
            for block in recipe.text.split("```commands\n")[1:]:
                for request in json.loads(block.split("```", 1)[0]):
                    params = {
                        key: ids.get(value, value) if isinstance(value, str) else value
                        for key, value in request["params"].items()
                    }
                    answer = ai.request(request["method"], params)
                    if not answer["ok"]:
                        refused.append(f"{recipe.title}: {answer['error']['message']}")
        return refused

    assert asyncio.run(run()) == []
