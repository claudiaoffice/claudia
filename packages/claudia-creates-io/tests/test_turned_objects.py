"""A turned object in a presentation file (D1021, D1022): exported with its turn, read back with it, and kept on the
slide by its outline."""

from __future__ import annotations

from io import BytesIO

import pytest
from claudia_creates_io import pptx_import_losses, pptx_to_slides, slides_to_pptx
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu

from claudia_core import ObjectBody, VisualObject, paragraph_for
from claudia_creates import SlideAnchor, SlideModel

_UNIT = 12_192_000 // 1600  # EMU in one slide unit, for the deck these files are made at


def _model(*objects: tuple[str, str, int, int, int, int, int]) -> SlideModel:
    """A deck of one slide with ``(id, kind, x, y, w, h, rotation)`` objects on it."""
    model = SlideModel.empty()
    for object_id, kind, x, y, w, h, rotation in objects:
        words = "shape-label" if kind == "shape" else "body-text"
        body = ObjectBody(
            object_id,
            kind,
            w,
            h,
            "plain-shape" if kind == "shape" else "plain-box",
            paragraph_for(object_id, words, "hello", "ana"),
            rotation=rotation,
        )
        model.insert_object(VisualObject(body, SlideAnchor("s1", x, y)))
    return model


def _file_with_rotated_rectangle(x: int, y: int, w: int, h: int, degrees: float) -> bytes:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12_192_000), Emu(6_858_000)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(x * _UNIT), Emu(y * _UNIT), Emu(w * _UNIT), Emu(h * _UNIT))
    shape.rotation = degrees
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


def test_a_turned_text_box_is_written_with_its_turn():
    model = _model(("o1", "text", 100, 100, 400, 100, 30))
    shape = Presentation(BytesIO(slides_to_pptx(model))).slides[0].shapes[0]
    assert shape.rotation == pytest.approx(30)
    assert (shape.left, shape.top) == (100 * _UNIT, 100 * _UNIT)  # the unturned frame, as PowerPoint keeps it


def test_each_turned_object_is_written_with_its_own_turn():
    model = _model(("o1", "text", 100, 100, 400, 100, 0), ("o2", "text", 700, 300, 200, 200, 315))
    shapes = Presentation(BytesIO(slides_to_pptx(model))).slides[0].shapes
    assert [round(s.rotation) for s in shapes] == [0, 315]


def test_an_upright_object_writes_no_rotation_at_all():
    model = _model(("o1", "text", 100, 100, 400, 100, 0))
    shape = Presentation(BytesIO(slides_to_pptx(model))).slides[0].shapes[0]
    assert shape._element.xpath(".//a:xfrm/@rot") == []


def test_a_turn_survives_a_trip_through_the_file():
    model = _model(("o1", "text", 100, 100, 400, 100, 30), ("o2", "text", 900, 500, 300, 150, 270))
    back = pptx_to_slides(slides_to_pptx(model))
    assert [(o.anchor.x, o.anchor.y, o.body.w, o.body.h, o.body.rotation) for o in back.objects_on("s1")] == [
        (100, 100, 400, 100, 30),
        (900, 500, 300, 150, 270),
    ]


def test_a_shape_turned_to_stick_out_of_the_slide_is_moved_back_in_on_import():
    # 300 x 100 at the top left, turned a quarter: its outline is 100 wide and 300 high, centred on (150, 50),
    # so it reaches 100 units above the slide. The nearest place with the outline inside is one 100 units lower.
    back = pptx_to_slides(_file_with_rotated_rectangle(0, 0, 300, 100, 90))
    (obj,) = back.objects_on("s1")
    assert (obj.body.rotation, obj.anchor.x, obj.anchor.y) == (90, 0, 100)


def test_a_shape_too_large_to_turn_is_read_upright_and_the_report_says_so():
    data = _file_with_rotated_rectangle(50, 50, 1500, 800, 45)
    (obj,) = pptx_to_slides(data).objects_on("s1")
    assert (obj.body.rotation, obj.anchor.x, obj.anchor.y) == (0, 50, 50)
    assert [(loss.kind, loss.count) for loss in pptx_import_losses(data)] == [("turn", 1)]


def test_a_shape_that_stays_on_the_slide_is_not_moved():
    (obj,) = pptx_to_slides(_file_with_rotated_rectangle(600, 300, 300, 100, 20)).objects_on("s1")
    assert (obj.body.rotation, obj.anchor.x, obj.anchor.y) == (20, 600, 300)
