"""A real coworker file (plain text, no tracked changes yet) gets an open suggestion added in claudia and
re-exported as a native Word tracked change (D217) -- which ``docx_to_text`` cannot reimport, by design
(python-docx's own ``paragraph.text`` already skips a tracked change's text), so the round-trip leg checks the
raw exported XML directly instead of the reimported model."""

from __future__ import annotations

from io import BytesIO

import docx

from claudia_composes import Suggestion, TextModel, TextRange
from claudia_test_documents.case import Case


def import_checks(model: TextModel) -> None:
    assert [(b.style, b.text) for b in model.blocks] == [("body", "The committee rejected the proposal.")]


def modify(model: TextModel) -> TextModel:
    anchor = TextRange("b1", 14, 22)  # "rejected"
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", anchor, "rejected", "approved", "tone")
    return model


def after_checks(model: TextModel) -> None:
    # python-docx's own `.text` skips a run under `w:ins`/`w:del`, so the tracked word is simply gone from here --
    # expected, not a bug, and exactly what `apply_edits_to_docx`'s own docstring and tests already document.
    assert model.blocks[0].text == "The committee  the proposal."


def export_checks(edited_bytes: bytes) -> None:
    xml = docx.Document(BytesIO(edited_bytes)).paragraphs[0]._p.xml
    assert "<w:delText" in xml and "rejected" in xml
    assert "<w:ins" in xml and "approved" in xml


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks, export_checks=export_checks)
