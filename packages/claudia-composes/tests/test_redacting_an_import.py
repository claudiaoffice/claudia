"""Redacting an imported text (D723): the paragraphs keep their ids and lengths, so later typing still lands."""

import json
from dataclasses import replace

import pytest

from claudia_composes import InsertText, SplitBlock, TextModel
from claudia_core import FILLER, Document, Import, MemoryStore, RedactionError, Revision


def imported_text() -> Document:
    source = TextModel.empty()
    source.blocks = [source.blocks[0].with_text("Our pin is 4711", source.blocks[0].runs)]
    doc = Document(TextModel.empty(), store=MemoryStore())
    doc.execute(Import("minutes.docx", "docx", source.serialize(), "ab" * 32, True), author="ana")
    doc.execute(SplitBlock("b1", 10, "b2", "body"), author="ana")  # "Our pin is" | " 4711"
    doc.execute(InsertText("b1", 3, " new"), author="ben")  # typing after the import, at a place in it
    return doc


def test_an_imported_text_is_blanked_in_full_and_what_came_after_still_applies():
    doc = imported_text()
    plan = doc.plan_redaction([Revision("main", 1)])
    assert plan.dependents == () and plan.changes_now
    doc.redact(plan, author="ana")
    texts = [block.text for block in doc.model.blocks]
    assert texts == [FILLER * 3 + " new" + FILLER * 7, FILLER * 5]
    assert "4711" not in json.dumps(doc.log.to_data())


def test_an_imported_text_is_blanked_in_parts():
    source = TextModel.empty()
    first = source.blocks[0]
    source.blocks = [first.with_text("Agenda", first.runs), replace(first, id="b2").with_text("pin 4711", first.runs)]
    model = TextModel.restore(source.serialize())
    model.blank(frozenset({"b2"}))
    assert [b.text for b in model.blocks] == ["Agenda", FILLER * 8]


def test_a_part_the_text_does_not_have_is_named():
    doc = imported_text()
    with pytest.raises(RedactionError) as caught:
        doc.plan_redaction([Revision("main", 1)], parts={Revision("main", 1): ["b9"]})
    assert "b9" in str(caught.value)
