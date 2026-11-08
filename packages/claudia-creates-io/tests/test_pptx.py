"""slides_to_pptx: a base export, and add_transition: a slide transition added additively."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pptx
import pytest
from claudia_creates_io import add_transition, slides_to_pptx
from lxml import etree

from claudia_core import ObjectBody, VisualObject, paragraph_for
from claudia_creates import ShapeDefinition, SlideAnchor, SlideModel


def _object(object_id, slide, kind, x, y, w, h, style, text="", shape=None):
    """A slide object from the flat fields these tests have always used: an ``ObjectBody`` plus a
    ``SlideAnchor`` (E10.16), its words a paragraph of their own (E10.17)."""
    body = ObjectBody(object_id, kind, w, h, style, paragraph_for(object_id, style, text, "ana"), shape=shape)
    return VisualObject(body, SlideAnchor(slide, x, y))


PNS = "http://schemas.openxmlformats.org/presentationml/2006/main"

_CIRCLE = ShapeDefinition(id="circle", name="Circle", path="M50 0 A50 50 0 1 1 50 100 A50 50 0 1 1 50 0 Z", aspect=1)


def two_slide_deck() -> SlideModel:
    model = SlideModel.empty()  # "s1"
    model.insert_slide("s2")
    model.define_shape(_CIRCLE)
    model.insert_object(_object("o1", "s1", "text", 100, 100, 400, 100, "body-text", "Hello"))
    model.insert_object(_object("o2", "s2", "shape", 100, 100, 200, 200, "plain-shape", "Circle", "circle"))
    return model


def test_each_slide_and_its_objects_come_out():
    model = two_slide_deck()
    prs = pptx.Presentation(BytesIO(slides_to_pptx(model)))
    assert len(prs.slides) == 2
    assert prs.slides[0].shapes[0].text_frame.text == "Hello"
    assert prs.slides[1].shapes[0].text_frame.text == "Circle"


def test_shapes_map_to_the_right_autoshape():
    model = two_slide_deck()
    prs = pptx.Presentation(BytesIO(slides_to_pptx(model)))
    from pptx.enum.shapes import MSO_SHAPE

    assert prs.slides[1].shapes[0].auto_shape_type == MSO_SHAPE.OVAL


def test_an_empty_model_still_has_its_one_slide():
    prs = pptx.Presentation(BytesIO(slides_to_pptx(SlideModel.empty())))
    assert len(prs.slides) == 1
    assert len(prs.slides[0].shapes) == 0


def test_add_transition_is_recognized_on_the_right_slide():
    base = slides_to_pptx(two_slide_deck())
    out = add_transition(base, slide_index=1, kind="fade", speed="slow")
    with zipfile.ZipFile(BytesIO(out)) as z:
        slide1 = etree.fromstring(z.read("ppt/slides/slide1.xml"))
        slide2 = etree.fromstring(z.read("ppt/slides/slide2.xml"))
    assert slide1.find(f"{{{PNS}}}transition") is None
    transition = slide2.find(f"{{{PNS}}}transition")
    assert transition is not None
    assert transition.get("spd") == "slow"
    assert transition.find(f"{{{PNS}}}fade") is not None


def test_add_transition_none_removes_an_existing_one():
    base = slides_to_pptx(two_slide_deck())
    with_fade = add_transition(base, slide_index=0, kind="fade")
    cleared = add_transition(with_fade, slide_index=0, kind="none")
    with zipfile.ZipFile(BytesIO(cleared)) as z:
        slide1 = etree.fromstring(z.read("ppt/slides/slide1.xml"))
    assert slide1.find(f"{{{PNS}}}transition") is None


def test_add_transition_refuses_an_out_of_range_slide():
    base = slides_to_pptx(two_slide_deck())
    with pytest.raises(ValueError, match="slide_index"):
        add_transition(base, slide_index=5, kind="fade")


def test_transition_survives_a_python_pptx_round_trip():
    base = slides_to_pptx(two_slide_deck())
    out = add_transition(base, slide_index=0, kind="fade", speed="slow")
    prs = pptx.Presentation(BytesIO(out))
    resaved = BytesIO()
    prs.save(resaved)
    with zipfile.ZipFile(resaved) as z:
        slide1 = etree.fromstring(z.read("ppt/slides/slide1.xml"))
    assert slide1.find(f"{{{PNS}}}transition") is not None
