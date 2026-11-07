"""Exporting a :class:`~claudia_composes.TextModel` to docx, with open suggestions as native tracked changes.

``text_to_docx`` is a minimal base export (paragraphs, built-in styles mapped to Word's own) -- not the ODF-first,
loss-reporting import/export story of E9.5 (D5, D70). What it adds beyond the base is the additive extension the
spike validated: python-docx has no way to read or write ``w:ins``/``w:del`` (tracked changes), so a suggestion's
``original``/``replacement`` is written directly as a tracked deletion and insertion by building the two elements
with ``docx.oxml.OxmlElement`` -- python-docx's own documented escape hatch for markup it does not model -- and
appending them to the paragraph's element. A suggestion becomes something a reviewer can Accept or Reject in Word
like any other tracked change, even though Claudia's own UI shows it as a suggestion.
"""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from itertools import count

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.xmlchemy import BaseOxmlElement
from docx.text.paragraph import Paragraph

from claudia_composes import Suggestion, TextModel

#: The built-in styles (model.py's BUILTIN_STYLES) mapped to Word's own built-in style names; anything else
#: (a deviated or custom style) falls back to Normal -- styling fidelity beyond this is E9.5's job, not this slice's.
_WORD_STYLE = {
    "title": "Title",
    "heading-1": "Heading 1",
    "heading-2": "Heading 2",
    "quote": "Quote",
}


def text_to_docx(model: TextModel, *, track_suggestions: bool = True) -> bytes:
    """``model`` as docx bytes: one paragraph per block. When ``track_suggestions`` (the default), every open
    suggestion that proposes a replacement is written as a tracked change instead of being silently dropped; a
    remark (no replacement) carries no text to track and is left out, same as a withdrawn or resolved suggestion."""
    document = Document()
    by_block: dict[str, list[Suggestion]] = {}
    if track_suggestions:
        for suggestion in model.suggestions.values():
            if suggestion.state == "open" and suggestion.replacement is not None:
                by_block.setdefault(suggestion.anchor.block, []).append(suggestion)
    change_ids = count(1)
    for block in model.blocks:
        paragraph = document.add_paragraph(style=_WORD_STYLE.get(block.style, "Normal"))
        ordered = sorted(by_block.get(block.id, ()), key=lambda s: s.anchor.start)
        _fill_paragraph(paragraph, block.text, ordered, change_ids)
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def _fill_paragraph(paragraph: Paragraph, text: str, suggestions: list[Suggestion], change_ids: Iterator[int]) -> None:
    position = 0
    element = paragraph._p  # python-docx's own documented way to reach markup it does not model (its FAQ)
    for suggestion in suggestions:
        start, end = suggestion.anchor.start, suggestion.anchor.end
        if start < position or end > len(text):
            continue  # the anchor no longer matches this text; skip it rather than guess where it went
        if start > position:
            paragraph.add_run(text[position:start])
        deleted = text[start:end]
        if deleted:
            element.append(_tracked_change("w:del", next(change_ids), suggestion.author, deleted, deleted=True))
        if suggestion.replacement:
            element.append(_tracked_change("w:ins", next(change_ids), suggestion.author, suggestion.replacement))
        position = end
    if position < len(text):
        paragraph.add_run(text[position:])


def _tracked_change(
    tag: str, change_id: int, author: str | None, text: str, *, deleted: bool = False
) -> BaseOxmlElement:
    """A ``w:ins`` or ``w:del`` wrapping one run of ``text`` (``w:delText`` when ``deleted``, per the schema)."""
    change = OxmlElement(tag)
    change.set(qn("w:id"), str(change_id))
    change.set(qn("w:author"), author or "Claudia AI")
    run = OxmlElement("w:r")
    run_text = OxmlElement("w:delText" if deleted else "w:t")
    run_text.set(qn("xml:space"), "preserve")
    run_text.text = text
    run.append(run_text)
    change.append(run)
    return change
