"""AI suggestions (D63, E9.9): proposals anchored to text. They change nothing until a person accepts one."""

import pytest
from composes_helpers import SENTENCE, text_of

from claudia_composes import (
    AcceptSuggestion,
    DeleteText,
    InsertText,
    JoinBlocks,
    ProposeSuggestion,
    ResolveSuggestion,
    SplitBlock,
    TextModel,
    TextRange,
)
from claudia_core import CommandLog, Document, RegionHeld

QUICK = SENTENCE.index("quick")


def propose(doc, sid="s1", start=QUICK, end=QUICK + 5, replacement="fast", *, reason="shorter", author="ai"):
    original = text_of(doc)[start:end]
    doc.execute(ProposeSuggestion(sid, "b1", start, end, original, replacement, reason), author=author)


def accept(doc, sid="s1", who="ann"):
    s = doc.model.suggestion(sid)
    a = s.anchor
    return doc.execute(AcceptSuggestion(sid, a.block, a.start, a.end, s.replacement, s.author), author=who)


def runs(doc):
    return [(r.length, r.author, r.via) for r in doc.model.block("b1").runs]


def test_a_suggestion_changes_no_text(doc):
    propose(doc)
    assert text_of(doc) == SENTENCE
    (item,) = doc.model.visible_suggestions()
    assert (item["author"], item["original"], item["replacement"], item["outdated"]) == ("ai", "quick", "fast", False)


def test_a_suggestion_is_not_blocked_by_somebodys_zone(doc):
    doc.lock("ben", [TextRange("b1", 0, 20)], ttl=5)
    propose(doc)  # it touches no text, so no lock applies to it
    assert len(doc.model.visible_suggestions()) == 1


def test_accepting_is_an_edit_by_the_accepter_and_records_whose_suggestion_it_was(doc):
    propose(doc)
    accept(doc, who="ben")
    assert text_of(doc) == SENTENCE.replace("quick", "fast")
    assert (runs(doc)[1][0], text_of(doc)[4:8]) == (4, "fast")
    assert runs(doc)[1] == (4, "ben", "ai")
    assert doc.model.suggestion("s1").state == "accepted" and doc.model.visible_suggestions() == []
    assert doc.log.get(doc.revision).author == "ben"


def test_the_history_names_both_people(doc):
    propose(doc)
    accept(doc, who="ben")
    assert doc.log.get(doc.revision).command.summary == "accepted a suggestion by ai: “fast”"


def test_undoing_an_accept_gives_the_text_and_the_suggestion_back(doc):
    propose(doc)
    accept(doc, who="ben")
    doc.undo("ben")
    assert text_of(doc) == SENTENCE
    assert runs(doc) == [(len(SENTENCE), "ann", None)]
    (item,) = doc.model.visible_suggestions()
    assert (item["state"], item["outdated"], item["start"], item["end"]) == ("open", False, QUICK, QUICK + 5)
    doc.redo("ben")
    assert text_of(doc) == SENTENCE.replace("quick", "fast") and runs(doc)[1] == (4, "ben", "ai")


def test_accepting_inside_somebodys_zone_is_refused_like_any_edit(doc):
    propose(doc)
    doc.lock("ben", [TextRange("b1", QUICK - 2, QUICK + 2)], ttl=5)
    with pytest.raises(RegionHeld):
        accept(doc, who="ann")
    assert text_of(doc) == SENTENCE


def test_a_deletion_is_a_suggestion_with_an_empty_replacement(doc):
    propose(doc, start=3, end=9, replacement="")
    accept(doc)
    assert text_of(doc) == SENTENCE[:3] + SENTENCE[9:]


def test_rejecting_is_logged_and_keeps_the_text(doc):
    propose(doc)
    doc.execute(ResolveSuggestion("s1", "rejected"), author="ann")
    assert doc.model.visible_suggestions() == [] and text_of(doc) == SENTENCE
    assert doc.log.get(doc.revision).command.summary == "rejected a suggestion"


def test_a_remark_can_be_dismissed_but_not_accepted(doc):
    doc.execute(ProposeSuggestion("s1", "b1", 0, 9, "the quick", None, "long sentence"), author="ai")
    with pytest.raises(ValueError):
        doc.execute(AcceptSuggestion("s1", "b1", 0, 9, "x", "ai"), author="ann")
    doc.execute(ResolveSuggestion("s1", "dismissed"), author="ann")
    assert doc.model.visible_suggestions() == []


def test_a_suggestion_follows_text_typed_before_it(doc):
    propose(doc)
    doc.execute(InsertText("b1", 0, "Look: "), author="ben")
    (item,) = doc.model.visible_suggestions()
    assert (item["start"], item["outdated"]) == (QUICK + 6, False)
    accept(doc)
    assert text_of(doc).startswith("Look: the fast")


def test_a_suggestion_is_outdated_when_its_text_changed_and_then_cannot_be_accepted(doc):
    propose(doc)
    doc.execute(InsertText("b1", QUICK + 2, "X"), author="ben")  # inside "quick"
    (item,) = doc.model.visible_suggestions()
    assert item["outdated"] is True
    with pytest.raises(ValueError):
        accept(doc)
    assert "fast" not in text_of(doc)


def test_a_suggestion_becomes_valid_again_if_the_change_is_undone(doc):
    propose(doc)
    doc.execute(InsertText("b1", QUICK + 2, "X"), author="ben")
    doc.undo("ben")
    assert doc.model.visible_suggestions()[0]["outdated"] is False


def test_a_suggestion_whose_text_was_deleted_is_outdated(doc):
    propose(doc)
    doc.execute(DeleteText("b1", QUICK - 1, 8), author="ben")
    assert doc.model.visible_suggestions()[0]["outdated"] is True


def test_suggestions_move_with_a_split_and_a_join(doc):
    propose(doc, "s1", SENTENCE.index("lazy"), SENTENCE.index("lazy") + 4, "idle")
    doc.execute(SplitBlock("b1", 9, "b2", "body"), author="ben")
    (item,) = doc.model.visible_suggestions()
    assert (item["block"], item["start"], item["outdated"]) == ("b2", SENTENCE.index("lazy") - 9, False)
    doc.execute(JoinBlocks("b2", "b1", 9), author="ben")
    (item,) = doc.model.visible_suggestions()
    assert (item["block"], item["start"], item["outdated"]) == ("b1", SENTENCE.index("lazy"), False)


def test_a_split_through_the_suggested_text_makes_it_outdated(doc):
    propose(doc)
    doc.execute(SplitBlock("b1", QUICK + 2, "b2", "body"), author="ben")
    assert doc.model.visible_suggestions()[0]["outdated"] is True


def test_two_suggestions_on_overlapping_text_each_work_until_the_other_is_taken(doc):
    propose(doc, "s1", QUICK, QUICK + 5, "fast")
    propose(doc, "s2", QUICK - 4, QUICK + 5, "a swift", reason="plainer")  # "the quick"
    accept(doc, "s2")
    assert text_of(doc).startswith("a swift brown")
    assert doc.model.suggestion("s1").state == "open"
    assert doc.model.is_outdated(doc.model.suggestion("s1")), "its text is gone"
    with pytest.raises(ValueError):
        accept(doc, "s1")


def test_the_command_must_say_what_the_suggestion_says(doc):
    propose(doc)
    with pytest.raises(ValueError):
        doc.execute(AcceptSuggestion("s1", "b1", QUICK, QUICK + 5, "slow", "ai"), author="ann")
    with pytest.raises(KeyError):
        doc.execute(AcceptSuggestion("s9", "b1", QUICK, QUICK + 5, "fast", "ai"), author="ann")


def test_a_suggestion_must_lie_inside_the_text_and_have_a_new_id(doc):
    with pytest.raises(IndexError):
        doc.execute(ProposeSuggestion("s1", "b1", 40, 90, "x", "y", "r"), author="ai")
    propose(doc)
    with pytest.raises(ValueError):
        propose(doc)


def test_a_rejection_can_be_undone(doc):
    propose(doc)
    doc.execute(ResolveSuggestion("s1", "rejected"), author="ann")
    doc.undo("ann")
    assert len(doc.model.visible_suggestions()) == 1


def test_proposing_is_nobodys_undo_step(doc):
    propose(doc)
    assert doc.history_for("ai").can_undo is False


def test_replay_and_snapshots_keep_suggestions(doc):
    propose(doc)
    propose(doc, "s2", 0, 3, "a")
    accept(doc, "s2")
    again = Document.open(TextModel, CommandLog.from_data(doc.log.to_data(), TextModel.registry))
    assert again.model.serialize() == doc.model.serialize()
    assert TextModel.restore(doc.model.serialize()).serialize() == doc.model.serialize()
    assert doc.model.fresh_suggestion_id() == "s3"


def test_a_suggestion_that_was_taken_back_by_the_log_is_not_listed(doc):
    propose(doc)
    inverse = doc.log.get(doc.revision).command
    from claudia_core import Context

    ResolveSuggestion("s1", "withdrawn").apply(Context(doc.model))
    assert doc.model.visible_suggestions() == [] and inverse.kind == "composes.ProposeSuggestion"


def test_the_ids_of_the_two_kinds_are_counted_apart(doc):
    propose(doc, "s5")
    doc.execute(SplitBlock("b1", 3, "b2", "body"), author="ann")
    assert (doc.model.fresh_id(), doc.model.fresh_suggestion_id()) == ("b3", "s6")
