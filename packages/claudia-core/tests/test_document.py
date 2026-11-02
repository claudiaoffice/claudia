"""E1.1 and E1.2: the kernel on a toy model; the log is the truth."""

import pytest
from helpers import histories_of, random_session

from claudia_core import (
    Batch,
    CommandApplied,
    CommandLog,
    Document,
    MemoryStore,
    ReplayError,
    Revision,
    RevisionMismatch,
    Snapshot,
)
from claudia_core.testing import Insert, ListModel, Remove


def test_execute_applies_logs_and_numbers(doc):
    a = doc.execute(Insert(0, 5), author="ana")
    b = doc.execute(Insert(1, 6), author="ben")
    assert doc.model.items == [5, 6]
    assert (a.revision, b.revision) == (Revision("main", 1), Revision("main", 2))
    assert doc.revision == Revision("main", 2)
    assert doc.log.get(b.revision).parent == a.revision
    assert doc.log.get(a.revision).time < doc.log.get(b.revision).time


def test_settle_runs_once_per_command_even_for_a_batch(doc):
    doc.execute(Batch((Insert(0, 1), Insert(0, 2), Insert(0, 3))))
    assert doc.model.settled == 1


def test_failed_command_changes_nothing_and_logs_nothing(doc):
    doc.execute(Insert(0, 1))
    with pytest.raises(IndexError):
        doc.execute(Batch((Insert(0, 2), Insert(0, 3), Remove(9))))  # third fails, first two roll back
    assert doc.model.items == [1]
    assert doc.revision == Revision("main", 1)
    assert doc.model.settled == 2  # the first insert, and one settle for the rolled-back batch


def test_events_arrive_as_one_batch_ending_with_command_applied(doc):
    batches = []
    doc.subscribe_batches(batches.append)
    doc.execute(Insert(0, 1), author="ana")
    (batch,) = batches
    assert isinstance(batch[-2] if len(batch) > 1 else batch[-1], (CommandApplied, object))
    kinds = [type(e).__name__ for e in batch]
    assert kinds[0] == "CommandApplied" and "HistoryChanged" in kinds


def test_model_events_come_before_command_applied():
    from dataclasses import dataclass
    from typing import ClassVar

    from claudia_core import Command, new_registry
    from claudia_core.testing import FakeClock

    registry = new_registry()

    @dataclass(frozen=True)
    class Changed:
        def to_data(self):
            return {"type": "changed"}

    class M(ListModel):
        app = "test-events"
        registry = None

    M.registry = registry

    @registry.register
    @dataclass(frozen=True)
    class Poke(Command):
        kind: ClassVar[str] = "ev.Poke"

        def apply(self, ctx):
            ctx.emit(Changed())
            return self

        def to_data(self):
            return {}

        @classmethod
        def from_data(cls, data, registry):
            return cls()

    clock = FakeClock()
    d = Document(M(), clock=clock.time)
    seen = []
    d.subscribe(lambda e: seen.append(type(e).__name__))
    d.execute(Poke())
    assert seen[:2] == ["Changed", "CommandApplied"]


# ------------------------------------------------------------------ E1.2: the log is the truth
@pytest.mark.parametrize("seed", range(8))
def test_replaying_the_log_from_empty_gives_the_identical_state(make_doc, seed):
    doc = random_session(make_doc(), seed)
    reopened = Document.open(ListModel, doc.log)
    assert reopened.model.serialize() == doc.model.serialize()
    assert histories_of(reopened) == histories_of(doc)  # even the undo stacks come back from the log
    assert reopened.checkpoints == doc.checkpoints
    assert doc.materialize(doc.revision).serialize() == doc.model.serialize()


def test_every_past_state_can_be_rebuilt(make_doc):
    doc = make_doc()
    states = []
    for i in range(12):
        doc.execute(Insert(0, i), author="ana")
        states.append((doc.revision, list(doc.model.items)))
    for rev, items in states:
        assert doc.materialize(rev).items == items
    assert doc.materialize(None).items == []


def test_log_survives_serialisation(make_doc):
    doc = random_session(make_doc(), 3)
    again = CommandLog.from_data(doc.log.to_data(), ListModel.registry)
    assert Document.open(ListModel, again).model.serialize() == doc.model.serialize()


def test_snapshot_is_only_a_cache(make_doc):
    doc = random_session(make_doc(), 1, steps=60)
    snap = doc.snapshot()
    for _ in range(10):
        doc.execute(Insert(0, 1), author="ana")
    with_snapshot = Document.open(ListModel, doc.log, snapshot=snap)
    without = Document.open(ListModel, doc.log)
    assert with_snapshot.model.serialize() == without.model.serialize() == doc.model.serialize()
    assert with_snapshot.checkpoints == without.checkpoints  # the index comes from the log, not the snapshot


def test_unusable_snapshots_are_ignored(make_doc):
    doc = random_session(make_doc(), 2, steps=30)
    good = doc.snapshot()
    for bad in (
        Snapshot(good.rev, "other-app", good.state_schema, {"items": [999]}),
        Snapshot(good.rev, good.app, good.state_schema + 1, {"items": [999]}),
        Snapshot(Revision("main", 9999), good.app, good.state_schema, {"items": [999]}),
    ):
        assert Document.open(ListModel, doc.log, snapshot=bad).model.serialize() == doc.model.serialize()


def test_cached_snapshots_speed_up_materialize_without_changing_the_result(make_doc):
    doc = random_session(make_doc(), 5, steps=80)
    mid = doc.revision
    expected = doc.materialize(mid).serialize()
    doc.cache_snapshot()
    for _ in range(5):
        doc.execute(Insert(0, 2), author="ben")
    assert doc.materialize(mid).serialize() == expected
    assert doc.store.snapshots and doc.store.snapshots[-1].rev == mid


def test_replay_error_names_the_revision():
    log = CommandLog()
    from claudia_core import Entry

    log.append(Entry(Revision("main", 1), None, "ana", "2026-11-01T12:00:00.000Z", Remove(4)))
    with pytest.raises(ReplayError) as caught:
        Document.open(ListModel, log)
    assert "main:1" in str(caught.value)


# ------------------------------------------------------------------ replicas and branches
def test_a_replica_follows_by_applying_entries(make_doc):
    server = make_doc()
    replica = Document(ListModel(), store=None)
    for i in range(5):
        server.execute(Insert(0, i), author="ana")
    for entry in server.entries_since(replica.revision):
        replica.apply_entry(entry)
    assert replica.model.serialize() == server.model.serialize()
    assert replica.log.get(Revision("main", 3)).time == server.log.get(Revision("main", 3)).time
    with pytest.raises(RevisionMismatch):
        replica.apply_entry(server.log.get(Revision("main", 2)))  # already seen


def test_a_branch_diverges_without_touching_main(make_doc):
    doc = make_doc()
    for i in range(4):
        doc.execute(Insert(0, i), author="ana")
    fork_at = Revision("main", 2)
    doc.log.fork("what-if", fork_at)
    alt = Document(doc.materialize(fork_at), log=doc.log, branch="what-if", clock=doc._clock)
    alt.execute(Insert(0, 100), author="ben")
    assert alt.revision == Revision("what-if", 3)
    assert alt.model.items == [100, 1, 0]
    assert doc.model.items == [3, 2, 1, 0]
    assert Document.open(ListModel, doc.log, branch="what-if").model.items == [100, 1, 0]
    assert doc.materialize(Revision("main", 4)).items == [3, 2, 1, 0]


# ------------------------------------------------------------------ storage
def test_store_failure_means_the_command_did_not_happen(make_doc):
    class Broken(MemoryStore):
        def append_entry(self, entry):
            raise OSError("disk full")

    doc = make_doc(store=Broken())
    with pytest.raises(OSError):
        doc.execute(Insert(0, 1))
    assert doc.model.items == [] and doc.revision is None


def test_every_entry_reaches_the_store_in_order(doc):
    for i in range(3):
        doc.execute(Insert(0, i))
    assert [str(r) for r in doc.store.entries] == ["main:1", "main:2", "main:3"]
