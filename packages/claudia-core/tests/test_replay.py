"""E1.2: ``replay_collecting`` -- the decoupled-from-``Document`` shape of replay (D37, D178 groundwork)."""

import pytest

from claudia_core import Entry, ReplayError, Revision
from claudia_core.replay import replay_collecting
from claudia_core.testing import Insert, ListModel, Remove


def _entry(seq: int, command, *, author: str = "ana", of=None, origin: str = "do") -> Entry:
    parent = Revision("main", seq - 1) if seq > 1 else None
    return Entry(Revision("main", seq), parent, author, f"2026-11-01T12:00:{seq:02d}.000Z", command, origin, of, False)


def test_returns_the_entry_inverse_pairs_in_order():
    model = ListModel.empty()
    entries = [_entry(1, Insert(0, 5)), _entry(2, Insert(1, 6)), _entry(3, Insert(0, 7))]
    applied = replay_collecting(model, entries)
    assert [e.rev for e, _ in applied] == [Revision("main", 1), Revision("main", 2), Revision("main", 3)]
    assert [inv.index for _, inv in applied] == [0, 1, 0]  # each inverse is the Remove that undoes its Insert


def test_mutates_the_model_exactly_like_replay():
    model = ListModel.empty()
    replay_collecting(model, [_entry(1, Insert(0, 5)), _entry(2, Insert(1, 6))])
    assert model.items == [5, 6]


def test_an_empty_log_gives_an_empty_model_and_an_empty_list():
    model = ListModel.empty()
    applied = replay_collecting(model, [])
    assert applied == []
    assert model.items == []


def test_a_bad_entry_still_raises_replayerror_naming_the_revision():
    model = ListModel.empty()
    with pytest.raises(ReplayError) as caught:
        replay_collecting(model, [_entry(1, Remove(4))])
    assert "main:1" in str(caught.value)


def test_needs_no_live_document_at_all():
    """The whole point: nothing here is a bound method of a ``Document`` -- callable with just a model and
    plain log entries, so a future round could hand exactly this call to a worker process."""
    model = ListModel.empty()
    applied = replay_collecting(model, [_entry(1, Insert(0, 1))])
    assert len(applied) == 1  # no exception, no callback, no Document in sight
