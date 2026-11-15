"""``Document.last_seen``: the last step at which a state had some property, e.g. a thing still existed (D551).

What a tag to a deleted thing needs: the replay jumps to the last moment the thing was there."""

from claudia_core import Revision
from claudia_core.testing import Insert, Remove


def rev(text: str) -> Revision:
    return Revision.parse(text)


def has(value):
    return lambda model: value in model.items


def test_a_thing_that_is_there_now_was_last_seen_at_the_head(doc):
    doc.execute(Insert(0, 10), author="ana")
    doc.execute(Insert(1, 20), author="ana")
    assert doc.last_seen(has(10)) == rev("main:2")


def test_a_thing_that_was_taken_away_was_last_seen_before_that_step(doc):
    doc.execute(Insert(0, 10), author="ana")  # main:1
    doc.execute(Insert(1, 20), author="ana")  # main:2
    doc.execute(Remove(0), author="ben")  # main:3 takes away the 10
    doc.execute(Insert(1, 30), author="ana")  # main:4
    assert doc.last_seen(has(10)) == rev("main:2")


def test_a_thing_that_was_never_there_was_never_seen(doc):
    doc.execute(Insert(0, 10), author="ana")
    assert doc.last_seen(has(99)) is None


def test_the_last_time_counts_when_a_thing_came_and_went_and_came_back(doc):
    doc.execute(Insert(0, 10), author="ana")  # main:1
    doc.execute(Remove(0), author="ana")  # main:2
    doc.execute(Insert(0, 10), author="ana")  # main:3
    doc.execute(Remove(0), author="ana")  # main:4
    assert doc.last_seen(has(10)) == rev("main:3")


def test_an_empty_document_has_seen_nothing(doc):
    assert doc.last_seen(has(10)) is None


def test_looking_changes_nothing_that_is_live(doc):
    doc.execute(Insert(0, 10), author="ana")
    state, branch = doc.model.serialize(), doc.branch
    doc.last_seen(has(10))
    assert (doc.model.serialize(), doc.branch) == (state, branch)
