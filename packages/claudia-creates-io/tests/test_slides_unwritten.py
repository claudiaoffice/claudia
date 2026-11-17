"""odp_unwritten_changes / pptx_unwritten_changes, pptx_import_losses and the export losses odp and pptx share:
what a presentation file cannot hold of the model, and what the model does not show of the file (D299, D405)."""

from __future__ import annotations

from io import BytesIO

import pytest
from claudia_creates_io import (
    add_transition,
    odp_export_losses,
    odp_unwritten_changes,
    pptx_export_losses,
    pptx_import_losses,
    pptx_to_slides,
    pptx_unwritten_changes,
    slides_to_pptx,
)
from pptx import Presentation
from pptx.util import Inches

from claudia_core import ObjectBody, VisualObject, paragraph_for
from claudia_creates import SlideAnchor, SlideModel
from claudia_odf_io import NOT_WRITTEN, Loss

BOTH = pytest.mark.parametrize("unwritten", [odp_unwritten_changes, pptx_unwritten_changes])


def a_deck() -> SlideModel:
    model = SlideModel.empty()  # "s1"
    body = ObjectBody("o1", "text", 400, 100, "body-text", paragraph_for("o1", "body-text", "Hello", "ana"))
    model.insert_object(VisualObject(body, SlideAnchor("s1", 100, 100)))
    return model


@BOTH
def test_a_deck_that_did_not_change_has_no_unwritten_changes(unwritten):
    assert unwritten(a_deck(), a_deck()) == ()


@BOTH
def test_edited_objects_and_notes_are_written_so_they_are_no_loss(unwritten):
    after = a_deck()
    after.set_notes("s1", "words")
    after.insert_slide("s2")
    assert unwritten(after, a_deck()) == ()


@BOTH
def test_a_planned_time_is_not_written(unwritten):
    after = a_deck()
    after.set_time("s1", 90)
    assert unwritten(after, a_deck()) == (Loss("planned-time", "", 1),)


def test_the_language_of_a_kept_pptx_is_not_written_but_that_of_a_kept_odp_is():
    after = a_deck()
    after.language = "de"
    assert pptx_unwritten_changes(after, a_deck()) == (Loss(NOT_WRITTEN, "language", 1),)
    assert odp_unwritten_changes(after, a_deck()) == ()


@BOTH
def test_a_fresh_export_compares_with_an_empty_presentation(unwritten):
    model = a_deck()
    model.set_time("s1", 60)
    assert unwritten(model) == (Loss("planned-time", "", 1),)


def test_the_export_losses_say_what_the_converters_do_not_write():
    model = a_deck()
    model.set_time("s1", 60)
    assert Loss("planned-time", "", 1) in odp_export_losses(model)
    assert Loss("planned-time", "", 1) in pptx_export_losses(model)


def test_pptx_does_not_keep_who_wrote_the_words_or_what_notes_show_beyond_plain_words():
    model = a_deck()
    model.set_notes("s1", "see [the site](https://example.org)")
    assert pptx_export_losses(model) == (Loss("authorship", "", 1), Loss("notes-link", "", 1))


def a_pptx_with_more_than_claudia_models() -> bytes:
    document = Presentation(BytesIO(slides_to_pptx(a_deck())))
    slide = document.slides[0]
    slide.shapes.add_table(1, 2, Inches(1), Inches(1), Inches(3), Inches(1))
    slide.shapes.add_group_shape()
    out = BytesIO()
    document.save(out)
    return add_transition(out.getvalue(), slide_index=0)


def test_what_the_model_does_not_show_of_a_pptx_is_listed():
    assert pptx_import_losses(a_pptx_with_more_than_claudia_models()) == (
        Loss("table", "", 1),
        Loss("group", "", 1),
        Loss("transition", "", 1),
    )


def test_a_pptx_claudia_made_has_nothing_the_model_does_not_show():
    assert pptx_import_losses(slides_to_pptx(a_deck())) == ()


# ---------------------------------------------------------------------------- pptx: look, formatting, links
def a_pptx_made_by_another_program() -> bytes:
    """A text box with a bold word and a link: what PowerPoint users do."""
    document = Presentation(BytesIO(slides_to_pptx(SlideModel.empty())))
    slide = document.slides[0]
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    paragraph = box.text_frame.paragraphs[0]
    plain = paragraph.add_run()
    plain.text = "plain "
    bold = paragraph.add_run()
    bold.text = "bold"
    bold.font.bold = True
    linked = paragraph.add_run()
    linked.text = " site"
    linked.hyperlink.address = "https://example.org"
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def test_bold_words_and_links_of_a_pptx_are_listed_as_what_the_model_does_not_show():
    losses = {loss.kind: loss.count for loss in pptx_import_losses(a_pptx_made_by_another_program())}
    assert losses["formatting"] == 1 and losses["link"] == 1
    assert "look" not in losses  # a text box that says nothing of its look has the one the model gives it


def two_ovals(fill) -> bytes:  # noqa: ANN001 (what a shape's fill does with the colour it is given)
    from pptx.enum.shapes import MSO_SHAPE

    document = Presentation(BytesIO(slides_to_pptx(SlideModel.empty())))
    for index in range(2):
        shape = document.slides[0].shapes.add_shape(MSO_SHAPE.OVAL, Inches(1), Inches(1 + index), Inches(1), Inches(1))
        fill(shape.fill)
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def test_a_colour_a_shape_says_is_read_and_so_is_no_loss():
    from pptx.dml.color import RGBColor

    def red(fill) -> None:  # noqa: ANN001
        fill.solid()
        fill.fore_color.rgb = RGBColor(255, 0, 0)

    data = two_ovals(red)
    assert pptx_import_losses(data) == ()
    model = pptx_to_slides(data)
    assert {model.styles.resolved(o.body.style, {})["fill"] for o in model.objects.values()} == {"#ff0000"}


def test_a_look_the_model_has_no_property_for_is_listed_once_for_each_object():
    data = two_ovals(lambda fill: fill.gradient())
    assert pptx_import_losses(data) == (Loss("look", "", 2),)


def test_a_pptx_written_by_claudia_with_the_default_looks_has_no_look_to_list():
    assert pptx_import_losses(slides_to_pptx(a_deck())) == ()
