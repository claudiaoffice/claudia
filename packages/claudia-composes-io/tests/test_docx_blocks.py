"""Paragraphs added to and removed from a kept docx: they land where the text says, what the file holds around them
stays, and what goes with a removed paragraph is named (D456)."""

from __future__ import annotations

import base64
import random
from io import BytesIO

import pytest
from claudia_composes_io import UnsupportedEdit, apply_edits_to_docx, docx_to_text
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from test_docx_setup import parts, saved

from claudia_composes import Block, TextModel
from claudia_core import StyleDef
from claudia_odf_io import Loss, LossLog

_PNG = BytesIO(
    base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
)


def a_file(*texts: str, table_after: int | None = None) -> bytes:
    """A file with a paragraph for each text, and a table after the ``table_after``-th of them."""
    document = Document()
    for index, text in enumerate(texts, start=1):
        document.add_paragraph(text)
        if index == table_after:
            document.add_table(rows=1, cols=2).cell(0, 0).text = "cell"
    return saved(document)


def patch(original: bytes, edit, *, losses: LossLog | None = None) -> bytes:
    baseline, current = docx_to_text(original), docx_to_text(original)
    edit(current)
    return apply_edits_to_docx(original, baseline, current, losses=losses)


def body_of(data: bytes) -> list[str]:
    """The paragraphs and tables of the body, as ``text`` and ``[table]``."""
    body = Document(BytesIO(data)).element.body
    return [
        "[table]" if child.tag == qn("w:tbl") else "".join(t.text or "" for t in child.iter(qn("w:t")))
        for child in body
        if child.tag in (qn("w:p"), qn("w:tbl"))
    ]


def test_a_paragraph_added_at_the_end_is_the_last_one_before_the_end_of_the_body():
    edited = patch(a_file("one", "two"), lambda m: m.blocks.append(Block("n1", "body", "three")))
    assert body_of(edited) == ["one", "two", "three"]
    assert [b.text for b in docx_to_text(edited).blocks] == ["one", "two", "three"]


def test_a_paragraph_added_in_the_middle_follows_the_paragraph_of_the_block_before_it():
    edited = patch(a_file("one", "two"), lambda m: m.blocks.insert(1, Block("n1", "heading-1", "new")))
    assert body_of(edited) == ["one", "new", "two"]
    assert [b.style for b in docx_to_text(edited).blocks] == ["body", "heading-1", "body"]


def test_a_paragraph_added_at_the_start_comes_before_the_one_that_was_first():
    edited = patch(a_file("one", "two"), lambda m: m.blocks.insert(0, Block("n1", "title", "new")))
    assert body_of(edited) == ["new", "one", "two"]


def test_several_paragraphs_added_together_keep_their_order():
    def edit(model: TextModel) -> None:
        model.blocks[1:1] = [Block("n1", "body", "a"), Block("n2", "body", "b"), Block("n3", "body", "c")]

    assert body_of(patch(a_file("one", "two"), edit)) == ["one", "a", "b", "c", "two"]


def test_a_paragraph_added_after_one_that_a_table_follows_stays_with_that_paragraph():
    edited = patch(a_file("one", "two", table_after=1), lambda m: m.blocks.insert(1, Block("n1", "body", "new")))
    assert body_of(edited) == ["one", "new", "[table]", "two"]


def test_a_paragraph_removed_is_gone_and_the_table_next_to_it_stays():
    edited = patch(a_file("one", "two", "three", table_after=2), lambda m: m.blocks.pop(1))
    assert body_of(edited) == ["one", "[table]", "three"]


def test_every_paragraph_removed_leaves_the_table_and_a_file_that_can_be_opened_again():
    edited = patch(a_file("one", "two", table_after=1), lambda m: m.blocks.clear())
    assert body_of(edited) == ["[table]"]
    assert [b.text for b in docx_to_text(edited).blocks] == [""]  # a text always has a block: here the empty one


def test_the_paragraphs_that_were_not_touched_are_the_ones_of_the_file():
    original = a_file("one", "two", "three")

    def edit(model: TextModel) -> None:
        model.blocks.pop(1)
        model.blocks.append(Block("n1", "body", "four"))

    def paragraph(data: bytes, index: int) -> bytes:
        return Document(BytesIO(data)).paragraphs[index]._p.xml.encode()

    edited = patch(original, edit)
    assert paragraph(edited, 0) == paragraph(original, 0)
    assert paragraph(edited, 1) == paragraph(original, 2)
    assert parts(edited)["word/styles.xml"] == parts(original)["word/styles.xml"]


def test_what_goes_with_a_removed_paragraph_is_named():
    document = Document()
    document.add_paragraph("one")
    paragraph = document.add_paragraph("two")
    for tag in ("w:hyperlink", "w:ins"):
        paragraph._p.append(OxmlElement(tag))
    for tag in ("w:drawing", "w:footnoteReference", "w:commentReference"):
        run = OxmlElement("w:r")
        run.append(OxmlElement(tag))
        paragraph._p.append(run)
    losses = LossLog()
    patch(saved(document), lambda m: m.blocks.pop(1), losses=losses)
    assert losses.result() == (
        Loss("removed-frame", "", 1),
        Loss("removed-footnote", "", 1),
        Loss("removed-comment", "", 1),
        Loss("removed-link", "", 1),
        Loss("removed-tracked-change", "", 1),
    )


def test_a_paragraph_that_ends_a_section_is_emptied_and_not_taken_out():
    document = Document()
    document.add_paragraph("one")
    document.add_section()
    document.add_paragraph("three")
    ends = next(p for p in document.paragraphs if p._p.find(qn("w:pPr") + "/" + qn("w:sectPr")) is not None)
    ends.add_run("two")
    original = saved(document)
    index = next(i for i, b in enumerate(docx_to_text(original).blocks) if b.text == "two")
    edited = patch(original, lambda m: m.blocks.pop(index))
    assert len(Document(BytesIO(edited)).sections) == 2
    assert "two" not in body_of(edited) and body_of(edited).count("") == 1


def test_blocks_moved_relative_to_each_other_cannot_be_patched():
    original = a_file("one", "two")
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.blocks.reverse()
    with pytest.raises(UnsupportedEdit, match="moved"):
        apply_edits_to_docx(original, baseline, current)


def test_a_paragraph_added_with_a_style_the_file_lacks_is_given_the_style():
    def edit(model: TextModel) -> None:
        model.styles.add(StyleDef("callout", "Call out", "", "body", {"font-style": "italic"}))
        model.blocks.append(Block("n1", "callout", "new"))

    edited = Document(BytesIO(patch(a_file("one"), edit)))
    assert edited.paragraphs[1].style.name == "Call out" and edited.styles["Call out"].font.italic is True


def test_a_paragraph_added_with_a_style_the_text_lacks_is_body_text_and_a_loss():
    losses = LossLog()
    edited = patch(a_file("one"), lambda m: m.blocks.append(Block("n1", "unknown", "new")), losses=losses)
    assert Document(BytesIO(edited)).paragraphs[1].style.name == "Normal"
    assert losses.result() == (Loss("style", "unknown", 1),)


@pytest.mark.parametrize("seed", range(8))
def test_whatever_is_added_and_removed_the_file_says_the_blocks_in_their_order(seed: int):
    rng = random.Random(seed)
    original = a_file(*(f"p{i}" for i in range(6)), table_after=3)
    baseline = docx_to_text(original)
    current = docx_to_text(original)
    for number in range(rng.randint(1, 6)):
        if current.blocks and rng.random() < 0.5:
            current.blocks.pop(rng.randrange(len(current.blocks)))
        else:
            current.blocks.insert(rng.randint(0, len(current.blocks)), Block(f"n{number}", "body", f"new{number}"))
    edited = apply_edits_to_docx(original, baseline, current)
    assert [b.text for b in docx_to_text(edited).blocks] == [b.text for b in current.blocks]
    assert body_of(edited).count("[table]") == 1


def test_the_words_of_a_paragraph_with_a_picture_are_written_again_and_the_picture_stays():
    document = Document()
    paragraph = document.add_paragraph("before ")
    paragraph.add_run().add_picture(_PNG)
    original = saved(document)

    def edit(model: TextModel) -> None:
        model.blocks[0] = Block(model.blocks[0].id, "body", "after")

    edited = Document(BytesIO(patch(original, edit)))
    assert len(edited.inline_shapes) == 1 and edited.paragraphs[0].text == "after"
