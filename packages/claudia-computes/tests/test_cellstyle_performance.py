"""Performance guards for cell styles (E6.13, D307): a million styled cells are a few thousand ranges, and what the
grid asks of them — one window, a row inserted, a snapshot — must cost what the ranges cost, never the cells.

Scaling tests, not stopwatches (see test_formula_performance.py): ten times the ranges may cost about ten times as
much (the work is linear in the ranges by design, kept small by the bound on them), and ten times the *cells* in
the same number of ranges must cost the same.
"""

from test_formula_performance import best_of

from claudia_computes import CellStyles, InsertRows
from claudia_computes.limits import MAX_COLS, MAX_ROWS

LINEAR = 25.0  # 10x the ranges: linear work shows near 10x; allow for noise without letting quadratic (100x) through
FLAT = 3.0  # 10x the cells in the same ranges: should cost the same


def styled(ranges: int, height: int) -> CellStyles:
    """``ranges`` ranges of ``height`` rows by 10 columns, stacked down the sheet, in both slots of a cell."""
    made = CellStyles()
    for slot in ("box", "words"):
        pieces = [((i * height, 0, i * height + height - 1, 9), "header" if i % 2 else "note") for i in range(ranges)]
        made.replace(slot, "range", (0, 0, ranges * height - 1, 9), pieces)
    made.replace("words", "column", (0, 12, MAX_ROWS - 1, 12), [((0, 12, MAX_ROWS - 1, 12), "input")])
    made.replace("box", "row", (5, 0, 5, MAX_COLS - 1), [((5, 0, 5, MAX_COLS - 1), "result")])
    return made


def test_a_million_styled_cells_are_a_few_thousand_ranges():
    made = styled(5_000, 20)  # 5,000 ranges of 200 cells, in two slots: a million cells
    assert len(made) == 10_002
    assert made.style_at(99_999, 9, "words") == ("header", "range")


def test_the_window_the_grid_asks_for_costs_the_ranges_not_the_cells():
    def window(cells_per_range):
        made = styled(2_000, cells_per_range)
        return best_of(5, lambda: made.ranges_in((40_000, 0, 40_060, 30)))

    ratio = window(200) / window(20)
    assert ratio < FLAT, f"10x the cells in the same ranges made a window {ratio:.1f}x as dear"


def test_inserting_a_row_and_a_snapshot_grow_with_the_ranges_no_faster():
    def work(ranges):
        made = styled(ranges, 20)
        return best_of(3, lambda: (made.restructure(InsertRows("s1", 10, 1)), CellStyles.from_data(made.to_data())))

    ratio = work(5_000) / work(500)
    assert ratio < LINEAR, f"10x the ranges made a row insert and a snapshot {ratio:.1f}x as dear"
