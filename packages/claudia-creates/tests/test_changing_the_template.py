"""Giving a finished presentation the look of a template, or the whole template (E10.4, E10.23, D1531)."""

import pytest
from conftest import add, frame, image_asset, put_image, reopen, text_box

from claudia_core import ChangeStyle, CreateStyle, Document, MemoryStore, SetRole, StyleDef
from claudia_creates import AddSlide, DefineLayout, SetSlideLayout, SlideModel, TemplateInfo, check_template
from claudia_creates.template import (
    ChangePreview,
    plan_change_template,
    plan_change_theme,
    preview_change,
    template_state,
)

TALK = TemplateInfo("Conference talk", "Talks of twenty minutes", "en")


@pytest.fixture
def other(clock):
    """A second document, in which the template is made."""
    return Document(SlideModel.empty(), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)


def a_talk_template(doc):
    """A template with layouts "Two lists" (title placeholder, logo) and "Title only", and its own look."""
    doc.execute(DefineLayout("l-two", "Two lists"), author="ana")
    doc.execute(add(text_box("t-title", slide="l-two", purpose="Title", x=300, y=40, w=700, h=90)), author="ana")
    put_image(doc, "t-logo", slide="l-two", asset=image_asset(30, 30), x=1500, y=10, w=60, h=60)
    doc.execute(DefineLayout("l-only", "Title only"), author="ana")
    doc.execute(add(text_box("t-only", slide="l-only", purpose="Title", x=50, y=400, w=1500, h=120)), author="ana")
    doc.execute(ChangeStyle("body-text", {"font-size": "30px"}), author="ana")
    doc.execute(SetRole("accent", "#aa0000"), author="ana")
    doc.execute(
        CreateStyle(StyleDef("big-number", "Big number", "one number", "body-text", {"font-size": "120px"})),
        author="ana",
    )
    doc.execute(AddSlide("s2"), author="ana")  # the slides are not part of the template
    return check_template(template_state(doc.model, TALK))


def a_finished_deck(doc):
    """A deck on its own layouts "Two lists" and "Title only" and "Wide list", slides with a bound title each."""
    doc.execute(DefineLayout("two", "two lists"), author="ana")
    doc.execute(add(text_box("p-title", slide="two", purpose="Title", x=100, y=50, w=800, h=100)), author="ana")
    doc.execute(DefineLayout("only", "Title only"), author="ana")
    doc.execute(add(text_box("p-sub", slide="two", purpose="Subtitle", x=100, y=160, w=800, h=60)), author="ana")
    doc.execute(add(text_box("p-only", slide="only", purpose="Title", x=10, y=10, w=300, h=30)), author="ana")
    doc.execute(DefineLayout("wide", "Wide list"), author="ana")
    doc.execute(add(text_box("p-wide", slide="wide", purpose="List", x=0, y=0, w=1600, h=900)), author="ana")
    doc.execute(AddSlide("s2"), author="ana")
    doc.execute(AddSlide("s3"), author="ana")
    for slide, layout, placeholder in (("s1", "two", "p-title"), ("s2", "only", "p-only"), ("s3", "wide", "p-wide")):
        doc.execute(SetSlideLayout(slide, layout), author="ana")
        doc.execute(
            add(text_box(f"h-{slide}", slide=slide, text=f"Words of {slide}", bound_to_placeholder=placeholder)),
            author="ana",
        )
        doc.execute(add(text_box(f"free-{slide}", slide=slide, x=5, y=5, w=40, h=40, text="mine")), author="ana")
    doc.execute(
        add(text_box("h-sub", slide="s1", text="A subtitle", bound_to_placeholder="p-sub")),
        author="ana",
    )
    doc.execute(ChangeStyle("body-text", {"font-size": "44px"}), author="ana")
    doc.execute(CreateStyle(StyleDef("quote", "Quote", "", "body-text", {"font-style": "italic"})), author="ana")


# -- Change theme: the styles and the colours only ------------------------------------------------------------------
def test_change_theme_gives_the_styles_and_colours_of_the_template_and_leaves_the_layouts_alone(doc, other):
    template = a_talk_template(other)
    a_finished_deck(doc)
    before = doc.model.serialize()
    doc.execute(plan_change_theme(doc.model, template), author="ana")
    assert doc.model.styles.get("body-text").css["font-size"] == "30px"
    assert doc.model.palette.get("accent").colour == "#AA0000"
    assert doc.model.styles.get("big-number").origin == "template"
    assert doc.model.styles.get("quote").css == {"font-style": "italic"}, "the deck's own style is not touched"
    after = doc.model.serialize()
    assert (after["layouts"], after["slide_layouts"], after["objects"]) == (
        before["layouts"],
        before["slide_layouts"],
        before["objects"],
    )
    assert doc.model.template is None, "changing the look does not change what the deck came from"
    doc.undo("ana")
    assert doc.model.serialize() == before, "one Undo takes it all back"


def test_changing_to_the_theme_the_deck_has_does_nothing(doc, other):
    template = a_talk_template(other)
    doc.execute(plan_change_theme(doc.model, template), author="ana")
    steps = len(doc.log.to_data()["entries"])
    assert plan_change_theme(doc.model, template) is None
    assert len(doc.log.to_data()["entries"]) == steps


# -- Change template: the layouts too, by name -------------------------------------------------------------------------
def test_change_template_lets_the_slides_follow_the_layouts_of_the_template_that_have_their_names(doc, other):
    template = a_talk_template(other)
    a_finished_deck(doc)
    before = doc.model.serialize()
    doc.execute(plan_change_template(doc.model, template), author="ana")
    model = doc.model
    assert model.layout_of("s1") == "two" and model.layouts["two"].name == "two lists", (
        "the deck's own layout, as it was called"
    )
    assert [(obj.anchor.purpose, obj.anchor.x) for obj in model.objects_on("two") if obj.anchor.purpose] == [
        ("Title", 300)
    ]
    assert [obj.body.image is not None for obj in model.objects_on("two")] == [False, True], (
        "the logo comes with its picture"
    )
    assert frame(doc, "h-s1") == (300, 40, 700, 90) and model.placeholder_of(model.get("h-s1")).holder == "two"
    assert frame(doc, "h-s2") == (50, 400, 1500, 120)
    assert model.template == TALK
    assert model.styles.get("body-text").css["font-size"] == "30px"
    doc.undo("ana")
    assert doc.model.serialize() == before
    assert reopen(doc).model.serialize() == doc.model.serialize()


def test_a_box_whose_placeholder_has_no_purpose_in_the_new_layout_stays_a_free_box_where_it_was(doc, other):
    template = a_talk_template(other)
    a_finished_deck(doc)
    doc.execute(plan_change_template(doc.model, template), author="ana")
    sub = doc.model.get("h-sub")
    assert sub.anchor.bound_to_placeholder == "" and frame(doc, "h-sub") == (100, 160, 800, 60)
    assert frame(doc, "free-s1") == (5, 5, 40, 40)


def test_what_the_template_does_not_have_stays_in_the_presentation(doc, other):
    template = a_talk_template(other)
    a_finished_deck(doc)
    doc.execute(plan_change_template(doc.model, template), author="ana")
    assert doc.model.layouts["wide"].name == "Wide list" and doc.model.layout_of("s3") == "wide"
    assert frame(doc, "h-s3") == (0, 0, 1600, 900) and doc.model.get("h-s3").anchor.bound_to_placeholder == "p-wide"
    assert "quote" in doc.model.styles


def test_a_layout_the_template_has_and_the_presentation_lacks_is_added_with_its_objects(doc, other):
    template = a_talk_template(other)
    doc.execute(plan_change_template(doc.model, template), author="ana")
    assert [layout.name for layout in doc.model.layouts] == ["Basic", "Two lists", "Title only"]
    added = next(layout for layout in doc.model.layouts if layout.name == "Two lists")
    assert added.origin == "template" and len(doc.model.objects_on(added.id)) == 2
    assert len({*doc.model.objects}) == len(doc.model.objects)


def test_a_layout_added_by_a_template_does_not_take_an_id_that_is_in_use(doc, other):
    template = a_talk_template(other)
    doc.execute(DefineLayout("l-two", "Mine"), author="ana")  # the id the template's layout has
    doc.execute(add(text_box("t-title", slide="l-two", x=1, y=1, w=100, h=100)), author="ana")  # and its object's id
    doc.execute(plan_change_template(doc.model, template), author="ana")
    ids = [layout.id for layout in doc.model.layouts]
    assert len(ids) == len(set(ids)) == 4
    assert doc.model.get("t-title").holder == "l-two", "the deck's object is where it was"


# -- What the change would do, said before it is done ------------------------------------------------------------------
def test_the_preview_counts_what_the_change_would_replace_add_and_leave(doc, other):
    template = a_talk_template(other)
    a_finished_deck(doc)
    assert preview_change(doc.model, template) == ChangePreview(
        styles_changed=1,  # body-text
        styles_added=1,  # big-number
        styles_kept=1,  # quote has no match
        colours_changed=1,  # accent
        colours_added=0,
        layouts_matched=3,  # Basic, "two lists" (as "Two lists") and Title only
        layouts_added=0,
        layouts_kept=1,  # Wide list
        slides_reframed=2,  # s1 and s2 follow a matched layout
        slides_unchanged=1,  # s3 follows Wide list
    )


def test_the_preview_counts_a_layout_the_presentation_lacks_as_added(doc, other):
    template = a_talk_template(other)
    preview = preview_change(doc.model, template)
    assert (preview.layouts_matched, preview.layouts_added, preview.layouts_kept) == (1, 2, 0)
    assert (preview.slides_reframed, preview.slides_unchanged) == (1, 0), "the one slide is on Basic"


def test_the_preview_of_the_theme_a_deck_has_already_is_all_zero_and_changes_nothing(doc, other):
    template = a_talk_template(other)
    doc.execute(plan_change_template(doc.model, template), author="ana")
    before = doc.model.serialize()
    preview = preview_change(doc.model, template)
    assert (preview.styles_changed, preview.styles_added, preview.colours_changed, preview.colours_added) == (
        0,
        0,
        0,
        0,
    )
    assert preview.layouts_added == 0
    assert doc.model.serialize() == before, "looking does not change the document"
