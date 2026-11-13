"""A rendered text container in a text: it hangs from a paragraph and follows the words, like any composes object
(D340, D179). A formula in a paragraph must stay at its word while somebody types in front of it."""

import pytest

from claudia_composes import BlockAnchor, InsertText, TextModel
from claudia_core import (
    AddObject,
    Batch,
    DefineRendering,
    Document,
    MemoryStore,
    ObjectBody,
    RenderedDefinition,
    UpdateRendering,
)


def text_with_a_formula(words: str = "Einstein wrote E = mc2 once") -> Document:
    d = Document(TextModel(), store=MemoryStore())
    d.execute(InsertText("b1", 0, words), author="ann")
    body = ObjectBody("c1", "rendered", 120, 40, "plain-image", rendered="r1")
    definition = RenderedDefinition("r1", "latex", "E = mc^2")
    d.execute(
        Batch((DefineRendering(definition.to_data()), AddObject(body, BlockAnchor("b1", 15).to_data()))), author="ann"
    )
    return d


def test_a_container_hangs_from_a_paragraph_and_follows_the_words_in_front_of_it():
    d = text_with_a_formula()
    d.execute(InsertText("b1", 0, "Albert "), author="ben")
    assert d.model.objects["c1"].anchor.offset == 22
    d.undo("ben")
    assert d.model.objects["c1"].anchor.offset == 15


def test_a_container_in_a_text_refuses_a_definition_nobody_knows():
    d = Document(TextModel(), store=MemoryStore())
    d.execute(InsertText("b1", 0, "hello"), author="ann")
    body = ObjectBody("c1", "rendered", 120, 40, "plain-image", rendered="r1")
    with pytest.raises(ValueError, match="does not know the rendering"):
        d.execute(AddObject(body, BlockAnchor("b1", 2).to_data()), author="ann")


def test_the_text_of_the_container_is_kept_in_the_snapshot_and_in_the_log():
    d = text_with_a_formula()
    d.execute(UpdateRendering("r1", RenderedDefinition("r1", "latex", r"\sqrt{2}").to_data()), author="ann")
    state = d.model.serialize()
    assert TextModel.restore(state).renderings["r1"].source == r"\sqrt{2}"
    del state["renderings"]
    assert TextModel.restore(state).renderings == {}
