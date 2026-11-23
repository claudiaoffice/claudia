"""Naming, hiding and ordering the layouts of a presentation (E10.4, D1530)."""

import pytest
from conftest import reopen

from claudia_creates import AddSlide, DefineLayout, HideLayout, MoveLayout, RenameLayout


def test_a_layout_is_renamed_and_a_provisional_one_is_named_by_it(doc):
    doc.execute(DefineLayout("two-lists", "Two lists 2", to_name=True), author="ana")
    doc.execute(RenameLayout("two-lists", "Two lists"), author="ana")
    layout = doc.model.layouts["two-lists"]
    assert (layout.name, layout.to_name) == ("Two lists", False)
    assert reopen(doc).model.layouts["two-lists"] == layout
    doc.undo("ana")
    layout = doc.model.layouts["two-lists"]
    assert (layout.name, layout.to_name) == ("Two lists 2", True)


def test_no_two_layouts_have_the_same_name_whatever_the_case(doc):
    doc.execute(DefineLayout("a", "Agenda"), author="ana")
    with pytest.raises(ValueError, match="name"):
        doc.execute(DefineLayout("b", "agenda"), author="ana")
    doc.execute(DefineLayout("b", "Budget"), author="ana")
    with pytest.raises(ValueError, match="name"):
        doc.execute(RenameLayout("b", "AGENDA"), author="ana")
    doc.execute(RenameLayout("b", "BUDGET"), author="ana")  # its own name in other letters is fine


def test_a_layout_is_hidden_and_shown_again_even_the_built_in_one(doc):
    doc.execute(HideLayout("basic", True), author="ana")
    assert doc.model.layouts["basic"].hidden
    doc.undo("ana")
    assert not doc.model.layouts["basic"].hidden


def test_layouts_are_moved_in_the_list_and_the_first_visible_one_is_the_first_of_a_new_deck(doc):
    doc.execute(DefineLayout("agenda", "Agenda"), author="ana")
    doc.execute(MoveLayout("agenda", 0), author="ana")
    assert doc.model.layouts.ids() == ["agenda", "basic"]
    doc.undo("ana")
    assert doc.model.layouts.ids() == ["basic", "agenda"]
    doc.execute(HideLayout("basic", True), author="ana")
    assert doc.model.layouts.first_visible().id == "agenda"
    doc.execute(AddSlide("s0", 0), author="ana")
    assert doc.model.layout_of("s0") == "agenda", "a slide that has no slide before it follows the first visible layout"
    doc.execute(AddSlide("s9"), author="ana")
    assert doc.model.layout_of("s9") == "basic", "a slide follows the one before it, hidden layout or not"
