"""Edits in flight: an edit written against a view that is no longer the document's line is refused.

A restore (or a switch) moves everybody to another line. A colleague whose edit was already on the wire was
looking at the old one; applying it to the new line would put a change there that was meant for a state that
no longer exists. ``execute(..., base=revision)`` carries the revision the author saw; the kernel refuses it
with ``StaleEdit`` when that revision is not on the path of the active line.
"""

import pytest

from claudia_core import KernelError, Revision, StaleEdit
from claudia_core.testing import Insert, Remove


@pytest.fixture
def worked(doc):
    doc.execute(Insert(0, 1), author="ana")  # main:1
    doc.execute(Insert(1, 2), author="ben")  # main:2
    doc.save_checkpoint("ana", "good")  # main:3 labels main:2
    doc.execute(Insert(0, 3), author="ben")  # main:4
    doc.execute(Remove(1), author="ana")  # main:5
    return doc


def test_an_edit_without_a_base_is_not_checked(worked):
    worked.restore_checkpoint(1, author="ana")
    assert worked.execute(Insert(0, 9), author="ben").revision == Revision("restore-1", 5)


def test_an_older_base_on_the_active_line_is_fine(worked):
    applied = worked.execute(Insert(0, 9), author="ben", base=Revision("main", 2))
    assert applied.revision == Revision("main", 6)


def test_the_current_head_is_fine(worked):
    worked.execute(Insert(0, 9), author="ben", base=worked.revision)


def test_an_edit_from_the_abandoned_future_is_refused_after_a_restore(worked):
    worked.restore_checkpoint(1, author="ana")
    before, items = worked.revision, list(worked.model.items)
    with pytest.raises(StaleEdit) as caught:
        worked.execute(Insert(0, 9), author="ben", base=Revision("main", 5))
    assert worked.revision == before and worked.model.items == items  # nothing happened
    assert caught.value.base == Revision("main", 5) and caught.value.line == "restore-1"
    assert "reload" in str(caught.value).lower() or "changed" in str(caught.value).lower()


def test_a_refused_edit_is_not_stored(worked):
    worked.restore_checkpoint(1, author="ana")
    calls = list(worked.store.calls)
    with pytest.raises(StaleEdit):
        worked.execute(Insert(0, 9), author="ben", base=Revision("main", 4))
    assert worked.store.calls == calls


def test_what_the_old_and_the_new_line_share_is_still_a_good_base(worked):
    worked.restore_checkpoint(1, author="ana")
    worked.execute(Insert(0, 9), author="ben", base=Revision("main", 3))  # the checkpoint label: on both paths
    worked.execute(Insert(0, 8), author="ben", base=Revision("restore-1", 4))


def test_a_base_that_never_existed_is_stale(worked):
    with pytest.raises(StaleEdit):
        worked.execute(Insert(0, 9), author="ben", base=Revision("main", 99))
    with pytest.raises(StaleEdit):
        worked.execute(Insert(0, 9), author="ben", base=Revision("elsewhere", 1))


def test_a_base_whose_history_was_discarded_is_stale(worked):
    worked.restore_checkpoint(1, author="ana")
    worked.discard_side_history()
    with pytest.raises(StaleEdit):
        worked.execute(Insert(0, 9), author="ben", base=Revision("main", 5))


def test_the_way_back_makes_the_new_line_stale(worked):
    worked.restore_checkpoint(1, author="ana")
    worked.switch_to("main", author="ana")
    with pytest.raises(StaleEdit):
        worked.execute(Insert(0, 9), author="ben", base=Revision("restore-1", 4))
    worked.execute(Insert(0, 9), author="ben", base=Revision("main", 5))  # the old line is the active one again


def test_stale_edit_is_a_kernel_error(worked):
    assert issubclass(StaleEdit, KernelError)
