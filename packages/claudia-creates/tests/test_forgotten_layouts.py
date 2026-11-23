"""A provisional layout nobody follows and nobody named is taken away with the step that made it unused (D1536)."""

from conftest import move, reopen
from test_layout_deviation import two_slides_on_a_layout_with_a_title

from claudia_creates import RenameLayout
from claudia_creates.layout_plans import deviate_layout, remove_slide_command, set_layout_command


def deviated(doc):
    """s1 on the provisional layout l1; s2 still on "two-lists"."""
    two_slides_on_a_layout_with_a_title(doc)
    doc.execute(deviate_layout(doc.model, "s1", move("h-s1", 10, 10)), author="ana")


def test_a_slide_that_follows_another_layout_takes_the_provisional_one_it_leaves_with_it(doc):
    deviated(doc)
    doc.execute(set_layout_command(doc.model, "s1", "two-lists"), author="ana")
    assert "l1" not in doc.model.layouts
    assert not [obj for obj in doc.model.objects.values() if obj.holder == "l1"]
    assert doc.model.get("h-s1").anchor.bound_to_placeholder == "title"
    doc.undo("ana")
    assert doc.model.layout_of("s1") == "l1" and len(doc.model.objects_on("l1")) == 2
    assert doc.model.placeholder_of(doc.model.get("h-s1")).holder == "l1"
    assert reopen(doc).model.serialize() == doc.model.serialize()


def test_a_deviation_of_a_deviation_does_not_leave_the_first_one_behind(doc):
    deviated(doc)
    doc.execute(deviate_layout(doc.model, "s1", move("h-s1", 20, 20)), author="ana")
    assert [layout.id for layout in doc.model.layouts] == ["basic", "two-lists", "l2"]
    doc.undo("ana")
    assert doc.model.layout_of("s1") == "l1" and doc.model.get("h-s1").anchor.x == 10


def test_a_provisional_layout_another_slide_still_follows_stays(doc):
    deviated(doc)
    doc.execute(set_layout_command(doc.model, "s2", "l1"), author="ana")
    doc.execute(set_layout_command(doc.model, "s1", "two-lists"), author="ana")
    assert doc.model.layout_of("s2") == "l1" and "l1" in doc.model.layouts


def test_a_layout_a_person_named_stays_when_nobody_follows_it(doc):
    deviated(doc)
    doc.execute(RenameLayout("l1", "Wide title"), author="ana")
    doc.execute(set_layout_command(doc.model, "s1", "two-lists"), author="ana")
    assert doc.model.layouts["l1"].name == "Wide title"


def test_removing_the_last_slide_on_a_provisional_layout_takes_the_layout_with_it(doc):
    deviated(doc)
    doc.execute(remove_slide_command(doc.model, "s1"), author="ana")
    assert "s1" not in doc.model.slides and "l1" not in doc.model.layouts
    doc.undo("ana")
    assert doc.model.layout_of("s1") == "l1" and "h-s1" in doc.model.objects and len(doc.model.objects_on("l1")) == 2
    assert reopen(doc).model.serialize() == doc.model.serialize()


def test_removing_a_slide_on_an_ordinary_layout_removes_only_the_slide(doc):
    two_slides_on_a_layout_with_a_title(doc)
    doc.execute(remove_slide_command(doc.model, "s1"), author="ana")
    assert "s1" not in doc.model.slides and "two-lists" in doc.model.layouts
