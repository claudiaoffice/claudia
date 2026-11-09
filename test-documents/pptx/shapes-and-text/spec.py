"""A text box and the two autoshapes claudia ships (circle, rectangle) import as objects on the right slides,
with their position and size read back exactly; editing one object's text and moving/resizing another leaves
every other object alone (D179, the pptx analogue of docx's heading-styles case)."""

from __future__ import annotations

from claudia_creates import SlideModel
from claudia_test_documents.case import Case
from claudia_test_documents.edits import flat, place_object, retext_object


def import_checks(model: SlideModel) -> None:
    assert model.slides == ["s1", "s2"]
    assert [(f["kind"], f["style"], f["text"], f["shape"]) for f in map(flat, model.objects_on("s1"))] == [
        ("text", "body-text", "Welcome to Claudia", None),
        ("shape", "plain-shape", "Idea", "circle"),
    ]
    places = [
        (f["kind"], f["style"], f["text"], f["shape"], f["x"], f["y"], f["w"], f["h"])
        for f in map(flat, model.objects_on("s2"))
    ]
    assert places == [("shape", "plain-shape", "Box", "rectangle", 100, 500, 400, 200)]


def modify(model: SlideModel) -> SlideModel:
    retext_object(model, "o2", "Idea (refined)")
    return place_object(model, "o3", 150, 550, 300, 150)


def after_checks(model: SlideModel) -> None:
    assert [flat(o)["text"] for o in model.objects_on("s1")] == ["Welcome to Claudia", "Idea (refined)"]
    box = flat(model.objects_on("s2")[0])
    assert (box["x"], box["y"], box["w"], box["h"]) == (150, 550, 300, 150)


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks)
