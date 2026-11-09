"""slides_to_pptx/pptx_to_slides: a base export and import with a real edit-and-reexport round trip, and
add_transition: a slide transition added additively."""

from __future__ import annotations

import zipfile
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace

import pptx
import pytest
from claudia_creates_io import UnsupportedEdit, add_transition, apply_edits_to_pptx, pptx_to_slides, slides_to_pptx
from lxml import etree
from pptx.dml.color import RGBColor
from pptx.util import Emu

from claudia_core import ObjectBody, VisualObject, paragraph_for
from claudia_creates import ShapeDefinition, SlideAnchor, SlideModel


def _object(object_id, slide, kind, x, y, w, h, style, text="", shape=None):
    """A slide object from the flat fields these tests have always used: an ``ObjectBody`` plus a
    ``SlideAnchor`` (E10.16), its words a paragraph of their own (E10.17)."""
    body = ObjectBody(object_id, kind, w, h, style, paragraph_for(object_id, style, text, "ana"), shape=shape)
    return VisualObject(body, SlideAnchor(slide, x, y))


PNS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_DECK_WIDTH, _DECK_HEIGHT = Emu(12_192_000), Emu(6_858_000)

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


def flat(obj):
    """An object's fields the way these tests were written to read them, before D177 split a body from an anchor.

    `VisualObject` keeps what a thing *is* in `.body`, where it sits in `.anchor`, and its words in a `Paragraph`.
    Reading that split out once here keeps the assertions below about pptx, which is what they are for."""
    body, anchor = obj.body, obj.anchor
    return SimpleNamespace(
        id=body.id,
        kind=body.kind,
        text=body.paragraph.text if body.paragraph else "",
        style=body.style,
        shape=body.shape,
        x=anchor.x,
        y=anchor.y,
        w=body.w,
        h=body.h,
    )


def retexted(obj, text):
    """The same object with other words in it. Its one paragraph carries them (D181), not the body itself."""
    paragraph = obj.body.paragraph
    assert paragraph is not None, "only a text box or a shape has words to change"
    # `written_by` is what lays one run over the new words; a paragraph whose runs do not cover its text exactly
    # is refused, which is the kernel keeping authorship honest (E10.17).
    return obj.with_body(paragraph=paragraph.with_text(text, ()).written_by(None))


def placed(obj, x, y, w, h):
    """The same object moved and resized: the size is the body's, the position the slide anchor's (D177)."""
    return replace(obj.with_body(w=w, h=h), anchor=replace(obj.anchor, x=x, y=y))


# -- pptx_to_slides ----------------------------------------------------------------------------------------------


def test_pptx_to_slides_imports_text_and_shape_objects_in_order():
    model = pptx_to_slides(slides_to_pptx(two_slide_deck()))
    assert model.slides == ["s1", "s2"]
    assert [(f.kind, f.text) for f in map(flat, model.objects_on("s1"))] == [("text", "Hello")]
    assert [(f.kind, f.text, f.shape) for f in map(flat, model.objects_on("s2"))] == [("shape", "Circle", "circle")]


def test_pptx_to_slides_falls_back_to_the_default_styles():
    model = pptx_to_slides(slides_to_pptx(two_slide_deck()))
    assert flat(model.objects_on("s1")[0]).style == "body-text"
    assert flat(model.objects_on("s2")[0]).style == "plain-shape"


def test_pptx_to_slides_keeps_position_and_size_through_a_round_trip():
    model = two_slide_deck()
    reimported = pptx_to_slides(slides_to_pptx(model))
    original = flat(model.objects_on("s2")[0])
    reimported_object = flat(reimported.objects_on("s2")[0])
    assert (reimported_object.x, reimported_object.y, reimported_object.w, reimported_object.h) == (
        original.x,
        original.y,
        original.w,
        original.h,
    )


def test_pptx_to_slides_reads_the_decks_own_slide_size_not_a_fixed_one():
    prs = pptx.Presentation()
    prs.slide_width, prs.slide_height = Emu(9_144_000), Emu(6_858_000)  # a 4:3 deck, not claudia's 16:9 export
    # scale_x = 9_144_000 / 1600 = 5715; scale_y = 6_858_000 / 900 = 7620 -- so (left, top, width, height) below
    # map back to exactly (100, 100, 400, 100) in claudia's own units, same as the assertion checks.
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(Emu(571_500), Emu(762_000), Emu(2_286_000), Emu(762_000)).text_frame.text = "Hi"
    out = BytesIO()
    prs.save(out)
    model = pptx_to_slides(out.getvalue())
    obj = flat(model.objects_on("s1")[0])
    assert (obj.x, obj.y, obj.w, obj.h) == (100, 100, 400, 100)


def test_pptx_to_slides_skips_a_table():
    prs = pptx.Presentation()
    prs.slide_width, prs.slide_height = _DECK_WIDTH, _DECK_HEIGHT
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(Emu(762_000), Emu(762_000), Emu(3_048_000), Emu(762_000)).text_frame.text = "Hi"
    slide.shapes.add_table(1, 2, Emu(762_000), Emu(2_286_000), Emu(3_048_000), Emu(762_000))
    out = BytesIO()
    prs.save(out)
    model = pptx_to_slides(out.getvalue())
    assert [(f.kind, f.text) for f in map(flat, model.objects_on("s1"))] == [("text", "Hi")]


# -- apply_edits_to_pptx -------------------------------------------------------------------------------------------

_RED_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x02\x00\x00\x00\xfd\xd4\x9as\x00\x00"
    b"\x00\x16IDATx\x9cc\xfc\xcf\xc0\xc0\xc0\xc0\xc0\xc4\xc0\xc0\xc0\xc0\xc0\x00\x00\r\x1d\x01\x03j\xc2\x9b\xe9\x00"
    b"\x00\x00\x00IEND\xaeB`\x82"
)


def _pptx_with_table() -> bytes:
    prs = pptx.Presentation()
    prs.slide_width, prs.slide_height = _DECK_WIDTH, _DECK_HEIGHT
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(Emu(762_000), Emu(762_000), Emu(3_048_000), Emu(762_000)).text_frame.text = "First"
    table_shape = slide.shapes.add_table(1, 2, Emu(762_000), Emu(2_286_000), Emu(3_048_000), Emu(762_000))
    table_shape.table.cell(0, 0).text = "A"
    table_shape.table.cell(0, 1).text = "B"
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


def test_apply_edits_patches_only_the_changed_object_and_preserves_a_table():
    original_bytes = _pptx_with_table()
    baseline = pptx_to_slides(original_bytes)
    current = pptx_to_slides(original_bytes)
    obj = baseline.objects_on("s1")[0]
    current.replace_object(retexted(obj, "First edited"))

    out = apply_edits_to_pptx(original_bytes, baseline, current)
    reopened = pptx.Presentation(BytesIO(out))
    assert reopened.slides[0].shapes[0].text_frame.text == "First edited"
    table = reopened.slides[0].shapes[1].table
    assert (table.cell(0, 0).text, table.cell(0, 1).text) == ("A", "B")


def test_apply_edits_moves_and_resizes_an_object():
    model = two_slide_deck()
    original_bytes = slides_to_pptx(model)
    baseline = pptx_to_slides(original_bytes)
    current = pptx_to_slides(original_bytes)
    obj = current.objects_on("s2")[0]
    current.replace_object(placed(obj, 300, 300, 100, 100))

    out = apply_edits_to_pptx(original_bytes, baseline, current)
    reimported = pptx_to_slides(out)
    moved = flat(reimported.objects_on("s2")[0])
    assert (moved.x, moved.y, moved.w, moved.h) == (300, 300, 100, 100)


def test_apply_edits_leaves_an_untouched_slides_media_part_byte_identical():
    prs = pptx.Presentation()
    prs.slide_width, prs.slide_height = _DECK_WIDTH, _DECK_HEIGHT
    layout = prs.slide_layouts[6]
    slide1 = prs.slides.add_slide(layout)
    slide1.shapes.add_textbox(Emu(762_000), Emu(762_000), Emu(3_048_000), Emu(762_000)).text_frame.text = "First"
    slide2 = prs.slides.add_slide(layout)
    slide2.shapes.add_picture(BytesIO(_RED_PNG), Emu(762_000), Emu(762_000), Emu(1_524_000), Emu(1_524_000))
    out = BytesIO()
    prs.save(out)
    original_bytes = out.getvalue()

    baseline = pptx_to_slides(original_bytes)
    current = pptx_to_slides(original_bytes)
    obj = current.objects_on("s1")[0]
    current.replace_object(retexted(obj, "First edited"))

    edited_bytes = apply_edits_to_pptx(original_bytes, baseline, current)
    with zipfile.ZipFile(BytesIO(original_bytes)) as before, zipfile.ZipFile(BytesIO(edited_bytes)) as after:
        assert before.read("ppt/media/image1.png") == after.read("ppt/media/image1.png")
        assert before.read("ppt/slides/slide2.xml") == after.read("ppt/slides/slide2.xml")


def test_apply_edits_raises_unsupported_edit_when_an_object_is_added():
    model = two_slide_deck()
    original_bytes = slides_to_pptx(model)
    baseline = pptx_to_slides(original_bytes)
    current = pptx_to_slides(original_bytes)
    body = ObjectBody("onew", "text", 300, 100, "body-text", paragraph_for("onew", "body-text", "New"))
    current.insert_object(VisualObject(body, SlideAnchor("s1", 100, 500)))

    with pytest.raises(UnsupportedEdit):
        apply_edits_to_pptx(original_bytes, baseline, current)


def test_apply_edits_raises_unsupported_edit_when_an_object_is_removed():
    model = two_slide_deck()
    original_bytes = slides_to_pptx(model)
    baseline = pptx_to_slides(original_bytes)
    current = pptx_to_slides(original_bytes)
    object_id = current.objects_on("s1")[0].id
    current.delete_object(object_id)

    with pytest.raises(UnsupportedEdit):
        apply_edits_to_pptx(original_bytes, baseline, current)


def test_apply_edits_raises_unsupported_edit_when_objects_are_reordered():
    prs = pptx.Presentation()
    prs.slide_width, prs.slide_height = _DECK_WIDTH, _DECK_HEIGHT
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(Emu(100_000), Emu(100_000), Emu(1_000_000), Emu(500_000)).text_frame.text = "One"
    slide.shapes.add_textbox(Emu(100_000), Emu(1_000_000), Emu(1_000_000), Emu(500_000)).text_frame.text = "Two"
    out = BytesIO()
    prs.save(out)
    original_bytes = out.getvalue()

    baseline = pptx_to_slides(original_bytes)
    current = pptx_to_slides(original_bytes)
    first, second = current.objects_on("s1")
    current.delete_object(first.id)
    current.insert_object(first, at=1)  # same two objects, swapped stacking order -- not a per-object content change

    with pytest.raises(UnsupportedEdit):
        apply_edits_to_pptx(original_bytes, baseline, current)


def test_a_shapes_colours_reach_the_file_even_though_the_style_names_a_palette_role():
    """D200's consequence for every exporter: a built-in style says ``fill: @accent/14``, not a colour.

    ``_rgb`` looks for a hex and finds none in a role, so reading `computed` here lost the fill and the stroke
    without a word — a deck exported from a brand-new presentation came out colourless. The palette is what turns
    a role into something a file can hold.
    """
    model = two_slide_deck()
    shape = model.styles.computed("plain-shape")
    assert shape["fill"].startswith("@"), "the premise: the built-in style names a role, not a colour"

    reopened = pptx.Presentation(BytesIO(slides_to_pptx(model)))
    circle = reopened.slides[1].shapes[0]
    # The border is the accent itself; the fill is the accent at 14%, flattened over the slide's own colour,
    # because a solid pptx fill has nowhere to keep the opacity (see `_rgb`).
    assert circle.line.color.rgb == RGBColor.from_string("5B4BC4")
    assert circle.fill.fore_color.rgb == RGBColor.from_string("E1DBE6")


def test_changing_a_role_changes_what_the_exported_file_holds():
    model = two_slide_deck()
    model.palette.set_colour("accent", "#008080")
    reopened = pptx.Presentation(BytesIO(slides_to_pptx(model)))
    assert reopened.slides[1].shapes[0].line.color.rgb == RGBColor.from_string("008080")
