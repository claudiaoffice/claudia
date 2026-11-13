"""A file written by LibreOffice itself (converted from the docx fixture of the same name, then checked in): its
Title / Heading 1 / Heading 2 styles map to claudia's style ids on import, and an edit to one paragraph leaves
every other paragraph, the styles and the rest of the package byte-identical (D401)."""

from __future__ import annotations

import re

from claudia_composes import TextModel
from claudia_core import Run
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

BLOCKS = [
    ("title", "Claudia Field Notes"),
    ("heading-1", "Introduction"),
    ("body", "This is the introduction."),
    ("heading-2", "Background"),
    ("body", "More background text."),
]


def import_checks(model: TextModel) -> None:
    assert [(b.style, b.text) for b in model.blocks] == BLOCKS


def modify(model: TextModel) -> TextModel:
    block_id, new_text = model.blocks[2].id, "This is the revised introduction."
    model.remove(block_id, 0, len(model.block(block_id).text))
    model.insert(block_id, 0, new_text, [Run(len(new_text), None)])
    return model


def after_checks(model: TextModel) -> None:
    assert [(b.style, b.text) for b in model.blocks] == [
        *BLOCKS[:2],
        ("body", "This is the revised introduction."),
        *BLOCKS[3:],
    ]


def preserve_other_paragraphs(original: bytes, edited: bytes) -> None:
    before = read_parts(original)["content.xml"].decode()
    after = read_parts(edited)["content.xml"].decode()
    pattern = re.compile(r"<text:p text:style-name=\"[^\"]*\">This is the introduction\.</text:p>")
    match = pattern.search(before)
    assert match is not None
    assert after[: match.start()] == before[: match.start()]  # everything before the edited paragraph
    assert after.endswith(before[match.end() :])  # and everything after it


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["styles.xml", "meta.xml", "settings.xml", "META-INF/manifest.xml"],
    preserve_elements=preserve_other_paragraphs,
)
