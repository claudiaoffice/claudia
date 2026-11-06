"""Row heights and column widths: sheet layout (D135), not a cell style (E6.13's open point) — a sparse per-line
override that moves with structural edits and undoes exactly, the same way cell content does."""

import pytest
from conftest import S1, reopen

from claudia_computes import CellRegion, RemoveSheet, ResizeLines, Structure
from claudia_computes.model import (
    DEFAULT_COL_WIDTH,
    DEFAULT_ROW_HEIGHT,
    MAX_COL_WIDTH,
    MAX_ROW_HEIGHT,
    MIN_COL_WIDTH,
    MIN_ROW_HEIGHT,
)
from claudia_computes.refs import DeleteRows, InsertCols, InsertRows
from claudia_core import UndoConflict


def resize(doc, axis, sizes, *, author="ana", sheet=S1):
    return doc.execute(ResizeLines(sheet, axis, tuple(sizes)), author=author)


def heights(doc, sheet=S1):
    return dict(doc.model.sheet(sheet).row_heights)


def widths(doc, sheet=S1):
    return dict(doc.model.sheet(sheet).col_widths)


# ------------------------------------------------------------------ setting and undoing
def test_resizing_a_row_and_a_column_and_undo(doc):
    resize(doc, "row", [(3, 40)])
    resize(doc, "col", [(2, 120)])
    assert heights(doc) == {3: 40}
    assert widths(doc) == {2: 120}
    doc.undo("ana")
    assert widths(doc) == {}
    doc.undo("ana")
    assert heights(doc) == {}


def test_resizing_several_lines_at_once(doc):
    resize(doc, "col", [(0, 50), (1, 60), (2, 70)])
    assert widths(doc) == {0: 50, 1: 60, 2: 70}
    doc.undo("ana")
    assert widths(doc) == {}


def test_resizing_again_changes_only_what_is_asked(doc):
    resize(doc, "row", [(0, 40), (1, 40)])
    resize(doc, "row", [(1, 80)])
    assert heights(doc) == {0: 40, 1: 80}
    doc.undo("ana")
    assert heights(doc) == {0: 40, 1: 40}


def test_clearing_a_size_returns_the_line_to_default(doc):
    resize(doc, "row", [(3, 40)])
    resize(doc, "row", [(3, None)])
    assert heights(doc) == {}
    doc.undo("ana")
    assert heights(doc) == {3: 40}
    doc.undo("ana")
    assert heights(doc) == {}


# ------------------------------------------------------------------ bounds
def test_resize_rejects_an_out_of_range_index(doc):
    with pytest.raises(IndexError):
        resize(doc, "row", [(-1, 40)])
    with pytest.raises(IndexError):
        resize(doc, "col", [(16_384, 40)])
    assert heights(doc) == {} and widths(doc) == {}


def test_resize_rejects_a_size_outside_the_allowed_range(doc):
    with pytest.raises(ValueError):
        resize(doc, "row", [(0, MIN_ROW_HEIGHT - 1)])
    with pytest.raises(ValueError):
        resize(doc, "row", [(0, MAX_ROW_HEIGHT + 1)])
    with pytest.raises(ValueError):
        resize(doc, "col", [(0, MIN_COL_WIDTH - 1)])
    with pytest.raises(ValueError):
        resize(doc, "col", [(0, MAX_COL_WIDTH + 1)])
    assert heights(doc) == {} and widths(doc) == {}, "a rejected command changes nothing, not even the valid lines"


def test_a_bad_line_in_a_batch_leaves_every_line_unchanged(doc):
    with pytest.raises(IndexError):
        resize(doc, "row", [(0, 40), (-1, 40)])
    assert heights(doc) == {}


def test_the_defaults_match_the_grid_s_current_fixed_size(doc):
    # SheetGrid.vue hardcodes W=96 / H=26 today; these constants are what a future client-side default should read.
    assert (DEFAULT_ROW_HEIGHT, DEFAULT_COL_WIDTH) == (26, 96)


# ------------------------------------------------------------------ serialization
def test_resized_lines_survive_a_reload(doc):
    resize(doc, "row", [(3, 40)])
    resize(doc, "col", [(2, 120)])
    rebuilt = reopen(doc)
    assert dict(rebuilt.model.sheet(S1).row_heights) == {3: 40}
    assert dict(rebuilt.model.sheet(S1).col_widths) == {2: 120}
    assert rebuilt.model.serialize() == doc.model.serialize()


def test_a_sheet_with_no_resized_lines_serializes_the_same_both_ways(doc):
    assert reopen(doc).model.serialize() == doc.model.serialize()


# ------------------------------------------------------------------ structural edits move or drop sizes
def test_inserting_rows_shifts_row_heights_below_the_insertion(doc):
    resize(doc, "row", [(1, 40), (5, 60)])
    doc.execute(Structure(InsertRows(S1, 2, 3)), author="ana")
    assert heights(doc) == {1: 40, 8: 60}  # row 1 is before the insert and stays; row 5 moves to row 8


def test_deleting_rows_drops_the_heights_of_the_deleted_rows(doc):
    resize(doc, "row", [(1, 40), (2, 50), (5, 60)])
    doc.execute(Structure(DeleteRows(S1, 1, 2)), author="ana")  # rows 1 and 2 go
    assert heights(doc) == {3: 60}  # row 5 shifts up to row 3; rows 1 and 2's heights are gone with them


def test_deleting_a_resized_row_and_undoing_the_delete_restores_its_height(doc):
    resize(doc, "row", [(1, 40)])
    doc.execute(Structure(DeleteRows(S1, 1, 1)), author="ana")
    assert heights(doc) == {}
    doc.undo("ana")
    assert heights(doc) == {1: 40}


def test_deleting_rows_around_a_resized_one_and_undoing_restores_everything(doc):
    resize(doc, "row", [(0, 20), (3, 30), (6, 50)])
    doc.execute(Structure(DeleteRows(S1, 2, 3)), author="ana")  # rows 2,3,4 go; row 6 -> row 3
    assert heights(doc) == {0: 20, 3: 50}
    doc.undo("ana")
    assert heights(doc) == {0: 20, 3: 30, 6: 50}


def test_column_structure_never_touches_row_heights_and_vice_versa(doc):
    resize(doc, "row", [(1, 40)])
    resize(doc, "col", [(1, 120)])
    doc.execute(Structure(InsertCols(S1, 0, 2)), author="ana")
    assert heights(doc) == {1: 40}, "row heights are indexed by row; a column edit must not touch them"
    assert widths(doc) == {3: 120}
    doc.execute(Structure(InsertRows(S1, 0, 2)), author="ana")
    assert widths(doc) == {3: 120}, "column widths are indexed by column; a row edit must not touch them"
    assert heights(doc) == {3: 40}


def test_removing_a_sheet_and_undo_restores_its_resized_lines(doc):
    doc.execute(RemoveSheet(S1), author="ana")
    doc.undo("ana")  # the sheet comes back, with nothing to restore
    resize(doc, "row", [(1, 40)])
    resize(doc, "col", [(0, 50)])
    doc.execute(RemoveSheet(S1), author="ana")
    assert S1 not in doc.model.sheets, "the whole sheet, sizes included, is gone until undone"
    doc.undo("ana")
    assert heights(doc) == {1: 40} and widths(doc) == {0: 50}


# ------------------------------------------------------------------ per-author undo with colleagues at work
def test_undo_follows_rows_a_colleague_inserted(doc):
    resize(doc, "row", [(4, 40)])
    doc.execute(Structure(InsertRows(S1, 0, 2)), author="ben")  # my row is now row 6
    doc.undo("ana")
    assert heights(doc) == {}


def test_undo_is_refused_where_a_colleague_resized_the_same_line_after_me(doc):
    resize(doc, "row", [(0, 40)])
    resize(doc, "row", [(0, 80)], author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")
    assert heights(doc) == {0: 80}


def test_undo_is_unaffected_by_a_colleague_resizing_a_different_line(doc):
    resize(doc, "row", [(0, 40)])
    resize(doc, "row", [(1, 80)], author="ben")
    doc.undo("ana")
    assert heights(doc) == {1: 80}


def test_undoing_my_resize_is_refused_once_a_colleague_deletes_its_line(doc):
    resize(doc, "row", [(1, 40)])
    doc.execute(Structure(DeleteRows(S1, 1, 1)), author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")
    assert heights(doc) == {}


# ------------------------------------------------------------------ redaction, locks, history text
def test_redacting_a_resize_changes_nothing_a_size_is_not_secret_content(doc):
    applied = resize(doc, "row", [(2, 40)])
    doc.redact([applied.revision], author="ana")
    assert heights(doc) == {2: 40}, "a size is layout, not content with anything to hide, same as Structure/RemoveSheet"
    assert reopen(doc).model.serialize() == doc.model.serialize()


def test_resizing_requires_no_lock_and_is_unaffected_by_one(doc):
    doc.lock("ben", [CellRegion.of(S1, 0, 0, 0, 0)], ttl=5)
    resize(doc, "row", [(0, 40)])  # layout, not content: a colleague's cell lock must not block it
    assert heights(doc) == {0: 40}


def test_history_text_names_the_row_or_column_and_its_size(doc):
    applied = resize(doc, "row", [(2, 40)])
    assert applied.command.summary == "row 3 = 40px"
    applied = resize(doc, "col", [(1, 120)])
    assert applied.command.summary == "column B = 120px"
    applied = resize(doc, "row", [(2, None)])
    assert applied.command.summary == "row 3 reset"


def test_history_text_for_several_lines(doc):
    applied = resize(doc, "col", [(0, 50), (1, 50), (2, 50)])
    assert applied.command.summary == "column A = 50px, column B = 50px, column C = 50px"
    applied = resize(doc, "row", [(i, 20) for i in range(10)])
    assert applied.command.summary == "10 rows in rows 1:10"
