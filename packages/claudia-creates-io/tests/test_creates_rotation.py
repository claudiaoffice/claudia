"""Rotation of an object (``RotateObject``) in pptx and odp files (D459): written on export, read on import, patched
into a kept file."""

from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import pytest
from claudia_creates_io import (
    apply_edits_to_odp,
    apply_edits_to_pptx,
    odp_export_losses,
    odp_import_losses,
    odp_to_slides,
    pptx_to_slides,
    slides_to_odp,
    slides_to_pptx,
)
from claudia_creates_io.odp_transform import angle_of, transform_of, turned_box
from lxml import etree
from pptx import Presentation
from test_odp import CM_PER_UNIT, an_object, an_odp, content, page, textbox

from claudia_core import VisualObject
from claudia_creates import ShapeLibrary, SlideModel
from claudia_odf_io import NS


def a_deck(rotation: int = 0, kind: str = "shape") -> SlideModel:
    model = SlideModel()
    library = ShapeLibrary.load()
    for shape_id in ("circle", "rectangle", "triangle"):
        model.define_shape(library.get(shape_id))
    model.insert_slide("s1")
    if kind == "shape":
        placed = an_object("o1", "s1", "shape", 400, 300, 400, 200, "plain-shape", "boxed", "rectangle")
    else:
        placed = an_object("o1", "s1", "text", 400, 300, 400, 200, "body-text", "Hello")
    model.insert_object(VisualObject(replace(placed.body, rotation=rotation), placed.anchor))
    return model


def only(model: SlideModel) -> VisualObject:
    return next(iter(model.objects.values()))


# ------------------------------------------------------------------------------------------------ pptx export
@pytest.mark.parametrize("kind", ["shape", "text"])
def test_the_rotation_of_an_object_is_in_a_fresh_pptx(kind):
    prs = Presentation(BytesIO(slides_to_pptx(a_deck(30, kind))))
    assert [round(shape.rotation) for shape in prs.slides[0].shapes] == [30]


def test_a_rotation_survives_a_pptx_round_trip():
    assert only(pptx_to_slides(slides_to_pptx(a_deck(300)))).body.rotation == 300


# ------------------------------------------------------------------------------------------------ the transform of odp
def test_an_angle_in_degrees_clockwise_is_radians_counter_clockwise_as_the_standard_writes_it():
    assert transform_of(0, (0, 0, 10, 10)) is None
    assert angle_of("rotate (0.5235987755982988) translate (1cm 1cm)") == pytest.approx(330)
    assert angle_of("rotate (-0.5235987755982988) translate (1cm 1cm)") == pytest.approx(30)
    assert transform_of(30, (0, 0, 0, 0)) == "rotate (-0.5235987756) translate (0cm 0cm)"


@pytest.mark.parametrize("degrees", [0, 1, 30, 90, 180, 270, 359])
def test_the_box_of_a_turned_object_comes_back_as_the_box_it_had(degrees):
    box = (400.0, 300.0, 400.0, 200.0)
    text = transform_of(degrees, box)
    if degrees == 0:
        assert text is None
        return
    assert text is not None
    assert turned_box(text, box[2], box[3]) == pytest.approx((degrees, *box[:2]), abs=1e-3)


def test_the_skew_of_nothing_that_libreoffice_writes_before_a_rotation_is_none():
    text = "skewX (-5.19699498214747E-017) rotate (-0.349065850398867) translate (3.096cm 1.855cm)"
    assert angle_of(text) == pytest.approx(20)
    assert turned_box(text, 8.466, 4.232) is not None
    assert angle_of("skewX (0.3) rotate (-0.3) translate (1cm 1cm)") is None


def test_a_transform_with_a_skew_or_a_scale_is_not_a_rotation():
    for text in ("scale (2 2)", "skewX (0.3)", "rotate (0.1) scale (2)", "translate (1cm 1cm)", "rotate (x)"):
        assert angle_of(text) is None


# ------------------------------------------------------------------------------------------------ odp export
def test_a_turned_object_is_written_with_a_transform_and_without_a_position_of_its_own():
    root = etree.fromstring(content(slides_to_odp(a_deck(30))).encode())
    shape = root.find(".//draw:page/*", NS)
    assert shape is not None
    assert shape.get(f"{{{NS['draw']}}}transform", "").startswith("rotate (")
    assert shape.get(f"{{{NS['svg']}}}x") is None and shape.get(f"{{{NS['svg']}}}width") is not None


def test_an_object_that_is_not_turned_has_no_transform():
    assert "draw:transform" not in content(slides_to_odp(a_deck(0)))


@pytest.mark.parametrize("kind", ["shape", "text"])
@pytest.mark.parametrize("degrees", [30, 90, 200])
def test_a_rotation_survives_an_odp_round_trip_with_its_place(kind, degrees):
    back = only(odp_to_slides(slides_to_odp(a_deck(degrees, kind))))
    assert back.body.rotation == degrees
    assert (back.anchor.x, back.anchor.y, back.body.w, back.body.h) == (400, 300, 400, 200)


def test_no_loss_is_reported_for_a_rotation_either_way():
    assert [loss for loss in odp_export_losses(a_deck(30)) if "rot" in loss.kind] == []
    data = slides_to_odp(a_deck(30))
    assert [loss for loss in odp_import_losses(data) if "rot" in loss.kind] == []


def test_a_file_that_rotates_by_a_transform_a_program_made_comes_in_turned():
    """LibreOffice's own form: ``rotate`` (counter-clockwise radians) and ``translate`` to where the turned box's top
    left corner is, with the size the box has before it is turned."""
    # a box 4cm x 2cm turned 90 degrees clockwise around its centre (8cm, 4cm): its corner (6cm, 3cm) goes to (9cm, 2cm)
    markup = (
        '<draw:frame draw:style-name="gr1" svg:width="4cm" svg:height="2cm" '
        'draw:transform="rotate (-1.5707963267949) translate (9cm 2cm)">'
        '<draw:text-box><text:p text:style-name="P1">Hello</text:p></draw:text-box></draw:frame>'
    )
    model = odp_to_slides(an_odp(page(markup)))
    obj = only(model)
    assert obj.body.rotation == 90
    assert (obj.anchor.x, obj.anchor.y, obj.body.w, obj.body.h) == tuple(
        round(value / CM_PER_UNIT) for value in (6, 3, 4, 2)
    )


@pytest.mark.parametrize(
    "extra",
    [
        ' draw:transform="skewX (0.3)"',
        ' draw:transform="scale (2 2) rotate (0.5)"',
        ' draw:transform="translate (1cm 1cm)"',
    ],
)
def test_a_transform_that_is_more_than_a_rotation_still_leaves_the_object_out_and_says_so(extra):
    data = an_odp(page(textbox(extra=extra)))
    assert odp_to_slides(data).objects == {}
    assert any(loss.kind == "rotated-object" for loss in odp_import_losses(data))


# ------------------------------------------------------------------------------------------------ odp patch
def patched(original: bytes, rotation: int) -> tuple[bytes, SlideModel]:
    baseline = odp_to_slides(original)
    current = odp_to_slides(original)
    obj = only(current)
    current.objects[obj.body.id] = VisualObject(replace(obj.body, rotation=rotation), obj.anchor)
    return apply_edits_to_odp(original, baseline, current), current


def test_an_object_turned_in_claudia_is_turned_in_the_kept_file_and_keeps_its_place():
    original = slides_to_odp(a_deck(0))
    data, _ = patched(original, 45)
    back = only(odp_to_slides(data))
    assert back.body.rotation == 45
    assert (back.anchor.x, back.anchor.y, back.body.w, back.body.h) == (400, 300, 400, 200)


def test_an_object_turned_back_to_upright_loses_its_transform_and_gets_its_place_back():
    original = slides_to_odp(a_deck(120))
    data, _ = patched(original, 0)
    assert "draw:transform" not in content(data)
    back = only(odp_to_slides(data))
    assert back.body.rotation == 0
    assert (back.anchor.x, back.anchor.y) == (400, 300)


def test_a_turned_object_that_is_moved_keeps_its_rotation_and_goes_where_it_was_sent():
    original = slides_to_odp(a_deck(60))
    baseline, current = odp_to_slides(original), odp_to_slides(original)
    obj = only(current)
    current.objects[obj.body.id] = VisualObject(obj.body, replace(obj.anchor, x=700, y=100))
    back = only(odp_to_slides(apply_edits_to_odp(original, baseline, current)))
    assert back.body.rotation == 60
    assert (back.anchor.x, back.anchor.y) == (700, 100)


def test_a_turned_object_in_a_pptx_is_patched_too():
    original = slides_to_pptx(a_deck(0))
    baseline, current = pptx_to_slides(original), pptx_to_slides(original)
    obj = only(current)
    current.objects[obj.body.id] = VisualObject(replace(obj.body, rotation=75), obj.anchor)
    assert only(pptx_to_slides(apply_edits_to_pptx(original, baseline, current))).body.rotation == 75
