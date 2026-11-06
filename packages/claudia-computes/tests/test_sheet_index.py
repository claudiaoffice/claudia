"""Correctness of the sheet's row/column index: ``cells_in`` (a window) and ``extent`` must agree with a full scan
of ``sheet.cells`` at every point, including after the index has grown and shrunk repeatedly (QA review 2026-11-06,
PERF-01, PERF-05). A single populate-then-query test cannot catch an index that drifts out of sync with the cells it
describes — only a cycle that returns to an earlier state and checks the index still agrees can.
"""

import random

from conftest import S1

from claudia_computes import InsertRows, SetCells, Structure, content_of
from claudia_core import Revision


def put(doc, cells, *, author="ana"):
    return doc.execute(SetCells(S1, tuple((r, c, content_of(v)) for r, c, v in cells)), author=author)


def naive_cells_in(sheet, row0, row1, col0, col1):
    """What ``cells_in`` must return: a full scan, the same comparison the old ``_cells`` made."""
    return sorted((r, c) for r, c in sheet.cells if row0 <= r <= row1 and col0 <= c <= col1)


def naive_extent(sheet):
    """What ``extent`` must return: the same two full passes the old ``_extent`` made."""
    rows = max((r for r, _ in sheet.cells), default=-1) + 1
    cols = max((c for _, c in sheet.cells), default=-1) + 1
    return rows, cols


def assert_index_agrees(sheet):
    assert sheet.cells_in(0, 999, 0, 999) == naive_cells_in(sheet, 0, 999, 0, 999)
    assert sheet.extent() == naive_extent(sheet)


def test_an_empty_sheet_has_no_cells_and_zero_extent(doc):
    sheet = doc.model.sheet(S1)
    assert sheet.cells_in(0, 10, 0, 10) == []
    assert sheet.extent() == (0, 0)


def test_a_window_is_sorted_by_row_then_column(doc):
    put(doc, [(5, 5, "far"), (1, 1, "a"), (2, 0, "b"), (1, 0, "c")])
    sheet = doc.model.sheet(S1)
    assert sheet.cells_in(1, 2, 0, 1) == [(1, 0), (1, 1), (2, 0)]


def test_extent_grows_and_shrinks_with_the_boundary_cell(doc):
    sheet = doc.model.sheet(S1)
    put(doc, [(9, 3, "x")])
    assert sheet.extent() == (10, 4)
    put(doc, [(9, 3, None)])  # clearing the single cell that set the boundary
    assert sheet.extent() == (0, 0)


def test_extent_falls_back_to_the_next_largest_cell_when_the_boundary_is_cleared(doc):
    sheet = doc.model.sheet(S1)
    put(doc, [(9, 3, "x"), (4, 1, "y")])
    assert sheet.extent() == (10, 4)
    put(doc, [(9, 3, None)])  # the row-9 boundary goes; row 4 and col 1 are what is left
    assert sheet.extent() == (5, 2)


def test_repeated_edit_and_clear_cycles_never_drift(doc):
    """The index is maintained incrementally on every set and clear (not rebuilt from the cells each time), so this
    is the test that would catch an off-by-one on removal, a row entry left behind empty, or a boundary that doesn't
    fall back correctly: a single populate-then-query pass cannot."""
    sheet = doc.model.sheet(S1)
    rng = random.Random(1)
    live: set[tuple[int, int]] = set()
    for _ in range(40):
        if live and rng.random() < 0.5:
            r, c = rng.choice(sorted(live))
            put(doc, [(r, c, None)])
            live.discard((r, c))
        else:
            r, c = rng.randrange(0, 50), rng.randrange(0, 50)
            put(doc, [(r, c, rng.randint(0, 100))])
            live.add((r, c))
        assert_index_agrees(sheet)


def test_a_structural_edit_still_rebuilds_a_correct_index(doc):
    put(doc, [(0, 0, "a"), (1, 0, "b"), (2, 0, "c")])
    doc.execute(Structure(InsertRows(S1, 1, 1)), author="ana")
    sheet = doc.model.sheet(S1)
    assert_index_agrees(sheet)
    assert sheet.cells_in(0, 10, 0, 10) == [(0, 0), (2, 0), (3, 0)]


def test_reopening_from_a_snapshot_rebuilds_a_correct_index(doc):
    put(doc, [(9, 3, "x"), (4, 1, "y")])
    put(doc, [(4, 1, "")])
    from claudia_computes import WorkbookModel

    model = WorkbookModel.restore(doc.model.serialize())
    sheet = model.sheet(S1)
    assert_index_agrees(sheet)
    assert sheet.extent() == (10, 4)


def test_undo_after_clearing_restores_the_index(doc):
    put(doc, [(9, 3, "x")])
    rev = put(doc, [(9, 3, None), (0, 0, "y")]).revision
    assert isinstance(rev, Revision)
    doc.undo("ana")
    sheet = doc.model.sheet(S1)
    assert_index_agrees(sheet)
    assert sheet.extent() == (10, 4)
