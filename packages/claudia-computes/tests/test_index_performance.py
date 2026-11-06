"""Performance guards for the sheet index: a grid window and the sheet extent must cost what their answer costs,
not what the sheet holds (QA review 2026-11-06, PERF-01, PERF-05). Before the index, both scaled with every cell on
the sheet: a 64x16 window cost 21.08 ms and the extent 37.97 ms at 500k cells, against 0.12 ms and 0.06 ms at 1k.

Scaling tests, not stopwatches: see test_formula_performance.py. The tolerance here is tighter than the "roughly
linear is fine" guards elsewhere (4x) because these two are meant to be flat, not merely sub-linear.
"""

from test_formula_performance import best_of

from claudia_computes import AddSheet, SetCells, WorkbookModel, parse_input
from claudia_core import Document, MemoryStore

S1 = "s1"
FLAT = 3.0  # 50x more cells may cost at most 3x per call; O(1)/O(log n) shows close to 1x


def filled_sheet(n, *, row_width=20):
    """``n`` cells spread across many rows (not one dense block), ``row_width`` of them per row, so a full scan has
    all ``n`` to look at — the same shape the QA measurements used. ``row_width`` stays fixed as ``n`` grows, so a
    window near the start sees the same density whatever the sheet's total size."""
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet(S1, "Sheet1"), author="ana")
    cells = tuple((i // row_width, i % row_width, parse_input(str(i))) for i in range(n))
    doc.execute(SetCells(S1, cells), author="ana")
    return doc.model.sheet(S1)


def test_a_grid_window_costs_what_the_window_costs_not_the_sheet():
    def windows(n):
        sheet = filled_sheet(n)
        # stays inside the first 450 rows, which are populated whether the sheet holds 10k cells or 500k
        return best_of(5, lambda: [sheet.cells_in(r, r + 63, 0, 15) for r in range(0, 400, 64)])

    ratio = windows(500_000) / windows(10_000)
    assert ratio < FLAT, f"a 64x16 window cost {ratio:.1f}x as much with 50x more cells on the sheet"


def test_the_sheet_extent_costs_what_it_costs_not_the_sheet():
    def extents(n):
        sheet = filled_sheet(n)
        return best_of(5, lambda: [sheet.extent() for _ in range(1_000)])

    ratio = extents(500_000) / extents(10_000)
    assert ratio < FLAT, f"the sheet extent cost {ratio:.1f}x as much with 50x more cells on the sheet"
