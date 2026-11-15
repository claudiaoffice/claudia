"""A file written by LibreOffice itself (converted from a pptx): a picture turned by 20 degrees, which LibreOffice
writes as ``draw:transform="skewX (-5E-017) rotate (...) translate (...)"`` and no ``svg:x``/``svg:y``. It comes in
as an image object with its alt text and its turn; moving and turning it in Claudia patches the transform and leaves
the picture's bytes alone (D460)."""

from __future__ import annotations

from dataclasses import replace

from claudia_creates import SlideAnchor, SlideModel
from claudia_test_documents.case import Case

PICTURE = "Pictures/10000000000000280000001408AA6836.gif"


def import_checks(model: SlideModel) -> None:
    (picture,) = model.objects_on("s1")
    assert (picture.body.kind, picture.body.rotation, picture.body.description) == ("image", 20, "a picture of cats")
    assert (picture.anchor.x, picture.anchor.y, picture.body.w, picture.body.h) == (100, 150, 400, 200)


def modify(model: SlideModel) -> SlideModel:
    picture = model.get("o1")
    model.replace_object(replace(picture.with_body(rotation=75), anchor=SlideAnchor("s1", 300, 400)))
    return model


def after_checks(model: SlideModel) -> None:
    (picture,) = model.objects_on("s1")
    assert (picture.body.rotation, picture.anchor.x, picture.anchor.y) == (75, 300, 400)


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks, preserve_parts=[PICTURE])
