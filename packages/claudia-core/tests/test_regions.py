"""E1.5: one Region interface for presence, locks and AI edits."""

import pytest

from claudia_core import Batch, RegionHeld, transform
from claudia_core.testing import Insert, Interval, Remove, Replace


def test_interval_moves_with_edits():
    region = Interval(2, 5)
    assert transform(region, Insert(0, 1)) == Interval(3, 6)
    assert transform(region, Insert(3, 1)) == Interval(2, 6)  # inside: grows
    assert transform(region, Insert(5, 1)) == Interval(2, 5)  # after: unchanged
    assert transform(region, Remove(0)) == Interval(1, 4)
    assert transform(region, Remove(3)) == Interval(2, 4)
    assert transform(region, Replace(3, 9)) == region
    assert transform(Interval(2, 3), Remove(2)) is None  # gone


def test_batches_are_transformed_leaf_by_leaf():
    assert transform(Interval(2, 5), Batch((Insert(0, 1), Insert(0, 1)))) == Interval(4, 7)
    assert transform(Interval(2, 3), Batch((Insert(0, 1), Remove(3)))) is None


def test_presence_follows_the_edits_and_ends_with_the_region(doc):
    for i in range(4):
        doc.execute(Insert(0, i), author="ana")
    doc.show_presence("ben", [Interval(1, 3)])
    doc.execute(Insert(0, 1), author="ana")
    assert doc.presence.of("ben").regions == (Interval(2, 4),)
    doc.execute(Remove(0), author="ana")
    doc.show_presence("ben", [Interval(2, 4)])
    doc.execute(Remove(2), author="ana")
    doc.execute(Remove(2), author="ana")
    assert doc.presence.of("ben") is None


def test_locks_conflict_by_overlap_only(doc, clock):
    doc.lock("ana", [Interval(0, 3)], ttl=10)
    with pytest.raises(RegionHeld):
        doc.lock("ben", [Interval(2, 4)], ttl=10)
    doc.lock("ben", [Interval(3, 4)], ttl=10)
    with pytest.raises(RegionHeld):
        doc.check_free("ben", Replace(1, 5))  # touches ana's lock
    doc.check_free("ana", Replace(1, 5))  # her own lock never blocks her
    doc.check_free("ben", Replace(3, 5))


def test_locks_expire_but_presence_stays(doc, clock):
    doc.lock("ana", [Interval(0, 3)], ttl=10)
    clock.advance(11)
    assert doc.presence.conflicts("ben", [Interval(0, 1)]) == []
    assert doc.presence.of("ana").regions == (Interval(0, 3),)


def test_regions_travel_as_plain_data(doc):
    published = []
    from claudia_core import EphemeralPublished

    doc.subscribe(lambda e: published.append(e) if isinstance(e, EphemeralPublished) else None)
    doc.show_presence("ben", [Interval(1, 3)])
    data = published[-1].message.data["regions"]
    assert [doc.model.region_from_data(d) for d in data] == [Interval(1, 3)]


def test_releasing_and_empty_presence(doc):
    doc.show_presence("ben", [Interval(1, 3)])
    doc.presence.release("ben")
    assert doc.presence.of("ben") is None
    doc.show_presence("ben", [])
    assert doc.presence.holds() == []
