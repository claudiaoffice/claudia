"""Word's built-in styles (Title, Heading 1, Heading 2) import to claudia's style ids and back out unchanged,
and editing one paragraph's text leaves every other paragraph -- and its own style -- alone."""

from __future__ import annotations

from claudia_composes import DEFAULT_STYLE, TextModel
from claudia_core import Run
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
    # a block (a paragraph, D181) is immutable -- replace its whole text through the same remove/insert the
    # model itself builds character edits from, rather than reaching for a private part of the model.
    block_id = model.blocks[1].id
    new_text = "Introduction (revised)"
    model.remove(block_id, 0, len(model.block(block_id).text))
    model.insert(block_id, 0, new_text, [Run(len(new_text), None)])
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
