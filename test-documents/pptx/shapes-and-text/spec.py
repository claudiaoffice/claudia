"""A text box and the two autoshapes claudia ships (circle, rectangle) import as objects on the right slides,
with their position and size read back exactly; editing one object's text and moving/resizing another leaves
every other object alone (D219, the pptx analogue of docx's heading-styles case)."""

from __future__ import annotations

from dataclasses import replace

from claudia_creates import SlideAnchor, SlideModel
from claudia_test_documents.case import Case


def import_checks(model: SlideModel) -> None:
    assert model.slides == ["s1", "s2"]
    assert [(o.body.kind, o.body.style, o.body.paragraph.text, o.body.shape) for o in model.objects_on("s1")] == [
        ("text", "body-text", "Welcome to Claudia", None),
        ("shape", "plain-shape", "Idea", "circle"),
    ]
    s2_objects = [
        (o.body.kind, o.body.style, o.body.paragraph.text, o.body.shape, o.anchor.x, o.anchor.y, o.body.w, o.body.h)
        for o in model.objects_on("s2")
    ]
    assert s2_objects == [("shape", "plain-shape", "Box", "rectangle", 100, 500, 400, 200)]


def modify(model: SlideModel) -> SlideModel:
    circle = model.get("o2")
    new_paragraph = circle.body.paragraph.with_text("Idea (refined)", ()).written_by("ana")
    model.replace_object(circle.with_body(paragraph=new_paragraph))
    box = model.get("o3")
    moved = replace(box, anchor=SlideAnchor(box.anchor.slide, 150, 550)).with_body(w=300, h=150)
    model.replace_object(moved)
    return model


def after_checks(model: SlideModel) -> None:
    assert [o.body.paragraph.text for o in model.objects_on("s1")] == ["Welcome to Claudia", "Idea (refined)"]
    box = model.objects_on("s2")[0]
    assert (box.anchor.x, box.anchor.y, box.body.w, box.body.h) == (150, 550, 300, 150)


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks)
