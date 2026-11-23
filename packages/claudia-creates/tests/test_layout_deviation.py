"""A change on a slide that belongs to its layout makes the slide follow a layout of its own (E10.4, E10.5, D1530)."""

from conftest import add, frame, move, reopen, resize, text_box

from claudia_core import InsertText, RemoveObject
from claudia_creates import AddSlide, DefineLayout, SetSlideLayout
from claudia_creates.layout_plans import delete_layout, deviate_layout, update_layout


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


# -- the other answer: change the layout itself, for every slide that follows it ------------------------------
def test_updating_the_layout_makes_the_change_to_the_placeholder_for_every_slide_that_follows_it(doc):
    two_slides_on_a_layout_with_a_title(doc)
    doc.execute(update_layout(doc.model, "s1", resize("h-s1", 120, 60, 700, 90)), author="ana")
    assert frame(doc, "title") == (120, 60, 700, 90)
    assert frame(doc, "h-s1") == frame(doc, "h-s2") == (120, 60, 700, 90)
    assert doc.model.layout_of("s1") == "two-lists", "no layout of its own"
    doc.undo("ana")
    assert frame(doc, "h-s2") == (100, 50, 800, 100)


def test_updating_a_layout_with_a_change_to_a_layout_object_changes_that_object(doc):
    two_slides_on_a_layout_with_a_title(doc)
    doc.execute(update_layout(doc.model, "s2", move("logo", 800, 20, slide="two-lists")), author="ana")
    assert frame(doc, "logo") == (800, 20, 60, 40)


def test_deleting_a_placeholder_takes_the_empty_objects_with_it_and_frees_the_filled_ones(doc):
    two_slides_on_a_layout_with_a_title(doc)
    doc.execute(InsertText("h-s2", 0, "Hello"), author="ana")
    doc.execute(update_layout(doc.model, "s1", RemoveObject("h-s1")), author="ana")
    assert "title" not in doc.model.objects and "h-s1" not in doc.model.objects
    assert doc.model.get("h-s2").anchor.bound_to_placeholder == ""
    assert frame(doc, "h-s2") == (100, 50, 800, 100), "the words stay where they were"
    doc.undo("ana")
    assert doc.model.get("title").anchor.purpose == "Title" and "h-s1" in doc.model.objects


def test_the_slides_that_follow_a_layout_are_counted(doc):
    two_slides_on_a_layout_with_a_title(doc)
    assert doc.model.slides_following("two-lists") == ["s1", "s2"]
    assert doc.model.slides_following("basic") == []


def test_deleting_a_layout_moves_its_slides_to_another_one_and_frees_what_has_no_placeholder_there(doc):
    two_slides_on_a_layout_with_a_title(doc)
    doc.execute(delete_layout(doc.model, "two-lists", "basic"), author="ana")
    assert "two-lists" not in doc.model.layouts and "title" not in doc.model.objects
    assert [doc.model.layout_of(slide) for slide in ("s1", "s2")] == ["basic", "basic"]
    assert doc.model.get("h-s1").anchor.bound_to_placeholder == ""
    assert frame(doc, "h-s1") == (100, 50, 800, 100)
    doc.undo("ana")
    assert doc.model.layout_of("s2") == "two-lists" and doc.model.get("h-s2").anchor.bound_to_placeholder == "title"
    assert [obj.id for obj in doc.model.objects_on("two-lists")] == ["title", "logo"]
    assert reopen(doc).model.serialize() == doc.model.serialize()
