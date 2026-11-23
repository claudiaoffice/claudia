"""A slide that follows a layout is written with what the layout shows beneath it (E10.4, D1530, D1534): a presentation
file has no layouts of Claudia's kind yet (E10.24), so the slide carries the logo itself, and what is lost is said."""

from __future__ import annotations

from io import BytesIO

import pptx
from claudia_creates_io import odp_unwritten_changes, pptx_unwritten_changes, slides_to_odp, slides_to_pptx
from lxml import etree

from claudia_core import AddObject, Document, ObjectBody, paragraph_for
from claudia_creates import DefineLayout, SetSlideLayout, SlideAnchor, SlideModel
from claudia_odf_io import NS
from claudia_opc_io import read_parts


def a_deck_on_a_layout_with_a_logo() -> SlideModel:
    """A layout "Branded" with a title placeholder and a logo; slide s1 follows it, heading bound."""
    doc = Document(SlideModel.empty())

    def text(object_id: str, slide: str, words: str, anchor: SlideAnchor, w: int = 300, h: int = 80) -> AddObject:
        body = ObjectBody(object_id, "text", w, h, "body-text", paragraph_for(object_id, "body-text", words, "ana"))
        return AddObject(body, anchor.to_data())

    doc.execute(DefineLayout("branded", "Branded"), author="ana")
    doc.execute(text("title", "branded", "", SlideAnchor("branded", 100, 50, "Title")), author="ana")
    doc.execute(text("logo", "branded", "Acme", SlideAnchor("branded", 800, 20), 100, 40), author="ana")
    doc.execute(SetSlideLayout("s1", "branded"), author="ana")
    doc.execute(text("heading", "s1", "Hello", SlideAnchor("s1", 100, 50, "", "title")), author="ana")
    return doc.model


def test_the_logo_of_the_layout_is_written_beneath_the_objects_of_the_slide_in_a_pptx():
    prs = pptx.Presentation(BytesIO(slides_to_pptx(a_deck_on_a_layout_with_a_logo())))
    assert [shape.text_frame.text for shape in prs.slides[0].shapes] == ["Acme", "Hello"], "the placeholder is no shape"


def test_the_logo_of_the_layout_is_written_beneath_the_objects_of_the_slide_in_an_odp():
    parts = read_parts(slides_to_odp(a_deck_on_a_layout_with_a_logo()))
    root = etree.fromstring(parts["content.xml"])
    page = root.find(".//draw:page", NS)
    assert [etree.tostring(frame, method="text", encoding="unicode") for frame in page] == ["Acme", "Hello"]


def test_what_the_file_cannot_keep_of_the_layouts_is_said_and_a_deck_on_the_basic_layout_loses_nothing():
    deck = a_deck_on_a_layout_with_a_logo()
    for unwritten in (pptx_unwritten_changes, odp_unwritten_changes):
        assert [(loss.kind, loss.detail, loss.count) for loss in unwritten(deck)] == [("not-written", "layouts", 1)]
        assert unwritten(SlideModel.empty()) == ()
