"""A text box and three shapes as LibreOffice writes them into a odt (the text box in the middle of a paragraph, a
circle, a triangle and a turned rectangle in the next): they come in as text box and shape objects hanging from their
character, with their words, size, turn and description. One box gets other words, the circle a new size, the turned
rectangle goes; what nobody touched comes back as LibreOffice wrote it (D465)."""

from __future__ import annotations

from dataclasses import replace

from claudia_composes import BlockAnchor, TextModel
from claudia_core import Run, VisualObject
from claudia_test_documents.case import Case


def words(model: TextModel, object_id: str) -> str:
    paragraph = model.get_object(object_id).body.paragraph
    assert paragraph is not None
    return paragraph.text


def import_checks(model: TextModel) -> None:
    kinds = [(obj.body.kind, obj.body.shape, obj.body.w, obj.body.h) for obj in model.objects.values()]
    assert kinds == [
        ("text", None, 240, 60),
        ("shape", "circle", 90, 90),
        ("shape", "triangle", 120, 100),
        ("shape", "rectangle", 120, 60),
    ]
    first, circle, _, turned = (model.get_object(f"x{number}") for number in range(1, 5))
    assert (first.anchor, first.body.description, words(model, "x1")) == (
        BlockAnchor("b2", 22),
        "A note about the boxes",
        "A note in a box",
    )
    assert (circle.anchor, circle.body.description, words(model, "x2")) == (BlockAnchor("b3", 0), "A dot", "Dot")
    assert (turned.body.rotation, words(model, "x4")) == (20, "Turned")


def modify(model: TextModel) -> TextModel:
    found = model.get_object("x1")
    text = "Other words in the box"
    paragraph = replace(found.body.paragraph, text=text, runs=(Run(len(text), None),))
    model.replace_object(VisualObject(replace(found.body, paragraph=paragraph), found.anchor))
    circle = model.get_object("x2")
    model.replace_object(VisualObject(replace(circle.body, w=150, h=150), circle.anchor))
    model.delete_object("x4")
    return model


def after_checks(model: TextModel) -> None:
    assert [obj.body.shape for obj in model.objects.values()] == [None, "circle", "triangle"]
    assert words(model, "x1") == "Other words in the box"
    circle = model.get_object("x2")
    assert ((circle.body.w, circle.body.h), circle.anchor) == ((150, 150), BlockAnchor("b3", 0))
    assert words(model, "x3") == "Up"
    assert model.blocks[2].text == "Nothing here changes."


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks)
