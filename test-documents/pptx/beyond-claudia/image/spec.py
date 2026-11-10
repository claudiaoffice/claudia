"""A picture lives in its own package part (``ppt/media/image1.png``), on a slide the edit never touches at
all -- the other Tier 2 mechanic from the table fixture: a whole part, untouched by the edit, must come back
byte-for-byte identical. ``slides_to_pptx`` cannot export claudia's own "image" object kind yet (model.py's
docstring), so a picture is never modeled -- `pptx_to_slides` leaves the slide it is on with no objects at all."""

from __future__ import annotations

from claudia_creates import SlideModel
from claudia_test_documents.case import Case


def import_checks(model: SlideModel) -> None:
    assert [(o.body.kind, o.body.paragraph.text) for o in model.objects_on("s1")] == [("text", "Photo attached.")]
    assert model.objects_on("s2") == []


def modify(model: SlideModel) -> SlideModel:
    obj = model.get("o1")
    new_paragraph = obj.body.paragraph.with_text("Photo attached below.", ()).written_by("ana")
    model.replace_object(obj.with_body(paragraph=new_paragraph))
    return model


def after_checks(model: SlideModel) -> None:
    assert [(o.body.kind, o.body.paragraph.text) for o in model.objects_on("s1")] == [("text", "Photo attached below.")]
    assert model.objects_on("s2") == []


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["ppt/media/image1.png"],
)
