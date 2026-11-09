"""A table -- content claudia has no model for at all -- sits on the same slide (the same part) an edit
rewrites, so its survival is not a separate-part guarantee (unlike the image fixture): it depends on python-pptx
keeping the table's own graphic-frame element untouched while only the edited text box's element changes.
``preserve_elements`` checks that directly, at the element level, same mechanic as docx's own table fixture."""

from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import pptx

from claudia_creates import SlideModel
from claudia_test_documents.case import Case


def import_checks(model: SlideModel) -> None:
    # the table is invisible to `pptx_to_slides`: only the text box becomes an object -- exactly the claim this
    # case is testing.
    assert [(o.kind, o.text) for o in model.objects_on("s1")] == [("text", "Status report.")]


def modify(model: SlideModel) -> SlideModel:
    obj = model.get("o1")
    model.replace_object(replace(obj, text="Status report (updated)."))
    return model


def after_checks(model: SlideModel) -> None:
    assert [(o.kind, o.text) for o in model.objects_on("s1")] == [("text", "Status report (updated).")]


def preserve_table(original_bytes: bytes, edited_bytes: bytes) -> None:
    before = next(s for s in pptx.Presentation(BytesIO(original_bytes)).slides[0].shapes if s.has_table)
    after = next(s for s in pptx.Presentation(BytesIO(edited_bytes)).slides[0].shapes if s.has_table)
    assert before._element.xml == after._element.xml
    rows = [[cell.text for cell in row.cells] for row in after.table.rows]
    assert rows == [["Region", "Amount"], ["North", "120"]]


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks, preserve_elements=preserve_table)
