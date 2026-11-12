"""A group, a line, speaker notes with words, a slide transition and an animation sit on the slide whose text box
an edit rewrites. None of them is in the model (the import says so), all of them are in the file afterwards: the
slide's markup is the original's byte for byte except the one paragraph that was edited (D412)."""

from __future__ import annotations

from claudia_creates import SlideModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case


def import_checks(model: SlideModel) -> None:
    assert [(o.body.kind, o.body.paragraph.text, o.body.shape) for o in model.objects_on("s1")] == [
        ("text", "Quarterly plan", None),
        ("shape", "Goal", "circle"),
    ]


def modify(model: SlideModel) -> SlideModel:
    title = model.get("o1")
    words = title.body.paragraph.with_text("Quarterly plan (draft)", ()).written_by("ana")
    model.replace_object(title.with_body(paragraph=words))
    return model


def after_checks(model: SlideModel) -> None:
    assert [o.body.paragraph.text for o in model.objects_on("s1")] == ["Quarterly plan (draft)", "Goal"]


def everything_else_is_untouched(original: bytes, edited: bytes) -> None:
    before = read_parts(original)["content.xml"].decode()
    after = read_parts(edited)["content.xml"].decode()
    assert after == before.replace("Quarterly plan<", "Quarterly plan (draft)<")
    for kept in ("<draw:g>", "<draw:line", "<anim:par", "Mention the budget first.", "presentation:transition-type"):
        assert kept in after


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["styles.xml", "META-INF/manifest.xml"],
    preserve_elements=everything_else_is_untouched,
)
