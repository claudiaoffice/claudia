"""A presentation has layouts, and every slide follows one of them (E10.4, D1530)."""

from claudia_creates import SlideModel


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
