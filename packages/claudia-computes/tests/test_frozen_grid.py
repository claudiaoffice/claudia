"""``freeze``/``FrozenGrid``: the minimal, picklable copy of a ``Range``'s footprint that crosses a process
boundary for a deferred heavy call to run on -- never the live ``Sheet`` itself (D37, D177).
"""

from __future__ import annotations

import pickle

from formula_helpers import FakeSheet

from claudia_computes.functions.range import FrozenGrid, Range, freeze


def test_a_frozen_grid_holds_only_the_cells_inside_the_footprint():
    sheet = FakeSheet({"A1": 1, "A2": 2, "B1": "outside the range"})
    frozen = FrozenGrid.of(sheet, 0, 0, 1, 0)  # A1:A2
    assert frozen.grid == {(0, 0): 1, (1, 0): 2}


def test_a_frozen_grid_clips_to_the_sheets_own_extent():
    sheet = FakeSheet({"A1": 1})  # rows_used = 1
    frozen = FrozenGrid.of(sheet, 0, 0, 999, 0)  # A1:A1000, far past the sheet's extent
    assert frozen.grid == {(0, 0): 1}
    assert frozen.rows_used == sheet.rows_used


def test_freezing_a_range_argument_replaces_its_sheet_with_a_frozen_grid():
    sheet = FakeSheet({"A1": 1, "A2": 2})
    live = Range(sheet, 0, 0, 1, 0, sheet_id="s1")
    frozen = freeze(live)
    assert isinstance(frozen.sheet, FrozenGrid)
    assert sorted(frozen.present()) == [1, 2]
    assert frozen.sheet_id == "s1"
    assert (frozen.row0, frozen.col0, frozen.row1, frozen.col1) == (0, 0, 1, 0)


def test_freezing_a_range_is_independent_of_later_changes_to_the_live_sheet():
    sheet = FakeSheet({"A1": 1})
    live = Range(sheet, 0, 0, 0, 0)
    frozen = freeze(live)
    sheet.set("A1", 999)  # the sheet keeps changing after the snapshot was taken
    assert list(frozen.present()) == [1]
    assert list(live.present()) == [999]  # (the live range still follows the live sheet, as it must)


def test_freezing_a_non_range_value_passes_it_through_unchanged():
    assert freeze(42) is 42  # noqa: F632 (identity is the point: nothing was copied)
    assert freeze(None) is None
    assert freeze("text") == "text"


def test_a_frozen_range_pickles_for_a_worker_process():
    sheet = FakeSheet({"A1": 1, "A2": 2})
    frozen = freeze(Range(sheet, 0, 0, 1, 0, sheet_id="s1"))
    restored = pickle.loads(pickle.dumps(frozen))
    assert sorted(restored.present()) == [1, 2]
