"""A change on a slide that belongs to its layout makes the slide follow a layout of its own (E10.4, E10.5, D1530)."""

from conftest import add, frame, move, reopen, resize, text_box

from claudia_core import RemoveObject
from claudia_creates import AddSlide, DefineLayout, SetSlideLayout
from claudia_creates.layout_plans import deviate_layout


def two_slides_on_a_layout_with_a_title(doc):
    """Layout "two-lists" with a title placeholder and a logo, slides s1 and s2 on it, each with a bound heading."""
    doc.execute(DefineLayout("two-lists", "Two lists"), author="ana")
    doc.execute(add(text_box("title", slide="two-lists", purpose="Title", x=100, y=50, w=800, h=100)), author="ana")
    doc.execute(add(text_box("logo", slide="two-lists", x=900, y=10, w=60, h=40)), author="ana")
    doc.execute(AddSlide("s2"), author="ana")
    for slide in ("s1", "s2"):
        doc.execute(SetSlideLayout(slide, "two-lists"), author="ana")
        doc.execute(
            add(text_box(f"h-{slide}", slide=slide, x=100, y=50, w=800, h=100, bound_to_placeholder="title")),
            author="ana",
        )


def test_resizing_a_bound_object_makes_its_slide_follow_a_provisional_copy_of_the_layout(doc):
    two_slides_on_a_layout_with_a_title(doc)
    steps = len(doc.log.to_data()["entries"])
    doc.execute(deviate_layout(doc.model, "s1", resize("h-s1", 120, 60, 700, 90)), author="ana")
    assert doc.model.layout_of("s1") == "two-lists-2"
    deviation = doc.model.layouts["two-lists-2"]
    assert (deviation.name, deviation.to_name, deviation.origin) == ("Two lists 2", True, "document")
    copy = doc.model.get(doc.model.get("h-s1").anchor.bound_to_placeholder)
    assert (copy.holder, copy.anchor.purpose) == ("two-lists-2", "Title")
    assert frame(doc, "h-s1") == (120, 60, 700, 90) == (copy.anchor.x, copy.anchor.y, copy.body.w, copy.body.h)
    assert len(doc.model.objects_on("two-lists-2")) == 2, "the logo is copied too: the layout is whole"
    # nothing else moved: the layout and the other slide are as they were
    assert doc.model.layout_of("s2") == "two-lists" and frame(doc, "h-s2") == (100, 50, 800, 100)
    assert frame(doc, "title") == (100, 50, 800, 100)
    assert len(doc.log.to_data()["entries"]) == steps + 1, "one step"
    assert reopen(doc).model.serialize() == doc.model.serialize()
    doc.undo("ana")
    assert doc.model.layout_of("s1") == "two-lists" and "two-lists-2" not in doc.model.layouts
    assert frame(doc, "h-s1") == (100, 50, 800, 100)
    assert doc.model.get("h-s1").anchor.bound_to_placeholder == "title"
    doc.redo("ana")
    assert doc.model.layout_of("s1") == "two-lists-2"


def test_a_second_deviation_gets_the_next_free_name(doc):
    two_slides_on_a_layout_with_a_title(doc)
    doc.execute(deviate_layout(doc.model, "s1", move("h-s1", 10, 10)), author="ana")
    doc.execute(deviate_layout(doc.model, "s2", move("h-s2", 20, 20)), author="ana")
    assert [doc.model.layouts[doc.model.layout_of(slide)].name for slide in ("s1", "s2")] == [
        "Two lists 2",
        "Two lists 3",
    ]


def test_removing_a_bound_object_leaves_its_placeholder_off_the_layout_of_its_slide(doc):
    two_slides_on_a_layout_with_a_title(doc)
    doc.execute(deviate_layout(doc.model, "s1", RemoveObject("h-s1")), author="ana")
    assert "h-s1" not in doc.model.objects
    assert [obj.anchor.purpose for obj in doc.model.objects_on("two-lists-2")] == [""], "only the logo is left"
    assert [obj.id for obj in doc.model.objects_on("two-lists")] == ["title", "logo"]
    assert "h-s2" in doc.model.objects
    doc.undo("ana")
    assert "h-s1" in doc.model.objects and doc.model.layout_of("s1") == "two-lists"
