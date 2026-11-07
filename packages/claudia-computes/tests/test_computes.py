"""The mini computes model on the kernel: real structure edits, regions that follow them, per-author undo."""

import json
import random

import pytest
from conftest import S1, reopen

from claudia_computes import (
    AddSheet,
    CellRegion,
    DeleteCols,
    DeleteRows,
    InsertCols,
    InsertRows,
    RemoveSheet,
    SetCells,
    Structure,
    content_of,
)
from claudia_core import Batch, RegionHeld, Revision, UndoConflict, UndoRefused


def put(doc, row, col, value, *, author="ana", sheet=S1):
    return doc.execute(SetCells(sheet, ((row, col, content_of(value)),)), author=author)


def cell(doc, row, col, sheet=S1):
    c = doc.model.get(sheet, row, col)
    return None if c is None else c["v"]


def test_set_cells_and_undo(doc):
    put(doc, 0, 0, 5)
    put(doc, 0, 0, "five")
    assert cell(doc, 0, 0) == "five"
    doc.undo("ana")
    assert cell(doc, 0, 0) == 5
    doc.undo("ana")
    assert cell(doc, 0, 0) is None
    doc.redo("ana")
    doc.redo("ana")
    assert cell(doc, 0, 0) == "five"


def test_structure_moves_cells_and_undo_brings_deleted_cells_back(doc):
    for r in range(4):
        put(doc, r, 0, r * 10)
    doc.execute(Structure(DeleteRows(S1, 1, 2)), author="ana")  # rows 1 and 2 go
    assert [cell(doc, r, 0) for r in range(3)] == [0, 30, None]
    doc.undo("ana")
    assert [cell(doc, r, 0) for r in range(4)] == [0, 10, 20, 30]
    doc.execute(Structure(InsertCols(S1, 0, 1)), author="ana")
    assert cell(doc, 2, 1) == 20 and cell(doc, 2, 0) is None
    doc.undo("ana")
    assert cell(doc, 2, 0) == 20


def test_structure_errors_change_nothing(doc):
    put(doc, 0, 0, 1)
    with pytest.raises(ValueError):
        doc.execute(Structure(DeleteRows(S1, 1_048_570, 20)))
    with pytest.raises(ValueError):
        doc.execute(Structure(InsertRows("nope", 0, 1)))
    assert cell(doc, 0, 0) == 1 and doc.revision == Revision("main", 2)


def test_sheets_keep_their_tab_order_through_remove_and_undo(doc):
    doc.execute(AddSheet("s2", "Two"), author="ana")
    doc.execute(AddSheet("s3", "Three"), author="ana")
    put(doc, 0, 0, 7, sheet="s2")
    doc.execute(RemoveSheet("s2"), author="ana")
    assert list(doc.model.sheets) == [S1, "s3"]
    doc.undo("ana")
    assert list(doc.model.sheets) == [S1, "s2", "s3"] and cell(doc, 0, 0, "s2") == 7
    with pytest.raises(ValueError):
        doc.execute(AddSheet("s9", "two"))  # names are unique, case-insensitively


# ------------------------------------------------------------------ regions follow structure edits
def test_a_colleagues_region_follows_inserted_rows(doc):
    doc.show_presence("ben", [CellRegion.of(S1, 5, 1, 8, 2)])
    doc.execute(Structure(InsertRows(S1, 0, 3)), author="ana")
    (region,) = doc.presence.of("ben").regions
    assert (region.range.first.row, region.range.last.row) == (8, 11)
    doc.execute(Structure(DeleteRows(S1, 8, 4)), author="ana")  # the rows they were on are gone
    assert doc.presence.of("ben") is None


def test_regions_travel_as_data(doc):
    region = CellRegion.of(S1, 1, 2, 3, 4)
    assert doc.model.region_from_data(json.loads(json.dumps(region.to_data()))) == region


def test_a_lock_blocks_an_undo_that_would_touch_it(doc, clock):
    put(doc, 2, 2, 1)
    doc.lock("ben", [CellRegion.of(S1, 2, 2, 2, 2)], ttl=5)
    with pytest.raises(UndoRefused):
        doc.undo("ana")
    doc.lock("ben", [CellRegion.of(S1, 9, 9, 9, 9)], ttl=5)  # moved elsewhere
    doc.undo("ana")
    assert cell(doc, 2, 2) is None


# ------------------------------------------------------------------ per-author undo with colleagues at work
def test_undo_follows_rows_inserted_by_a_colleague(doc):
    put(doc, 4, 0, "mine")
    doc.execute(Structure(InsertRows(S1, 0, 2)), author="ben")  # my cell is now in row 6
    doc.undo("ana")
    assert cell(doc, 6, 0) is None and doc.model.sheet(S1).cells == {}


def test_undo_is_refused_where_a_colleague_wrote_after_me(doc):
    put(doc, 0, 0, "mine")
    put(doc, 0, 0, "theirs", author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")
    assert cell(doc, 0, 0) == "theirs"


def test_undoing_my_inserted_rows_is_refused_when_a_colleague_typed_into_them(doc):
    doc.execute(Structure(InsertRows(S1, 2, 3)), author="ana")
    put(doc, 3, 0, "ben was here", author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")
    assert cell(doc, 3, 0) == "ben was here"


def test_my_other_cells_are_undone_while_a_colleague_works_elsewhere(doc):
    put(doc, 0, 0, 1)
    put(doc, 5, 5, "ben", author="ben")
    doc.undo("ana")
    assert cell(doc, 0, 0) is None and cell(doc, 5, 5) == "ben"


# ------------------------------------------------------------------ redaction on a real model
def test_redacting_a_secret_cell_keeps_the_sheet_intact(doc):
    put(doc, 1, 1, "salary 123456", author="ben")  # main:2
    put(doc, 1, 2, "ok", author="ana")
    doc.redact([Revision("main", 2)], author="ana")
    assert cell(doc, 1, 1) is None and cell(doc, 1, 2) == "ok"
    assert "123456" not in json.dumps(doc.log.to_data()) and "123456" not in json.dumps(doc.model.serialize())
    assert reopen(doc).model.serialize() == doc.model.serialize()


def test_redacting_the_sheet_that_later_edits_use_keeps_it_alive(doc):
    doc.execute(AddSheet("s2", "Payroll"), author="ana")  # main:2
    put(doc, 0, 0, 1, sheet="s2")
    doc.redact([Revision("main", 2)])
    assert doc.model.sheet("s2").name == "s2" and cell(doc, 0, 0, "s2") == 1
    assert "Payroll" not in json.dumps(doc.log.to_data())


# ------------------------------------------------------------------ the kernel on a real model, randomized
def random_workbook_session(doc, seed, steps=300):
    rng = random.Random(seed)
    authors = ["ana", "ben", "ai"]
    created = 1
    for _ in range(steps):
        who = rng.choice(authors)
        roll = rng.random()
        sheet = rng.choice(list(doc.model.sheets) or [S1])  # (an undo may have taken a sheet away again)
        try:
            if roll < 0.40:
                cells = tuple(
                    (rng.randrange(8), rng.randrange(5), content_of(rng.choice([1, 2.5, "x", True, None])))
                    for _ in range(rng.randint(1, 4))
                )
                doc.execute(SetCells(sheet, cells), author=who)
            elif roll < 0.60:
                cls = rng.choice([InsertRows, DeleteRows, InsertCols, DeleteCols])
                doc.execute(Structure(cls(sheet, rng.randrange(6), rng.randint(1, 3))), author=who)
            elif roll < 0.64 and created < 6:
                created += 1
                doc.execute(AddSheet(f"s{created}", f"Sheet s{created}"), author=who)
            elif roll < 0.78:
                doc.undo(who)
            elif roll < 0.88:
                doc.redo(who)
            elif roll < 0.94:
                doc.save_checkpoint(who)
            else:
                pair = Batch((SetCells(sheet, ((0, 0, content_of(1)),)), Structure(InsertRows(sheet, 0, 1))), "pair")
                doc.execute(pair, author=who)
        except (UndoConflict, UndoRefused, ValueError, IndexError):
            pass  # refused or rejected: by contract nothing changed
    return doc


@pytest.mark.parametrize("seed", range(10))
def test_random_sessions_replay_identically_with_the_same_undo_stacks(doc, seed):
    random_workbook_session(doc, seed)
    again = reopen(doc)
    assert again.model.serialize() == doc.model.serialize()
    for who in ("ana", "ben", "ai"):
        a, b = doc.history_for(who), again.history_for(who)
        assert (a.undo_label, a.redo_label, a.can_undo, a.can_redo) == (
            b.undo_label,
            b.redo_label,
            b.can_undo,
            b.can_redo,
        )
    assert doc.materialize(doc.revision).serialize() == doc.model.serialize()
    for sheet in doc.model.sheets.values():  # structure edits never leave a cell off the grid
        assert all(r >= 0 and c >= 0 for r, c in sheet.cells)


@pytest.mark.parametrize("seed", range(6))
def test_restoring_a_checkpoint_on_a_real_model(doc, seed):
    random_workbook_session(doc, seed, steps=200)
    for _ in range(3):
        if not doc.checkpoints:
            break
        info = doc.checkpoints[len(doc.checkpoints) // 2]
        expected = doc.materialize(info.marks).serialize()
        doc.restore_checkpoint(info.number, author="ana")
        assert doc.model.serialize() == expected
        assert reopen(doc).model.serialize() == expected
        random_workbook_session(doc, seed + 100, steps=40)  # and work goes on on the new line


def test_a_colleagues_lock_stops_an_edit_in_computes(doc):
    doc.lock("ben", [CellRegion.of(S1, 0, 0, 3, 3)], ttl=5)
    with pytest.raises(RegionHeld):
        put(doc, 1, 1, "blocked")
    put(doc, 9, 9, "free")
    doc.execute(Structure(InsertRows(S1, 0, 1)), author="ben")  # ben may move things in his own zone
    with pytest.raises(RegionHeld):
        doc.execute(Structure(DeleteRows(S1, 2, 1)), author="ai")
