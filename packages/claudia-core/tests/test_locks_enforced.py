"""execute() itself enforces locks, for every author including the AI (D6).

Replicas replaying accepted entries do not."""

import pytest

from claudia_core import Batch, Document, RegionHeld
from claudia_core.testing import FakeClock, Insert, Interval, ListModel, Replace


@pytest.fixture
def locked(doc):
    for i in range(4):
        doc.execute(Insert(0, i), author="ana")
    doc.lock("ben", [Interval(1, 3)], ttl=10)
    return doc


def test_execute_refuses_a_command_that_touches_a_colleagues_lock(locked):
    before, revision, calls = list(locked.model.items), locked.revision, list(locked.store.calls)
    with pytest.raises(RegionHeld) as caught:
        locked.execute(Replace(1, 99), author="ana")
    assert "ben" in str(caught.value)
    assert (locked.model.items, locked.revision, locked.store.calls) == (before, revision, calls)  # nothing happened


def test_the_owner_of_the_lock_may_edit_it(locked):
    locked.execute(Replace(1, 99), author="ben")
    assert locked.model.items[1] == 99


def test_a_command_elsewhere_is_not_blocked(locked):
    locked.execute(Replace(0, 99), author="ana")
    locked.execute(Replace(3, 98), author="ana")


def test_the_ai_is_bound_like_everybody_else(locked):
    with pytest.raises(RegionHeld):
        locked.execute(Replace(2, 5), author="ai")


def test_one_blocked_part_blocks_the_whole_batch(locked):
    with pytest.raises(RegionHeld):
        locked.execute(Batch((Replace(0, 7), Replace(1, 7))), author="ana")
    assert locked.model.items[0] == 3  # the free part was not applied either


def test_an_expired_lock_no_longer_blocks(locked, clock):
    clock.advance(11)
    locked.execute(Replace(1, 99), author="ana")


def test_presence_without_a_lock_never_blocks(doc):
    doc.execute(Insert(0, 1), author="ana")
    doc.show_presence("ben", [Interval(0, 1)])
    doc.execute(Replace(0, 2), author="ana")


def test_a_replica_applying_accepted_entries_ignores_locks(locked):
    replica = Document(ListModel(), clock=FakeClock().time)
    entries = locked.entries_since(None)
    replica.lock("ben", [Interval(0, 4)], ttl=10)
    for entry in entries:
        replica.apply_entry(entry)  # the server already decided; the replica must follow
    assert replica.model.items == locked.model.items
