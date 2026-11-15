"""``Document.changes_since``: every place that changed after one step, for "show differences from now" (D553).

The replay bar tints what a later step changed, so a person at an old step sees where the document has moved on. The
history is read once, forwards, on a scratch model; nothing live is touched."""

import pytest

from claudia_core import KernelError, Revision
from claudia_core.testing import Insert, Interval, Remove, Replace


def rev(text: str) -> Revision:
    return Revision.parse(text)


@pytest.fixture
def worked(doc):
    doc.execute(Insert(0, 10), author="ana")  # main:1
    doc.execute(Insert(1, 20), author="ben")  # main:2
    doc.execute(Replace(0, 11), author="ana")  # main:3
    doc.execute(Insert(2, 30), author="ana")  # main:4
    return doc


def test_the_places_of_every_later_step_are_collected(worked):
    found = worked.changes_since(rev("main:2"))
    assert found.truncated is False
    assert set(found.regions) == {Interval(0, 1), Interval(2, 3)}


def test_a_step_itself_is_not_a_change_since_it(worked):
    assert worked.changes_since(rev("main:4")).regions == ()


def test_a_place_changed_twice_is_named_once(worked):
    worked.execute(Replace(0, 12), author="ben")  # main:5
    found = worked.changes_since(rev("main:2"))
    assert list(found.regions).count(Interval(0, 1)) == 1


def test_what_was_taken_away_is_still_a_change(worked):
    worked.execute(Remove(1), author="ben")  # main:5
    assert Interval(1, 2) in worked.changes_since(rev("main:3")).regions


def test_the_list_is_cut_at_the_limit_and_says_so(worked):
    found = worked.changes_since(rev("main:1"), limit=1)
    assert len(found.regions) == 1 and found.truncated is True


def test_a_revision_that_is_not_on_the_line_is_refused(worked):
    with pytest.raises(KernelError):
        worked.changes_since(rev("main:99"))


def test_looking_changes_nothing_that_is_live(worked):
    state, branch, head = worked.model.serialize(), worked.branch, worked.revision
    worked.changes_since(rev("main:1"))
    assert (worked.model.serialize(), worked.branch, worked.revision) == (state, branch, head)
