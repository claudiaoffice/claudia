"""``RestoreCoordinator``: the consent a live session needs before going back to a checkpoint or a line (E3.7).

Pure logic, no kernel and no sockets: what ``propose``/``answer``/``withdraw``/``joined``/``left``/``sweep`` do to
the group and when they resolve. What actually gets carried out is ``apply``, a plain callable the test can record.
"""

import pytest

from claudia_server.restore import RestoreCoordinator, RestoreError


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def applied():
    return []


@pytest.fixture
def coord(clock, applied):
    return RestoreCoordinator(applied.append, clock=clock, timeout=600.0)


LABEL = 'checkpoint "good"'


def propose_restore(coord, by="ana", group=(), checkpoint=1):
    return coord.propose(kind="restore", by=by, checkpoint=checkpoint, line=None, label=LABEL, group=group)


def restore_record(by="ana", checkpoint=1, agreed=("ana",)):
    """What ``apply`` is called with once a restore proposal is carried out."""
    return {"kind": "restore", "by": by, "checkpoint": checkpoint, "line": None, "label": LABEL, "agreed": list(agreed)}


# ------------------------------------------------------------------ opening
def test_the_only_editor_gets_no_vote_and_it_happens_at_once(coord, applied):
    proposal, applied_now = propose_restore(coord, by="ana", group=())
    assert proposal is None and applied_now is True
    assert applied == [restore_record()]
    assert coord.open_proposal is None


def test_more_than_one_editor_opens_a_proposal_instead(coord, applied):
    proposal, applied_now = propose_restore(coord, by="ana", group=["ben"])
    assert applied_now is False and applied == []
    assert proposal is coord.open_proposal
    assert proposal.group == {"ana", "ben"} and proposal.agreed == {"ana"}
    assert proposal.policy == "consensus"  # the document's default


def test_only_one_proposal_may_be_open_at_a_time(coord):
    propose_restore(coord, by="ana", group=["ben"])
    with pytest.raises(RestoreError):
        propose_restore(coord, by="ben", group=["ana"])


def test_a_switch_proposal_carries_its_own_fields(coord, applied):
    coord.propose(kind="switch", by="ana", checkpoint=None, line="main", label='line "main"', group=())
    assert applied == [
        {"kind": "switch", "by": "ana", "checkpoint": None, "line": "main", "label": 'line "main"', "agreed": ["ana"]}
    ]


# ------------------------------------------------------------------ answering
def test_everybody_agreeing_resolves_and_carries_it_out(coord, applied):
    propose_restore(coord, by="ana", group=["ben", "cara"])
    assert coord.answer(user="ben", agree=True) is None
    assert applied == []
    assert coord.answer(user="cara", agree=True) == "agreed"
    assert applied == [restore_record(agreed=["ana", "ben", "cara"])]
    assert coord.open_proposal is None


def test_one_decline_resolves_it_declined_at_once(coord, applied):
    propose_restore(coord, by="ana", group=["ben", "cara"])
    assert coord.answer(user="ben", agree=False) == "declined"
    assert applied == []
    assert coord.open_proposal is None


def test_answering_with_nothing_open_is_an_error(coord):
    with pytest.raises(RestoreError):
        coord.answer(user="ana", agree=True)


# ------------------------------------------------------------------ withdrawing
def test_the_proposer_may_withdraw(coord):
    propose_restore(coord, by="ana", group=["ben"])
    coord.withdraw(user="ana", is_owner=False)
    assert coord.open_proposal is None


def test_an_owner_may_withdraw_somebody_elses_suggestion(coord):
    propose_restore(coord, by="ben", group=["ana"])
    coord.withdraw(user="ana", is_owner=True)
    assert coord.open_proposal is None


def test_nobody_else_may_withdraw(coord):
    propose_restore(coord, by="ana", group=["ben"])
    with pytest.raises(RestoreError):
        coord.withdraw(user="ben", is_owner=False)


def test_withdrawing_with_nothing_open_is_an_error(coord):
    with pytest.raises(RestoreError):
        coord.withdraw(user="ana", is_owner=True)


# ------------------------------------------------------------------ people connecting and disconnecting
def test_a_writer_who_connects_during_a_vote_joins_the_group(coord):
    propose_restore(coord, by="ana", group=["ben"])
    coord.joined("cara", True)
    assert coord.open_proposal.group == {"ana", "ben", "cara"}


def test_a_viewer_who_connects_does_not_join_the_group(coord):
    propose_restore(coord, by="ana", group=["ben"])
    coord.joined("cara", False)
    assert "cara" not in coord.open_proposal.group


def test_joining_with_nothing_open_does_nothing(coord):
    coord.joined("ana", True)  # no proposal exists; must not raise


def test_an_editor_leaving_is_dropped_from_the_vote(coord):
    propose_restore(coord, by="ana", group=["ben", "cara"])
    outcome = coord.left("ben", "main")
    assert outcome is None
    assert coord.open_proposal.group == {"ana", "cara"}


def test_if_everybody_left_has_agreed_leaving_can_resolve_it(coord, applied):
    propose_restore(coord, by="ana", group=["ben", "cara"])
    coord.answer(user="ben", agree=True)
    assert coord.left("cara", "main") == "agreed"  # only ana and ben remain, and both agreed
    assert applied


def test_the_proposer_leaving_withdraws_it(coord, applied):
    propose_restore(coord, by="ana", group=["ben", "cara"])
    assert coord.left("ana", "main") == "withdrawn"
    assert coord.open_proposal is None
    assert applied == []


def test_leaving_with_nothing_open_just_remembers_where_they_were(coord):
    assert coord.left("ana", "main") is None


# ------------------------------------------------------------------ the deadline
def test_consensus_reads_silence_at_the_deadline_as_a_decline(coord, clock, applied):
    propose_restore(coord, by="ana", group=["ben"])
    clock.now = 600.0
    assert coord.sweep() == "declined"
    assert applied == []
    assert coord.open_proposal is None


def test_veto_reads_silence_at_the_deadline_as_agreement(coord, clock, applied):
    coord.policy = "veto"
    propose_restore(coord, by="ana", group=["ben"])
    clock.now = 600.0
    assert coord.sweep() == "agreed"
    assert applied


def test_sweep_before_the_deadline_does_nothing(coord, clock):
    propose_restore(coord, by="ana", group=["ben"])
    clock.now = 599.0
    assert coord.sweep() is None
    assert coord.open_proposal is not None


def test_sweep_with_nothing_open_does_nothing(coord):
    assert coord.sweep() is None


def test_a_later_proposal_gets_its_own_deadline(coord, clock):
    propose_restore(coord, by="ana", group=["ben"])
    coord.answer(user="ben", agree=False)  # declined; closed
    clock.now = 100.0
    propose_restore(coord, by="ana", group=["ben"])
    assert coord.open_proposal.expires_at == 700.0


# ------------------------------------------------------------------ the returning-person notice
def test_nothing_is_reported_to_somebody_who_never_left(coord):
    assert coord.notice_for("ana", "main") is None


def test_nothing_is_reported_if_the_line_they_left_on_is_still_active(coord):
    coord.left("ana", "main")
    assert coord.notice_for("ana", "main") is None


def test_a_resolution_recorded_for_the_line_they_left_is_reported_once(coord):
    from claudia_server.restore import Resolution

    coord.left("ana", "main")
    resolution = Resolution(by="ben", kind="restore", label='checkpoint "good"', agreed=["ben", "cara"])
    coord.record_resolution("main", resolution)
    assert coord.notice_for("ana", "restore-1") == {
        "by": "ben",
        "kind": "restore",
        "label": 'checkpoint "good"',
        "agreed": ["ben", "cara"],
    }
    assert coord.notice_for("ana", "restore-1") is None  # delivered once


def test_a_second_departure_can_get_a_notice_of_its_own(coord):
    from claudia_server.restore import Resolution

    coord.left("ana", "main")
    coord.record_resolution("main", Resolution(by="ben", kind="restore", label="x", agreed=["ben"]))
    coord.notice_for("ana", "restore-1")  # delivered, and now "on" restore-1
    coord.left("ana", "restore-1")
    coord.record_resolution("restore-1", Resolution(by="cara", kind="switch", label="y", agreed=["cara"]))
    assert coord.notice_for("ana", "main")["by"] == "cara"
