"""Paragraphs inside a list and a section are blocks of the model (so they can be edited and styled), but the list
and the section themselves are structure the model does not have. Adding a paragraph before the list and emptying
the one in the section must leave the list -- its style, its items -- exactly as it was. (A block added *after* a
list item goes into that item, as a paragraph of its own: the model has no bullets to give it.)"""

from __future__ import annotations

from claudia_composes import TextModel
from claudia_core import Run
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

LIST = (
    '<text:list text:style-name="L1"><text:list-item><text:p text:style-name="Standard">Bread</text:p></text:list-item>'
    '<text:list-item><text:p text:style-name="Standard">Milk</text:p></text:list-item></text:list>'
)


def import_checks(model: TextModel) -> None:
    assert [b.text for b in model.blocks] == ["Shopping.", "Bread", "Milk", "Remember the bag.", "Done."]


def modify(model: TextModel) -> TextModel:
    model.remove(model.blocks[3].id, 0, len("Remember the bag."))  # the paragraph in the section: emptied...
    new_id = model.fresh_id()
    model.split(model.blocks[0].id, len("Shopping."), new_id, "body")  # ...and one added before the list
    model.insert(new_id, 0, "Check the list.", [Run(15, None)])
    return model


def after_checks(model: TextModel) -> None:
    assert [b.text for b in model.blocks] == ["Shopping.", "Check the list.", "Bread", "Milk", "", "Done."]


def preserve_the_list(original: bytes, edited: bytes) -> None:
    after = read_parts(edited)["content.xml"].decode()
    assert LIST in after
    assert '<text:section text:style-name="Sect1" text:name="Notes">' in after
    assert '<text:list-style style:name="L1">' in after


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["styles.xml", "meta.xml", "META-INF/manifest.xml"],
    preserve_elements=preserve_the_list,
)
