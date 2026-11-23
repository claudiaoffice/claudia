"""A presentation has layouts, and every slide follows one of them (E10.4, D1530)."""

import pytest
from conftest import add, frame, move, reopen, resize, text_box

from claudia_core import RemoveObject
from claudia_creates import AddSlide, DefineLayout, RemoveLayout, RemoveSlide, SetSlideLayout, SlideModel


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


def test_a_new_slide_follows_the_layout_of_the_slide_before_it(doc):
    doc.execute(DefineLayout("two-lists", "Two lists"), author="ana")
    doc.execute(SetSlideLayout("s1", "two-lists"), author="ana")
    doc.execute(AddSlide("s2"), author="ana")
    doc.execute(AddSlide("s0", 0), author="ana")
    assert [doc.model.layout_of(slide) for slide in doc.model.order] == ["basic", "two-lists", "two-lists"]


def test_a_removed_slide_comes_back_on_its_layout(doc):
    doc.execute(DefineLayout("two-lists", "Two lists"), author="ana")
    doc.execute(AddSlide("s2"), author="ana")
    doc.execute(SetSlideLayout("s2", "two-lists"), author="ana")
    doc.execute(RemoveSlide("s2"), author="ana")
    doc.undo("ana")
    assert doc.model.layout_of("s2") == "two-lists"
    assert reopen(doc).model.layout_of("s2") == "two-lists"


def test_a_layout_holds_a_placeholder_with_its_purpose_and_it_survives_snapshot_and_replay(doc):
    doc.execute(DefineLayout("two-lists", "Two lists"), author="ana")
    doc.execute(add(text_box("title", slide="two-lists", purpose="Title")), author="ana")
    placeholder = doc.model.get("title")
    assert (placeholder.holder, placeholder.anchor.purpose, placeholder.anchor.bound_to_placeholder) == (
        "two-lists",
        "Title",
        "",
    )
    assert [obj.id for obj in doc.model.objects_on("two-lists")] == ["title"]
    assert doc.model.objects_on("s1") == []
    state = doc.model.serialize()
    assert SlideModel.restore(state).get("title").anchor.purpose == "Title"
    assert SlideModel.restore(state).serialize() == state
    assert reopen(doc).model.get("title").anchor.purpose == "Title"
    doc.undo("ana")
    assert "title" not in doc.model.objects


def test_a_slide_object_can_be_bound_to_a_placeholder_of_the_layout_its_slide_follows(doc):
    doc.execute(DefineLayout("two-lists", "Two lists"), author="ana")
    doc.execute(add(text_box("title", slide="two-lists", purpose="Title")), author="ana")
    doc.execute(SetSlideLayout("s1", "two-lists"), author="ana")
    doc.execute(add(text_box("heading", bound_to_placeholder="title")), author="ana")
    assert doc.model.get("heading").anchor.bound_to_placeholder == "title"
    assert doc.model.get("heading").anchor.to_data()["bound_to_placeholder"] == "title"
    assert "purpose" not in doc.model.get("heading").anchor.to_data(), "only what is set is written"


def two_lists_with_a_heading(doc):
    """A layout with a title placeholder, slide s1 on it with a heading bound to it, and s2 on it with another."""
    doc.execute(DefineLayout("two-lists", "Two lists"), author="ana")
    doc.execute(add(text_box("title", slide="two-lists", purpose="Title", x=100, y=50, w=800, h=100)), author="ana")
    doc.execute(AddSlide("s2"), author="ana")
    doc.execute(SetSlideLayout("s1", "two-lists"), author="ana")
    doc.execute(SetSlideLayout("s2", "two-lists"), author="ana")
    doc.execute(add(text_box("h1", slide="s1", x=100, y=50, w=800, h=100, bound_to_placeholder="title")), author="ana")
    doc.execute(add(text_box("h2", slide="s2", x=100, y=50, w=800, h=100, bound_to_placeholder="title")), author="ana")


def test_objects_bound_to_a_placeholder_follow_it_when_it_moves_or_is_resized(doc):
    seen = []
    doc.bus.subscribe(lambda event: seen.append(event.to_data()) if hasattr(event, "to_data") else None)
    two_lists_with_a_heading(doc)
    seen.clear()
    doc.execute(move("title", 200, 80, slide="two-lists"), author="ana")
    assert frame(doc, "h1") == (200, 80, 800, 100) and frame(doc, "h2") == (200, 80, 800, 100)
    assert {e["holder"] for e in seen if e["type"] == "objects"} >= {"two-lists", "s1", "s2"}
    doc.execute(resize("title", 200, 80, 600, 90, slide="two-lists"), author="ana")
    assert frame(doc, "h1") == (200, 80, 600, 90)
    assert reopen(doc).model.get("h2").body.w == 600, "a replay settles to the same document"
    doc.undo("ana")
    doc.undo("ana")
    assert frame(doc, "h1") == (100, 50, 800, 100) and frame(doc, "h2") == (100, 50, 800, 100)
    doc.redo("ana")
    assert frame(doc, "h1") == (200, 80, 800, 100)


def test_an_object_is_free_where_it_stands_when_its_placeholder_is_gone_or_its_slide_follows_another_layout(doc):
    two_lists_with_a_heading(doc)
    doc.execute(SetSlideLayout("s2", "basic"), author="ana")
    assert doc.model.get("h2").anchor.bound_to_placeholder == ""
    assert frame(doc, "h2") == (100, 50, 800, 100)
    doc.execute(RemoveObject("title"), author="ana")
    assert doc.model.get("h1").anchor.bound_to_placeholder == ""
    assert frame(doc, "h1") == (100, 50, 800, 100)
    doc.undo("ana")  # the placeholder is back, but nobody binds to it again by themselves
    assert doc.model.get("h1").anchor.bound_to_placeholder == ""
    assert reopen(doc).model.serialize() == doc.model.serialize()


def test_changing_the_layout_of_a_slide_moves_its_objects_to_the_placeholder_with_the_same_purpose(doc):
    two_lists_with_a_heading(doc)
    doc.execute(DefineLayout("title-only", "Title only"), author="ana")
    doc.execute(add(text_box("t", slide="title-only", purpose="Title", x=300, y=200, w=500, h=60)), author="ana")
    doc.execute(add(text_box("free", slide="s1", x=10, y=10, w=50, h=50)), author="ana")
    doc.execute(doc.model.set_layout_command("s1", "title-only"), author="ana")
    assert doc.model.layout_of("s1") == "title-only"
    assert doc.model.get("h1").anchor.bound_to_placeholder == "t"
    assert frame(doc, "h1") == (300, 200, 500, 60)
    assert frame(doc, "free") == (10, 10, 50, 50), "a free object stays where it is"
    doc.execute(doc.model.set_layout_command("s1", "basic"), author="ana")
    assert doc.model.get("h1").anchor.bound_to_placeholder == ""
    assert frame(doc, "h1") == (300, 200, 500, 60), "no placeholder with that purpose: a free box where it stands"
    doc.undo("ana")
    doc.undo("ana")
    assert doc.model.get("h1").anchor.bound_to_placeholder == "title"
    assert frame(doc, "h1") == (100, 50, 800, 100)
    assert reopen(doc).model.serialize() == doc.model.serialize()
