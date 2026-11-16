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
custom style. Paragraphs can be changed, added and removed; blocks cannot be moved (D456).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from io import BytesIO
from itertools import count
from typing import Any, cast

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.xmlchemy import BaseOxmlElement
from docx.text.paragraph import Paragraph

from claudia_composes import DEFAULT_STYLE, Block, BlockAnchor, Run, Suggestion, TextModel
from claudia_core import Rasterise, VisualObject
from claudia_odf_io import Loss, LossLog
from claudia_opc_io import owns, reconcile

from ._docx_blocks import hidden_content, place, remove
from ._docx_lists import ListWriter, numbering_in, read_lists
from ._docx_pictures import (
    PictureEdits,
    PictureWriter,
    file_pictures,
    unheld_pictures,
)
from ._docx_setup import read_setup, write_language, write_page
from ._docx_styles import WORD_NAMES, WordNames, unsaid_of, write_styles
from ._pictures import picture_losses, pictures_of
from ._style_look import look_for
from ._suggestions import WhenMade, open_replacements, when_made
from ._unwritten import DOCX_WRITTEN, text_unwritten_changes

#: Word's names of the built-in styles mapped back to them, for import: any other name (a custom style, or no style at
#: all) becomes body text and is reported -- the same fallback ``text_to_docx`` uses on the way out.
_CLAUDIA_STYLE = {word_name: claudia_id for claudia_id, word_name in WORD_NAMES.items()}


class UnsupportedEdit(Exception):
    """Raised by :func:`apply_edits_to_docx` for an edit it cannot patch onto the original file: blocks moved
    relative to each other, and a baseline that is not what the file holds. Changing, adding and removing paragraphs
    is supported (D456)."""


def text_to_docx(
    model: TextModel,
    *,
    track_suggestions: bool = True,
    change_times: Mapping[str, str] | None = None,
    rasterise: Rasterise | None = None,
) -> bytes:
    """``model`` as docx bytes: one paragraph per block. When ``track_suggestions`` (the default), every open
    suggestion that proposes a replacement is written as a tracked change instead of being silently dropped; a
    remark (no replacement) carries no text to track and is left out, same as a withdrawn or resolved suggestion.
    ``change_times`` has when each suggestion was made, by id, and dates its tracked change; one with no time is
    written without a date, which Word shows as undated (D411). The pictures floating over the text (an image, a
    rendered text container) are written as anchored drawings in the paragraph they hang from, with their alt text;
    an SVG is shown by the picture ``rasterise`` draws of it, or else by an empty one (D464)."""
    document = Document()
    write_page(document, None, model.page)
    write_language(document, model.language)
    names = _word_names(document, model)
    write_styles(document, model.styles, names, model.palette.colours())
    by_block = open_replacements(model, track=track_suggestions)
    change_ids, when = count(1), when_made(change_times)
    lists = ListWriter(document, model.lists)
    pictures = PictureWriter(document, rasterise)
    for block in model.blocks:
        paragraph = document.add_paragraph(style=names.of(block.style))
        if block.item is not None:
            lists.write(paragraph, block.item)
        marks = [(obj.anchor.offset, pictures.run(obj, asset)) for obj, asset in pictures_of(model, block.id)]
        _fill_paragraph(paragraph, block.text, by_block.get(block.id, []), change_ids, when, marks)
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def _patch_setup(document: Any, baseline: TextModel, current: TextModel) -> tuple[WordNames, set[str]]:
    """Write the page, the language and the styles that changed; the Word names of the styles, and the parts of the
    package that changed with them."""
    owned: set[str] = set()
    if baseline.page != current.page:
        owned |= write_page(document, baseline.page, current.page)
    if baseline.language != current.language:
        write_language(document, current.language)
        owned.add("word/styles.xml")
    names = _word_names(document, current)
    if _write_changed_styles(document, baseline, current, names):
        owned |= {"word/styles.xml", "word/settings.xml"}
    return names, owned


class _BlockWriter:
    """Writes the paragraphs of the blocks that were added or changed into a kept document."""

    def __init__(
        self,
        document: Any,
        names: WordNames,
        lists: ListWriter,
        replacements: dict[str, list[Suggestion]],
        when: WhenMade,
        losses: LossLog | None,
        marks: Mapping[str, list[tuple[int, Any]]],
    ) -> None:
        self.document, self.names, self.lists = document, names, lists
        self.marks = marks  # the pictures of each block that are written with its words (by block id)
        self.replacements, self.when, self.losses = replacements, when, losses
        self.change_ids = count(1)

    def add(self, block: Block, after: Any, before: Any) -> Any:
        """A new paragraph for ``block`` after the element ``after`` or else before ``before``; its element."""
        paragraph = self.document.add_paragraph(style=self.names.of(block.style))
        place(paragraph._p, after, before)
        if block.style not in self.names and self.losses is not None:
            self.losses.add("style", block.style)
        if block.item is not None:
            self.lists.write(paragraph, block.item)
        self._fill(paragraph, block)
        return paragraph._p

    def edit(self, paragraph: Paragraph, before: Block, after: Block) -> Any:
        """``paragraph`` as the changes from ``before`` to ``after`` have it (as it is when there are none); its
        element."""
        if before == after and after.id not in self.replacements:
            return paragraph._p  # neither the text/style nor its suggestions changed: leave it exactly as it is
        if before.style != after.style:  # a style the model does not know stays as the file has it
            paragraph.style = self.names.of(after.style)
        if before.item != after.item:
            self.lists.write(paragraph, after.item)
        _clear_runs(paragraph)
        self._fill(paragraph, after)
        return paragraph._p

    def _fill(self, paragraph: Paragraph, block: Block) -> None:
        _fill_paragraph(
            paragraph,
            block.text,
            self.replacements.get(block.id, []),
            self.change_ids,
            self.when,
            self.marks.get(block.id, []),
        )


#: What a run of text holds: the words and the marks between them. A run that holds anything else (a picture, a note's
#: mark, a field) is not text and stays when the words of its paragraph are written again.
_TEXT_ONLY = tuple(qn(tag) for tag in ("w:rPr", "w:t", "w:tab", "w:br", "w:cr", "w:noBreakHyphen", "w:softHyphen"))


def _clear_runs(paragraph: Paragraph) -> None:
    """Take the runs of words out of ``paragraph``: the new text is written after what stays."""
    for run in list(paragraph.runs):
        if any(child.tag not in _TEXT_ONLY for child in run._element):
            continue
        # python-docx's own documented way to clear a paragraph; a run's ``w:r`` always has the paragraph's
        # ``w:p`` as its parent, so this is never actually None -- lxml-stubs just cannot know that.
        parent = run._element.getparent()
        assert parent is not None
        parent.remove(run._element)


def _remove_block(element: Any, losses: LossLog | None) -> None:
    if losses is not None:
        for kind in hidden_content(element):
            losses.add(f"removed-{kind}")
    remove(element)


def _word_names(document: Any, model: TextModel) -> WordNames:
    """The Word name of each style of ``model``, none of them one that ``document`` has for another style."""
    return WordNames(model.styles, taken={style.name for style in document.styles})


def _fill_paragraph(
    paragraph: Paragraph,
    text: str,
    suggestions: list[Suggestion],
    change_ids: Iterator[int],
    when: WhenMade,
    marks: list[tuple[int, Any]] | None = None,
) -> None:
    """Write ``text`` into ``paragraph`` with its suggestions as tracked changes and ``marks`` (``(offset, run)``: the
    pictures) after the characters they stand behind; one that stands inside words a tracked change deletes follows the
    change."""
    waiting = sorted(marks or [], key=lambda mark: mark[0])
    position = 0
    element = paragraph._p  # python-docx's own documented way to reach markup it does not model (its FAQ)

    def release() -> None:
        while waiting and waiting[0][0] <= position:
            element.append(waiting.pop(0)[1])

    def write(end: int) -> None:
        nonlocal position
        while position < end:
            release()
            cut = min(end, waiting[0][0]) if waiting else end
            paragraph.add_run(text[position:cut])
            position = cut
        release()

    for suggestion in suggestions:
        start, stop = suggestion.anchor.start, suggestion.anchor.end
        if start < position or stop > len(text):
            continue  # the anchor no longer matches this text; skip it rather than guess where it went
        write(start)
        deleted = text[start:stop]
        if deleted:
            element.append(
                _tracked_change("w:del", next(change_ids), suggestion.author, deleted, when(suggestion), deleted=True)
            )
        if suggestion.replacement:
            element.append(
                _tracked_change("w:ins", next(change_ids), suggestion.author, suggestion.replacement, when(suggestion))
            )
        position = stop
    write(len(text))
    for _, run in waiting:
        element.append(run)


def _tracked_change(
    tag: str, change_id: int, author: str | None, text: str, date: str | None, *, deleted: bool = False
) -> BaseOxmlElement:
    """A ``w:ins`` or ``w:del`` wrapping one run of ``text`` (``w:delText`` when ``deleted``, per the schema)."""
    # OxmlElement's own return type is `BaseOxmlElement | etree._Element`: the fallback branch is for a tag python-
    # docx has no custom class for, which none of ``w:ins``/``w:del``/``w:r``/``w:t``/``w:delText`` are (all
    # standard WordprocessingML elements it registers), so the narrower type is what every one of these calls
    # actually returns at runtime.
    change = cast(BaseOxmlElement, OxmlElement(tag))
    change.set(qn("w:id"), str(change_id))
    change.set(qn("w:author"), author or "Claudia AI")
    if date:
        change.set(qn("w:date"), date)
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
    becomes body text, the same fallback ``text_to_docx`` uses going the other way). A picture the model can show as it
    is (an image the app decodes, not cropped or flipped, in its own proportions) comes in as an image object hanging
    from its paragraph, with its alt text (D464). A tracked change's own text
    is not seen here: python-docx's own ``paragraph.text`` already skips it (only runs that are direct children
    of the paragraph count), and re-importing an existing tracked change is not this slice's job."""
    document = Document(BytesIO(docx_bytes))
    reading = read_lists(document.paragraphs, numbering_in(document))
    setup = read_setup(document)
    blocks = []
    for index, paragraph in enumerate(document.paragraphs, start=1):
        style = paragraph.style
        style_id = _CLAUDIA_STYLE.get(style.name, DEFAULT_STYLE) if style is not None else DEFAULT_STYLE
        text = paragraph.text
        runs = (Run(len(text), None),) if text else ()
        blocks.append(Block(f"b{index}", style_id, text, runs, reading.items.get(paragraph._p)))
    model = TextModel(blocks or None, page=setup.page, language=setup.language, lists=reading.book if blocks else None)
    for picture in file_pictures(document):
        if picture.asset.id not in model.images:
            model.define_image(picture.asset)
        model.insert_object(VisualObject(picture.body, BlockAnchor(f"b{picture.block + 1}", picture.offset)))
    return model


def docx_import_losses(docx_bytes: bytes) -> tuple[Loss, ...]:
    """What :func:`docx_to_text` does not show of the file, each as a code (``"table"``, ``"list-look"`` (a list drawn
    otherwise than the model draws it), ``"list-depth"``, ``"page"`` (a page the model cannot hold), ``"frame"``,
    ``"picture"`` (a picture the model does not show as it is: cropped, flipped, stretched, in a table, an image the app
    cannot decode), ``"footnote"``, ``"comment"``, ``"formatting"``, ``"link"``, ``"tracked-change"`` and a ``"style"``
    named by what the file calls it) with how many there are, in the order they come. None of it is lost from the
    *file*: an edit that is exported with :func:`apply_edits_to_docx` keeps all of it."""
    document = Document(BytesIO(docx_bytes))
    body = document.element.body
    losses = LossLog()
    for paragraph in document.paragraphs:
        style = paragraph.style
        if style is not None and style.name not in _CLAUDIA_STYLE and style.name != "Normal":
            losses.add("style", style.name)
    reading = read_lists(document.paragraphs, numbering_in(document))
    held = file_pictures(document)
    counts = {
        "list-look": reading.odd_looks,
        "list-depth": reading.too_deep,
        "page": int(read_setup(document).odd_page),
        "picture": unheld_pictures(document, held),
        "frame": _frames(body),
    }
    for code, tags in _IMPORT_LOSSES:
        number = counts[code] if code in counts else sum(1 for tag in tags for _ in body.iter(qn(tag)))
        if number:
            losses.add(code, count=number)
    return losses.result()


def _frames(body: Any) -> int:  # noqa: ANN401
    """How many drawings and legacy pictures of ``body`` are not pictures (a text box, a shape, a chart, a diagram)."""
    drawings = sum(1 for drawing in body.iter(qn("w:drawing")) if not drawing.xpath(".//pic:pic"))
    return drawings + sum(1 for _ in body.iter(qn("w:pict")))


#: What a docx has that the model does not show, by code in the order it is reported: the elements to count (a
#: ``w:rPr`` is one run's own formatting; the looks and depths of lists are counted by :func:`read_lists`).
_IMPORT_LOSSES = (
    ("table", ("w:tbl",)),
    ("list-look", ()),
    ("list-depth", ()),
    ("page", ()),
    ("frame", ()),
    ("picture", ()),
    ("footnote", ("w:footnoteReference", "w:endnoteReference")),
    ("comment", ("w:commentReference",)),
    ("formatting", ("w:rPr",)),
    ("link", ("w:hyperlink",)),
    ("tracked-change", ("w:ins", "w:del")),
)


def docx_export_losses(
    model: TextModel, *, track_suggestions: bool = True, rasterised: bool = False
) -> tuple[Loss, ...]:
    """What :func:`text_to_docx` cannot put into the file for ``model``, each as a code with how many: a ``"style"``
    (named by its id) that is written as Normal, ``"authorship"`` (who wrote which run of a block: a docx does not
    keep it), a ``"remark"`` (nothing to track), a ``"suggestion"`` that is not written because tracking is off, a
    ``"suggestion-anchor"`` that no longer matches its text, ``"svg-fallback"`` (a picture that is an SVG, which only
    Word 2016 and later draw: another program shows an empty picture unless a rasteriser was given, ``rasterised``),
    ``"rendering-pending"`` (a rendered text container nothing has been drawn for: left out), and what
    :func:`docx_unwritten_changes` says of a fresh file."""
    losses = LossLog()
    names = WordNames(model.styles)
    for block in model.blocks:
        if block.style not in names:
            losses.add("style", block.style)
    for style_id, prop in _unsaid_properties(model):
        losses.add("style-property", f"{style_id}: {prop}")
    authored = sum(1 for block in model.blocks if any(run.author is not None for run in block.runs))
    if authored:
        losses.add("authorship", count=authored)
    open_ones = [s for s in model.suggestions.values() if s.state == "open"]
    remarks = sum(1 for s in open_ones if s.replacement is None)
    if remarks:
        losses.add("remark", count=remarks)
    if not track_suggestions:
        if len(open_ones) > remarks:
            losses.add("suggestion", count=len(open_ones) - remarks)
    else:
        skipped = _unplaced(model)
        if skipped:
            losses.add("suggestion-anchor", count=skipped)
    picture_losses(model, losses, vector_loss=None if rasterised else "svg-fallback")
    return (*losses.result(), *docx_unwritten_changes(model))


def _write_changed_styles(document: Any, baseline: TextModel, current: TextModel, names: WordNames) -> bool:
    """Write the styles of ``current`` that look other than they did in ``baseline`` (or did not exist), and those a
    restyled paragraph now has that the file lacks; ``True`` when the file's styles changed."""
    colours, before_colours = current.palette.colours(), baseline.palette.colours()
    known = {block.id: block.style for block in baseline.blocks}
    wanted = {block.style for block in current.blocks if known.get(block.id) != block.style} - WORD_NAMES.keys()
    changed = set()
    for style in current.styles:
        if style.kind != "paragraph":
            continue
        if (
            style.id in wanted
            and style.id not in baseline.styles.ids()
            or style.id not in baseline.styles.ids()
            or look_for(current.styles, style.id, colours) != look_for(baseline.styles, style.id, before_colours)
            or _parent(current, style.id) != _parent(baseline, style.id)
        ):
            changed.add(style.id)
    if wanted:
        existing = {s.name for s in document.styles}
        changed |= {sid for sid in wanted if names.of(sid) not in existing}
    if not changed:
        return False
    write_styles(document, current.styles, names, colours, only=changed)
    return True


def _parent(model: TextModel, style_id: str) -> str | None:
    return model.styles.get(style_id).based_on if style_id in model.styles.ids() else None


def _unsaid_properties(model: TextModel) -> list[tuple[str, str]]:
    colours = model.palette.colours()
    return [
        (style.id, prop)
        for style in model.styles
        if style.kind == "paragraph"
        for prop in unsaid_of(model.styles, style, colours)
    ]


def _unplaced(model: TextModel) -> int:
    """How many open replacements ``text_to_docx`` skips: those whose anchor no longer matches their block's text."""
    blocks = {block.id: block for block in model.blocks}
    skipped = 0
    for block_id, suggestions in open_replacements(model).items():
        owner = blocks.get(block_id)
        position = 0
        for suggestion in suggestions:
            start, end = suggestion.anchor.start, suggestion.anchor.end
            if owner is None or start < position or end > len(owner.text):
                skipped += 1
            else:
                position = end
    return skipped


def docx_unwritten_changes(model: TextModel, baseline: TextModel | None = None) -> tuple[Loss, ...]:
    """What changed in ``model`` that the docx converters do not write: each a ``"not-written"`` code with the facet
    (``"page"``, ``"language"``, ``"lists"``...) and how many entries of it differ from ``baseline`` -- the model the
    original file was read as, for an edit-and-reexport -- or from an empty text, for a fresh file (``None``)."""
    return text_unwritten_changes(model, baseline, written=DOCX_WRITTEN)


def apply_edits_to_docx(
    original_bytes: bytes,
    baseline: TextModel,
    current: TextModel,
    *,
    track_suggestions: bool = True,
    change_times: Mapping[str, str] | None = None,
    losses: LossLog | None = None,
    rasterise: Rasterise | None = None,
) -> bytes:
    """Re-export ``current`` to docx by patching only what changed since ``baseline`` (the model as it stood
    right after :func:`docx_to_text` imported ``original_bytes``) onto those same bytes, instead of rebuilding
    the file from the model alone -- so a table, an image, a custom style, anything claudia never modeled,
    survives untouched (D217). Reopens ``original_bytes`` fresh, rewrites the paragraphs whose text or style
    changed (and any block an open suggestion now touches, rendered as a tracked change same as
    ``text_to_docx``), then calls :func:`claudia_opc_io.reconcile` so every other part of the package -- and
    every paragraph this call did not touch -- comes back exactly as it was.

    A block that was added is a new paragraph right after the paragraph of the block before it (or right before that
    of the one after it, when it comes first); a block that was removed takes its paragraph with it, and ``losses`` gets
    a ``removed-...`` entry for each picture, note, comment, link or tracked change that went with it. A paragraph that
    ends a section of the file is only emptied, so that the section stays. ``losses`` also gets a ``style`` entry for
    a block whose style the text does not have.

    The pictures of the text are kept in step (D464): a picture that was removed takes its drawing out of the file, one
    that was added is drawn into the paragraph it hangs from (an SVG as ``rasterise`` draws it, else an empty picture),
    one that was moved is put where it hangs now and one that was resized, turned or described changes only that; the
    picture's own bytes stay. A picture of the file that the model does not show (cropped, flipped, in a table) is not
    touched.

    Raises :class:`UnsupportedEdit` for what cannot be patched: a baseline that is not what the file holds, and blocks
    moved relative to each other (a move would have to carry what is inside a paragraph, which it does not know)."""
    held = baseline.blocks
    document = Document(BytesIO(original_bytes))
    paragraphs = document.paragraphs
    if len(paragraphs) != len(held):
        raise UnsupportedEdit("the text the edits are measured from is not what the file holds")
    baseline_by_id = {b.id: b for b in held}
    current_ids = {b.id for b in current.blocks}
    kept = [block.id for block in current.blocks if block.id in baseline_by_id]
    if kept != [block.id for block in held if block.id in current_ids]:
        raise UnsupportedEdit("blocks cannot be moved relative to each other in the file")
    paragraph_of = {block.id: paragraph for block, paragraph in zip(held, paragraphs, strict=True)}
    lists = ListWriter(document, current.lists, read_lists(paragraphs, numbering_in(document)).num_of)
    names, owned = _patch_setup(document, baseline, current)
    for list_id in baseline.lists.ids():
        if list_id in current.lists and current.lists.get(list_id) != baseline.lists.get(list_id):
            lists.restyle(list_id)
    replacements = open_replacements(current, track=track_suggestions)
    rewritten = {
        block.id for block in current.blocks if baseline_by_id.get(block.id) != block or block.id in replacements
    }
    if losses is not None:  # (what a rendered container is that nothing has been drawn for)
        picture_losses(current, losses)
    pictures = PictureEdits(document, baseline, current, rewritten, rasterise, losses)
    for block in held:
        if block.id not in current_ids:
            _remove_block(paragraph_of[block.id]._p, losses)
    writer = _BlockWriter(document, names, lists, replacements, when_made(change_times), losses, pictures.marks)
    last: Any = None  # the element of the block before the one at hand, in the text
    for index, after in enumerate(current.blocks):
        before = baseline_by_id.get(after.id)
        if before is None:
            following = next((paragraph_of[b.id]._p for b in current.blocks[index + 1 :] if b.id in paragraph_of), None)
            last = writer.add(after, last, following)
        else:
            last = writer.edit(paragraph_of[after.id], before, after)
    pictures.settle({block_id: paragraph._p for block_id, paragraph in paragraph_of.items()})
    patched = BytesIO()
    document.save(patched)
    if pictures.changed:
        owned.update(("word/_rels/document.xml.rels", "[Content_Types].xml"))
    return reconcile(original_bytes, patched.getvalue(), owns(["word/document.xml", *lists.owned(), *owned]))
