"""``Document.restore_revision``: go back to the state after any one step, not only to a checkpoint (D553).

Same as a checkpoint restore it forks: the document continues from that step on a new line, and what came after
stays in the log on the side line."""

import pytest

from claudia_core import KernelError, Restore, Revision
from claudia_core.testing import Insert, Remove


def rev(text: str) -> Revision:
    return Revision.parse(text)


@pytest.fixture
def worked(doc):
    doc.execute(Insert(0, 10), author="ana")  # main:1
    doc.execute(Insert(1, 20), author="ben")  # main:2
    doc.execute(Insert(2, 30), author="ana")  # main:3
    doc.execute(Remove(0), author="ben")  # main:4
    return doc


def test_the_document_goes_back_to_the_state_after_that_step(worked):
    worked.restore_revision(rev("main:2"), author="ana")
    assert worked.model.items == [10, 20]


def test_it_continues_on_a_new_line_and_keeps_what_came_after(worked):
    after = worked.revision
    worked.restore_revision(rev("main:2"), author="ana")
    assert worked.branch != "main"
    assert worked.log.head("main") == after
    assert worked.peek_line("main").items == [20, 30]


def test_the_first_entry_of_the_new_line_says_who_went_back_to_what(worked):
    applied = worked.restore_revision(rev("main:2"), author="ana")
    assert isinstance(applied.command, Restore)
    assert (applied.entry.author, applied.command.marks, applied.command.from_branch) == ("ana", rev("main:2"), "main")


def test_going_back_to_where_the_document_is_changes_nothing(worked):
    assert worked.restore_revision(rev("main:4"), author="ana") is None
    assert worked.branch == "main"


def test_a_revision_the_line_does_not_have_is_refused(worked):
    with pytest.raises(KernelError):
        worked.restore_revision(rev("main:99"), author="ana")


def test_a_revision_of_a_side_line_is_refused(worked):
    worked.restore_revision(rev("main:2"), author="ana")
    with pytest.raises(KernelError):
        worked.restore_revision(rev("main:3"), author="ana")
