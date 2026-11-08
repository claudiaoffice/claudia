"""Word's built-in styles (Title, Heading 1, Heading 2) import to claudia's style ids and back out unchanged,
and editing one paragraph's text leaves every other paragraph -- and its own style -- alone."""

from __future__ import annotations

from claudia_composes import DEFAULT_STYLE, TextModel
from claudia_test_documents.case import Case


def import_checks(model: TextModel) -> None:
    assert [(b.style, b.text) for b in model.blocks] == [
        ("title", "Claudia Field Notes"),
        ("heading-1", "Introduction"),
        (DEFAULT_STYLE, "This is the introduction."),
        ("heading-2", "Background"),
        (DEFAULT_STYLE, "More background text."),
    ]


def modify(model: TextModel) -> TextModel:
    model.blocks[1].text = "Introduction (revised)"
    return model


def after_checks(model: TextModel) -> None:
    assert [(b.style, b.text) for b in model.blocks] == [
        ("title", "Claudia Field Notes"),
        ("heading-1", "Introduction (revised)"),
        (DEFAULT_STYLE, "This is the introduction."),
        ("heading-2", "Background"),
        (DEFAULT_STYLE, "More background text."),
    ]


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks)
