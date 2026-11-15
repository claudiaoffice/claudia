"""``peek_revision``: the document as it was after one step of its history, and where that step touched it (D551).

What scrubbing shows: the state at the playhead, and the places the view has to bring into sight. Like ``peek_line`` it
is a look: the live model, the active line and everybody's undo steps stay as they are."""

import pytest

from claudia_core import Batch, KernelError, Look, Revision
from claudia_core.testing import Insert, Interval, Remove


@pytest.fixture
def worked(doc):
    doc.execute(Insert(0, 10), author="ana")  # main:1
    doc.execute(Insert(1, 20), author="ben")  # main:2
    doc.execute(Insert(0, 5), author="ana")  # main:3
    doc.execute(Remove(1), author="ben")  # main:4 takes away the 10
    return doc


def rev(text: str) -> Revision:
    return Revision.parse(text)


def test_a_step_shows_the_state_after_it_and_nothing_later(worked):
    assert worked.peek_revision(rev("main:2")).model.items == [10, 20]
    assert worked.peek_revision(rev("main:3")).model.items == [5, 10, 20]
    assert worked.peek_revision(rev("main:4")).model.items == [5, 20]


def test_the_first_step_starts_from_the_empty_document(worked):
    look = worked.peek_revision(rev("main:1"))
    assert look.model.items == [10]
    assert look.entry.parent is None


def test_it_says_who_did_it_and_what(worked):
    look = worked.peek_revision(rev("main:3"))
    assert isinstance(look, Look)
    assert (look.revision, look.entry.author, look.entry.command) == (rev("main:3"), "ana", Insert(0, 5))


def test_the_focus_is_the_place_the_step_touched(worked):
    assert worked.peek_revision(rev("main:3")).focus == (Interval(0, 1),)
    assert worked.peek_revision(rev("main:4")).focus == (Interval(1, 2),)


def test_a_batch_has_the_places_of_all_its_parts_once_each(doc):
    doc.execute(Insert(0, 1), author="ana")
    doc.execute(Batch((Insert(1, 2), Insert(2, 3), Insert(2, 4))), author="ana")
    look = doc.peek_revision(rev("main:2"))
    assert look.focus == (Interval(1, 2), Interval(2, 3))


def test_a_look_changes_nothing_that_is_live(worked):
    state, branch = worked.model.serialize(), worked.branch
    can_undo = worked.history_for("ben").can_undo
    worked.peek_revision(rev("main:2"))
    assert (worked.model.serialize(), worked.branch) == (state, branch)
    assert worked.history_for("ben").can_undo == can_undo


def test_a_revision_on_a_hidden_line_can_be_looked_at(worked):
    worked.save_checkpoint("ana", "good")  # main:5 labels main:4
    worked.restore_checkpoint(1, author="ana")  # the document goes on on restore-1; main is hidden
    assert worked.peek_revision(rev("main:3")).model.items == [5, 10, 20]


def test_a_revision_that_is_not_there_is_an_error(worked):
    with pytest.raises(KernelError, match="main:99"):
        worked.peek_revision(rev("main:99"))


def test_a_redacted_step_still_shows_where_it_was(worked):
    worked.redact([rev("main:3")], author="ana")
    look = worked.peek_revision(rev("main:3"))
    assert look.entry.redacted
    assert look.focus == (Interval(0, 1),)
