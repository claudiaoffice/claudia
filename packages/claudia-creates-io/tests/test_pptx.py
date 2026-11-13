"""slides_to_pptx/pptx_to_slides: a base export and import with a real edit-and-reexport round trip, and
add_transition: a slide transition added additively."""

from __future__ import annotations

import struct
import zipfile
from dataclasses import replace
from io import BytesIO

import pptx
import pytest
from claudia_creates_io import UnsupportedEdit, add_transition, apply_edits_to_pptx, pptx_to_slides, slides_to_pptx
from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Emu

from claudia_core import ImageAsset, ImageImport, ObjectBody, VisualObject, decode_image, paragraph_for
from claudia_creates import ShapeDefinition, SlideAnchor, SlideModel


def _object(object_id, slide, kind, x, y, w, h, style, text="", shape=None):
    """A slide object from the flat fields these tests have always used: an ``ObjectBody`` plus a
    ``SlideAnchor`` (E10.16), its words a paragraph of their own (E10.17)."""
    words = "shape-label" if kind == "shape" else style  # a shape's words have a style of their own (D310)
    body = ObjectBody(object_id, kind, w, h, style, paragraph_for(object_id, words, text, "ana"), shape=shape)
    return VisualObject(body, SlideAnchor(slide, x, y))


def _image_asset(width: int = 40, height: int = 20) -> ImageAsset:
    """A tiny, valid GIF, decoded through the real decoder (no pixels, just a header python-pptx needs to
    recognise it as a picture) -- the same construction ``claudia-creates``' own test fixtures use."""
    header = b"GIF89a" + struct.pack("<HHBBB", width, height, 0, 0, 0)
    frame = b"\x2c" + struct.pack("<HHHH", 0, 0, width, height) + b"\x00" + b"\x02\x01\x00\x00"
    return decode_image(header + frame + b"\x3b")


def _image_object(object_id, slide, x, y, w, h, asset: ImageAsset) -> VisualObject:
    imported = ImageImport.from_data(
        {
            "asset": asset.id,
            "alt": "a sample picture",
            "imported_by": "ana",
            "imported_at": "2026-11-07T10:00:00.000Z",
            "source": "disk",
            "source_name": "pic.gif",
            "source_path": None,
        }
    )
    body = ObjectBody(object_id, "image", w, h, "plain-image", image=asset.id, imported=imported)
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


def test_an_image_object_becomes_a_real_picture_not_a_blue_box():
    model = SlideModel.empty()  # "s1"
    asset = _image_asset()  # 40x20, aspect 2 -- the object's own w/h must keep that proportion
    model.define_image(asset)
    model.insert_object(_image_object("i1", "s1", 150, 300, 400, 200, asset))
    prs = pptx.Presentation(BytesIO(slides_to_pptx(model)))
    shape = prs.slides[0].shapes[0]
    assert shape.shape_type == MSO_SHAPE_TYPE.PICTURE
    assert shape.image.blob == asset.data


def test_an_image_object_keeps_its_place_alongside_other_objects():
    model = two_slide_deck()
    asset = _image_asset()
    model.define_image(asset)
    model.insert_object(_image_object("i1", "s1", 150, 300, 400, 200, asset))
    prs = pptx.Presentation(BytesIO(slides_to_pptx(model)))
    kinds = [shape.shape_type for shape in prs.slides[0].shapes]
    assert MSO_SHAPE_TYPE.PICTURE in kinds


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


# -- pptx_to_slides ----------------------------------------------------------------------------------------------


def test_pptx_to_slides_imports_text_and_shape_objects_in_order():
    model = pptx_to_slides(slides_to_pptx(two_slide_deck()))
    assert model.slides == ["s1", "s2"]
    assert [(o.body.kind, o.body.paragraph.text) for o in model.objects_on("s1")] == [("text", "Hello")]
    assert [(o.body.kind, o.body.paragraph.text, o.body.shape) for o in model.objects_on("s2")] == [
        ("shape", "Circle", "circle")
    ]


def test_pptx_to_slides_falls_back_to_the_default_styles():
    model = pptx_to_slides(slides_to_pptx(two_slide_deck()))
    assert model.objects_on("s1")[0].body.style == "plain-box"  # a text box's box (D310)
    assert model.objects_on("s2")[0].body.style == "plain-shape"


def test_pptx_to_slides_gives_a_shapes_words_the_shape_label_style():
    """D310: a shape's outline and its words are two slots; the words start under ``shape-label``."""
    model = pptx_to_slides(slides_to_pptx(two_slide_deck()))
    assert model.objects_on("s1")[0].body.paragraph.style == "body-text"
    assert model.objects_on("s2")[0].body.paragraph.style == "shape-label"


def test_pptx_to_slides_keeps_position_and_size_through_a_round_trip():
    model = two_slide_deck()
    reimported = pptx_to_slides(slides_to_pptx(model))
    original, again = model.objects_on("s2")[0], reimported.objects_on("s2")[0]
    assert (again.anchor.x, again.anchor.y, again.body.w, again.body.h) == (
        original.anchor.x,
        original.anchor.y,
        original.body.w,
        original.body.h,
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
    obj = model.objects_on("s1")[0]
    assert (obj.anchor.x, obj.anchor.y, obj.body.w, obj.body.h) == (100, 100, 400, 100)


def test_pptx_to_slides_skips_a_table():
    prs = pptx.Presentation()
    prs.slide_width, prs.slide_height = _DECK_WIDTH, _DECK_HEIGHT
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(Emu(762_000), Emu(762_000), Emu(3_048_000), Emu(762_000)).text_frame.text = "Hi"
    slide.shapes.add_table(1, 2, Emu(762_000), Emu(2_286_000), Emu(3_048_000), Emu(762_000))
    out = BytesIO()
    prs.save(out)
    model = pptx_to_slides(out.getvalue())
    assert [(o.body.kind, o.body.paragraph.text) for o in model.objects_on("s1")] == [("text", "Hi")]


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
    current.replace_object(obj.with_body(paragraph=obj.body.paragraph.with_text("First edited", ()).written_by("ana")))

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
    moved_obj = replace(obj, anchor=SlideAnchor("s2", 300, 300)).with_body(w=100, h=100)
    current.replace_object(moved_obj)

    out = apply_edits_to_pptx(original_bytes, baseline, current)
    reimported = pptx_to_slides(out)
    moved = reimported.objects_on("s2")[0]
    assert (moved.anchor.x, moved.anchor.y, moved.body.w, moved.body.h) == (300, 300, 100, 100)


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
    current.replace_object(obj.with_body(paragraph=obj.body.paragraph.with_text("First edited", ()).written_by("ana")))

    edited_bytes = apply_edits_to_pptx(original_bytes, baseline, current)
    with zipfile.ZipFile(BytesIO(original_bytes)) as before, zipfile.ZipFile(BytesIO(edited_bytes)) as after:
        assert before.read("ppt/media/image1.png") == after.read("ppt/media/image1.png")
        assert before.read("ppt/slides/slide2.xml") == after.read("ppt/slides/slide2.xml")


def test_apply_edits_raises_unsupported_edit_when_an_object_is_added():
    model = two_slide_deck()
    original_bytes = slides_to_pptx(model)
    baseline = pptx_to_slides(original_bytes)
    current = pptx_to_slides(original_bytes)
    current.insert_object(_object("onew", "s1", "text", 100, 500, 300, 100, "body-text", "New"))

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


# -- what an object says to someone who cannot see it (BITV 1.1.1) -------------------------------------------------
_ADEC = "http://schemas.microsoft.com/office/drawing/2017/decorative"
_ADEC_URI = "{C183D7F6-B498-43B3-948B-1728B52AA6E4}"


def _properties(shape):
    """The shape's own non-visual drawing properties (``p:cNvPr``), where PowerPoint keeps its alt text."""
    return shape._element.xpath("./*[1]/p:cNvPr")[0]


def _exported_shape(obj, *, shapes=()):
    model = SlideModel.empty()
    for shape in shapes:
        model.define_shape(shape)
    if obj.body.image:
        model.define_image(_image_asset())
    model.insert_object(obj)
    prs = pptx.Presentation(BytesIO(slides_to_pptx(model)))
    return prs.slides[0].shapes[0]


def test_a_picture_carries_its_description_as_alt_text():
    asset = _image_asset()
    picture = _image_object("o1", "s1", 10, 10, 400, 200, asset)
    picture = VisualObject(replace(picture.body, description="two cyclists at a finish line"), picture.anchor)
    assert _properties(_exported_shape(picture)).get("descr") == "two cyclists at a finish line"


def test_a_picture_without_a_description_of_its_own_is_described_by_what_it_was_imported_with():
    picture = _image_object("o1", "s1", 10, 10, 400, 200, _image_asset())
    assert _properties(_exported_shape(picture)).get("descr") == "a sample picture"


def test_a_shape_and_a_text_box_carry_their_description_too():
    box = _object("o1", "s1", "text", 10, 10, 400, 100, "body-text", "Hello")
    box = VisualObject(replace(box.body, description="the greeting"), box.anchor)
    assert _properties(_exported_shape(box)).get("descr") == "the greeting"
    circle = _object("o2", "s1", "shape", 10, 10, 200, 200, "plain-shape", "", "circle")
    circle = VisualObject(replace(circle.body, description="a circle that stands for the server"), circle.anchor)
    assert _properties(_exported_shape(circle, shapes=(_CIRCLE,))).get("descr") == "a circle that stands for the server"


def test_an_object_nobody_described_has_no_alt_text_attribute_at_all():
    box = _object("o1", "s1", "text", 10, 10, 400, 100, "body-text", "Hello")
    assert _properties(_exported_shape(box)).get("descr") is None


def test_a_decorative_picture_is_marked_the_way_powerpoint_marks_one_and_has_no_alt_text():
    picture = _image_object("o1", "s1", 10, 10, 400, 200, _image_asset())
    picture = VisualObject(replace(picture.body, decorative=True, description=""), picture.anchor)
    properties = _properties(_exported_shape(picture))
    assert properties.get("descr") == "", "a decorative object has no text alternative, not even its file name"
    (ext,) = properties.xpath("./a:extLst/a:ext")
    assert ext.get("uri") == _ADEC_URI
    (mark,) = list(ext)
    assert etree.QName(mark).text == f"{{{_ADEC}}}decorative" and mark.get("val") == "1"


def test_an_object_that_is_not_decorative_carries_no_decorative_mark():
    picture = _image_object("o1", "s1", 10, 10, 400, 200, _image_asset())
    assert _properties(_exported_shape(picture)).xpath("./a:extLst") == []


# -- a rendered text container is a picture to a file (D344) ---------------------------------------------------------
_GLYPHS = (
    b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="30" height="10">'
    b'<defs><symbol id="g"><path d="M0 0L5 5"/></symbol></defs><use xlink:href="#g"/></svg>'
)
_PNG = b"\x89PNG\r\n\x1a\n"


def _deck_with_container(*, pictured: bool = True, **changes) -> SlideModel:
    from claudia_core import RenderedDefinition

    model = SlideModel.empty()
    asset = decode_image(_GLYPHS, checked_drawing=True)
    model.define_image(asset)
    model.define_rendering(RenderedDefinition("r1", "typst", "= Hi", image=asset.id if pictured else None))
    body = ObjectBody("c1", "rendered", 300, 100, "plain-image", rendered="r1", **changes)
    model.insert_object(VisualObject(body, SlideAnchor("s1", 10, 10)))
    return model


def _package(data: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(BytesIO(data))


def test_a_rendered_container_is_a_real_picture_with_its_alt_text_and_the_drawing_itself_for_powerpoint():
    data = slides_to_pptx(_deck_with_container(description="a heading that says Hi"))
    (picture,) = [
        s for s in pptx.Presentation(BytesIO(data)).slides[0].shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE
    ]
    assert picture._element.xpath("./*[1]/p:cNvPr")[0].get("descr") == "a heading that says Hi"
    package = _package(data)
    (svg_name,) = [n for n in package.namelist() if n.endswith(".svg")]
    assert b"<use" in package.read(svg_name)
    assert picture.image.blob.startswith(_PNG), "a program that cannot draw SVG shows a picture, not a hole"
    blips = etree.fromstring(package.read("ppt/slides/slide1.xml")).xpath("//*[local-name()='svgBlip']")
    assert len(blips) == 1


def test_a_picture_that_a_rasteriser_made_is_what_a_program_without_svg_shows():
    from PIL import Image

    made = BytesIO()
    Image.new("RGBA", (30, 10), (200, 30, 30, 255)).save(made, "PNG")
    seen = []

    def rasterise(svg: bytes, width: int, height: int) -> bytes:
        seen.append((svg, width, height))
        return made.getvalue()

    data = slides_to_pptx(_deck_with_container(), rasterise=rasterise)
    (picture,) = [
        s for s in pptx.Presentation(BytesIO(data)).slides[0].shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE
    ]
    assert seen == [(decode_image(_GLYPHS, checked_drawing=True).data, 300, 100)]
    assert picture.image.blob == made.getvalue()
    assert not [n for n in _package(data).namelist() if n.endswith(".svg")], "one picture, the same in every program"


def test_a_container_nothing_was_made_for_yet_is_left_out():
    shapes = pptx.Presentation(BytesIO(slides_to_pptx(_deck_with_container(pictured=False)))).slides[0].shapes
    assert len(shapes) == 0


def test_an_imported_svg_picture_no_longer_stops_the_export():
    asset = decode_image(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect width="40" height="20"/></svg>'
    )
    model = SlideModel.empty()
    model.define_image(asset)
    model.insert_object(_image_object("i1", "s1", 150, 300, 400, 200, asset))
    assert any(n.endswith(".svg") for n in _package(slides_to_pptx(model)).namelist())


def test_the_export_report_names_what_powerpoint_cannot_keep():
    from claudia_creates_io import pptx_export_losses

    assert [(loss.kind, loss.count) for loss in pptx_export_losses(_deck_with_container())] == [("svg-fallback", 1)]
    assert pptx_export_losses(_deck_with_container(), rasterised=True) == ()
    assert [(loss.kind, loss.count) for loss in pptx_export_losses(_deck_with_container(pictured=False))] == [
        ("rendering-pending", 1)
    ]
