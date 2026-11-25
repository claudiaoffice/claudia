"""Performance guards: how the cost of the hot paths grows with the size of the history.

These are scaling tests, not stopwatches: they compare the same operation on a small and a large log and fail if
the cost grows with the length of the history where it should not. The work is counted (``work_of``: the same on
every machine, PERF-14, D1661); only the lookups, whose cost would hide in C (``in`` on a list), are timed.
Whatever is O(history) by design is named in the docs (opening a document replays it; E4 adds snapshots to bound
that).
"""

from claudia_core import CommandLog, Document, MemoryStore, Step
from claudia_core.testing import Insert, ListModel, best_of, work_of

SMALL, LARGE = 2_000, 20_000
TOLERATED_GROWTH = 4.0  # 10x more history may cost at most 4x per operation (O(1) would show ~1x)
BACKSTOP = 3.0
"""The log keeps its steps in lists, and a slice of one is work done in C, which counting does not see (a copy of the
history per call would count as nothing). So each counted guard is backed by the clock as well, with three times its
room: enough for a loaded machine, too little for work that grows with the whole history (PERF-14, D1661)."""


def timed(fn) -> float:
    return best_of(3, fn)


def do_and_undo(n: int) -> float:
    """The processor time of 50 steps, each made and undone, on a history of ``n``: a measure that leaves the document
    as it found it, so that it can be repeated as often as :func:`best_of` likes."""
    doc = Document.open(ListModel, build_log(n), store=MemoryStore())
    return timed(lambda: [(doc.execute(Insert(n, 1), author="ben"), doc.undo("ben")) for _ in range(50)])


def backstop() -> float:
    return do_and_undo(LARGE) / do_and_undo(SMALL)


def build_log(n: int) -> CommandLog:
    log, parent = CommandLog(), None
    for i in range(n):
        rev = log.next_revision()
        # appending (index i) keeps the toy model itself O(1) per command
        log.append(Step(rev, parent, "ana", "2026-11-02T00:00:00Z", Insert(i, i)))
        parent = rev
    return log


def grows_with_history(operation, *, rounds: int = 200, measure=work_of) -> float:
    """Cost ratio large/small of ``operation(log)``, run ``rounds`` times, as ``measure`` (counted work by default)."""
    costs = []
    for n in (SMALL, LARGE):
        log = build_log(n)
        costs.append(measure(lambda log=log: [operation(log) for _ in range(rounds)]))
    return costs[1] / costs[0]


def test_asking_for_the_latest_entries_does_not_scan_the_history():
    def latest(log):
        return log.since(log.get(log.head()).parent)

    ratio = grows_with_history(latest)
    assert ratio < TOLERATED_GROWTH, f"since() near the head grew {ratio:.1f}x for 10x more history"
    assert grows_with_history(latest, measure=timed) < TOLERATED_GROWTH * BACKSTOP, "since() copies the history"


def test_membership_and_lookup_are_constant_time():
    def lookups(log):
        head = log.head()
        return log.has(head), log.get(head), log.on_path(head, head)

    ratio = grows_with_history(lookups, measure=lambda fn: best_of(5, fn))  # timed: a regression would be in C
    assert ratio < TOLERATED_GROWTH, f"has/get/on_path grew {ratio:.1f}x for 10x more history"


def test_executing_does_not_slow_down_with_the_length_of_the_history():
    def per_execute(n: int) -> int:
        doc = Document(ListModel(), log=build_log(n), store=MemoryStore())
        doc.model.items = list(range(n))  # the model matches the log without replaying it
        return work_of(lambda: [doc.execute(Insert(len(doc.model.items), 0), author="ben") for _ in range(100)])

    ratio = per_execute(LARGE) / per_execute(SMALL)
    assert ratio < TOLERATED_GROWTH, f"execute() grew {ratio:.1f}x for 10x more history"
    timed_ratio = backstop()
    assert timed_ratio < TOLERATED_GROWTH * BACKSTOP, f"a step took {timed_ratio:.1f}x as long: work in C grew"


def test_undoing_the_latest_step_does_not_depend_on_the_history_before_it():
    def per_undo(n: int) -> int:
        # counted: one timed sample failed now and then at 4.04x on a loaded machine (QA 2026-11-12, PROC-07)
        doc = Document.open(ListModel, build_log(n), store=MemoryStore())
        for i in range(50):
            doc.execute(Insert(n + i, 1), author="ben")
        return work_of(lambda: [doc.undo("ben") for _ in range(50)])

    ratio = per_undo(LARGE) / per_undo(SMALL)
    assert ratio < TOLERATED_GROWTH, f"undo() grew {ratio:.1f}x for 10x more history"
    timed_ratio = backstop()
    assert timed_ratio < TOLERATED_GROWTH * BACKSTOP, f"an undo took {timed_ratio:.1f}x as long: work in C grew"


def test_replaying_a_log_is_linear():
    """Opening replays everything (by design until snapshots, E4): twice the history must cost about twice."""

    def open_cost(n: int, measure=work_of) -> float:
        log = build_log(n)
        return measure(lambda: Document.open(ListModel, log))

    ratio = open_cost(LARGE) / open_cost(SMALL)
    assert ratio < 10 * 2.5, f"opening grew {ratio:.1f}x for 10x more history (should be about 10x)"
    timed_ratio = open_cost(LARGE, timed) / open_cost(SMALL, timed)
    assert timed_ratio < 10 * 2.5 * BACKSTOP, f"opening took {timed_ratio:.1f}x as long: work in C grew"
