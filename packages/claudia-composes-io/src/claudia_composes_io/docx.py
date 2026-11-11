"""Converting between a :class:`~claudia_composes.TextModel` and docx, with open suggestions as native tracked
changes, and a real edit-and-reexport path that keeps what claudia never modeled (D135, D217).

``text_to_docx`` is a minimal base export (paragraphs, built-in styles mapped to Word's own) -- not the ODF-first,
loss-reporting import/export story of E9.5 (D5, D70). What it adds beyond the base is the additive extension the
spike validated: python-docx has no way to read or write ``w:ins``/``w:del`` (tracked changes), so a suggestion's
``original``/``replacement`` is written directly as a tracked deletion and insertion by building the two elements
with ``docx.oxml.OxmlElement`` -- python-docx's own documented escape hatch for markup it does not model -- and
appending them to the paragraph's element. A suggestion becomes something a reviewer can Accept or Reject in Word
like any other tracked change, even though Claudia's own UI shows it as a suggestion.

``docx_to_text`` is the reverse: a docx's paragraphs become a :class:`TextModel`, Word's built-in styles mapped
back. ``apply_edits_to_docx`` closes the loop D217 set out to fix: re-exporting an *edited* imported document by
patching only the changed paragraphs onto the original bytes (through ``claudia_opc_io.reconcile``), instead of
rebuilding the file from the model alone and losing everything claudia never modeled -- a table, an image, a
custom style. See the implementation note for what it does not cover yet (adding or removing a paragraph).
"""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from itertools import count
from typing import cast

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.xmlchemy import BaseOxmlElement
from docx.text.paragraph import Paragraph

from claudia_composes import DEFAULT_STYLE, Block, Run, Suggestion, TextModel
from claudia_opc_io import owns, reconcile

from ._suggestions import open_replacements

#: The built-in styles (model.py's BUILTIN_STYLES) mapped to Word's own built-in style names; anything else
#: (a deviated or custom style) falls back to Normal -- styling fidelity beyond this is E9.5's job, not this slice's.
_WORD_STYLE = {
    "title": "Title",
    "heading-1": "Heading 1",
    "heading-2": "Heading 2",
    "quote": "Quote",
}
#: The reverse of ``_WORD_STYLE``, for import: anything not one of these four names (including "Normal", a custom
#: style, or no style at all) becomes body text -- the same fallback ``text_to_docx`` uses on the way out.
_CLAUDIA_STYLE = {word_name: claudia_id for claudia_id, word_name in _WORD_STYLE.items()}


class UnsupportedEdit(Exception):
    """Raised by :func:`apply_edits_to_docx` for an edit it cannot patch onto the original file yet: adding or
    removing a paragraph. Changing an existing paragraph's text or style is supported; see the implementation
    note for what is still missing."""


def text_to_docx(model: TextModel, *, track_suggestions: bool = True) -> bytes:
    """``model`` as docx bytes: one paragraph per block. When ``track_suggestions`` (the default), every open
    suggestion that proposes a replacement is written as a tracked change instead of being silently dropped; a
    remark (no replacement) carries no text to track and is left out, same as a withdrawn or resolved suggestion."""
    document = Document()
    by_block = open_replacements(model, track=track_suggestions)
    change_ids = count(1)
    for block in model.blocks:
        paragraph = document.add_paragraph(style=_WORD_STYLE.get(block.style, "Normal"))
        _fill_paragraph(paragraph, block.text, by_block.get(block.id, []), change_ids)
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
    # OxmlElement's own return type is `BaseOxmlElement | etree._Element`: the fallback branch is for a tag python-
    # docx has no custom class for, which none of ``w:ins``/``w:del``/``w:r``/``w:t``/``w:delText`` are (all
    # standard WordprocessingML elements it registers), so the narrower type is what every one of these calls
    # actually returns at runtime.
    change = cast(BaseOxmlElement, OxmlElement(tag))
    change.set(qn("w:id"), str(change_id))
    change.set(qn("w:author"), author or "Claudia AI")
    run = OxmlElement("w:r")
    run_text = OxmlElement("w:delText" if deleted else "w:t")
    run_text.set(qn("xml:space"), "preserve")
    run_text.text = text
    run.append(run_text)
    change.append(run)
    return change


def docx_to_text(docx_bytes: bytes) -> TextModel:
    """``docx_bytes`` as a :class:`~claudia_composes.TextModel`: one block per paragraph, in order, Word's
    built-in styles mapped back to claudia's (anything else -- "Normal", a custom style, no style at all --
    becomes body text, the same fallback ``text_to_docx`` uses going the other way). A tracked change's own text
    is not seen here: python-docx's own ``paragraph.text`` already skips it (only runs that are direct children
    of the paragraph count), and re-importing an existing tracked change is not this slice's job."""
    document = Document(BytesIO(docx_bytes))
    blocks = []
    for index, paragraph in enumerate(document.paragraphs, start=1):
        style = paragraph.style
        style_id = _CLAUDIA_STYLE.get(style.name, DEFAULT_STYLE) if style is not None else DEFAULT_STYLE
        text = paragraph.text
        blocks.append(Block(f"b{index}", style_id, text, (Run(len(text), None),) if text else ()))
    return TextModel(blocks) if blocks else TextModel()


def apply_edits_to_docx(
    original_bytes: bytes, baseline: TextModel, current: TextModel, *, track_suggestions: bool = True
) -> bytes:
    """Re-export ``current`` to docx by patching only what changed since ``baseline`` (the model as it stood
    right after :func:`docx_to_text` imported ``original_bytes``) onto those same bytes, instead of rebuilding
    the file from the model alone -- so a table, an image, a custom style, anything claudia never modeled,
    survives untouched (D217). Reopens ``original_bytes`` fresh, rewrites the paragraphs whose text or style
    changed (and any block an open suggestion now touches, rendered as a tracked change same as
    ``text_to_docx``), then calls :func:`claudia_opc_io.reconcile` so every other part of the package -- and
    every paragraph this call did not touch -- comes back exactly as it was.

    Raises :class:`UnsupportedEdit` if a block was added or removed since ``baseline``: patching a paragraph's
    own content onto the original is covered; inserting or deleting a paragraph in it is not, yet."""
    baseline_by_id = {b.id: b for b in baseline.blocks}
    current_by_id = {b.id: b for b in current.blocks}
    added = current_by_id.keys() - baseline_by_id.keys()
    removed = baseline_by_id.keys() - current_by_id.keys()
    if added or removed:
        raise UnsupportedEdit("adding or removing a paragraph cannot be patched onto the original file yet")
    position_of = {block.id: index for index, block in enumerate(baseline.blocks)}
    by_block = open_replacements(current, track=track_suggestions)
    document = Document(BytesIO(original_bytes))
    paragraphs = document.paragraphs
    change_ids = count(1)
    for block_id, after in current_by_id.items():
        if baseline_by_id[block_id] == after and block_id not in by_block:
            continue  # neither the text/style nor its suggestions changed: leave the paragraph exactly as is
        paragraph = paragraphs[position_of[block_id]]
        paragraph.style = _WORD_STYLE.get(after.style, "Normal")
        for run in list(paragraph.runs):
            # python-docx's own documented way to clear a paragraph; a run's ``w:r`` always has the paragraph's
            # ``w:p`` as its parent, so this is never actually None -- lxml-stubs just cannot know that.
            parent = run._element.getparent()
            assert parent is not None
            parent.remove(run._element)
        _fill_paragraph(paragraph, after.text, by_block.get(block_id, []), change_ids)
    patched = BytesIO()
    document.save(patched)
    return reconcile(original_bytes, patched.getvalue(), owns(["word/document.xml"]))
