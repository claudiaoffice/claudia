"""``HeavyDispatcher``: watches a document's deferred heavy formula calls and runs the ones it can safely
resolve on a worker pool (PERF review 2026-11-08, D37, D291).

Most tests use a ``FakePool`` -- ``WorkerPool``'s own pickling and process-isolation story is
``test_server_workers.py``'s concern; this file is about the dispatcher's own decisions: which calls it may
resolve, when an answer is stale, when it is not pending any more. One slow test at the end runs the real thing
end to end, to prove the pieces actually fit together, not just in theory.
"""

from __future__ import annotations

import asyncio

from claudia_computes import AddSheet, SetCells, WorkbookModel, parse_input
from claudia_computes.functions.base import Example, UserFunction
from claudia_computes.functions.builtin import builtin_registry
from claudia_computes.functions.range import Range
from claudia_computes.refs import parse_cell_ref
from claudia_core import Document, MemoryStore
from claudia_core.testing import FakeClock
from claudia_server.heavy_dispatch import DEFAULT_TIMEOUT, HeavyDispatcher
from claudia_server.workers import WorkerPool

S1 = "s1"


class COUNT_HEAVY(UserFunction):
    description = "Counts the cells of a range (heavy above 3)"
    examples = (Example("=COUNT_HEAVY(A1:A1)", 1),)
    heavy = True
    heavy_above = 3

    def call(self, values: Range) -> int:
        return len(list(values.present()))


def _registry():
    registry = builtin_registry()
    registry.register(COUNT_HEAVY)
    return registry


def _doc():
    clock = FakeClock()
    d = Document(WorkbookModel(_registry()), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)
    d.execute(AddSheet(S1, "Sheet1"), author="ana")
    return d


def at(address):
    ref = parse_cell_ref(address)
    return ref.row, ref.col


def fill(doc, cells: dict, *, sheet=S1):
    items = tuple((*at(address), parse_input(str(text))) for address, text in cells.items())
    return doc.execute(SetCells(sheet, items), author="ana")


def shown(doc, address, sheet=S1):
    row, col = at(address)
    return doc.model.value(sheet, row, col)


class FakePool:
    """A worker pool stand-in that runs ``fn`` inline -- the dispatcher cannot tell the difference, and the test
    does not pay for a real process. ``answers`` lets a test control what a call returns, or make it hang until
    released, without touching the dispatcher."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.gate: asyncio.Event | None = None  # set to make submit() wait until the test releases it

    async def submit(self, fn, /, *args, **kwargs):
        self.calls.append((fn, args, kwargs))
        if self.gate is not None:
            await self.gate.wait()
        return fn(*args, **kwargs)


def run(coro):
    asyncio.run(coro)


def test_a_bare_heavy_call_is_dispatched_and_its_answer_lands():
    async def scenario():
        doc = _doc()
        pool = FakePool()
        HeavyDispatcher(doc, pool)
        fill(doc, {f"A{r + 1}": r for r in range(5)})
        fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
        await asyncio.sleep(0)  # let the dispatched task run
        assert shown(doc, "B1") == 5
        assert doc.model.calc.pending_heavy == {}

    run(scenario())


def test_a_heavy_call_wrapped_in_more_expression_is_never_dispatched():
    async def scenario():
        doc = _doc()
        pool = FakePool()
        HeavyDispatcher(doc, pool)
        fill(doc, {f"A{r + 1}": r for r in range(5)})
        fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)+1"})
        await asyncio.sleep(0)
        assert pool.calls == []  # never submitted: the dispatcher cannot safely resolve this shape (see module docs)
        key = (S1, *at("B1"))
        assert key in doc.model.calc.pending_heavy  # left deferred, not guessed at

    run(scenario())


def test_a_resolved_calls_readers_are_woken():
    async def scenario():
        doc = _doc()
        pool = FakePool()
        HeavyDispatcher(doc, pool)
        fill(doc, {f"A{r + 1}": r for r in range(5)})
        fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
        fill(doc, {"C1": "=B1*10"})
        await asyncio.sleep(0)
        assert shown(doc, "C1") == 50

    run(scenario())


def test_a_stale_answer_is_discarded_not_applied():
    async def scenario():
        doc = _doc()
        pool = FakePool()
        pool.gate = asyncio.Event()
        HeavyDispatcher(doc, pool)
        fill(doc, {f"A{r + 1}": r for r in range(5)})
        fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
        await asyncio.sleep(0)  # the dispatcher has submitted and is now waiting on the gate
        fill(doc, {"B1": "=1+1"})  # the document moves on while the worker is "still running"
        pool.gate.set()  # let the stale answer come back
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert shown(doc, "B1") == 2  # the new formula's value, untouched by the late answer

    run(scenario())


def test_a_second_submission_for_the_same_cell_is_not_launched_twice():
    async def scenario():
        doc = _doc()
        pool = FakePool()
        pool.gate = asyncio.Event()
        dispatcher = HeavyDispatcher(doc, pool)
        fill(doc, {f"A{r + 1}": r for r in range(5)})
        fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
        await asyncio.sleep(0)
        dispatcher._on_event(None)  # another event fires while the first submission is still in flight
        await asyncio.sleep(0)
        assert len(pool.calls) == 1
        pool.gate.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    run(scenario())


def test_a_call_whose_formula_is_removed_before_it_answers_is_discarded_quietly():
    async def scenario():
        doc = _doc()
        pool = FakePool()
        pool.gate = asyncio.Event()
        HeavyDispatcher(doc, pool)
        fill(doc, {f"A{r + 1}": r for r in range(5)})
        fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
        await asyncio.sleep(0)
        fill(doc, {"B1": ""})  # the formula itself is gone before the worker answers
        pool.gate.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert shown(doc, "B1") is None

    run(scenario())


def test_close_stops_the_dispatcher_from_noticing_further_work():
    async def scenario():
        doc = _doc()
        pool = FakePool()
        dispatcher = HeavyDispatcher(doc, pool)
        dispatcher.close()
        fill(doc, {f"A{r + 1}": r for r in range(5)})
        fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
        await asyncio.sleep(0)
        assert pool.calls == []

    run(scenario())


def test_default_timeout_is_a_positive_number_of_seconds():
    assert DEFAULT_TIMEOUT > 0


# -- the real thing, end to end (slow: spins up actual worker processes) ---------------------------------------
def test_a_bare_heavy_call_resolves_through_a_real_worker_pool():
    async def scenario():
        doc = _doc()
        pool = WorkerPool()
        HeavyDispatcher(doc, pool)
        try:
            fill(doc, {f"A{r + 1}": r for r in range(5)})
            fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
            for _ in range(200):  # the real pool answers on its own schedule: poll briefly instead of one sleep(0)
                if (S1, *at("B1")) not in doc.model.calc.pending_heavy:
                    break
                await asyncio.sleep(0.05)
            assert shown(doc, "B1") == 5
        finally:
            await pool.stop()

    run(scenario())
