"""A style property no presentation file can hold is a loss, named by the property (CODE-58).

The converters write a style's font, size, colour, bold, italic and alignment, and a shape's fill and outline. A style
may say much more (line height, a border, padding, letter spacing...); before CODE-58 ``styles`` counted as written, so
an export of such a style said nothing while the file showed something else."""

from __future__ import annotations

import pytest
from claudia_creates_io import odp_export_losses, odp_unwritten_changes, pptx_export_losses, pptx_unwritten_changes

from claudia_core import ObjectBody, StyleDef, VisualObject, paragraph_for
from claudia_creates import ShapeDefinition, SlideAnchor, SlideModel
from claudia_odf_io import Loss

CIRCLE = ShapeDefinition(id="circle", name="Circle", path="M50 0 A50 50 0 1 1 50 100 A50 50 0 1 1 50 0 Z", aspect=1)
BOTH = pytest.mark.parametrize("unwritten", [odp_unwritten_changes, pptx_unwritten_changes])
EXPORTS = pytest.mark.parametrize("losses", [odp_export_losses, pptx_export_losses])


def a_text(model: SlideModel, object_id: str, words_style: str = "body-text", box_style: str = "plain-box") -> None:
    body = ObjectBody(object_id, "text", 400, 100, box_style, paragraph_for(object_id, words_style, "Hello", "ana"))
    model.insert_object(VisualObject(body, SlideAnchor("s1", 100, 100)))


def a_shape(model: SlideModel, object_id: str) -> None:
    if model.shapes.get("circle") is None:
        model.define_shape(CIRCLE)
    body = ObjectBody(
        object_id, "shape", 200, 200, "plain-shape", paragraph_for(object_id, "shape-label", "", "ana"), ref="circle"
    )
    model.insert_object(VisualObject(body, SlideAnchor("s1", 100, 100)))


def say(model: SlideModel, style_id: str, **css: str) -> None:
    """Give a built-in style more to say, keeping what it says already."""
    model.styles.set_css(
        style_id, {**model.styles.get(style_id).css, **{k.replace("_", "-"): v for k, v in css.items()}}
    )


@BOTH
def test_a_deck_that_says_only_what_the_file_holds_loses_nothing(unwritten):
    model = SlideModel.empty()
    a_text(model, "o1")
    a_shape(model, "o2")
    say(model, "body-text", font_size="48px", text_align="center", font_weight="700", color="#336699")
    assert unwritten(model) == ()


@BOTH
def test_the_defaults_of_the_built_in_styles_are_no_loss(unwritten):
    """``body-text`` says ``line-height: 1.3``; every deck does, so it is the file's default, not a loss."""
    model = SlideModel.empty()
    a_text(model, "o1")
    assert unwritten(model) == ()


@BOTH
def test_a_line_height_the_deck_changed_is_a_loss_named_by_the_property(unwritten):
    model = SlideModel.empty()
    a_text(model, "o1")
    say(model, "body-text", line_height="1.8")
    assert unwritten(model) == (Loss("style-property", "line-height", 1),)


@BOTH
def test_every_unwritten_property_is_named_once_with_the_objects_it_touches(unwritten):
    model = SlideModel.empty()
    a_text(model, "o1")
    a_text(model, "o2")
    say(model, "body-text", letter_spacing="2px", border_left="3px solid #ff0000", padding_left="12px")
    assert unwritten(model) == (
        Loss("style-property", "letter-spacing", 2),
        Loss("style-property", "border-left", 2),
        Loss("style-property", "padding-left", 2),
    )


@BOTH
def test_a_style_nothing_uses_is_no_loss(unwritten):
    model = SlideModel.empty()
    a_text(model, "o1")
    model.styles.add(StyleDef("quote", "Quote", "a quotation", "body-text", {"letter-spacing": "2px"}))
    assert unwritten(model) == ()


@BOTH
def test_a_style_the_deck_made_is_judged_against_the_parent_the_file_knows(unwritten):
    model = SlideModel.empty()
    model.styles.add(StyleDef("quote", "Quote", "a quotation", "body-text", {"letter-spacing": "2px"}))
    a_text(model, "o1", words_style="quote")
    assert unwritten(model) == (Loss("style-property", "letter-spacing", 1),)


@BOTH
def test_a_text_box_writes_none_of_its_box_style_but_a_shape_writes_its_outline(unwritten):
    model = SlideModel.empty()
    a_text(model, "o1")
    a_shape(model, "o2")
    model.styles.set_css("plain-box", {"background-color": "#eeeeee"})
    say(model, "plain-shape", stroke_width="8px", fill="#00ff00")
    assert unwritten(model) == (Loss("style-property", "background-color", 1),)


@BOTH
def test_the_words_of_a_shape_lose_what_the_words_of_a_text_lose(unwritten):
    model = SlideModel.empty()
    a_shape(model, "o1")
    say(model, "shape-label", letter_spacing="2px")
    assert unwritten(model) == (Loss("style-property", "letter-spacing", 1),)


@BOTH
def test_an_edit_reports_only_what_changed_since_the_file_was_read(unwritten):
    before = SlideModel.empty()
    a_text(before, "o1")
    say(before, "body-text", line_height="1.8")
    after = SlideModel.empty()
    a_text(after, "o1")
    say(after, "body-text", line_height="1.8", letter_spacing="1px")
    assert unwritten(after, before) == (Loss("style-property", "letter-spacing", 1),)
    assert unwritten(before, before) == ()


@EXPORTS
def test_the_export_losses_name_the_properties_too(losses):
    model = SlideModel.empty()
    a_text(model, "o1")
    say(model, "body-text", border_left="3px solid #ff0000")
    assert Loss("style-property", "border-left", 1) in losses(model)
