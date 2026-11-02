"""Performance guards: how the cost of the hot paths grows with the size of the history.

These are scaling tests, not stopwatches: they compare the same operation on a small and a large log and fail if
the cost grows with the length of the history where it should not. That is robust against slow machines. Whatever
is O(history) by design is named in the docs (opening a document replays it; E4 adds snapshots to bound that).
"""

import time

from claudia_core import CommandLog, Document, Entry, MemoryStore
from claudia_core.testing import Insert, ListModel

SMALL, LARGE = 2_000, 20_000
TOLERATED_GROWTH = 4.0  # 10x more history may cost at most 4x per operation (O(1) would show ~1x)


def build_log(n: int) -> CommandLog:
    log, parent = CommandLog(), None
    for i in range(n):
        rev = log.next_revision()
        # appending (index i) keeps the toy model itself O(1) per command
        log.append(Entry(rev, parent, "ana", "2026-11-02T00:00:00Z", Insert(i, i)))
        parent = rev
    return log


def best_of(repeat: int, fn) -> float:
    best = float("inf")
    for _ in range(repeat):
        started = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - started)
    return best


def grows_with_history(operation, *, rounds: int = 200) -> float:
    """Cost ratio large/small of ``operation(log)``, run ``rounds`` times."""
    costs = []
    for n in (SMALL, LARGE):
        log = build_log(n)
        costs.append(best_of(5, lambda log=log: [operation(log) for _ in range(rounds)]))
    return costs[1] / costs[0]


def test_asking_for_the_latest_entries_does_not_scan_the_history():
    ratio = grows_with_history(lambda log: log.since(log.get(log.head()).parent))
    assert ratio < TOLERATED_GROWTH, f"since() near the head grew {ratio:.1f}x for 10x more history"


def test_membership_and_lookup_are_constant_time():
    def lookups(log):
        head = log.head()
        return log.has(head), log.get(head), log.on_path(head, head)

    ratio = grows_with_history(lookups)
    assert ratio < TOLERATED_GROWTH, f"has/get/on_path grew {ratio:.1f}x for 10x more history"


def test_executing_does_not_slow_down_with_the_length_of_the_history():
    def per_execute(n: int) -> float:
        doc = Document(ListModel(), log=build_log(n), store=MemoryStore())
        doc.model.items = list(range(n))  # the model matches the log without replaying it
        return best_of(3, lambda: [doc.execute(Insert(len(doc.model.items), 0), author="ben") for _ in range(100)])

    ratio = per_execute(LARGE) / per_execute(SMALL)
    assert ratio < TOLERATED_GROWTH, f"execute() grew {ratio:.1f}x for 10x more history"


def test_undoing_the_latest_step_does_not_depend_on_the_history_before_it():
    def per_undo(n: int) -> float:
        log = build_log(n)
        doc = Document.open(ListModel, log, store=MemoryStore())
        for i in range(50):
            doc.execute(Insert(n + i, 1), author="ben")
        return best_of(1, lambda: [doc.undo("ben") for _ in range(50)])

    ratio = per_undo(LARGE) / per_undo(SMALL)
    assert ratio < TOLERATED_GROWTH, f"undo() grew {ratio:.1f}x for 10x more history"


def test_replaying_a_log_is_linear():
    """Opening replays everything (by design until snapshots, E4): twice the history must cost about twice."""

    def open_cost(n: int) -> float:
        log = build_log(n)
        return best_of(3, lambda: Document.open(ListModel, log))

    ratio = open_cost(LARGE) / open_cost(SMALL)
    assert ratio < 10 * 2.5, f"opening grew {ratio:.1f}x for 10x more history (should be about 10x)"
