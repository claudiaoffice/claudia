"""References in a text (step H): a field at one U+FFFC that points at a thing and shows what the document works out,
its number, its words or its name, so it never goes stale."""

import pytest

from claudia_composes import FieldsPut, JoinParagraphs, Paragraph, SplitParagraph, TextModel
from claudia_core import (
    FIELD_CHAR,
    CreateList,
    DeleteText,
    Document,
    FieldsChanged,
    InsertText,
    ListDef,
    ListItem,
    MemoryStore,
    RefField,
    SetField,
    SetListItem,
    Shown,
)


@pytest.fixture
def text():
    paragraphs = [
        Paragraph("b1", "heading-1", "Why we did it"),
        Paragraph("b2", "body", "Collect"),
        Paragraph("b3", "body", "see "),
    ]
    d = Document(TextModel(paragraphs), store=MemoryStore())
    d.execute(CreateList(ListDef("l1", "numbers")), author="ann")
    d.execute(SetListItem("b2", ListItem("l1", 0)), author="ann")
    return d


def refer(text, target, show="number", at=4):
    text.execute(InsertText("b3", at, FIELD_CHAR, fields=(RefField(target, show),)), author="ann")


def shown(text, paragraph="b3"):
    return text.model.structure.shown().get(paragraph)


def test_a_reference_shows_its_target_s_number_words_or_both_and_follows_them(text):
    events = []
    text.subscribe(events.append)
    refer(text, "b2")
    assert text.model.paragraph("b3").fields == (RefField("b2"),)
    assert shown(text) == (Shown("1"),)
    assert any(isinstance(e, FieldsPut) for e in events) and any(isinstance(e, FieldsChanged) for e in events)
    text.execute(SetField("b3", 0, RefField("b2", "number-text")), author="ann")
    assert shown(text)[0].text.endswith(" Collect")
    text.execute(SetField("b3", 0, RefField("b2", "text")), author="ann")
    events.clear()
    text.execute(InsertText("b2", 7, " results"), author="ben")
    assert shown(text) == (Shown("Collect results"),)
    assert FieldsChanged("b3", (Shown("Collect results"),)) in events
    text.undo("ann")
    assert text.model.paragraph("b3").fields[0].show == "number-text"


def test_an_unnumbered_heading_shows_its_words_and_a_missing_target_is_broken_until_undo_mends_it(text):
    refer(text, "b1")
    assert shown(text) == (Shown("Why we did it"),)
    refer(text, "gone", at=5)
    assert shown(text)[1] == Shown("", "broken")
    refer(text, "b2", show="text", at=6)
    text.execute(DeleteText("b2", 0, 7), author="ann")
    text.execute(JoinParagraphs("b2", "b1", 13), author="ann")  # the item is joined away: its references break
    assert shown(text)[2].state == "broken"
    text.undo("ann")
    assert shown(text)[2] == Shown("")
    text.undo("ann")
    assert shown(text)[2] == Shown("Collect")


def test_deleting_takes_the_field_with_its_character_and_undo_puts_it_back(text):
    refer(text, "b2")
    text.execute(DeleteText("b3", 3, 2), author="ann")
    assert text.model.paragraph("b3").fields == () and FIELD_CHAR not in text.model.paragraph("b3").text
    text.undo("ann")
    assert text.model.paragraph("b3").fields == (RefField("b2"),)


def test_splitting_and_joining_share_the_fields_out_by_their_characters(text):
    refer(text, "b1", at=0)
    refer(text, "b2", at=5)
    text.execute(SplitParagraph("b3", 3, "b9", "body"), author="ann")
    assert text.model.paragraph("b3").fields == (RefField("b1"),)
    assert text.model.paragraph("b9").fields == (RefField("b2"),)
    text.undo("ann")
    assert text.model.paragraph("b3").fields == (RefField("b1"), RefField("b2"))


def test_a_field_and_its_character_go_together_or_not_at_all(text):
    with pytest.raises(ValueError, match="U\\+FFFC"):
        text.execute(InsertText("b3", 0, "x", fields=(RefField("b1"),)), author="ann")
    with pytest.raises(IndexError):
        text.execute(SetField("b3", 0, RefField("b1")), author="ann")
    with pytest.raises(ValueError, match="shows one of"):
        text.execute(SetField("b3", 0, RefField("b1", "colour")), author="ann")


def test_a_reference_is_written_down_and_read_back_and_redacting_keeps_it(text):
    refer(text, "b2")
    restored = TextModel.restore(text.model.serialize())
    assert restored.paragraph("b3").fields == (RefField("b2"),)
    typed = InsertText("b3", 0, f"ab{FIELD_CHAR}", fields=(RefField("b2"),))
    assert typed.redacted().text == f"██{FIELD_CHAR}"
    assert SetField("b3", 0, RefField("b2", "text")).to_data()["field"] == {
        "kind": "ref",
        "target": "b2",
        "show": "text",
    }
