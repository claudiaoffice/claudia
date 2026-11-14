"""Word's list styles (List Bullet, List Number) make their paragraphs items of lists; changing the words of one
item leaves it an item and leaves the numbering part of the package as it was (D453)."""

from __future__ import annotations

from claudia_composes import TextModel
from claudia_core import Run
from claudia_test_documents.case import Case

WORDS = ["Shopping", "Bread", "Milk", "Then go home.", "Lock the door"]


def import_checks(model: TextModel) -> None:
    assert [b.text for b in model.blocks] == WORDS
    assert [b.item is not None for b in model.blocks] == [False, True, True, False, True]
    assert model.blocks[1].item.list == model.blocks[2].item.list != model.blocks[4].item.list
    assert [model.lists.get(model.blocks[n].item.list).scheme for n in (1, 4)] == ["bullets", "numbers"]


def modify(model: TextModel) -> TextModel:
    block_id = model.blocks[2].id
    model.remove(block_id, 0, len(model.block(block_id).text))
    model.insert(block_id, 0, "Oat milk", [Run(8, None)])
    return model


def after_checks(model: TextModel) -> None:
    assert [b.text for b in model.blocks] == [*WORDS[:2], "Oat milk", *WORDS[3:]]
    assert [b.item is not None for b in model.blocks] == [False, True, True, False, True]


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["word/numbering.xml", "word/styles.xml"],
)
