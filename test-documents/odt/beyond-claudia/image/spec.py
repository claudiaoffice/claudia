"""A picture lives in its own part (``Pictures/...``) and is anchored in a paragraph by a ``draw:frame``. Both must
come back unchanged from an edit of the paragraph next to it: the part byte for byte, and the paragraph that holds
the frame (no text of its own) byte for byte inside ``content.xml``."""

from __future__ import annotations

import re

from claudia_composes import DEFAULT_STYLE, TextModel
from claudia_core import Run
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

PICTURE = "Pictures/10000000000000100000001083524B19.png"


def import_checks(model: TextModel) -> None:
    assert [(b.style, b.text) for b in model.blocks] == [
        (DEFAULT_STYLE, "Photo attached."),
        (DEFAULT_STYLE, ""),
        (DEFAULT_STYLE, "See above."),
    ]


def modify(model: TextModel) -> TextModel:
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


def preserve_frame(original: bytes, edited: bytes) -> None:
    frame = re.compile(r"<text:p [^>]*><draw:frame .*?</draw:frame></text:p>", re.S)
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
