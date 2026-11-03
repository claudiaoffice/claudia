"""Cursors and the ± n words zone (E9.2, D11): they move with the text, and they are locks for edits and undo."""

import pytest
from composes_helpers import SENTENCE, text_of

from claudia_composes import (
    DeleteText,
    InsertText,
    JoinBlocks,
    SetStyle,
    SplitBlock,
    TextModel,
    TextRange,
    word_window,
)
from claudia_core import RegionHeld, UndoRefused


def shown(doc, owner):
    """The text the first region of ``owner`` covers."""
    (region, *_) = doc.presence.of(owner).regions
    return text_of(doc, region.block)[region.start : region.end]


def test_word_window_is_plus_minus_n_words():
    cursor = SENTENCE.index("fox") + 1  # inside "fox"
    zone = word_window(SENTENCE, cursor, 1)
    assert SENTENCE[zone.start : zone.end] == "brown fox jumps"
    assert SENTENCE[word_window(SENTENCE, 0, 2).start : word_window(SENTENCE, 0, 2).end] == "the quick"
    assert SENTENCE[word_window(SENTENCE, len(SENTENCE), 1).start :].strip() == "dog"
    assert word_window(SENTENCE, 10, 0) == TextRange("b1", 10, 10)
    assert word_window(SENTENCE, 10, 1, block="b7").block == "b7"


def test_a_range_overlaps_only_in_the_same_paragraph_and_never_when_empty():
    a = TextRange("b1", 2, 6)
    assert a.overlaps(TextRange("b1", 5, 9)) and not a.overlaps(TextRange("b1", 6, 9))
    assert not a.overlaps(TextRange("b2", 2, 6))
    assert not a.overlaps(TextRange("b1", 3, 3)), "a caret overlaps nothing"


def test_regions_travel_as_data(doc):
    zone = TextRange("b1", 4, 9)
    assert doc.model.region_from_data(zone.to_data()) == zone
    for bad in (
        {"kind": "cells"},
        {"kind": "text", "block": 1, "start": 0, "end": 1},
        {"kind": "text", "block": "b1", "start": 5, "end": 2},
    ):
        with pytest.raises((ValueError, KeyError)):
            doc.model.region_from_data(bad)


def test_a_zone_follows_a_colleagues_typing(doc):
    doc.show_presence("ben", [word_window(SENTENCE, SENTENCE.index("fox") + 1, 1)])
    doc.execute(InsertText("b1", 0, "Yesterday, "), author="ann")
    assert shown(doc, "ben") == "brown fox jumps"
    doc.execute(DeleteText("b1", doc.presence.of("ben").regions[0].start, 15), author="ann")
    assert doc.presence.of("ben") is None, "a zone whose text is gone is gone"


def test_a_caret_survives_deletions_around_it(doc):
    doc.show_presence("ben", [TextRange("b1", 10, 10)])
    doc.execute(DeleteText("b1", 0, 4), author="ann")
    assert doc.presence.of("ben").regions == (TextRange("b1", 6, 6),)


def test_a_zone_follows_a_split_and_a_join(doc):
    doc.show_presence("ben", [TextRange("b1", 20, 25), TextRange("b1", 22, 22)])
    doc.execute(SplitBlock("b1", 10, "b2", "body"), author="ann")
    assert doc.presence.of("ben").regions == (TextRange("b2", 10, 15), TextRange("b2", 12, 12))
    doc.execute(JoinBlocks("b2", "b1", 10), author="ann")
    assert doc.presence.of("ben").regions == (TextRange("b1", 20, 25), TextRange("b1", 22, 22))


def test_a_zone_cut_by_a_split_keeps_the_part_before_it(doc):
    doc.show_presence("ben", [TextRange("b1", 4, 14)])
    doc.execute(SplitBlock("b1", 9, "b2", "body"), author="ann")
    assert doc.presence.of("ben").regions == (TextRange("b1", 4, 9),)


def test_a_lock_keeps_colleagues_out_of_the_zone_but_not_from_the_rest(doc):
    zone = word_window(SENTENCE, SENTENCE.index("fox") + 1, 1)
    doc.lock("ben", [zone], ttl=5)
    for refused in (InsertText("b1", zone.start + 2, "x"), DeleteText("b1", zone.start, 2), SetStyle("b1", "quote")):
        with pytest.raises(RegionHeld):
            doc.execute(refused, author="ann")
    doc.execute(InsertText("b1", 0, "ok "), author="ann")
    doc.execute(InsertText("b1", len(text_of(doc)), "!"), author="ann")
    doc.execute(InsertText("b1", zone.start + 3, "mine"), author="ben")  # his own zone is his


def test_splitting_inside_a_zone_is_refused(doc):
    doc.lock("ben", [TextRange("b1", 4, 14)], ttl=5)
    with pytest.raises(RegionHeld):
        doc.execute(SplitBlock("b1", 9, "b2", "body"), author="ann")


def test_the_zone_is_a_lock_for_undo(doc):
    doc.execute(InsertText("b1", 0, "Hello "), author="ann")
    doc.lock("ben", [TextRange("b1", 0, 5)], ttl=5)
    with pytest.raises(UndoRefused):
        doc.undo("ann")


def test_a_lock_runs_out(doc, clock):
    doc.lock("ben", [TextRange("b1", 0, 5)], ttl=5)
    clock.advance(6)
    doc.execute(InsertText("b1", 1, "x"), author="ann")


def test_the_model_is_a_text_model():
    assert TextModel.app == "composes"
