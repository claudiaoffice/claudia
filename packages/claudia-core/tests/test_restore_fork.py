"""E1.7 revised: restoring a checkpoint forks. The document continues from the checkpoint on a new line; what
came after stays in the log on a hidden side line until an owner discards it. Revision ids never change."""

import pytest
from helpers import random_session, try_step

from claudia_core import (
    BranchSwitched,
    CommandLog,
    Document,
    KernelError,
    Rebuilt,
    Revision,
)
from claudia_core.testing import Insert, Interval, ListModel, Remove


@pytest.fixture
def worked(doc):
    doc.execute(Insert(0, 1), author="ana")  # main:1
    doc.execute(Insert(1, 2), author="ben")  # main:2
    doc.save_checkpoint("ana", "good")  # main:3 labels main:2
    doc.execute(Insert(0, 3), author="ben")  # main:4
    doc.execute(Remove(1), author="ana")  # main:5
    return doc


def test_restore_continues_from_the_checkpoint_on_a_new_line(worked):
    applied = worked.restore_checkpoint(1, author="ana")
    assert worked.model.items == [1, 2]
    assert worked.branch == "restore-1" and worked.log.active == "restore-1"
    entry = worked.log.get(applied.revision)
    assert str(entry.rev) == "restore-1:4" and entry.parent == Revision("main", 3)  # right after the label
    assert entry.command.kind == "core.Restore" and entry.author == "ana" and "good" in entry.command.label


def test_nothing_is_lost_and_no_id_changes(worked):
    worked.restore_checkpoint(1, author="ana")
    for seq in (1, 2, 3, 4, 5):
        assert worked.log.has(Revision("main", seq))
    assert worked.materialize(Revision("main", 5)).items == [3, 2]  # the abandoned future is still readable
    assert [str(e.rev) for e in worked.log.path(worked.revision)] == ["main:1", "main:2", "main:3", "restore-1:4"]


def test_the_visible_history_stops_at_the_checkpoint(worked):
    worked.restore_checkpoint(1, author="ana")
    assert [str(r) for r in worked.history_revisions()] == ["main:1", "main:2", "main:3", "restore-1:4"]
    assert [str(r) for r in worked.side_revisions()] == ["main:4", "main:5"]
    assert [c.label for c in worked.checkpoints] == ["good"]


def test_editing_goes_on_on_the_new_line(worked):
    worked.restore_checkpoint(1, author="ana")
    applied = worked.execute(Insert(2, 7), author="ben")
    assert str(applied.revision) == "restore-1:5" and worked.model.items == [1, 2, 7]
    assert worked.log.head("main") == Revision("main", 5)  # the old line did not move


def test_restoring_the_state_we_are_in_does_nothing(worked):
    worked.restore_checkpoint(1, author="ana")
    assert worked.restore_checkpoint(1, author="ana") is None


def test_checkpoints_after_the_restore_point_leave_the_visible_list(worked):
    worked.execute(Insert(0, 9), author="ana")
    worked.save_checkpoint("ana", "later")  # number 2, on the tail
    worked.restore_checkpoint(1, author="ana")
    assert [c.label for c in worked.checkpoints] == ["good"]
    assert worked.save_checkpoint("ana") is None  # nothing changed since "good"


def test_undo_steps_of_the_discarded_future_are_gone(worked):
    assert worked.history_for("ben").can_undo and worked.history_for("ana").can_undo
    worked.restore_checkpoint(1, author="ana")
    labels = [worked.history_for(a).undo_label for a in ("ana", "ben")]
    assert labels == ["Insert 1", "Insert 2"]  # only what led to the checkpoint


def test_presence_is_cleared_and_events_tell_views_to_reload(worked):
    worked.show_presence("ben", [Interval(0, 1)])
    seen = []
    worked.subscribe(lambda e: seen.append(type(e).__name__) if isinstance(e, (BranchSwitched, Rebuilt)) else None)
    worked.restore_checkpoint(1, author="ana")
    assert worked.presence.holds() == [] and seen == ["BranchSwitched", "Rebuilt"]


def test_the_switch_is_stored(worked):
    worked.restore_checkpoint(1, author="ana")
    assert worked.store.calls[-2:] == ["write_branch", "append_entry"]
    assert worked.store.active == "restore-1"


def test_reopening_follows_the_active_line(worked):
    worked.restore_checkpoint(1, author="ana")
    worked.execute(Insert(2, 7), author="ben")
    copy = CommandLog.from_data(worked.log.to_data(), ListModel.registry)
    again = Document.open(ListModel, copy)
    assert again.branch == "restore-1" and again.model.serialize() == worked.model.serialize()
    assert [c.label for c in again.checkpoints] == ["good"]


def test_a_second_restore_gets_its_own_line(worked):
    worked.restore_checkpoint(1, author="ana")
    worked.execute(Insert(0, 8), author="ana")
    worked.save_checkpoint("ana", "second")
    worked.execute(Insert(0, 6), author="ana")
    worked.restore_checkpoint(2, author="ana")
    assert worked.branch == "restore-2" and worked.model.items == [8, 1, 2]
    assert worked.log.has(Revision("restore-1", 7))  # the first abandoned line is still there


def test_unknown_checkpoint(worked):
    with pytest.raises(KernelError):
        worked.restore_checkpoint(7, author="ana")


@pytest.mark.parametrize("seed", range(10))
def test_random_restores_reproduce_the_state_and_survive_reopening(make_doc, seed):
    doc = random_session(make_doc(), seed, steps=200)
    for _ in range(3):
        if not doc.checkpoints:
            break
        info = doc.checkpoints[len(doc.checkpoints) // 2]
        expected = doc.materialize(info.marks).serialize()
        doc.restore_checkpoint(info.number, author="ana")
        assert doc.model.serialize() == expected
        again = Document.open(ListModel, CommandLog.from_data(doc.log.to_data(), ListModel.registry))
        assert again.model.serialize() == expected and again.branch == doc.branch
        for step in range(30):  # and life goes on, undo included
            doc.execute(Insert(0, 100 + step), author="ben")
            if step % 7 == 0:
                try_step(doc.undo, "ben")
        doc.save_checkpoint("ben")


# ------------------------------------------------------------------ discarding side lines (owner's act)
def test_discarding_the_abandoned_future_removes_it_for_good(worked):
    worked.restore_checkpoint(1, author="ana")
    removed = worked.discard_side_history()
    assert [str(r) for r in removed] == ["main:4", "main:5"]
    assert not worked.log.has(Revision("main", 5)) and worked.log.has(Revision("main", 3))
    assert worked.side_revisions() == []
    assert [str(r) for r in worked.history_revisions()] == ["main:1", "main:2", "main:3", "restore-1:4"]
    assert worked.store.discarded == [Revision("main", 4), Revision("main", 5)]
    again = Document.open(ListModel, CommandLog.from_data(worked.log.to_data(), ListModel.registry))
    assert again.model.serialize() == worked.model.serialize()


def test_discarding_with_nothing_to_discard(doc):
    doc.execute(Insert(0, 1))
    assert doc.discard_side_history() == []


def test_discarding_keeps_whole_older_lines_out_too(worked):
    worked.restore_checkpoint(1, author="ana")
    worked.execute(Insert(0, 8), author="ana")
    worked.save_checkpoint("ana", "second")
    worked.restore_checkpoint(1, author="ana")  # back to "good" again -> restore-2, restore-1 is now a side line
    worked.discard_side_history()
    assert not worked.log.has(Revision("restore-1", 5))
    assert worked.model.items == [1, 2] and worked.branch == "restore-2"
