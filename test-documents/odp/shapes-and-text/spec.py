"""A file written by LibreOffice itself (converted from the pptx fixture of the same name, then checked in): a
PowerPoint text box arrives as an unfilled rectangle with words in it and is read as a text box, a circle and a
rectangle as the shapes they are, read back from LibreOffice's ``ooxml-*`` outline names. Editing one object's
words and moving another leaves the rest of ``content.xml`` and every other part as it was (D412)."""

from __future__ import annotations

from dataclasses import replace

from claudia_creates import SlideAnchor, SlideModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case


def import_checks(model: SlideModel) -> None:
    assert model.slides == ["s1", "s2"]
    assert [(o.body.kind, o.body.paragraph.text, o.body.shape) for o in model.objects_on("s1")] == [
        ("text", "Welcome to Claudia", None),
        ("shape", "Idea", "circle"),
    ]
    assert [(o.body.kind, o.body.paragraph.text, o.body.shape) for o in model.objects_on("s2")] == [
        ("shape", "Box", "rectangle")
    ]


def modify(model: SlideModel) -> SlideModel:
    circle = model.get("o2")
    words = circle.body.paragraph.with_text("Idea (refined)", ()).written_by("ana")
    model.replace_object(circle.with_body(paragraph=words))
    box = model.get("o3")
    model.replace_object(replace(box, anchor=SlideAnchor(box.anchor.slide, 150, 550)))
    return model


def after_checks(model: SlideModel) -> None:
    assert [o.body.paragraph.text for o in model.objects_on("s1")] == ["Welcome to Claudia", "Idea (refined)"]
    box = model.objects_on("s2")[0]
    assert (box.anchor.x, box.anchor.y) == (150, 550)


def the_text_box_is_untouched(original: bytes, edited: bytes) -> None:
    before = read_parts(original)["content.xml"].decode()
    after = read_parts(edited)["content.xml"].decode()
    start = before.index('<draw:custom-shape draw:name="TextBox 1"')
    end = before.index("</draw:custom-shape>", start) + len("</draw:custom-shape>")
    assert before[start:end] in after
    assert "Idea (refined)" in after and "Idea<" not in after


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["styles.xml", "settings.xml", "META-INF/manifest.xml"],
    preserve_elements=the_text_box_is_untouched,
)
