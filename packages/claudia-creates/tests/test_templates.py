"""A template is a presentation without slides that a new presentation starts from (E10.4, E10.22, D1530)."""

import json

import pytest
from conftest import add, image_asset, put_image, text_box

from claudia_core import Refusal, SetRole, StyleDef
from claudia_creates import AddSlide, DefineLayout, HideLayout, MoveLayout, SetSlideNotes, SetSlideTime, SlideModel
from claudia_creates.template import (
    TemplateInfo,
    TemplateRefused,
    basic_template,
    check_template,
    start_from_template,
    template_state,
)

TALK = TemplateInfo("Conference talk", "Talks of twenty minutes with a speaker slide", "en")


def a_deck_with_slides(doc):
    """Two layouts (one with a logo), a style and a colour of its own, three slides with words, notes and a photo."""
    doc.execute(DefineLayout("title", "Title"), author="ana")
    doc.execute(add(text_box("heading", slide="title", purpose="Title", x=100, y=50, w=800, h=100)), author="ana")
    put_image(doc, "logo", slide="title", asset=image_asset(30, 30), w=60, h=60)
    doc.execute(AddSlide("s2"), author="ana")
    doc.execute(AddSlide("s3"), author="ana")
    doc.execute(add(text_box("t1", text="Q3 layoffs: 40 people")), author="ana")
    put_image(doc, "photo", slide="s2", asset=image_asset(50, 50), w=100, h=100)
    doc.execute(SetSlideNotes("s2", "do not say the number"), author="ana")
    doc.execute(SetSlideTime("s3", 90), author="ana")
    doc.execute(SetRole("accent", "#aa0000"), author="ana")
    doc.model.styles.add(StyleDef("quote", "Quote", "", None, {"font-style": "italic"}))
    return doc.model


def test_a_template_keeps_the_layouts_the_styles_and_the_colours_and_nothing_of_the_slides(doc):
    model = a_deck_with_slides(doc)
    state = template_state(model, TALK)
    assert state["slides"] == [] and state["slide_layouts"] == {} and state["notes"] == {} and state["times"] == {}
    assert [layout["id"] for layout in state["layouts"]] == ["basic", "title"]
    assert state["styles"] == model.styles.to_data() and state["palette"] == model.palette.to_data()
    assert sorted(obj["id"] for obj in state["objects"]) == ["heading", "logo"], "the objects of the layouts only"
    assert "layoffs" not in json.dumps(state) and "the number" not in json.dumps(state)
    assert len(state["images"]) == 1, "the logo's picture stays, the photo's goes"
    assert state["template"] == TALK.to_data()
    assert model.order == ["s1", "s2", "s3"], "the deck itself is as it was"


def test_a_template_opens_as_a_presentation_without_slides(doc):
    state = template_state(a_deck_with_slides(doc), TALK)
    model = SlideModel.restore(state)
    assert model.order == [] and list(model.layouts.ids()) == ["basic", "title"]
    assert model.template == TALK
    assert model.serialize() == state


def test_a_new_presentation_starts_with_one_slide_on_the_first_layout_and_a_note_of_its_template(doc):
    template = check_template(template_state(a_deck_with_slides(doc), TALK))
    deck = start_from_template(template)
    assert deck.order == ["s1"] and deck.layout_of("s1") == "basic"
    assert list(deck.layouts.ids()) == ["basic", "title"]
    assert deck.styles.to_data() == template.model.styles.to_data()
    assert deck.palette.to_data() == template.model.palette.to_data()
    assert deck.template == TALK


def test_the_first_slide_follows_the_first_layout_that_is_not_hidden(doc):
    model = a_deck_with_slides(doc)
    doc.execute(HideLayout("basic", True), author="ana")
    doc.execute(MoveLayout("title", 0), author="ana")
    deck = start_from_template(check_template(template_state(model, TALK)))
    assert deck.layout_of("s1") == "title"


def test_a_presentation_started_from_a_template_shares_nothing_with_it(doc):
    template = check_template(template_state(a_deck_with_slides(doc), TALK))
    before = json.dumps(template.model.serialize(), sort_keys=True)
    deck = start_from_template(template)
    deck.styles.add(StyleDef("mine", "Mine", "", None, {"font-style": "italic"}))
    deck.layouts.change("title", name="Renamed")
    assert json.dumps(template.model.serialize(), sort_keys=True) == before


def test_the_basic_template_is_one_layout_without_placeholders():
    template = basic_template()
    assert template.info.name == "Basic" and list(template.model.layouts.ids()) == ["basic"]
    deck = start_from_template(template)
    assert deck.order == ["s1"] and deck.objects_on("basic") == []


# -- what is not a template ------------------------------------------------------------------------------------------
def refused(state: dict) -> str:
    with pytest.raises(TemplateRefused) as caught:
        check_template(state)
    assert isinstance(caught.value, Refusal)
    return str(caught.value)


def test_a_presentation_with_slides_is_not_a_template(doc):
    state = a_deck_with_slides(doc).serialize() | {"template": TALK.to_data()}
    assert "slides" in refused(state)


def test_a_presentation_without_a_note_of_what_it_is_for_is_not_a_template(doc):
    state = template_state(a_deck_with_slides(doc), TALK)
    del state["template"]
    assert "Save as template" in refused(state)


def test_a_presentation_without_a_layout_is_not_a_template(doc):
    state = template_state(a_deck_with_slides(doc), TALK)
    state["layouts"] = []
    state["objects"] = []
    assert "layout" in refused(state)


def test_something_that_is_no_state_of_creates_is_not_a_template():
    assert "presentation" in refused({"cells": []})


@pytest.mark.parametrize("name", ["", "   ", "x" * 200])
def test_a_template_needs_a_name_that_fits(name):
    with pytest.raises(Refusal):
        TemplateInfo(name, "for talks", "en")


def test_a_template_says_what_language_it_is_written_in():
    assert TemplateInfo("T", "for talks", "EN-gb").language == "en-GB"
    with pytest.raises(Refusal):
        TemplateInfo("T", "for talks", "not a language")


def test_a_state_that_cannot_be_restored_in_any_way_is_no_presentation():
    state = SlideModel().serialize() | {"diagrams": {"d1": {"kind": "nope"}}}
    with pytest.raises(TemplateRefused, match="this is not a presentation"):
        check_template(state)


@pytest.mark.parametrize("name", ["two\nlines", "tab\there", "nul\x00", "\N{RIGHT-TO-LEFT OVERRIDE}evil"])
def test_the_name_and_the_purpose_of_a_template_are_one_line_of_plain_text(name):
    with pytest.raises(Refusal, match="plain text in one line"):
        TemplateInfo(name, "for talks", "en")
    with pytest.raises(Refusal, match="plain text in one line"):
        TemplateInfo("Talks", name, "en")
