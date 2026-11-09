"""A table -- content claudia has no model for at all -- sits inside the same part (``word/document.xml``) an
edit rewrites, so its own survival is not a separate-part guarantee (unlike the image fixture): it depends on
python-docx keeping the table's own lxml element untouched while only the edited paragraph's element changes.
``preserve_elements`` checks that directly, at the element level, rather than claiming anything about claudia
understanding tables -- it still has nothing to say about them."""

from __future__ import annotations

from io import BytesIO

import docx

from claudia_composes import DEFAULT_STYLE, TextModel
from claudia_test_documents.case import Case
from claudia_test_documents.edits import retext_block


def import_checks(model: TextModel) -> None:
    # the table is invisible to `docx_to_text`: `document.paragraphs` already skips it, so only the two
    # surrounding paragraphs become blocks -- exactly the claim this case is testing.
    assert [(b.style, b.text) for b in model.blocks] == [
        (DEFAULT_STYLE, "Status report."),
        (DEFAULT_STYLE, "End of report."),
    ]


def modify(model: TextModel) -> TextModel:
    return retext_block(model, 0, "Status report (updated).")


def after_checks(model: TextModel) -> None:
    assert [(b.style, b.text) for b in model.blocks] == [
        (DEFAULT_STYLE, "Status report (updated)."),
        (DEFAULT_STYLE, "End of report."),
    ]


def preserve_table(original_bytes: bytes, edited_bytes: bytes) -> None:
    before = docx.Document(BytesIO(original_bytes)).tables[0]
    after = docx.Document(BytesIO(edited_bytes)).tables[0]
    assert before._tbl.xml == after._tbl.xml
    assert [[cell.text for cell in row.cells] for row in after.rows] == [["Region", "Amount"], ["North", "120"]]


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks, preserve_elements=preserve_table)
