"""The pictures of a pptx and an odp come in as image objects, and stay in the file when they are edited (D460)."""

from __future__ import annotations

import struct
from dataclasses import replace
from io import BytesIO

import pytest
from claudia_creates_io import (
    apply_edits_to_odp,
    apply_edits_to_pptx,
    odp_import_losses,
    odp_to_slides,
    pptx_import_losses,
    pptx_to_slides,
    slides_to_odp,
    slides_to_pptx,
)
from pptx import Presentation
from pptx.util import Inches
from test_odp import CM_PER_UNIT, an_import, an_odp, content, page

from claudia_core import ImageAsset, ObjectBody, VisualObject, decode_image
from claudia_creates import SlideAnchor, SlideModel
from claudia_odf_io import NS
from claudia_opc_io import read_parts, write_parts


def a_picture(width: int = 40, height: int = 20, shade: int = 0) -> ImageAsset:
    """A tiny, valid GIF (the shade makes its bytes differ)."""
    header = b"GIF89a" + struct.pack("<HHBBB", width, height, 0, 0, 0)
    frame = b"\x2c" + struct.pack("<HHHH", 0, 0, width, height) + b"\x00" + b"\x02\x01" + bytes([shade]) + b"\x00"
    return decode_image(header + frame + b"\x3b")


def a_deck(**changes) -> SlideModel:
    deck = SlideModel.empty()
    asset = a_picture()
    deck.define_image(asset)
    body = ObjectBody("o1", "image", 400, 200, "plain-image", image=asset.id, imported=an_import(asset), **changes)
    deck.insert_object(VisualObject(body, SlideAnchor("s1", 100, 150)))
    return deck


def only(deck: SlideModel) -> VisualObject:
    return next(iter(deck.objects.values()))


FORMATS = pytest.mark.parametrize(
    "to_file, to_model", [(slides_to_pptx, pptx_to_slides), (slides_to_odp, odp_to_slides)], ids=["pptx", "odp"]
)


# ------------------------------------------------------------------------------------------------ both formats
@FORMATS
def test_a_picture_comes_back_as_an_image_object_with_its_bytes_and_its_place(to_file, to_model):
    deck = a_deck(description="two cyclists")
    back = to_model(to_file(deck))
    found = only(back)
    assert found.body.kind == "image"
    assert back.images[found.body.image].data == deck.images[only(deck).body.image].data
    assert (found.anchor.x, found.anchor.y, found.body.w, found.body.h) == (100, 150, 400, 200)
    assert found.body.description == "two cyclists"


@FORMATS
def test_a_turned_picture_comes_back_turned(to_file, to_model):
    deck = a_deck(rotation=40)
    assert only(to_model(to_file(deck))).body.rotation == 40


@FORMATS
def test_the_same_picture_twice_is_one_asset(to_file, to_model):
    deck = a_deck()
    first = only(deck)
    deck.insert_object(VisualObject(replace(first.body, id="o2"), SlideAnchor("s1", 600, 150)))
    back = to_model(to_file(deck))
    assert len(back.objects) == 2 and len(back.images) == 1


@FORMATS
def test_a_deck_with_pictures_has_nothing_it_does_not_show(to_file, to_model):
    data = to_file(a_deck())
    losses = pptx_import_losses(data) if to_file is slides_to_pptx else odp_import_losses(data)
    assert [loss for loss in losses if loss.kind == "picture"] == []


# ------------------------------------------------------------------------------------------------ pptx
def a_pptx_with(picture_setup) -> bytes:
    prs = Presentation(BytesIO(slides_to_pptx(SlideModel.empty())))
    picture_setup(prs.slides[0])
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


def test_a_picture_another_program_made_comes_in_with_its_alt_text():
    def setup(slide):
        picture = slide.shapes.add_picture(BytesIO(a_picture().data), Inches(1), Inches(1), Inches(4), Inches(2))
        picture._element.xpath("./*[1]/p:cNvPr")[0].set("descr", "a chart of sales")

    found = only(pptx_to_slides(a_pptx_with(setup)))
    assert found.body.kind == "image" and found.body.description == "a chart of sales"


def test_a_decorative_picture_comes_back_decorative():
    found = only(pptx_to_slides(slides_to_pptx(a_deck(decorative=True))))
    assert found.body.decorative and found.body.description == ""


@pytest.mark.parametrize("what", ["cropped", "stretched", "undecodable"])
def test_a_picture_the_model_cannot_hold_as_it_is_stays_in_the_file(what):
    def setup(slide):
        data = a_picture().data
        if what == "undecodable":
            data = b"II*\x00" + bytes(40)  # not an image the app decodes
        try:
            picture = slide.shapes.add_picture(
                BytesIO(data), Inches(1), Inches(1), Inches(4), Inches(1 if what == "stretched" else 2)
            )
        except Exception:  # python-pptx itself refuses it: use a real image with a name the app cannot decode
            pytest.skip("python-pptx does not take this")
        if what == "cropped":
            picture.crop_left = 0.2

    data = a_pptx_with(setup)
    assert pptx_to_slides(data).objects == {}
    assert [(loss.kind, loss.count) for loss in pptx_import_losses(data)] == [("picture", 1)]


def test_an_edited_picture_is_patched_into_a_kept_pptx_and_its_bytes_stay():
    original = slides_to_pptx(a_deck(description="before"))
    before = pptx_to_slides(original)
    after = pptx_to_slides(original)
    moved = only(after)
    after.delete_object(moved.id)
    after.insert_object(
        VisualObject(replace(moved.body, w=200, h=100, rotation=15, description="after"), SlideAnchor("s1", 20, 30))
    )
    patched = apply_edits_to_pptx(original, before, after)
    found = only(pptx_to_slides(patched))
    assert (found.anchor.x, found.anchor.y, found.body.w, found.body.h, found.body.rotation) == (20, 30, 200, 100, 15)
    assert found.body.description == "after"
    media = [name for name in read_parts(patched) if name.startswith("ppt/media/")]
    assert media == [name for name in read_parts(original) if name.startswith("ppt/media/")]
    for name in media:
        assert read_parts(patched)[name] == read_parts(original)[name]


def test_a_text_box_is_given_a_description_in_a_kept_pptx_too():
    from test_pptx import _object

    deck = SlideModel.empty()
    deck.insert_object(_object("o1", "s1", "text", 100, 100, 400, 100, "body-text", "Hi"))
    original = slides_to_pptx(deck)
    before, after = pptx_to_slides(original), pptx_to_slides(original)
    obj = only(after)
    after.delete_object(obj.id)
    after.insert_object(VisualObject(replace(obj.body, description="a greeting"), obj.anchor))
    assert only(pptx_to_slides(apply_edits_to_pptx(original, before, after))).body.description == "a greeting"


# ------------------------------------------------------------------------------------------------ odp
def a_frame(href: str = "Pictures/a.gif", *, x="2cm", y="3cm", w="8cm", h="4cm", inner: str = "", style="") -> str:
    return (
        f'<draw:frame draw:style-name="gr1" svg:x="{x}" svg:y="{y}" svg:width="{w}" svg:height="{h}"{style}>'
        f'<draw:image xlink:href="{href}" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/>{inner}'
        "</draw:frame>"
    )


def an_odp_with_picture(frame: str, *, data: bytes | None = None) -> bytes:
    base = an_odp(page(frame))
    parts = read_parts(base)
    parts["Pictures/a.gif"] = data if data is not None else a_picture().data
    return write_parts(parts)


def test_a_picture_libreoffice_wrote_comes_in_with_its_title_and_description():
    found = only(
        odp_to_slides(an_odp_with_picture(a_frame(inner="<svg:title>t</svg:title><svg:desc>a chart</svg:desc>")))
    )
    assert found.body.kind == "image" and found.body.description == "a chart"
    assert (found.body.w, found.body.h) == (round(8 / CM_PER_UNIT), round(4 / CM_PER_UNIT))


def test_a_picture_that_is_not_in_the_package_or_not_an_image_stays_in_the_file():
    for data in (b"not an image", b""):
        odp = an_odp_with_picture(a_frame(), data=data)
        assert odp_to_slides(odp).objects == {}
        assert [(loss.kind, loss.count) for loss in odp_import_losses(odp)] == [("picture", 1)]
    missing = an_odp(page(a_frame("Pictures/none.png")))
    assert [(loss.kind, loss.count) for loss in odp_import_losses(missing)] == [("picture", 1)]


def test_a_stretched_or_cropped_picture_stays_in_the_file():
    stretched = an_odp_with_picture(a_frame(h="8cm"))
    assert odp_to_slides(stretched).objects == {}
    graphic = (
        '<style:style style:name="gr1" style:family="graphic">'
        '<style:graphic-properties fo:clip="rect(0.5cm, 0cm, 0cm, 0cm)"/></style:style>"'.rstrip('"')
    )
    cropped = write_parts(
        {**read_parts(an_odp(page(a_frame()), automatic=graphic)), "Pictures/a.gif": a_picture().data}
    )
    assert odp_to_slides(cropped).objects == {}
    assert [loss.kind for loss in odp_import_losses(cropped)] == ["picture"]


def test_a_table_with_a_preview_picture_is_still_a_table():
    frame = (
        '<draw:frame svg:x="1cm" svg:y="1cm" svg:width="4cm" svg:height="2cm"><table:table/>'
        '<draw:image xlink:href="Pictures/a.gif"/></draw:frame>'
    )
    assert odp_to_slides(an_odp_with_picture(frame)).objects == {}


def test_an_edited_picture_is_patched_into_a_kept_odp_and_its_bytes_stay():
    original = slides_to_odp(a_deck(description="before"))
    before, after = odp_to_slides(original), odp_to_slides(original)
    moved = only(after)
    after.delete_object(moved.id)
    after.insert_object(
        VisualObject(replace(moved.body, w=200, h=100, rotation=15, description="after"), SlideAnchor("s1", 20, 30))
    )
    patched = apply_edits_to_odp(original, before, after)
    found = only(odp_to_slides(patched))
    assert (found.anchor.x, found.anchor.y, found.body.w, found.body.h, found.body.rotation) == (20, 30, 200, 100, 15)
    assert found.body.description == "after"
    assert [n for n in read_parts(patched) if n.startswith("Pictures/")] == [
        n for n in read_parts(original) if n.startswith("Pictures/")
    ]


def test_a_description_is_given_to_a_picture_that_had_none():
    original = an_odp_with_picture(a_frame())
    before, after = odp_to_slides(original), odp_to_slides(original)
    moved = only(after)
    after.delete_object(moved.id)
    after.insert_object(VisualObject(replace(moved.body, description="new words"), moved.anchor))
    patched = apply_edits_to_odp(original, before, after)
    assert only(odp_to_slides(patched)).body.description == "new words"
    assert b"<svg:desc>new words</svg:desc>" in read_parts(patched)["content.xml"]
    assert NS and content  # (the helpers other tests of the package share)
