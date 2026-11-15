"""A picture lives in its own package part (``ppt/media/image1.png``), on a slide the edit never touches at
all -- the other Tier 2 mechanic from the table fixture: a whole part, untouched by the edit, must come back
byte-for-byte identical. The picture is also an image object now (D460): ``pptx_to_slides`` holds it, with its alt
text, and an edit of another slide's text leaves its bytes alone."""

from __future__ import annotations

from claudia_creates import SlideModel
from claudia_test_documents.case import Case


def import_checks(model: SlideModel) -> None:
    assert [(o.body.kind, o.body.paragraph.text) for o in model.objects_on("s1")] == [("text", "Photo attached.")]
    assert [(o.body.kind, o.body.description) for o in model.objects_on("s2")] == [("image", "image.png")]


def modify(model: SlideModel) -> SlideModel:
    obj = model.get("o1")
    new_paragraph = obj.body.paragraph.with_text("Photo attached below.", ()).written_by("ana")
    model.replace_object(obj.with_body(paragraph=new_paragraph))
    return model


def after_checks(model: SlideModel) -> None:
    assert [(o.body.kind, o.body.paragraph.text) for o in model.objects_on("s1")] == [("text", "Photo attached below.")]
    assert [(o.body.kind, o.body.description) for o in model.objects_on("s2")] == [("image", "image.png")]


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["ppt/media/image1.png"],
)
