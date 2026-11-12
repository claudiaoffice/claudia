"""A table -- content claudia has no model for -- shares ``content.xml`` with the text box an edit rewrites, and with
a preview picture of itself in a part of its own. Both must come back as they were: the frame (table and preview
reference) byte for byte in ``content.xml``, the preview part byte for byte in the package (D412)."""

from __future__ import annotations

import re

from claudia_creates import SlideModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

PREVIEW = "Pictures/TablePreview1.svm"


def import_checks(model: SlideModel) -> None:
    assert [(o.body.kind, o.body.paragraph.text) for o in model.objects_on("s1")] == [("text", "Status report.")]


def modify(model: SlideModel) -> SlideModel:
    obj = model.get("o1")
    words = obj.body.paragraph.with_text("Status report (updated).", ()).written_by("ana")
    model.replace_object(obj.with_body(paragraph=words))
    return model


def after_checks(model: SlideModel) -> None:
    assert [(o.body.kind, o.body.paragraph.text) for o in model.objects_on("s1")] == [
        ("text", "Status report (updated).")
    ]


def preserve_table(original: bytes, edited: bytes) -> None:
    frame = re.compile(r"<draw:frame [^>]*><table:table>.*?</draw:frame>", re.S)
    before = frame.search(read_parts(original)["content.xml"].decode())
    after = frame.search(read_parts(edited)["content.xml"].decode())
    assert before is not None and after is not None and before.group() == after.group()


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=[PREVIEW, "styles.xml", "META-INF/manifest.xml"],
    preserve_elements=preserve_table,
)
