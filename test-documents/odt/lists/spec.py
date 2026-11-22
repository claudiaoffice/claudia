"""A numbered list that goes on after a paragraph is one list of the model, its nested item is at level 1, and an
item added to its second piece is an item of the same list: the file says it with a list that continues the first.
What the edit does not touch (the style sheets, the list style) stays as it was (D453)."""

from __future__ import annotations

from claudia_composes import TextModel
from claudia_core import ListItem, Run
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

STEPS = ["Open the box", "Cut the tape", "Take out the parts", "Mind the screws.", "Screw it together"]


def import_checks(model: TextModel) -> None:
    assert [b.text for b in model.paragraphs] == STEPS
    assert [(b.item.list, b.item.level) if b.item else None for b in model.paragraphs] == [
        ("l1", 0), ("l1", 1), ("l1", 0), None, ("l1", 0)
    ]  # fmt: skip
    assert model.lists.get("l1").scheme == "numbers"


def modify(model: TextModel) -> TextModel:
    new_id = model.fresh_id()
    last = model.paragraphs[-1]
    model.split(last.id, len(last.text), new_id, "body")  # a paragraph after the last item...
    model.insert(new_id, 0, "Check it stands", [Run(15, None)])
    model.set_item(new_id, ListItem("l1", 0))  # ...made an item of the same list
    return model


def after_checks(model: TextModel) -> None:
    assert [b.text for b in model.paragraphs] == [*STEPS, "Check it stands"]
    assert [b.item.list for b in model.paragraphs if b.item] == ["l1"] * 5  # one list, whatever lies between its items


def the_list_style_stays(original: bytes, edited: bytes) -> None:
    assert '<text:list-style style:name="Steps">' in read_parts(edited)["content.xml"].decode()


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["styles.xml", "meta.xml", "META-INF/manifest.xml"],
    preserve_elements=the_list_style_stays,
)
