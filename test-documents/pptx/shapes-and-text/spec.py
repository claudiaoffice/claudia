"""A text box and the two autoshapes claudia ships (circle, rectangle) import as objects on the right slides,
with their position and size read back exactly; editing one object's text and moving/resizing another leaves
every other object alone (D179, the pptx analogue of docx's heading-styles case)."""

from __future__ import annotations

from dataclasses import replace

from claudia_creates import SlideModel
from claudia_test_documents.case import Case


def import_checks(model: SlideModel) -> None:
    assert model.slides == ["s1", "s2"]
    assert [(o.kind, o.style, o.text, o.shape) for o in model.objects_on("s1")] == [
        ("text", "body-text", "Welcome to Claudia", None),
        ("shape", "plain-shape", "Idea", "circle"),
    ]
    assert [(o.kind, o.style, o.text, o.shape, o.x, o.y, o.w, o.h) for o in model.objects_on("s2")] == [
        ("shape", "plain-shape", "Box", "rectangle", 100, 500, 400, 200),
    ]


def modify(model: SlideModel) -> SlideModel:
    circle = model.get("o2")
    model.replace_object(replace(circle, text="Idea (refined)"))
    box = model.get("o3")
    model.replace_object(replace(box, x=150, y=550, w=300, h=150))
    return model


def after_checks(model: SlideModel) -> None:
    assert [o.text for o in model.objects_on("s1")] == ["Welcome to Claudia", "Idea (refined)"]
    box = model.objects_on("s2")[0]
    assert (box.x, box.y, box.w, box.h) == (150, 550, 300, 150)


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks)
