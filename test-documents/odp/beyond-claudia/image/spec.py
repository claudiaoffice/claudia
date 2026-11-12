"""A picture lives in its own package part (``Pictures/...``) and is placed by a ``draw:frame`` on a slide; the
edit rewrites the words of a text box next to it. The part must come back byte for byte, and so must the frame
that places it (D412)."""

from __future__ import annotations

import re

from claudia_creates import SlideModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

PICTURE = "Pictures/10000000000000100000001083524B19.png"


def import_checks(model: SlideModel) -> None:
    assert [(o.body.kind, o.body.paragraph.text) for o in model.objects_on("s1")] == [("text", "Photo attached.")]
    assert model.objects_on("s2") == []


def modify(model: SlideModel) -> SlideModel:
    obj = model.get("o1")
    words = obj.body.paragraph.with_text("Photo attached below.", ()).written_by("ana")
    model.replace_object(obj.with_body(paragraph=words))
    return model


def after_checks(model: SlideModel) -> None:
    assert [(o.body.kind, o.body.paragraph.text) for o in model.objects_on("s1")] == [("text", "Photo attached below.")]
    assert model.objects_on("s2") == []


def preserve_frame(original: bytes, edited: bytes) -> None:
    frame = re.compile(r"<draw:frame [^>]*><draw:image .*?</draw:frame>", re.S)
    before = frame.search(read_parts(original)["content.xml"].decode())
    after = frame.search(read_parts(edited)["content.xml"].decode())
    assert before is not None and after is not None and before.group() == after.group()


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=[PICTURE, "styles.xml", "META-INF/manifest.xml"],
    preserve_elements=preserve_frame,
)
