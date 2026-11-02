import pytest

from claudia_composes import DeleteText, InsertText, TextModel, TextRange, word_window
from claudia_core import Document, MemoryStore, UndoConflict, UndoRefused
from claudia_core.testing import FakeClock


@pytest.fixture
def doc():
    clock = FakeClock()
    d = Document(TextModel(), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)
    d.execute(InsertText(0, 0, "the quick brown fox jumps over the lazy dog"), author="ana")
    return d


def test_word_window_is_plus_minus_n_words():
    text = "the quick brown fox jumps over the lazy dog"
    cursor = text.index("fox") + 1  # inside "fox"
    zone = word_window(text, cursor, 1)
    assert text[zone.start : zone.end] == "brown fox jumps"
    assert text[word_window(text, 0, 2).start : word_window(text, 0, 2).end] == "the quick"
    assert text[word_window(text, len(text), 1).start :].strip() == "dog"
    assert word_window(text, 10, 0) == TextRange(0, 10, 10)


def test_typing_and_undo(doc):
    doc.execute(InsertText(0, 4, "very "), author="ben")
    assert doc.model.blocks[0].startswith("the very quick")
    doc.undo("ben")
    assert doc.model.blocks[0].startswith("the quick")


def test_a_cursor_zone_follows_a_colleagues_typing(doc):
    text = doc.model.blocks[0]
    zone = word_window(text, text.index("fox") + 1, 1)
    doc.show_presence("ben", [zone])
    doc.execute(InsertText(0, 0, "Yesterday, "), author="ana")
    (moved,) = doc.presence.of("ben").regions
    assert doc.model.blocks[0][moved.start : moved.end] == "brown fox jumps"
    doc.execute(DeleteText(0, moved.start, moved.end - moved.start), author="ana")
    assert doc.presence.of("ben") is None


def test_the_zone_is_a_lock_for_undo(doc):
    doc.execute(InsertText(0, 0, "Hello "), author="ana")
    doc.lock("ben", [TextRange(0, 0, 5)], ttl=5)
    with pytest.raises(UndoRefused):
        doc.undo("ana")


def test_undo_follows_text_typed_before_it_and_refuses_when_text_is_inside(doc):
    doc.execute(InsertText(0, 10, "SLOW "), author="ana")
    doc.execute(InsertText(0, 0, ">> "), author="ben")
    doc.undo("ana")
    assert "SLOW" not in doc.model.blocks[0] and doc.model.blocks[0].startswith(">> the quick")
    doc.execute(InsertText(0, 10, "ABCDEF"), author="ana")
    doc.execute(InsertText(0, 13, "xyz"), author="ben")  # inside ana's passage
    with pytest.raises(UndoConflict):
        doc.undo("ana")


def test_replay_and_redaction(doc):
    from claudia_core import CommandLog, Revision

    doc.execute(InsertText(0, 0, "SECRET "), author="ben")
    doc.redact([Revision("main", 2)])
    assert "SECRET" not in doc.model.blocks[0]
    again = Document.open(TextModel, CommandLog.from_data(doc.log.to_data(), TextModel.registry))
    assert again.model.blocks == doc.model.blocks
