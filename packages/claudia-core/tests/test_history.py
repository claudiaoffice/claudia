"""E1.4: undo and redo of one's own steps only."""

import random

import pytest
from helpers import histories_of, random_session, try_step

from claudia_core import Batch, CommandLog, Document, UndoConflict, UndoRefused
from claudia_core.testing import Insert, Interval, ListModel, Replace


def test_undo_is_a_new_command_not_a_rewind(doc):
    doc.execute(Insert(0, 1), author="ana")
    doc.execute(Insert(1, 2), author="ana")
    applied = doc.undo("ana")
    assert doc.model.items == [1]
    assert str(applied.revision) == "main:3" and doc.log.get(applied.revision).origin == "undo"
    assert str(doc.log.get(applied.revision).of) == "main:2"
    assert doc.redo("ana") is not None and doc.model.items == [1, 2]


def test_each_author_has_their_own_stack(doc):
    doc.execute(Insert(0, 10), author="ana")
    doc.execute(Insert(1, 20), author="ben")
    assert doc.undo("ana").entry.author == "ana"
    assert doc.model.items == [19 + 1]  # ben's 20 survives, ana's 10 is gone
    assert doc.undo("ana") is None
    assert doc.history_for("ben").undo_label == "Insert 20"


def test_undo_label_and_events(doc):
    seen = []
    doc.subscribe(lambda e: seen.append(e) if type(e).__name__ == "HistoryChanged" else None)
    doc.execute(Insert(0, 7), author="ana")
    assert seen[-1].author == "ana" and seen[-1].can_undo and seen[-1].undo_label == "Insert 7"
    doc.undo("ana")
    assert not seen[-1].can_undo and seen[-1].can_redo and seen[-1].redo_label == "Insert 7"


def test_a_new_edit_clears_the_redo_stack(doc):
    doc.execute(Insert(0, 1), author="ana")
    doc.undo("ana")
    doc.execute(Insert(0, 2), author="ana")
    assert not doc.history_for("ana").can_redo


def test_a_batch_is_one_undo_step(doc):
    doc.execute(Batch((Insert(0, 1), Insert(1, 2), Insert(2, 3)), "three"), author="ana")
    doc.undo("ana")
    assert doc.model.items == []


def test_undo_shifts_through_colleagues_edits(doc):
    doc.execute(Insert(0, 10), author="ana")
    doc.execute(Insert(0, 20), author="ben")  # ana's value is now at index 1
    doc.undo("ana")
    assert doc.model.items == [20]  # not [10]: the inverse followed the element


def test_undo_never_overwrites_a_colleagues_work(doc):
    doc.execute(Insert(0, 10), author="ana")
    doc.execute(Replace(0, 11), author="ben")
    with pytest.raises(UndoConflict) as caught:
        doc.undo("ana")
    assert "ben" in str(caught.value) and doc.model.items == [11]
    assert doc.history_for("ana").can_undo  # still there, nothing was consumed


def test_undo_is_refused_when_someone_holds_the_region(doc, clock):
    doc.execute(Insert(0, 10), author="ana")
    doc.lock("ben", [Interval(0, 1)], ttl=5)
    with pytest.raises(UndoRefused) as caught:
        doc.undo("ana")
    assert "ben" in str(caught.value) and doc.model.items == [10]
    clock.advance(6)  # the lock timed out
    doc.undo("ana")
    assert doc.model.items == []


def test_a_lock_elsewhere_does_not_block_undo(doc):
    doc.execute(Insert(0, 10), author="ana")
    doc.lock("ben", [Interval(5, 6)], ttl=5)
    assert doc.undo("ana") is not None


def test_failed_undo_consumes_nothing(doc):
    doc.execute(Insert(0, 1), author="ana")
    # sabotage: ana's inverse no longer fits although nobody "else" touched it (a bug in a model, say)
    doc.model.items.clear()
    with pytest.raises(UndoConflict):
        doc.undo("ana")
    assert doc.history_for("ana").can_undo and not doc.history_for("ana").can_redo


@pytest.mark.parametrize("seed", range(12))
def test_random_undo_redo_replays_identically(make_doc, seed):
    doc = random_session(make_doc(), seed, steps=300)
    again = Document.open(ListModel, CommandLog.from_data(doc.log.to_data(), ListModel.registry))  # its own copy
    assert again.model.serialize() == doc.model.serialize()
    assert histories_of(again) == histories_of(doc)
    # and the rebuilt stacks really work: undo everything everybody can, on both documents, identically
    for who in ("ana", "ben", "ai"):
        while True:
            a = try_step(doc.undo, who)
            b = try_step(again.undo, who)
            assert (a is None) == (b is None)
            if a is None:
                break
    assert again.model.serialize() == doc.model.serialize()


@pytest.mark.parametrize("seed", range(10))
def test_undo_only_removes_what_the_author_inserted(make_doc, seed):
    """With unique values: an undo may remove or restore the author's own values, nobody else's."""
    doc = make_doc()
    rng = random.Random(seed)
    owner, counter = {}, 0
    for _ in range(250):
        who = rng.choice(["ana", "ben"])
        roll = rng.random()
        if roll < 0.6:
            counter += 1
            owner[counter] = who
            doc.execute(Insert(rng.randint(0, len(doc.model.items)), counter), author=who)
        else:
            before = set(doc.model.items)
            if try_step(doc.undo if roll < 0.85 else doc.redo, who) is not None:
                after = set(doc.model.items)
                assert {owner[v] for v in before ^ after} <= {who}
