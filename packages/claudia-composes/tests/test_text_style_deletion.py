"""Deleting a style in a text (E1.10, D226): the paragraphs that have it, and the objects in it, keep their look."""

from claudia_composes import SetStyle, TextModel
from claudia_core import CreateStyle, Document, MemoryStore, StyleDef, plan_delete_style


def test_paragraphs_with_a_deleted_style_keep_their_look_through_a_stand_in_and_undo_restores_them():
    d = Document(TextModel(), store=MemoryStore())
    d.execute(CreateStyle(StyleDef("note", "Note", "a small note", "body", {"font-size": "9pt"})), author="ann")
    d.execute(SetStyle("b1", "note"), author="ann")
    look = d.model.styles.computed("note")
    before = d.model.styles.to_data()

    d.execute(plan_delete_style(d.model, "note"), author="ann")

    stand_in = d.model.block("b1").style
    assert "note" not in d.model.styles and stand_in != "note"
    assert d.model.styles.get(stand_in).to_name and d.model.styles.computed(stand_in) == look
    d.undo("ann")
    assert (d.model.block("b1").style, d.model.styles.to_data()) == ("note", before)


def test_a_built_in_style_of_a_text_can_only_be_hidden():
    import pytest

    model = TextModel()
    with pytest.raises(ValueError, match="built-in style and can only be hidden"):
        plan_delete_style(model, "quote")
    assert all(style.origin == "builtin" for style in model.styles)
