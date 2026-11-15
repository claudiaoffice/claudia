"""A paragraph that is split in two and a paragraph that goes: the table and the picture of the file stay where they
were, and the paragraphs nobody touched are the file's own (D456)."""

from __future__ import annotations

from io import BytesIO

import docx

from claudia_composes import TextModel
from claudia_test_documents.case import Case

WORDS = ["Quarterly report", "Sales rose. Costs fell.", "The chart:", "", "Thank you."]


def import_checks(model: TextModel) -> None:
    assert [b.text for b in model.blocks] == WORDS  # the picture's paragraph is an empty block


def modify(model: TextModel) -> TextModel:
    model.split(model.blocks[1].id, 11, "n1", "body")  # "Sales rose." / " Costs fell."
    model.join(model.blocks[-1].id, model.blocks[-2].id, 0)  # "Thank you." goes into the picture's paragraph
    return model


def after_checks(model: TextModel) -> None:
    assert [b.text for b in model.blocks] == [
        "Quarterly report",
        "Sales rose.",
        " Costs fell.",
        "The chart:",
        "Thank you.",
    ]


def table_and_picture_stay(original: bytes, edited: bytes) -> None:
    before, after = docx.Document(BytesIO(original)), docx.Document(BytesIO(edited))
    assert before.tables[0]._tbl.xml == after.tables[0]._tbl.xml
    assert len(after.inline_shapes) == 1
    body = [child.tag.rsplit("}", 1)[1] for child in after.element.body]
    assert body[:5] == ["p", "p", "p", "tbl", "p"], body


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["word/styles.xml", "word/media/image1.png"],
    preserve_elements=table_and_picture_stay,
)
