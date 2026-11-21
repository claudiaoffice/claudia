"""What-ifs and proposals (D236, D263, D1308): a private copy of the document that remembers what it was asked to do,
hands that back as plain data, and can be carried out on the live document as one step -- or refused as outdated, with
the places named, when somebody has worked on them since. Never a line, never a merge."""

import pytest

from claudia_core import (
    Document,
    KernelError,
    Proposal,
    ProposalOutdated,
    RegionHeld,
    Revision,
)
from claudia_core.testing import Insert, Interval, Remove, Replace, lists


@pytest.fixture
def worked(doc):
    for position, value in enumerate([10, 20, 30, 40]):
        doc.execute(Insert(position, value), author="ana")
    return doc


# -- the copy ---------------------------------------------------------------------------------------------------
def test_a_what_if_starts_from_the_state_now_and_runs_commands_on_its_own_copy(worked):
    live = worked.model.serialize()
    idea = worked.what_if(author="ai")
    idea.apply(Replace(1, 99))
    assert idea.document.model.items == [10, 99, 30, 40]
    assert worked.model.serialize() == live


def test_later_work_on_the_live_document_does_not_reach_the_what_if(worked):
    idea = worked.what_if(author="ai")
    worked.execute(Insert(0, 1), author="ben")
    assert idea.document.model.items == [10, 20, 30, 40]


def test_a_what_if_can_start_from_an_older_step(worked):
    idea = worked.what_if(Revision("main", 2), author="ai")
    assert idea.document.model.items == [10, 20]
    assert idea.base == Revision("main", 2)


def test_a_step_that_does_not_exist_is_refused(worked):
    with pytest.raises(KernelError):
        worked.what_if(Revision("main", 99))


def test_undo_last_takes_the_last_command_back_and_out_of_the_proposal(worked):
    idea = worked.what_if(author="ai")
    idea.apply(Replace(0, 1))
    idea.apply(Replace(1, 2))
    idea.undo_last()
    assert idea.document.model.items == [1, 20, 30, 40]
    assert idea.proposal().commands == (Replace(0, 1),)


def test_a_what_if_of_a_what_if_starts_from_the_copy(worked):
    idea = worked.what_if(author="ai")
    idea.apply(Replace(0, 1))
    deeper = idea.what_if()
    deeper.apply(Replace(1, 2))
    assert deeper.document.model.items == [1, 2, 30, 40]
    assert idea.document.model.items == [1, 20, 30, 40]


# -- the proposal -----------------------------------------------------------------------------------------------
def test_the_proposal_says_where_it_started_who_made_it_and_what_it_does(worked):
    idea = worked.what_if(author="ai")
    idea.apply(Replace(1, 99))
    idea.apply(Replace(2, 98))
    proposal = idea.proposal()
    assert isinstance(proposal, Proposal)
    assert (proposal.base, proposal.author) == (worked.revision, "ai")
    assert proposal.commands == (Replace(1, 99), Replace(2, 98))


def test_a_proposal_is_plain_data_and_comes_back_as_it_went(worked):
    idea = worked.what_if(author="ai")
    idea.apply(Replace(1, 99))
    proposal = idea.proposal()
    assert Proposal.from_data(proposal.to_data(), lists) == proposal


def test_changes_name_the_places_the_what_if_would_change(worked):
    idea = worked.what_if(author="ai")
    idea.apply(Replace(1, 99))
    idea.apply(Replace(3, 98))
    assert idea.changes() == (Interval(1, 2), Interval(3, 4))


def test_a_what_if_with_nothing_done_proposes_and_changes_nothing(worked):
    idea = worked.what_if(author="ai")
    assert idea.proposal().commands == () and idea.changes() == ()


# -- carrying it out --------------------------------------------------------------------------------------------
def test_a_proposal_on_a_quiet_document_is_one_step_and_one_undo_by_the_one_who_accepts_it(worked):
    idea = worked.what_if(author="ai")
    idea.apply(Replace(1, 99))
    idea.apply(Replace(2, 98))
    before = len(worked.log.path(worked.revision))
    applied = worked.apply_proposal(idea.proposal(), author="ana", via="ai")
    assert worked.model.items == [10, 99, 98, 40]
    assert len(worked.log.path(worked.revision)) == before + 1
    assert (applied.entry.author, applied.entry.via) == ("ana", "ai")
    worked.undo("ana")
    assert worked.model.items == [10, 20, 30, 40]


def test_an_edit_on_the_same_place_makes_the_proposal_outdated_and_changes_nothing(worked):
    idea = worked.what_if(author="ai")
    idea.apply(Replace(1, 99))
    proposal = idea.proposal()
    worked.execute(Replace(1, 5), author="ben")
    state, head = worked.model.serialize(), worked.revision
    with pytest.raises(ProposalOutdated) as outdated:
        worked.apply_proposal(proposal, author="ana", via="ai")
    assert outdated.value.conflicts == (Interval(1, 2),)
    assert (worked.model.serialize(), worked.revision) == (state, head)


def test_an_edit_elsewhere_does_not_outdate_it(worked):
    idea = worked.what_if(author="ai")
    idea.apply(Replace(1, 99))
    proposal = idea.proposal()
    worked.execute(Replace(3, 5), author="ben")
    worked.apply_proposal(proposal, author="ana")
    assert worked.model.items == [10, 99, 30, 5]


def test_a_step_that_moves_the_places_before_it_outdates_it_though_it_touches_nothing_of_it(worked):
    idea = worked.what_if(author="ai")
    idea.apply(Replace(2, 99))
    proposal = idea.proposal()
    worked.execute(Insert(0, 1), author="ben")  # the third value is now the fourth: Replace(2) would hit the wrong one
    with pytest.raises(ProposalOutdated) as outdated:
        worked.apply_proposal(proposal, author="ana")
    assert outdated.value.conflicts == (Interval(2, 3),)


def test_a_step_that_moves_places_after_it_does_not_outdate_it(worked):
    idea = worked.what_if(author="ai")
    idea.apply(Replace(1, 99))
    proposal = idea.proposal()
    worked.execute(Insert(4, 1), author="ben")
    worked.apply_proposal(proposal, author="ana")
    assert worked.model.items == [10, 99, 30, 40, 1]


def test_a_step_taken_back_and_done_again_counts_like_any_other(worked):
    idea = worked.what_if(author="ai")
    idea.apply(Remove(1))
    proposal = idea.proposal()
    worked.execute(Replace(1, 7), author="ben")
    worked.undo("ben")
    with pytest.raises(ProposalOutdated):
        worked.apply_proposal(proposal, author="ana")


def test_a_place_somebody_holds_refuses_the_whole_proposal(worked):
    idea = worked.what_if(author="ai")
    idea.apply(Replace(0, 1))
    idea.apply(Replace(3, 2))
    worked.lock("ben", [Interval(3, 4)], ttl=60)
    state = worked.model.serialize()
    with pytest.raises(RegionHeld):
        worked.apply_proposal(idea.proposal(), author="ana")
    assert worked.model.serialize() == state


def test_a_proposal_made_on_a_line_that_is_not_the_one_now_is_outdated(worked):
    worked.save_checkpoint("ana", "before")
    worked.execute(Insert(0, 1), author="ana")
    idea = worked.what_if(author="ai")
    idea.apply(Replace(1, 99))
    proposal = idea.proposal()
    worked.restore_checkpoint(1, "ana")  # forks the line: the step the proposal began at is on the old one
    with pytest.raises(ProposalOutdated):
        worked.apply_proposal(proposal, author="ana")


def test_a_proposal_of_nothing_is_nothing_to_apply(worked):
    with pytest.raises(KernelError):
        worked.apply_proposal(worked.what_if(author="ai").proposal(), author="ana")


# -- who made a step ----------------------------------------------------------------------------------------------
def test_a_step_says_by_what_it_was_made_and_the_log_keeps_it(make_doc):
    doc = make_doc()
    doc.execute(Insert(0, 1), author="ana", via="ai")
    doc.execute(Insert(1, 2), author="ana")
    entries = doc.log.path(doc.revision)
    assert [e.via for e in entries] == ["ai", None]
    assert [e.to_data().get("via") for e in entries] == ["ai", None]
    from claudia_core import Step

    assert Step.from_data(entries[0].to_data(), lists).via == "ai"


def test_the_tag_is_kept_when_a_step_is_redacted_and_when_the_document_is_opened_again(make_doc):
    doc = make_doc()
    doc.execute(Insert(0, 1), author="ana", via="ai")
    doc.redact([Revision("main", 1)], author="ana")
    assert doc.log.path(doc.revision)[0].via == "ai"
    again = Document.open(type(doc.model), doc.log)
    assert again.log.path(again.revision)[0].via == "ai"
