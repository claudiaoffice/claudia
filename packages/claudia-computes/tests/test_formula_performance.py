"""Performance guards of the formula engine: how the cost of the hot paths grows with the size of the problem.

Scaling tests, not stopwatches: they compare the same operation on a small and a large input and fail when the
cost grows faster than it should, which is robust against slow machines (see the guards of claudia-core).
"""

import time

from claudia_computes import AddSheet, InsertRows, SetCells, Structure, WorkbookModel, parse_input
from claudia_computes.formula import parse_formula
from claudia_core import Document, MemoryStore

S1 = "s1"


def best_of(repeat, fn):
    best = float("inf")
    for _ in range(repeat):
        started = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - started)
    return best


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


def test_calculating_a_long_chain_is_linear():
    def chain(n):
        doc = workbook()
        fill_column(doc, ["=1", *[f"=B{i}+1" for i in range(1, n)]])
        edit = SetCells(S1, ((0, 1, parse_input("=2")),))
        return best_of(3, lambda: doc.execute(edit, author="ana"))

    ratio = chain(10_000) / chain(1_000)
    assert ratio < 25, f"a chain 10x as long took {ratio:.0f}x as long to calculate (linear is about 10)"


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
