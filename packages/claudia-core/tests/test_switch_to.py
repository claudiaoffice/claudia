"""The way back: after a restore the old future is a side line; ``switch_to`` makes any line the active one again.

Switching, like restoring, moves everybody: the model, undo steps and checkpoints are those of the line switched
to, locks and presence are cleared, views get ``BranchSwitched`` + ``Rebuilt``. The act is recorded as a
``core.Switch`` entry on the line switched to (who, from where). Nothing is lost, no id changes.
"""

import pytest
from helpers import random_session

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


@pytest.fixture
def restored(worked):
    worked.restore_checkpoint(1, author="ana")
    return worked


def test_lines_lists_every_line_and_marks_the_active_one(restored):
    lines = restored.lines()
    summary = [(x.name, x.active, str(x.head)) for x in lines]
    assert summary == [("main", False, "main:5"), ("restore-1", True, "restore-1:4")]
    assert lines[1].forked_from == Revision("main", 3) and lines[0].forked_from is None


def test_a_document_that_never_restored_has_one_line(doc):
    doc.execute(Insert(0, 1))
    assert [(x.name, x.active) for x in doc.lines()] == [("main", True)]


def test_switching_back_brings_the_old_future_back(restored):
    expected = restored.materialize(Revision("main", 5)).serialize()
    applied = restored.switch_to("main", author="ana")
    assert restored.model.serialize() == expected and restored.model.items == [3, 2]
    assert restored.branch == "main" and restored.log.active == "main"
    entry = restored.log.get(applied.revision)
    assert str(entry.rev) == "main:6" and entry.parent == Revision("main", 5)
    assert entry.command.kind == "core.Switch" and entry.author == "ana"


def test_the_line_left_stays_readable_and_hidden(restored):
    restored.switch_to("main", author="ana")
    assert [str(r) for r in restored.side_revisions()] == ["restore-1:4"]
    assert restored.materialize(Revision("restore-1", 4)).items == [1, 2]
    visible = [str(r) for r in restored.history_revisions()]
    assert visible == ["main:1", "main:2", "main:3", "main:4", "main:5", "main:6"]


def test_undo_steps_and_checkpoints_are_those_of_the_line_switched_to(restored):
    restored.switch_to("main", author="ana")
    assert restored.history_for("ben").undo_label == "Insert 3"  # what ben did on the old future is his again
    assert restored.history_for("ana").can_undo
    assert [c.label for c in restored.checkpoints] == ["good"]


def test_locks_and_presence_are_cleared(restored):
    restored.show_presence("ben", [Interval(0, 1)])
    restored.switch_to("main", author="ana")
    assert restored.presence.holds() == []


def test_views_are_told_to_reload(restored):
    seen = []
    restored.subscribe(lambda e: seen.append(e) if isinstance(e, (BranchSwitched, Rebuilt)) else None)
    restored.switch_to("main", author="ana")
    assert [type(e).__name__ for e in seen] == ["BranchSwitched", "Rebuilt"]
    assert seen[0].old == "restore-1" and seen[0].new == "main"
    assert seen[0].fork_point == Revision("main", 3)  # the last revision both lines share


def test_the_switch_is_stored_before_the_entry(restored):
    restored.switch_to("main", author="ana")
    assert restored.store.calls[-2:] == ["write_branch", "append_entry"]
    assert restored.store.active == "main"


def test_switching_to_the_active_line_does_nothing(restored):
    calls = list(restored.store.calls)
    assert restored.switch_to("restore-1", author="ana") is None
    assert restored.store.calls == calls


def test_an_unknown_line_is_an_error(restored):
    with pytest.raises(KernelError):
        restored.switch_to("nowhere", author="ana")


def test_editing_goes_on_on_the_line_switched_to(restored):
    restored.switch_to("main", author="ana")
    applied = restored.execute(Insert(0, 7), author="ben")
    assert str(applied.revision) == "main:7" and restored.model.items == [7, 3, 2]
    assert restored.log.head("restore-1") == Revision("restore-1", 4)


def test_back_and_forth_loses_nothing(restored):
    restored.execute(Insert(2, 7), author="ben")  # restore-1:5
    restored.switch_to("main", author="ana")  # main:6
    restored.switch_to("restore-1", author="ana")  # restore-1:6
    assert restored.model.items == [1, 2, 7]
    assert restored.log.has(Revision("main", 6)) and restored.log.has(Revision("restore-1", 6))


def test_reopening_follows_the_active_line(restored):
    restored.switch_to("main", author="ana")
    again = Document.open(ListModel, CommandLog.from_data(restored.log.to_data(), ListModel.registry))
    assert again.branch == "main" and again.model.serialize() == restored.model.serialize()
    assert again.history_for("ben").undo_label == "Insert 3"


def test_a_restore_after_a_switch_gets_a_fresh_line_name(restored):
    restored.switch_to("main", author="ana")
    restored.restore_checkpoint(1, author="ana")
    assert restored.branch == "restore-2" and restored.model.items == [1, 2]


def test_discarding_after_a_switch_forgets_the_line_left(restored):
    restored.switch_to("main", author="ana")
    removed = restored.discard_side_history()
    assert [str(r) for r in removed] == ["restore-1:4"]
    assert [x.name for x in restored.lines()] == ["main"]


@pytest.mark.parametrize("seed", range(10))
def test_restore_and_back_gives_the_same_state_and_undo_steps(make_doc, seed):
    doc = random_session(make_doc(), seed, steps=200)
    if not doc.checkpoints:
        pytest.skip("this session saved no checkpoint")
    old = doc.branch
    state = doc.model.serialize()
    labels = {a: (doc.history_for(a).undo_label, doc.history_for(a).redo_label) for a in ("ana", "ben")}
    info = doc.checkpoints[len(doc.checkpoints) // 2]
    if doc.restore_checkpoint(info.number, author="ana") is None:
        pytest.skip("the document was already in that state")
    doc.switch_to(old, author="ana")
    assert doc.model.serialize() == state
    assert {a: (doc.history_for(a).undo_label, doc.history_for(a).redo_label) for a in ("ana", "ben")} == labels
