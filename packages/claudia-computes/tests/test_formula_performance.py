"""Performance guards of the formula engine: how the cost of the hot paths grows with the size of the problem.

Scaling tests, not stopwatches: they compare the same operation on a small and a large input and fail when the
cost grows faster than it should, which is robust against slow machines (see the guards of claudia-core). Where the
time itself still depends on the machine (memory caches), the work is counted instead (:func:`work_of`, PROC-61).
"""

import gc
import sys
import time

from claudia_computes import AddSheet, InsertRows, SetCells, Structure, WorkbookModel, parse_input
from claudia_computes.calc import Round, Waiting
from claudia_computes.formula import parse_formula
from claudia_core import Document, MemoryStore

S1 = "s1"


def best_of(repeat, fn):
    """The fastest of ``repeat`` runs of ``fn``, with the cyclic garbage collector held off while they run.

    A collection is triggered by how much has been allocated, not by the work being measured, so it lands in the
    large case far more often than in the small one and reads as super-linear cost: reopening 8,000 formulas
    measured 20-25x the time of 800 with it on, and 11x with it off (the guard's bound is 25x). ``timeit`` turns
    it off for the same reason.
    """
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        best = float("inf")
        for _ in range(repeat):
            started = time.perf_counter()
            fn()
            best = min(best, time.perf_counter() - started)
        return best
    finally:
        if was_enabled:
            gc.enable()


def work_of(fn):
    """How much Python ``fn`` runs: the lines it starts and the turns of its loops, a one-line comprehension's too.
    The same on every machine and on every run, however busy the machine is or how big its caches are. It does not
    see work done inside C (``x in a_list``, a list shifted by ``del``): a guard that must see that measures time."""
    monitoring = sys.monitoring
    tool = next(tool for tool in range(6) if monitoring.get_tool(tool) is None)  # (coverage may hold one)
    monitoring.use_tool_id(tool, "work_of")
    count = 0

    def counted(*_event):
        nonlocal count
        count += 1

    events = monitoring.events.LINE | monitoring.events.JUMP
    try:
        monitoring.register_callback(tool, monitoring.events.LINE, counted)
        monitoring.register_callback(tool, monitoring.events.JUMP, counted)
        monitoring.set_events(tool, events)
        fn()
    finally:
        monitoring.set_events(tool, 0)
        monitoring.free_tool_id(tool)
    return count


def workbook():
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet(S1, "Sheet1"), author="ana")
    return doc


def fill_column(doc, formulas):
    cells = tuple((i, 1, parse_input(text)) for i, text in enumerate(formulas))
    doc.execute(SetCells(S1, cells), author="ana")


def test_reading_a_formula_costs_what_its_length_costs():
    def parse_all(terms):
        text = "=" + "+".join(f"A{i % 90 + 1}*2" for i in range(terms))
        return best_of(5, lambda: [parse_formula(text) for _ in range(10)])

    ratio = parse_all(1000) / parse_all(100)
    assert ratio < 25, f"parsing 10x more formula took {ratio:.0f}x as long (linear is about 10)"


def test_one_edit_costs_the_same_in_a_small_and_a_large_workbook():
    def per_edit(n):
        doc = workbook()
        doc.execute(SetCells(S1, tuple((i, 0, parse_input(str(i))) for i in range(n))), author="ana")
        fill_column(doc, [f"=A{i + 1}*2" for i in range(n)])
        edits = [SetCells(S1, ((0, 0, parse_input(str(k))),)) for k in range(100, 160)]
        return best_of(3, lambda: [doc.execute(edit, author="ana") for edit in edits])

    ratio = per_edit(10_000) / per_edit(1_000)
    assert ratio < 4, f"one edit cost {ratio:.1f}x as much with 10x more formulas (they do not depend on it)"


#: How much more work a chain 10x as long may cost. Linear is 10 (measured: 9.96); a sort of the chain would make it
#: about 13 (n log n); a formula that looks at every waiting one makes it 49 already for 200 and 2,000 formulas. It is
#: counted, so no room is left for a slow or busy machine.
CHAIN_BOUND = 15


def chain_growth(small, large):
    """How much more work it is to calculate a chain of ``large`` formulas than one of ``small``, each reading the one
    above it, after its first cell changed."""

    def chain(n):
        doc = workbook()
        fill_column(doc, ["=1", *[f"=B{i}+1" for i in range(1, n)]])
        edit = SetCells(S1, ((0, 1, parse_input("=2")),))
        return work_of(lambda: doc.execute(edit, author="ana"))

    return chain(large) / chain(small)


def test_calculating_a_long_chain_is_linear():
    growth = chain_growth(1_000, 10_000)
    assert growth < CHAIN_BOUND, f"a chain 10x as long took {growth:.1f}x the work to calculate (linear is about 10)"


def test_letting_formulas_go_one_by_one_in_order_is_linear():
    """PERF-13: a chain is calculated from its top, and each formula done was deleted from the front of its column's
    sorted list, which shifts all the rest: quadratic, in C, where counting does not see it. On CI's runner a chain 10x
    as long took 44x as long (PROC-61). Measured with a clock, on lists long enough that a shift per formula costs far
    more than the bound lets through (about 100x against 10x)."""

    def let_go(n):
        keys = [(S1, row, 1) for row in range(n)]

        def run():
            waiting = Waiting(keys)
            for key in keys:
                waiting.done(key)

        return best_of(3, run)

    ratio = let_go(50_000) / let_go(5_000)
    assert ratio < 25, f"letting go of 10x as many formulas took {ratio:.0f}x as long (linear is about 10)"


def test_the_formulas_still_waiting_are_found_after_others_were_let_go():
    keys = [(S1, row, col) for col in (1, 2) for row in range(10)]
    waiting = Waiting(keys)
    for row in (0, 1, 2, 5, 9):
        waiting.done((S1, row, 1))
    assert waiting.inside((S1, 0, 1, 9, 1)) == [(S1, row, 1) for row in (3, 4, 6, 7, 8)]
    for row in (3, 4, 6, 7, 8):
        waiting.done((S1, row, 1))
    assert waiting.inside((S1, 0, 0, 9, 2)) == [(S1, row, 2) for row in range(10)]
    assert waiting.keys == {(S1, row, 2) for row in range(10)}


def quadratic_precedents(self, key):
    """A stand-in for ``Round._precedents`` that looks at every waiting formula to find the ones this one names."""
    named = set(self.calc.formulas[key].cells)
    return [other for other in self.waiting.keys if other in named]


def test_the_chain_guard_catches_a_calculation_that_is_quadratic_in_the_chain(monkeypatch):
    monkeypatch.setattr(Round, "_precedents", quadratic_precedents)
    assert chain_growth(200, 2_000) >= CHAIN_BOUND


def test_the_chain_guard_does_not_read_the_clock(monkeypatch):
    """PROC-61: on CI's runner a chain 10x as long took 44x as long, twice, and the rerun passed; here it takes 14x
    to 16x. A stopwatch measures the machine as well as the calculation. Counted work is the same on every machine."""

    def stopwatch():
        raise AssertionError("the guard read the clock")

    monkeypatch.setattr(time, "perf_counter", stopwatch)
    assert chain_growth(100, 1_000) < CHAIN_BOUND


def test_opening_from_a_snapshot_is_linear_in_the_formulas():
    def reopen(n):
        doc = workbook()
        doc.execute(SetCells(S1, tuple((i, 0, parse_input(str(i))) for i in range(n))), author="ana")
        fill_column(doc, [f"=A{i + 1}+B{max(i, 1)}" for i in range(n)])
        state = doc.model.serialize()
        return best_of(3, lambda: WorkbookModel.restore(state))

    ratio = reopen(8_000) / reopen(800)
    assert ratio < 25, f"10x more formulas took {ratio:.0f}x as long to open (linear is about 10)"


def test_one_edit_does_not_look_at_every_range_in_its_column():
    def per_edit(n):
        doc = workbook()
        doc.execute(SetCells(S1, tuple((i, 0, parse_input(str(i))) for i in range(n + 10))), author="ana")
        fill_column(doc, [f"=SUM(A{i + 1}:A{i + 10})" for i in range(n)])  # a window of ten rows for every row
        edits = [SetCells(S1, ((5, 0, parse_input(str(k))),)) for k in range(100, 160)]
        return best_of(3, lambda: [doc.execute(edit, author="ana") for edit in edits])

    ratio = per_edit(20_000) / per_edit(2_000)
    assert ratio < 4, f"one edit cost {ratio:.1f}x as much with 10x more ranges in its column (only 10 read the cell)"


def test_a_structural_edit_is_linear_in_the_formulas():
    def insert(n):
        def build():
            doc = workbook()
            doc.execute(SetCells(S1, tuple((i, 0, parse_input(str(i))) for i in range(n))), author="ana")
            fill_column(doc, [f"=A{i + 1}*2" for i in range(n)])
            return doc

        docs = [build() for _ in range(3)]
        return best_of(3, lambda: docs.pop().execute(Structure(InsertRows(S1, 0, 1)), author="ana"))

    ratio = insert(5_000) / insert(500)
    assert ratio < 25, f"10x more formulas took {ratio:.0f}x as long to insert a row (linear is about 10)"


def test_a_scratch_copy_costs_the_size_of_the_workbook_not_the_length_of_its_history():
    """E7.8: previewing an AI proposal copies the current state; 40x more edits on the same cells must not show."""

    def scratch_time(edits):
        doc = workbook()
        fill_column(doc, [f"=A{i % 90 + 1}*2" for i in range(3000)])
        for k in range(edits):
            doc.execute(SetCells(S1, ((k % 90, 0, parse_input(str(k))),)), author="ana")
        return best_of(3, doc.scratch)

    ratio = scratch_time(2000) / scratch_time(50)
    assert ratio < 3, f"a copy after 2,000 edits took {ratio:.1f}x as long as after 50 (it should not depend on them)"
