"""A deck in German with a text box and a picture turned by 30 degrees that has alt text: the picture comes in as an
image object with its alt text and its turn, and the language comes from the words. Moving and turning the picture and
changing the words patch the file; the picture's bytes stay (D460)."""

from __future__ import annotations

from dataclasses import replace

from claudia_creates import SlideAnchor, SlideModel
from claudia_test_documents.case import Case


def import_checks(model: SlideModel) -> None:
    assert model.language == "de-DE"
    assert [(o.body.kind, o.body.rotation, o.body.description) for o in model.objects_on("s1")] == [
        ("text", 0, ""),
        ("image", 30, "Ein roter Kasten"),
    ]


def modify(model: SlideModel) -> SlideModel:
    picture = model.get("o2")
    model.replace_object(
        replace(
            picture.with_body(rotation=90, description="Ein größerer roter Kasten"), anchor=SlideAnchor("s1", 500, 300)
        )
    )
    return model


def after_checks(model: SlideModel) -> None:
    picture = model.get("o2")
    assert (picture.anchor.x, picture.anchor.y, picture.body.rotation) == (500, 300, 90)
    assert picture.body.description == "Ein größerer roter Kasten"
    assert model.language == "de-DE"


CASE = Case(
    import_checks=import_checks, modify=modify, after_checks=after_checks, preserve_parts=["ppt/media/image1.png"]
)
