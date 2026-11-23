"""Redacting an imported presentation (D723): words, notes and pictures go; slides, places and sizes stay."""

import json

import pytest
from conftest import add, text_box

from claudia_core import FILLER, Document, Import, MemoryStore, RedactionError, Revision
from claudia_creates import AddSlide, DefineLayout, SetSlideNotes, SlideModel


def deck() -> SlideModel:
    doc = Document(SlideModel.empty(), store=MemoryStore())
    doc.execute(add(text_box("t1", text="Q3 layoffs: 40 people")), author="ana")
    doc.execute(SetSlideNotes("s1", "do not say the number"), author="ana")
    doc.execute(AddSlide("s2", 1), author="ana")
    doc.execute(add(text_box("t2", slide="s2", text="Thanks")), author="ana")
    return doc.model


def imported() -> Document:
    doc = Document(SlideModel.empty(), store=MemoryStore())
    doc.execute(Import("board.pptx", "pptx", deck().serialize(), "ab" * 32, True), author="ana")
    return doc


def words(doc: Document, object_id: str) -> str:
    return doc.model.get(object_id).body.paragraph.text


def test_an_imported_presentation_is_blanked_in_full():
    doc = imported()
    doc.redact(doc.plan_redaction([Revision("main", 1)]), author="ana")
    assert words(doc, "t1") == FILLER * len("Q3 layoffs: 40 people") and words(doc, "t2") == FILLER * 6
    assert doc.model.notes == {} and doc.model.order == ["s1", "s2"]
    assert "layoffs" not in json.dumps(doc.log.to_data()) and "the number" not in json.dumps(doc.log.to_data())


def test_a_slide_is_blanked_with_everything_on_it():
    doc = imported()
    doc.redact(doc.plan_redaction([Revision("main", 1)], parts={Revision("main", 1): ["s1"]}), author="ana")
    assert words(doc, "t1").startswith(FILLER) and words(doc, "t2") == "Thanks"
    assert "s1" not in doc.model.notes


def test_a_part_the_presentation_does_not_have_is_named():
    with pytest.raises(RedactionError) as caught:
        imported().plan_redaction([Revision("main", 1)], parts={Revision("main", 1): ["s9"]})
    assert "s9" in str(caught.value)


def imported_with_a_layout() -> Document:
    source = Document(SlideModel.empty(), store=MemoryStore())
    source.execute(DefineLayout("agenda", "Agenda"), author="ana")
    source.execute(add(text_box("footer", slide="agenda", text="Confidential: Project Falcon")), author="ana")
    source.execute(add(text_box("t1", text="Hello")), author="ana")
    doc = Document(SlideModel.empty(), store=MemoryStore())
    doc.execute(Import("board.pptx", "pptx", source.model.serialize(), "cd" * 32, True), author="ana")
    return doc


def test_the_words_on_a_layout_go_with_everything_else_in_a_full_redaction():
    doc = imported_with_a_layout()
    doc.redact(doc.plan_redaction([Revision("main", 1)]), author="ana")
    assert words(doc, "footer") == FILLER * len("Confidential: Project Falcon")
    assert "Falcon" not in json.dumps(doc.log.to_data())


def test_a_layout_is_a_part_of_its_own_and_blanks_what_is_on_it():
    doc = imported_with_a_layout()
    doc.redact(doc.plan_redaction([Revision("main", 1)], parts={Revision("main", 1): ["agenda"]}), author="ana")
    assert words(doc, "footer").startswith(FILLER) and words(doc, "t1") == "Hello"


def test_a_slide_alone_leaves_the_words_on_its_layout():
    doc = imported_with_a_layout()
    doc.redact(doc.plan_redaction([Revision("main", 1)], parts={Revision("main", 1): ["s1"]}), author="ana")
    assert words(doc, "footer") == "Confidential: Project Falcon" and words(doc, "t1").startswith(FILLER)
