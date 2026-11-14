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


@BOTH
def test_a_language_is_not_written(unwritten):
    after = a_deck()
    after.language = "de"
    assert unwritten(after, a_deck()) == (Loss(NOT_WRITTEN, "language", 1),)


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
