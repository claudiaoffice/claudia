"""How a presentation is printed and which language it is in, in a pptx and an odp (D461): written from the model,
read back, changed in a kept file -- and what a format has no place for is a loss."""

from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import pytest
from claudia_creates_io import (
    apply_edits_to_odp,
    apply_edits_to_pptx,
    odp_to_slides,
    odp_unwritten_changes,
    pptx_export_losses,
    pptx_to_slides,
    pptx_unwritten_changes,
    slides_to_odp,
    slides_to_pptx,
)
from lxml import etree
from pptx import Presentation
from pptx.util import Inches

from claudia_core import ObjectBody, PageSetup, VisualObject, paragraph_for
from claudia_creates import PrintSetup, SlideAnchor, SlideModel
from claudia_odf_io import NOT_WRITTEN, Loss, read_language
from claudia_opc_io import read_parts

HANDOUTS = PrintSetup("handouts-6", PageSetup.preset("a4", orientation="landscape"))


def a_deck(language: str | None = None, setup: PrintSetup | None = None) -> SlideModel:
    model = SlideModel.empty()
    body = ObjectBody("o1", "text", 400, 100, "body-text", paragraph_for("o1", "body-text", "Hello", "ana"))
    model.insert_object(VisualObject(body, SlideAnchor("s1", 100, 100)))
    model.language = language
    if setup is not None:
        model.print_setup = setup
    return model


# ------------------------------------------------------------------------------------------------ pptx: print setup
@pytest.mark.parametrize(
    "setup",
    [
        PrintSetup(),
        HANDOUTS,
        PrintSetup("handouts-3", PageSetup.preset("letter")),
        PrintSetup("slides", PageSetup.preset("a5", orientation="landscape")),
        PrintSetup("handouts-9", PageSetup("custom", 600000, 900000)),
    ],
)
def test_the_layout_and_the_paper_of_a_pptx_come_back(setup):
    back = pptx_to_slides(slides_to_pptx(a_deck(setup=setup))).print_setup
    assert back.layout == setup.layout
    assert (back.page.paper, back.page.orientation) == (setup.page.paper, setup.page.orientation)
    assert abs(back.page.width - setup.page.width) <= 1 and abs(back.page.height - setup.page.height) <= 1


def test_the_paper_is_the_size_of_the_notes_page_and_the_layout_what_is_printed():
    prs = Presentation(BytesIO(slides_to_pptx(a_deck(setup=HANDOUTS))))
    assert (prs.part._element.find("{*}notesSz").get("cx"), prs.part._element.find("{*}notesSz").get("cy")) == (
        str(round(841890 * 12.7)),
        str(round(595276 * 12.7)),
    )
    props = etree.fromstring(read_parts(slides_to_pptx(a_deck(setup=HANDOUTS)))["ppt/presProps.xml"])
    assert props.find("{*}prnPr").get("prnWhat") == "handouts6"


def test_a_file_that_says_nothing_of_printing_prints_as_a_new_presentation_does():
    prs = Presentation()  # PowerPoint's own notes page, and no word on what is printed
    prs.slides.add_slide(prs.slide_layouts[6])
    out = BytesIO()
    prs.save(out)
    assert pptx_to_slides(out.getvalue()).print_setup == PrintSetup()


def test_a_notes_page_of_powerpoints_own_size_is_no_paper_of_ours():
    prs = Presentation(BytesIO(slides_to_pptx(a_deck(setup=HANDOUTS))))
    notes = prs.part._element.find("{*}notesSz")
    notes.set("cx", "6858000")
    notes.set("cy", "9144000")
    out = BytesIO()
    prs.save(out)
    back = pptx_to_slides(out.getvalue()).print_setup
    assert (back.layout, back.page) == ("handouts-6", PrintSetup().page)


def test_what_a_pptx_has_no_place_for_is_a_loss_and_the_rest_is_not():
    assert pptx_unwritten_changes(a_deck(setup=HANDOUTS)) == ()
    margins = replace(HANDOUTS, page=replace(HANDOUTS.page, margin_left=100000))
    assert pptx_unwritten_changes(a_deck(setup=margins)) == (Loss(NOT_WRITTEN, "print_setup", 1),)
    numbered = replace(HANDOUTS, page=replace(HANDOUTS.page, page_numbers=True))
    assert Loss(NOT_WRITTEN, "print_setup", 1) in pptx_export_losses(a_deck(setup=numbered))


def test_a_new_print_setup_is_patched_into_a_kept_pptx_and_nothing_else_moves():
    original = slides_to_pptx(a_deck())
    before = pptx_to_slides(original)
    after = pptx_to_slides(original)
    after.print_setup = HANDOUTS
    patched = apply_edits_to_pptx(original, before, after)
    assert pptx_to_slides(patched).print_setup.layout == "handouts-6"
    assert pptx_to_slides(patched).print_setup.page.orientation == "landscape"
    assert pptx_unwritten_changes(after, before) == ()
    assert read_parts(patched)["ppt/slides/slide1.xml"] == read_parts(original)["ppt/slides/slide1.xml"]


# ------------------------------------------------------------------------------------------------ pptx: language
@pytest.mark.parametrize("language", ["de", "en-GB", "sr-Latn-RS"])
def test_the_language_of_a_pptx_comes_back(language):
    assert pptx_to_slides(slides_to_pptx(a_deck(language))).language == language


def test_a_deck_without_a_language_has_runs_without_one():
    assert pptx_to_slides(slides_to_pptx(a_deck())).language is None
    assert b"lang=" not in read_parts(slides_to_pptx(a_deck()))["ppt/slides/slide1.xml"]


def test_the_language_of_most_of_the_words_is_the_language_of_the_deck():
    data = slides_to_pptx(a_deck())
    prs = Presentation(BytesIO(data))
    for text, lang in (("a", "fr-FR"), ("b", "fr-FR"), ("c", "de-DE")):
        box = prs.slides[0].shapes.add_textbox(Inches(1), Inches(3), Inches(2), Inches(1))
        box.text_frame.paragraphs[0].add_run().text = text
        box.text_frame.paragraphs[0].runs[0]._r.get_or_add_rPr().set("lang", lang)
    out = BytesIO()
    prs.save(out)
    assert pptx_to_slides(out.getvalue()).language == "fr-FR"


def test_the_language_of_a_kept_pptx_is_not_rewritten_and_that_is_said():
    before = a_deck()
    after = a_deck("de")
    assert pptx_unwritten_changes(after, before) == (Loss(NOT_WRITTEN, "language", 1),)
    assert pptx_unwritten_changes(after) == ()  # a fresh file says it


# ------------------------------------------------------------------------------------------------ odp: language
@pytest.mark.parametrize("language", ["de", "en-GB", "sr-Latn-RS"])
def test_the_language_of_an_odp_comes_back(language):
    data = slides_to_odp(a_deck(language))
    assert odp_to_slides(data).language == language
    assert read_language(etree.fromstring(read_parts(data)["styles.xml"])) == language


def test_a_deck_without_a_language_says_none_in_an_odp():
    assert odp_to_slides(slides_to_odp(a_deck())).language is None
    assert b"fo:language" not in read_parts(slides_to_odp(a_deck()))["styles.xml"]


@pytest.mark.parametrize("start", [None, "de", "en-GB"])
@pytest.mark.parametrize("end", [None, "fr", "pt-BR"])
def test_a_language_is_changed_in_a_kept_odp(start, end):
    original = slides_to_odp(a_deck(start))
    before = odp_to_slides(original)
    after = odp_to_slides(original)
    after.language = end
    patched = apply_edits_to_odp(original, before, after)
    assert odp_to_slides(patched).language == end
    assert odp_unwritten_changes(after, before) == ()
    if start == end:
        assert patched == original


def test_an_odp_has_no_place_for_the_print_layout():
    assert odp_unwritten_changes(a_deck(setup=HANDOUTS)) == (Loss(NOT_WRITTEN, "print_setup", 2),)  # layout, page
