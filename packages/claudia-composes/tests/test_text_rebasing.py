"""How a step written against an older text follows what colleagues did since: the spans each command moves
(`follow`), the spans it cuts through (`breaks`), and the step rebased over another one (`shifted_by`), or refused
(`None`) when what it was about is gone."""

from __future__ import annotations

from claudia_composes.commands import (
    AcceptSuggestion,
    DeleteText,
    InsertText,
    JoinBlocks,
    ProposeSuggestion,
    ResolveSuggestion,
    SetPageSetup,
    SetStyle,
    SplitBlock,
)
from claudia_composes.page import PageSetup


def test_deleting_moves_what_comes_after_and_breaks_what_it_cuts_into():
    cut = DeleteText("b", 2, 3)  # characters 2, 3, 4
    assert cut.follow(("b", 6, 8)) == ("b", 3, 5)
    assert cut.follow(("b", 3, 6)) == ("b", 2, 3)
    assert cut.follow(("other", 6, 8)) == ("other", 6, 8)
    assert cut.breaks(("b", 4, 6))
    assert not cut.breaks(("b", 5, 6))
    assert not cut.breaks(("b", 3, 3))  # a caret is moved, not broken


def test_typing_follows_a_delete_before_it_and_lands_where_a_delete_around_it_began():
    typed = InsertText("b", 6, "x")
    assert typed.shifted_by(DeleteText("b", 0, 2)) == InsertText("b", 4, "x")
    assert typed.shifted_by(DeleteText("b", 5, 3)) == InsertText("b", 5, "x")
    assert typed.shifted_by(SetPageSetup(PageSetup())) is typed  # not a text command: nothing to follow


def test_deleting_follows_typing_before_it_and_is_refused_when_typed_into():
    cut = DeleteText("b", 4, 2)
    assert cut.shifted_by(InsertText("b", 0, "ab")) == DeleteText("b", 6, 2)
    assert cut.shifted_by(SplitBlock("b", 5, "c", "body")) is None
    assert cut.shifted_by(SetPageSetup(PageSetup())) is cut
    assert cut.redacted() is cut


def test_a_split_sends_what_follows_into_the_new_paragraph():
    split = SplitBlock("b", 4, "c", "body")
    assert split.follow(("b", 6, 9)) == ("c", 2, 5)
    assert split.follow(("b", 1, 9)) == ("b", 1, 4)
    assert split.follow(("x", 1, 2)) == ("x", 1, 2)
    assert split.breaks(("b", 2, 6))
    assert not split.breaks(("b", 4, 6))
    assert split.shifted_by(InsertText("b", 0, "ab")) == SplitBlock("b", 6, "c", "body")
    assert split.shifted_by(DeleteText("b", 3, 2)) == SplitBlock("b", 3, "c", "body")
    assert split.shifted_by(SetPageSetup(PageSetup())) is split


def test_a_join_moves_the_second_paragraph_into_the_first():
    join = JoinBlocks("c", "b", 5)
    assert join.follow(("c", 1, 2)) == ("b", 6, 7)
    assert join.follow(("b", 1, 2)) == ("b", 1, 2)
    assert join.to_data() == {"block": "c", "into": "b", "at": 5}
    assert JoinBlocks.from_data(join.to_data(), None) == join
    assert join.summary == "joined paragraphs"
    assert join.shifted_by(InsertText("b", 0, "ab")) == JoinBlocks("c", "b", 7)
    assert join.shifted_by(DeleteText("b", 4, 2)) == JoinBlocks("c", "b", 4)
    assert join.shifted_by(SetPageSetup(PageSetup())) is join


def test_styling_a_paragraph_that_was_joined_into_another_is_refused():
    style = SetStyle("c", "heading-1")
    assert style.shifted_by(JoinBlocks("c", "b", 5)) is None
    assert style.shifted_by(JoinBlocks("d", "c", 5)) is style


def test_a_resolved_suggestion_keeps_its_anchor_on_the_text_it_was_about():
    resolved = ResolveSuggestion("s1", "accepted", ("b", 4, 6))
    assert ResolveSuggestion.from_data(resolved.to_data(), None) == resolved
    assert ResolveSuggestion.from_data({"id": "s1", "state": "open"}, None).anchor is None
    assert resolved.shifted_by(InsertText("b", 0, "ab")) == ResolveSuggestion("s1", "accepted", ("b", 6, 8))
    assert ResolveSuggestion("s1", "open").shifted_by(InsertText("b", 0, "ab")).anchor is None
    assert resolved.stub() == {"id": "s1"}


def test_what_a_suggestion_says_is_blanked_when_the_history_is_redacted():
    proposed = ProposeSuggestion("s1", "b", 0, 3, "teh", "the", "spelling")
    blank = proposed.redacted()
    assert (blank.original, blank.replacement, blank.reason) == ("███", "███", "")
    assert ProposeSuggestion("s2", "b", 0, 3, "foo", None, "why").redacted().replacement is None
    assert proposed.stub() == {"id": "s1"}
    accepted = AcceptSuggestion("s1", "b", 0, 3, "the")
    assert accepted.redacted().replacement == "███"
    assert accepted.stub() == {"id": "s1"}
    assert accepted.follow(("b", 5, 6)) == ("b", 5, 6)  # three characters out, three in
