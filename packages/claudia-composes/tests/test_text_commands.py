"""The commands of the text model: typing, structure, styles, authorship, undo with colleagues."""

import pytest
from composes_helpers import SENTENCE, text_of, texts

from claudia_composes import (
    DeleteText,
    InsertText,
    JoinBlocks,
    SetStyle,
    SplitBlock,
    TextModel,
)
from claudia_composes.runs import Run
from claudia_core import Batch, CommandLog, Document, UndoConflict


def authors(doc, block="b1"):
    return [(r.length, r.author, r.via) for r in doc.model.block(block).runs]


# ----------------------------------------------------------------------------- typing
def test_a_new_document_has_one_empty_body_paragraph():
    model = TextModel.empty()
    assert [(b.id, b.style, b.text) for b in model.blocks] == [("b1", "body", "")]


def test_typing_and_undo(doc):
    doc.execute(InsertText("b1", 4, "very "), author="ben")
    assert text_of(doc).startswith("the very quick")
    doc.undo("ben")
    assert text_of(doc) == SENTENCE


def test_typing_outside_the_paragraph_is_refused_and_changes_nothing(doc):
    for bad in (InsertText("b1", 999, "x"), InsertText("nope", 0, "x"), DeleteText("b1", 40, 10)):
        with pytest.raises((IndexError, KeyError)):
            doc.execute(bad, author="ben")
    assert text_of(doc) == SENTENCE


def test_what_was_typed_is_credited_to_whoever_typed_it(doc):
    doc.execute(InsertText("b1", 4, "very "), author="ben")
    assert authors(doc) == [(4, "ann", None), (5, "ben", None), (39, "ann", None)]


def test_deleting_and_undoing_gives_the_text_back_to_its_author(doc):
    doc.execute(InsertText("b1", 4, "very "), author="ben")
    doc.execute(DeleteText("b1", 4, 5), author="ann")  # ann deletes ben's word
    assert authors(doc) == [(len(SENTENCE), "ann", None)]
    doc.undo("ann")
    assert authors(doc) == [(4, "ann", None), (5, "ben", None), (39, "ann", None)]


# ----------------------------------------------------------------------------- structure
def test_splitting_makes_a_new_paragraph_with_the_rest_and_the_chosen_style(doc):
    doc.execute(SplitBlock("b1", 9, "b2", "quote"), author="ann")
    assert texts(doc) == ["the quick", " brown fox jumps over the lazy dog"]
    assert [b.style for b in doc.model.blocks] == ["body", "quote"]
    assert authors(doc, "b2") == [(len(SENTENCE) - 9, "ann", None)]


def test_undoing_a_split_joins_the_paragraphs_again(doc):
    doc.execute(SplitBlock("b1", 9, "b2", "body"), author="ann")
    doc.undo("ann")
    assert texts(doc) == [SENTENCE]
    doc.redo("ann")
    assert texts(doc) == ["the quick", " brown fox jumps over the lazy dog"]


def test_joining_puts_the_second_paragraph_at_the_end_of_the_first_and_undo_splits_it(doc):
    doc.execute(SplitBlock("b1", 9, "b2", "heading-1"), author="ann")
    doc.execute(JoinBlocks("b2", "b1", 9), author="ben")
    assert texts(doc) == [SENTENCE]
    assert doc.model.block("b1").style == "body", "the first paragraph keeps its style"
    doc.undo("ben")
    assert [(b.id, b.style) for b in doc.model.blocks] == [("b1", "body"), ("b2", "heading-1")]


def test_a_join_must_name_the_paragraph_before_and_where_it_ends(doc):
    doc.execute(SplitBlock("b1", 9, "b2", "body"), author="ann")
    for bad in (JoinBlocks("b2", "b1", 3), JoinBlocks("b1", "b2", 0), JoinBlocks("b9", "b1", 9)):
        with pytest.raises((ValueError, KeyError)):
            doc.execute(bad, author="ann")
    assert len(doc.model.blocks) == 2


def test_new_paragraph_ids_must_be_new_and_the_style_known(doc):
    with pytest.raises(ValueError):
        doc.execute(SplitBlock("b1", 3, "b1", "body"), author="ann")
    with pytest.raises(ValueError):
        doc.execute(SplitBlock("b1", 3, "b2", "no-such-style"), author="ann")


def test_fresh_ids_are_never_reused_even_after_a_join(doc):
    doc.execute(SplitBlock("b1", 9, "b2", "body"), author="ann")
    doc.execute(JoinBlocks("b2", "b1", 9), author="ann")
    assert doc.model.fresh_id() == "b3"


# ----------------------------------------------------------------------------- styles
def test_setting_a_style_and_undoing_it(doc):
    doc.execute(SetStyle("b1", "heading-1"), author="ann")
    assert doc.model.block("b1").style == "heading-1"
    doc.undo("ann")
    assert doc.model.block("b1").style == "body"


def test_an_unknown_style_is_refused(doc):
    with pytest.raises(ValueError):
        doc.execute(SetStyle("b1", "sparkly"), author="ann")


def test_every_style_says_what_it_is_for_and_what_follows_it():
    styles = TextModel.styles
    assert styles["heading-1"].next == "body" and styles["quote"].purpose
    assert all(style.name and style.purpose and style.next in styles for style in styles.values())


# ----------------------------------------------------------------------------- history sentences
def test_the_history_reads_as_sentences(doc):
    doc.execute(InsertText("b1", 0, "Hello "), author="ben")
    doc.execute(SplitBlock("b1", 6, "b2", "body"), author="ben")
    doc.execute(SetStyle("b2", "heading-1"), author="ben")
    sentences = [entry.command.summary for entry in doc.log.path(doc.revision)]
    assert sentences[-3:] == ["typed “Hello ”", "new paragraph", "style Heading 1"]


# ----------------------------------------------------------------------------- undo with colleagues (E1.4)
def test_undo_follows_text_typed_before_it_and_refuses_when_text_is_inside(doc):
    doc.execute(InsertText("b1", 10, "SLOW "), author="ann")
    doc.execute(InsertText("b1", 0, ">> "), author="ben")
    doc.undo("ann")
    assert "SLOW" not in text_of(doc) and text_of(doc).startswith(">> the quick")
    doc.execute(InsertText("b1", 10, "ABCDEF"), author="ann")
    doc.execute(InsertText("b1", 13, "xyz"), author="ben")  # inside ann's passage
    with pytest.raises(UndoConflict):
        doc.undo("ann")


def test_undo_follows_a_colleague_who_split_the_paragraph_before_it(doc):
    doc.execute(InsertText("b1", 40, "!!"), author="ann")
    doc.execute(SplitBlock("b1", 9, "b2", "body"), author="ben")
    doc.undo("ann")  # the exclamation marks are now in b2
    assert text_of(doc, "b2").endswith("lazy dog") and "!" not in "".join(texts(doc))


def test_undo_refuses_when_a_colleague_split_the_passage_in_two(doc):
    doc.execute(InsertText("b1", 4, "ABCDEF"), author="ann")
    doc.execute(SplitBlock("b1", 7, "b2", "body"), author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ann")


def test_undo_follows_a_colleague_who_joined_paragraphs(doc):
    doc.execute(SplitBlock("b1", 9, "b2", "body"), author="ann")
    doc.execute(InsertText("b2", 1, "XX"), author="ann")
    doc.execute(JoinBlocks("b2", "b1", 9), author="ben")
    doc.undo("ann")  # her XX now sits at offset 10 of b1
    assert "XX" not in text_of(doc)


# ----------------------------------------------------------------------------- replay and redaction
def test_replay_gives_the_same_text_runs_and_styles(doc):
    doc.execute(InsertText("b1", 4, "very "), author="ben")
    doc.execute(SplitBlock("b1", 12, "b2", "quote"), author="ben")
    doc.execute(SetStyle("b1", "title"), author="ann")
    again = Document.open(TextModel, CommandLog.from_data(doc.log.to_data(), TextModel.registry))
    assert again.model.serialize() == doc.model.serialize()


def test_a_snapshot_restores_the_same_state(doc):
    doc.execute(SplitBlock("b1", 9, "b2", "quote"), author="ben")
    restored = TextModel.restore(doc.model.serialize())
    assert restored.serialize() == doc.model.serialize()
    assert restored.fresh_id() == "b3"


def test_redaction_blanks_what_was_typed_but_keeps_the_lengths(doc):
    from claudia_core import Revision

    doc.execute(InsertText("b1", 0, "SECRET "), author="ben")
    doc.redact([Revision("main", 2)])
    assert "SECRET" not in text_of(doc)
    again = Document.open(TextModel, CommandLog.from_data(doc.log.to_data(), TextModel.registry))
    assert again.model.serialize() == doc.model.serialize()


# ----------------------------------------------------------------------------- one undo step
def test_a_batch_is_one_undo_step(doc):
    doc.execute(Batch((DeleteText("b1", 0, 4), InsertText("b1", 0, "a "))), author="ben")
    assert text_of(doc).startswith("a quick")
    doc.undo("ben")
    assert text_of(doc) == SENTENCE


def test_inserted_runs_can_be_given_explicitly(doc):
    doc.execute(InsertText("b1", 0, "xy", by=(Run(1, "eve", None), Run(1, "ann", "ai"))), author="ben")
    assert authors(doc)[:2] == [(1, "eve", None), (1, "ann", "ai")]
    with pytest.raises(ValueError):
        doc.execute(InsertText("b1", 0, "xy", by=(Run(5, "eve", None),)), author="ben")
