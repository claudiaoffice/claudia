"""``Document.scratch``: a throwaway copy that runs commands without touching the live document (E7.8, D263).

An AI proposal is previewed by applying its commands to such a copy. The copy must behave like a document (execute,
check, undo) and the live one must not notice it exists.
"""

import pytest

from claudia_core import KernelError
from claudia_core.testing import Insert, Remove


@pytest.fixture
def worked(doc):
    doc.execute(Insert(0, 1), author="ana")
    doc.execute(Insert(1, 2), author="ben")
    doc.save_checkpoint("ana", "good")
    doc.execute(Insert(2, 3), author="ana")
    return doc


def test_a_scratch_copy_starts_from_the_live_state(worked):
    assert worked.scratch().model.serialize() == worked.model.serialize()


def test_commands_run_on_the_copy_and_the_live_document_does_not_change(worked):
    before_state, before_head, before_log = (
        worked.model.serialize(),
        worked.revision,
        len(worked.log.path(worked.revision)),
    )
    copy = worked.scratch()
    copy.execute(Insert(0, 99), author="ai")
    copy.execute(Remove(1), author="ai")
    assert copy.model.items == [99, 2, 3]
    assert worked.model.serialize() == before_state
    assert worked.revision == before_head
    assert len(worked.log.path(worked.revision)) == before_log


def test_the_copy_has_a_log_of_its_own_and_writes_nothing_to_the_store(worked):
    calls_before, entries_before = list(worked.store.calls), dict(worked.store.entries)
    copy = worked.scratch()
    applied = copy.execute(Insert(0, 7), author="ai")
    assert copy.revision == applied.revision
    assert copy.store is None
    assert worked.store.calls == calls_before
    assert worked.store.entries == entries_before


def test_later_changes_to_the_live_document_do_not_reach_the_copy(worked):
    copy = worked.scratch()
    worked.execute(Insert(0, 50), author="ben")
    assert copy.model.items == [1, 2, 3]


def test_a_copy_can_start_from_an_older_revision(worked):
    earlier = worked.checkpoints[0].marks
    assert worked.scratch(earlier).model.items == [1, 2]


def test_the_copy_can_undo_what_was_done_on_it(worked):
    copy = worked.scratch()
    copy.execute(Insert(0, 99), author="ai")
    copy.undo("ai")
    assert copy.model.items == [1, 2, 3]


def test_the_copy_does_not_inherit_locks_or_undo_steps(worked):
    copy = worked.scratch()
    assert copy.history_for("ana").can_undo is False


def test_a_copy_of_a_copy_is_independent(worked):
    first = worked.scratch()
    first.execute(Insert(0, 9), author="ai")
    second = first.scratch()
    second.execute(Insert(0, 8), author="ai")
    assert first.model.items == [9, 1, 2, 3]
    assert second.model.items == [8, 9, 1, 2, 3]


def test_an_unknown_revision_is_refused(worked):
    from claudia_core import Revision

    with pytest.raises(KernelError):
        worked.scratch(Revision("nowhere", 99))
