"""An embedded image lives in its own package part (``word/media/image1.png``), unlike the table fixture's
element-sitting-inside-a-rewritten-part case -- so this is the other Tier 2 mechanic: a whole part, left alone
by the edit, must come back byte-for-byte identical. The paragraph that actually holds the image (an inline
shape, no text of its own) is never touched by the edit in this case, on purpose."""

from __future__ import annotations

from claudia_composes import DEFAULT_STYLE, TextModel
from claudia_core import Run
from claudia_test_documents.case import Case


def import_checks(model: TextModel) -> None:
    # python-docx gives the image its own paragraph (empty text -- a drawing is not a `w:t` run), between the
    # two with real text; claudia imports it the same way, as an ordinary, if empty, body paragraph.
    assert [(b.style, b.text) for b in model.blocks] == [
        (DEFAULT_STYLE, "Photo attached."),
        (DEFAULT_STYLE, ""),
        (DEFAULT_STYLE, "See above."),
    ]


def modify(model: TextModel) -> TextModel:
    # a block is immutable (D181); swap its whole text in through the same remove/insert the model builds
    # character edits from.
    block_id, new_text = model.blocks[0].id, "Photo attached below."
    model.remove(block_id, 0, len(model.block(block_id).text))
    model.insert(block_id, 0, new_text, [Run(len(new_text), None)])
    return model


def after_checks(model: TextModel) -> None:
    assert [(b.style, b.text) for b in model.blocks] == [
        (DEFAULT_STYLE, "Photo attached below."),
        (DEFAULT_STYLE, ""),
        (DEFAULT_STYLE, "See above."),
    ]


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["word/media/image1.png"],
)
