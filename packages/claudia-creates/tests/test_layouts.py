"""A presentation has layouts, and every slide follows one of them (E10.4, D1530)."""

import pytest
from conftest import reopen

from claudia_creates import DefineLayout, RemoveLayout, SetSlideLayout, SlideModel


def test_a_new_presentation_has_one_slide_on_the_basic_layout():
    model = SlideModel.empty()
    assert model.order == ["s1"]
    assert model.layout_of("s1") == "basic"
    basic = model.layouts["basic"]
    assert (basic.name, basic.origin, basic.hidden) == ("Basic", "builtin", False)
    assert model.objects_on("basic") == []  # no placeholder, nothing else


def test_layouts_and_the_layout_of_every_slide_survive_a_snapshot():
    state = SlideModel.empty().serialize()
    assert state["layouts"] == [{"id": "basic", "name": "Basic", "origin": "builtin"}]
    assert state["slide_layouts"] == {"s1": "basic"}
    restored = SlideModel.restore(state)
    assert restored.layout_of("s1") == "basic"
    assert restored.serialize() == state


def test_a_presentation_saved_before_layouts_opens_with_every_slide_on_the_basic_layout():
    state = SlideModel.empty().serialize()
    del state["layouts"], state["slide_layouts"]
    state["slides"].append({"id": "s2"})
    restored = SlideModel.restore(state)
    assert [restored.layout_of(slide) for slide in restored.order] == ["basic", "basic"]


# -- defining layouts and putting a slide on one ----------------------------------------------------------------
def test_a_slide_can_follow_a_layout_that_was_defined_and_the_steps_can_be_undone(doc):
    seen = []
    doc.bus.subscribe(lambda event: seen.append(event.to_data()) if hasattr(event, "to_data") else None)
    doc.execute(DefineLayout("two-lists", "Two lists"), author="ana")
    doc.execute(SetSlideLayout("s1", "two-lists"), author="ana")
    assert doc.model.layout_of("s1") == "two-lists"
    assert doc.model.layouts["two-lists"].name == "Two lists"
    assert {"type": "layouts"} in seen and {"type": "slide_layout", "slide": "s1", "layout": "two-lists"} in seen
    assert reopen(doc).model.layout_of("s1") == "two-lists", "a replay of the log gives the same document"
    doc.undo("ana")
    assert doc.model.layout_of("s1") == "basic"
    doc.undo("ana")
    assert "two-lists" not in doc.model.layouts
    doc.redo("ana")
    doc.redo("ana")
    assert doc.model.layout_of("s1") == "two-lists"


def test_a_slide_follows_an_unknown_layout_never(doc):
    with pytest.raises(ValueError, match="unknown layout"):
        doc.execute(SetSlideLayout("s1", "nope"), author="ana")
    with pytest.raises(ValueError, match="unknown slide"):
        doc.execute(SetSlideLayout("nope", "basic"), author="ana")


def test_a_layout_that_a_slide_follows_cannot_be_removed_and_the_basic_layout_stays(doc):
    doc.execute(DefineLayout("two-lists", "Two lists"), author="ana")
    doc.execute(SetSlideLayout("s1", "two-lists"), author="ana")
    with pytest.raises(ValueError, match="still follows"):
        doc.execute(RemoveLayout("two-lists"), author="ana")
    with pytest.raises(ValueError, match="basic layout stays"):
        doc.execute(RemoveLayout("basic"), author="ana")


def test_a_layout_cannot_have_the_id_of_a_slide(doc):
    with pytest.raises(ValueError, match="is a slide"):
        doc.execute(DefineLayout("s1", "Mine"), author="ana")
