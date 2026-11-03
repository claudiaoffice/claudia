"""Formulas in a workbook: typed in, calculated, followed through edits, undone, replayed."""

from __future__ import annotations

import random

import pytest
from conftest import S1, reopen

from claudia_computes import (
    AddSheet,
    DeleteCols,
    DeleteRows,
    InsertCols,
    InsertRows,
    RemoveSheet,
    SetCells,
    Structure,
    WorkbookModel,
    parse_input,
)
from claudia_computes.refs import parse_cell_ref
from claudia_computes.values import ErrorValue
from claudia_core import Batch


def at(address):
    ref = parse_cell_ref(address)
    return ref.row, ref.col


def type_in(doc, address, text, *, sheet=S1, author="ana"):
    row, col = at(address)
    return doc.execute(SetCells(sheet, ((row, col, parse_input(text)),)), author=author)


def fill(doc, cells: dict, *, sheet=S1):
    items = tuple((*at(address), parse_input(str(text))) for address, text in cells.items())
    return doc.execute(SetCells(sheet, items), author="ana")


def shown(doc, address, sheet=S1):
    row, col = at(address)
    return doc.model.value(sheet, row, col)


def stored(doc, address, sheet=S1):
    row, col = at(address)
    content = doc.model.get(sheet, row, col)
    return None if content is None else content["v"]


def error_code(doc, address, sheet=S1):
    value = shown(doc, address, sheet)
    assert isinstance(value, ErrorValue), f"{address} shows {value!r}"
    return value.code


def values_of(model):
    return {sheet.id: dict(sheet.grid) for sheet in model.sheets.values()}


def assert_consistent(doc):
    """What the live document shows is what a document rebuilt from its log, and from its snapshot, shows."""
    live = doc.model
    assert values_of(reopen(doc).model) == values_of(live)
    assert values_of(WorkbookModel.restore(live.serialize())) == values_of(live)
    assert WorkbookModel.restore(live.serialize()).serialize() == live.serialize()


# -- the basics ------------------------------------------------------------------------------------------------
def test_typing_a_formula_stores_its_text_and_shows_its_value(doc):
    fill(doc, {"A1": 2, "A2": 3})
    type_in(doc, "A3", "=a1 + a2")
    assert stored(doc, "A3") == "=A1+A2"  # (canonical)
    assert shown(doc, "A3") == 5
    assert_consistent(doc)


def test_changes_flow_through_chains_and_ranges(doc):
    fill(doc, {"A1": 1, "A2": 2, "A3": 3})
    fill(doc, {"B1": "=SUM(A1:A3)", "B2": "=B1*2", "B3": "=B2+A1"})
    assert [shown(doc, f"B{i}") for i in (1, 2, 3)] == [6, 12, 13]
    type_in(doc, "A2", "10")
    assert [shown(doc, f"B{i}") for i in (1, 2, 3)] == [14, 28, 29]
    type_in(doc, "A5", "100")  # (outside the range: nothing changes)
    assert shown(doc, "B1") == 14
    type_in(doc, "A3", "")  # emptied
    assert shown(doc, "B1") == 11
    assert_consistent(doc)


def test_a_formula_can_be_replaced_by_a_constant_and_back(doc):
    fill(doc, {"A1": 1, "B1": "=A1+1"})
    type_in(doc, "B1", "7")
    assert shown(doc, "B1") == 7
    type_in(doc, "A1", "5")
    assert shown(doc, "B1") == 7  # (no longer follows A1)
    type_in(doc, "B1", "=A1+1")
    assert shown(doc, "B1") == 6
    assert_consistent(doc)


def test_undo_and_redo_of_formulas(doc):
    fill(doc, {"A1": 1})
    type_in(doc, "B1", "=A1+1")
    type_in(doc, "A1", "5")
    assert shown(doc, "B1") == 6
    doc.undo("ana")
    assert shown(doc, "B1") == 2
    doc.undo("ana")
    assert shown(doc, "B1") is None
    doc.redo("ana")
    doc.redo("ana")
    assert shown(doc, "B1") == 6
    assert_consistent(doc)


def test_errors_travel_and_can_be_caught(doc):
    fill(doc, {"A1": 0, "B1": "=1/A1", "C1": "=B1+1", "D1": "=IFERROR(C1, -1)"})
    assert error_code(doc, "B1") == "#DIV/0!"
    assert error_code(doc, "C1") == "#DIV/0!"
    assert shown(doc, "D1") == -1
    type_in(doc, "A1", "4")
    assert shown(doc, "C1") == 1.25
    assert shown(doc, "D1") == 1.25


def test_a_formula_that_cannot_be_read_is_kept_and_shows_an_error(doc):
    type_in(doc, "A1", "=1+*2")
    assert error_code(doc, "A1") == "#ERROR!"
    assert stored(doc, "A1") == "=1+*2"
    type_in(doc, "A1", "=1+2")
    assert shown(doc, "A1") == 3
    assert_consistent(doc)


def test_unknown_functions_and_wrong_argument_counts(doc):
    fill(doc, {"A1": "=NOSUCH(1)", "A2": "=SUM()", "A3": "=IF(1)", "A4": "=ROUND(1,2,3)"})
    assert error_code(doc, "A1") == "#NAME?"
    assert shown(doc, "A2") == 0
    assert error_code(doc, "A3") == "#VALUE!" or shown(doc, "A3") is not None
    assert error_code(doc, "A4") == "#VALUE!"


def test_an_apostrophe_keeps_a_formula_as_text(doc):
    type_in(doc, "A1", "'=1+1")
    assert shown(doc, "A1") == "=1+1"


# -- cycles ----------------------------------------------------------------------------------------------------
def test_cycles_are_circular_errors_and_clear_when_broken(doc):
    fill(doc, {"A1": "=B1", "B1": "=A1", "C1": "=A1+1", "D1": "=D1"})
    assert error_code(doc, "A1") == "#CIRC!"
    assert error_code(doc, "B1") == "#CIRC!"
    assert error_code(doc, "C1") == "#CIRC!"  # (reads a circular cell)
    assert error_code(doc, "D1") == "#CIRC!"
    type_in(doc, "B1", "5")
    assert shown(doc, "A1") == 5
    assert shown(doc, "C1") == 6
    type_in(doc, "D1", "1")
    assert shown(doc, "D1") == 1
    assert_consistent(doc)


def test_a_cycle_through_a_range(doc):
    fill(doc, {"A1": 1, "A2": "=SUM(A1:A3)"})
    fill(doc, {"A3": "=A2"})
    assert error_code(doc, "A2") == "#CIRC!"
    assert error_code(doc, "A3") == "#CIRC!"


def test_a_long_chain_of_formulas_is_calculated_in_order(doc):
    count = 3000
    cells = {"A1": 1, **{f"A{i}": f"=A{i - 1}+1" for i in range(2, count + 1)}}
    fill(doc, cells)
    assert shown(doc, f"A{count}") == count
    type_in(doc, "A1", "11")
    assert shown(doc, f"A{count}") == count + 10


def test_formulas_typed_in_reverse_order_are_calculated_in_dependency_order(doc):
    fill(doc, {"A3": "=A2+1", "A2": "=A1+1", "A1": 1})
    assert [shown(doc, f"A{i}") for i in (1, 2, 3)] == [1, 2, 3]


def test_running_totals_with_growing_ranges(doc):
    count = 300
    cells = {f"A{i}": i for i in range(1, count + 1)}
    cells.update({f"B{i}": f"=SUM(A$1:A{i})" for i in range(count, 0, -1)})
    fill(doc, cells)
    assert shown(doc, f"B{count}") == count * (count + 1) // 2
    type_in(doc, "A1", "101")
    assert shown(doc, "B1") == 101
    assert shown(doc, f"B{count}") == count * (count + 1) // 2 + 100
    assert_consistent(doc)


# -- sheets ----------------------------------------------------------------------------------------------------
def test_formulas_read_other_sheets_and_break_when_the_sheet_goes(doc):
    doc.execute(AddSheet("s2", "Costs"), author="ana")
    fill(doc, {"A1": 40, "A2": 2}, sheet="s2")
    fill(doc, {"A1": "=Costs!A1*Costs!A2", "A2": "=SUM(Costs!A1:A2)"})
    assert shown(doc, "A1") == 80 and shown(doc, "A2") == 42
    type_in(doc, "A1", "50", sheet="s2")
    assert shown(doc, "A1") == 100
    doc.execute(RemoveSheet("s2"), author="ana")
    assert error_code(doc, "A1") == "#REF!"
    assert stored(doc, "A1") == "=#REF!*#REF!"
    doc.undo("ana")
    assert stored(doc, "A1") == "=Costs!A1*Costs!A2"
    assert shown(doc, "A1") == 100 and shown(doc, "A2") == 52
    assert_consistent(doc)


def test_a_sheet_name_with_spaces_round_trips(doc):
    doc.execute(AddSheet("s2", "Q1 costs"), author="ana")
    fill(doc, {"A1": 3}, sheet="s2")
    type_in(doc, "A1", "='q1 costs'!A1+1")
    assert stored(doc, "A1") == "='Q1 costs'!A1+1"
    assert shown(doc, "A1") == 4
    assert_consistent(doc)


def test_a_reference_to_a_sheet_that_does_not_exist_is_a_broken_reference(doc):
    type_in(doc, "A1", "=Nowhere!A1")
    assert error_code(doc, "A1") == "#REF!"
    assert_consistent(doc)  # (a snapshot must read it the same way the live document did)


# -- structure -------------------------------------------------------------------------------------------------
def test_inserting_rows_keeps_formulas_pointing_at_the_same_cells(doc):
    fill(doc, {"A1": 1, "A2": 2, "A3": 3, "B1": "=SUM(A1:A3)", "B2": "=A3*2"})
    doc.execute(Structure(InsertRows(S1, 1, 1)), author="ana")  # a new row 2
    assert stored(doc, "B1") == "=SUM(A1:A4)"  # (the range grows)
    assert stored(doc, "B3") == "=A4*2"  # (moved down, and it follows A3)
    assert shown(doc, "B1") == 6 and shown(doc, "B3") == 6
    type_in(doc, "A2", "10")
    assert shown(doc, "B1") == 16
    doc.undo("ana")
    doc.undo("ana")
    assert stored(doc, "B1") == "=SUM(A1:A3)" and stored(doc, "B2") == "=A3*2"
    assert_consistent(doc)


def test_deleting_what_a_formula_points_at_breaks_it_and_undo_restores_it_exactly(doc):
    fill(doc, {"A1": 1, "A2": 2, "A3": 3, "B1": "=A2+A3", "B3": "=SUM(A1:A3)"})
    doc.execute(Structure(DeleteRows(S1, 1, 1)), author="ana")  # row 2 goes
    assert stored(doc, "B1") == "=#REF!+A2"
    assert error_code(doc, "B1") == "#REF!"
    assert stored(doc, "B2") == "=SUM(A1:A2)" and shown(doc, "B2") == 4  # (moved up, the range shrank)
    doc.undo("ana")
    assert stored(doc, "B1") == "=A2+A3"
    assert stored(doc, "B3") == "=SUM(A1:A3)"
    assert shown(doc, "B1") == 5 and shown(doc, "B3") == 6
    assert_consistent(doc)


def test_deleting_a_formula_cell_and_undoing(doc):
    fill(doc, {"A1": 1, "A2": "=A1+1", "A3": "=A2+1"})
    doc.execute(Structure(DeleteRows(S1, 1, 1)), author="ana")
    assert error_code(doc, "A2") == "#REF!"  # (was A3, read A2)
    doc.undo("ana")
    assert [shown(doc, f"A{i}") for i in (1, 2, 3)] == [1, 2, 3]
    assert stored(doc, "A3") == "=A2+1"


def test_columns_move_formulas_too(doc):
    fill(doc, {"A1": 1, "B1": 2, "C1": "=A1+B1"})
    doc.execute(Structure(InsertCols(S1, 0, 2)), author="ana")
    assert stored(doc, "E1") == "=C1+D1" and shown(doc, "E1") == 3
    doc.execute(Structure(DeleteCols(S1, 0, 2)), author="ana")
    assert stored(doc, "C1") == "=A1+B1"
    assert_consistent(doc)


def test_structure_edits_of_another_sheet_reach_formulas_that_read_it(doc):
    doc.execute(AddSheet("s2", "Data"), author="ana")
    fill(doc, {"A1": 1, "A2": 2}, sheet="s2")
    fill(doc, {"A1": "=Data!A2", "A2": "=A1"})
    doc.execute(Structure(InsertRows("s2", 0, 1)), author="ana")
    assert stored(doc, "A1") == "=Data!A3"  # (it still reads the 2)
    assert stored(doc, "A2") == "=A1"  # (this sheet did not change)
    assert shown(doc, "A1") == 2
    doc.undo("ana")
    assert stored(doc, "A1") == "=Data!A2"
    assert_consistent(doc)


def test_a_formula_pushed_off_the_sheet_breaks_and_undo_brings_it_back(doc):
    type_in(doc, "A1", "=A1048576")
    doc.execute(Structure(InsertRows(S1, 5, 1)), author="ana")
    assert error_code(doc, "A1") == "#CIRC!" or error_code(doc, "A1") == "#REF!"
    doc.undo("ana")
    assert stored(doc, "A1") == "=A1048576"


# -- agreement with a calculation from scratch -----------------------------------------------------------------
@pytest.mark.parametrize("seed", [7, 11, 23, 42, 99, 123, 2024, 31337])
def test_random_edits_always_agree_with_a_full_recalculation(doc, seed):
    rng = random.Random(seed)
    doc.execute(AddSheet("s2", "Other"), author="ana")
    sheets = [S1, "s2"]
    cols = "ABCD"

    def a_ref():
        return f"{rng.choice(cols)}{rng.randint(1, 8)}"

    def a_formula():
        pick = rng.randint(0, 6)
        if pick == 0:
            return f"={a_ref()}+{a_ref()}"
        if pick == 1:
            return f"=SUM({a_ref()}:{a_ref()})"
        if pick == 2:
            return f"=IF({a_ref()}>5, {a_ref()}, 0)"
        if pick == 3:
            return f"=Other!{a_ref()}*2"
        if pick == 4:
            return f"=MAX({a_ref()}:{a_ref()}, {a_ref()})"
        if pick == 5:
            return f"=XLOOKUP({a_ref()}, A1:A8, B1:B8, 0)"
        return f"=INDEX(A1:D8, {rng.randint(1, 8)}, {rng.randint(1, 4)})"

    for step in range(250):
        roll = rng.random()
        sheet = rng.choice(sheets)
        if roll < 0.55:
            text = a_formula() if rng.random() < 0.6 else str(rng.randint(0, 9))
            if rng.random() < 0.1:
                text = ""
            type_in(doc, a_ref(), text, sheet=sheet)
        elif roll < 0.7:
            edit = rng.choice([InsertRows, DeleteRows, InsertCols, DeleteCols])
            doc.execute(Structure(edit(sheet, rng.randint(0, 6), rng.randint(1, 2))), author="ana")
        elif roll < 0.85:
            doc.undo("ana")
        else:
            doc.redo("ana")
        if step % 10 == 0:
            assert_consistent(doc)
    assert_consistent(doc)


# -- dynamic references ----------------------------------------------------------------------------------------
def test_offset_and_indirect_follow_the_cells_they_read(doc):
    fill(
        doc,
        {
            "A1": 1,
            "A2": 2,
            "A3": 3,
            "C1": 2,
            "B1": "=INDEX(A1:A3, C1)",
            "B2": "=OFFSET(A1, C1, 0)",
            "B3": '=INDIRECT("A"&C1)',
        },
    )
    assert [shown(doc, f"B{i}") for i in (1, 2, 3)] == [2, 3, 2]
    type_in(doc, "A3", "30")  # a cell that OFFSET reads without naming it
    assert shown(doc, "B2") == 30
    type_in(doc, "A2", "20")
    assert shown(doc, "B3") == 20 and shown(doc, "B1") == 20
    type_in(doc, "C1", "1")
    assert shown(doc, "B3") == 1 and shown(doc, "B2") == 20


def test_a_dynamic_formula_waits_for_the_formulas_it_reads(doc):
    fill(doc, {"A1": "=A2+1", "A2": "=A3+1", "A3": 1, "C1": '=INDIRECT("A1")', "C2": "=C1*10"})
    assert shown(doc, "C1") == 3 and shown(doc, "C2") == 30
    type_in(doc, "A3", "5")
    assert shown(doc, "C1") == 7 and shown(doc, "C2") == 70


def test_a_dynamic_formula_that_reads_itself_is_circular(doc):
    type_in(doc, "A1", '=INDIRECT("A1")')
    assert error_code(doc, "A1") == "#CIRC!"


# -- lookups -----------------------------------------------------------------------------------------------------
def test_lookup_indexes_follow_edits_in_long_columns(doc):
    cells = {f"A{i}": f"k{i}" for i in range(1, 101)} | {f"B{i}": i * 10 for i in range(1, 101)}
    fill(doc, cells)
    type_in(doc, "D1", '=XLOOKUP("k77", A1:A100, B1:B100, "none")')
    type_in(doc, "D2", '=MATCH("k77", A:A, 0)')
    assert shown(doc, "D1") == 770 and shown(doc, "D2") == 77
    type_in(doc, "A77", "renamed")
    assert shown(doc, "D1") == "none"
    assert error_code(doc, "D2") == "#N/A"
    type_in(doc, "A3", "k77")
    assert shown(doc, "D1") == 30 and shown(doc, "D2") == 3
    doc.execute(Structure(InsertRows(S1, 0, 1)), author="ana")
    assert shown(doc, "D2") == 30 and shown(doc, "D3") == 4  # (the index did not survive the rows moving)


# -- events and rollback -----------------------------------------------------------------------------------------
def test_settling_tells_watchers_the_values_of_formulas(doc):
    fill(doc, {"A1": 1, "B1": "=A1+1", "C1": "=B1*2"})
    seen = []
    doc.subscribe(lambda event: seen.append(event.to_data()) if event.to_data()["type"] == "cells" else None)
    type_in(doc, "A1", "5")
    changed = {(r, c): content for event in seen for r, c, content in event["cells"]}
    assert changed[(0, 0)] == {"t": "int", "v": 5}
    assert changed[(0, 1)] == {"t": "int", "v": 6, "f": "=A1+1"}
    assert changed[(0, 2)] == {"t": "int", "v": 12, "f": "=B1*2"}


def test_a_new_formula_is_announced_even_when_its_value_is_the_old_one(doc):
    fill(doc, {"A1": 3})
    type_in(doc, "B1", "3")
    seen = []
    doc.subscribe(lambda event: seen.append(event.to_data()) if event.to_data()["type"] == "cells" else None)
    type_in(doc, "B1", "=A1")
    changed = {(r, c): content for event in seen for r, c, content in event["cells"]}
    assert changed[(0, 1)] == {"t": "int", "v": 3, "f": "=A1"}


def test_errors_are_announced_as_error_contents(doc):
    fill(doc, {"A1": 0})
    seen = []
    doc.subscribe(lambda event: seen.append(event.to_data()) if event.to_data()["type"] == "cells" else None)
    type_in(doc, "B1", "=1/A1")
    changed = {(r, c): content for event in seen for r, c, content in event["cells"]}
    assert changed[(0, 1)]["t"] == "error" and changed[(0, 1)]["v"] == "#DIV/0!" and changed[(0, 1)]["f"] == "=1/A1"


def test_a_failing_batch_leaves_everything_as_it_was(doc):
    fill(doc, {"A1": 1, "B1": "=A1+1"})
    before = (values_of(doc.model), doc.model.serialize())
    good = SetCells(S1, ((0, 0, parse_input("50")),))
    bad = SetCells("nowhere", ((0, 0, parse_input("1")),))
    with pytest.raises(ValueError):
        doc.execute(Batch((good, bad)), author="ana")
    assert (values_of(doc.model), doc.model.serialize()) == before
    type_in(doc, "A1", "7")
    assert shown(doc, "B1") == 8


def test_a_batch_calculates_once_with_everything_in_it(doc):
    doc.execute(
        Batch(
            (
                SetCells(S1, ((0, 1, parse_input("=A1*2")),)),
                SetCells(S1, ((0, 0, parse_input("4")),)),
            )
        ),
        author="ana",
    )
    assert shown(doc, "B1") == 8


# -- per author undo ---------------------------------------------------------------------------------------------
def test_undoing_my_formula_leaves_a_colleagues_work(doc):
    type_in(doc, "A1", "1", author="ana")
    type_in(doc, "B1", "=A1+1", author="ana")
    type_in(doc, "A2", "5", author="ben")
    type_in(doc, "B2", "=A2+A1", author="ben")
    doc.undo("ana")  # B1
    assert shown(doc, "B1") is None and shown(doc, "B2") == 6
    doc.undo("ben")
    assert shown(doc, "B2") is None
    assert_consistent(doc)


def test_undoing_my_edit_after_a_colleague_moved_rows_keeps_the_formula_pointing_at_the_same_cells(doc):
    fill(doc, {"A1": 1, "A2": 5})
    type_in(doc, "B2", "=A1+A2", author="ana")
    type_in(doc, "B2", "", author="ana")  # ana clears it
    doc.execute(Structure(InsertRows(S1, 0, 1)), author="ben")  # ben inserts a row at the top
    doc.undo("ana")  # the formula comes back, one row further down, still about the same two numbers
    assert stored(doc, "B3") == "=A2+A3"
    assert shown(doc, "B3") == 6
    assert_consistent(doc)


def test_a_formula_with_sheet_names_is_not_rewritten_by_a_colleagues_structure_edit_when_my_edit_is_undone(doc):
    doc.execute(AddSheet("s2", "Data"), author="ana")
    fill(doc, {"A1": 4}, sheet="s2")
    type_in(doc, "B1", "=Data!A1", author="ana")
    type_in(doc, "B1", "", author="ana")
    doc.execute(Structure(InsertRows(S1, 0, 1)), author="ben")  # (another sheet's cells did not move)
    doc.undo("ana")
    assert stored(doc, "B2") == "=Data!A1" and shown(doc, "B2") == 4
