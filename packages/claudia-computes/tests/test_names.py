"""Named ranges and tables (E6.5, D600): defined, used in formulas, scoped to a sheet, followed through edits, grown
by typing, renamed, undone and replayed."""

from __future__ import annotations

import pytest
from conftest import S1, reopen
from names_helpers import S2, SALES, at, code, define, fill, region_of, shown

from claudia_computes import (
    AddSheet,
    DeleteRows,
    InsertRows,
    NamedRange,
    RemoveName,
    RemoveSheet,
    RenameName,
    Structure,
    WorkbookModel,
)
from claudia_computes.refs import SheetId, parse_range_ref
from claudia_core import CommandLog, Document


@pytest.fixture
def sales(doc):
    fill(doc, SALES)
    define(doc, "Sales", "A1:D4", header=True, grows=True)
    return doc


# ------------------------------------------------------------------------------------ names in formulas
def test_a_name_stands_for_its_cells(doc):
    fill(doc, {"A1": 3, "A2": 4, "B1": "=SUM(Nums)", "B2": "=Rate*2", "C1": 21})
    define(doc, "Nums", "A1:A2")
    define(doc, "Rate", "C1")
    assert shown(doc, "B1") == 7
    assert shown(doc, "B2") == 42


def test_a_name_is_not_case_sensitive(doc):
    fill(doc, {"A1": 5, "B1": "=nums*2"})
    define(doc, "NUMS", "A1")
    assert shown(doc, "B1") == 10


def test_a_name_that_does_not_exist_is_an_error_until_it_does(doc):
    fill(doc, {"A1": 5, "B1": "=Rate*2"})
    assert code(doc, "B1") == "#NAME?"
    define(doc, "Rate", "A1")
    assert shown(doc, "B1") == 10


def test_a_name_follows_its_cells_when_they_change(doc):
    fill(doc, {"A1": 5, "B1": "=Rate*2"})
    define(doc, "Rate", "A1")
    fill(doc, {"A1": 6})
    assert shown(doc, "B1") == 12


def test_defining_a_name_again_changes_where_it_points(doc):
    fill(doc, {"A1": 5, "A2": 8, "B1": "=Rate"})
    define(doc, "Rate", "A1")
    define(doc, "Rate", "A2")
    assert shown(doc, "B1") == 8


def test_removing_a_name_breaks_the_formulas_that_use_it(doc):
    fill(doc, {"A1": 5, "B1": "=Rate"})
    define(doc, "Rate", "A1")
    doc.execute(RemoveName(None, "Rate"), author="ana")
    assert code(doc, "B1") == "#NAME?"


def test_a_cell_or_a_bad_word_cannot_be_a_name(doc):
    for text in ("A1", "XFD7", "1abc", "has space", "", "TRUE"):
        with pytest.raises(ValueError):
            define(doc, text, "A1")


def test_a_name_is_defined_once_per_scope(doc):
    define(doc, "Rate", "A1")
    define(doc, "RATE", "A2")  # (defining again replaces)
    assert len(doc.model.names) == 1
    assert region_of(doc, "Rate") == "Sheet1!A2:A2"


# ------------------------------------------------------------------------------------ scope
def test_a_sheet_scoped_name_shadows_a_workbook_name_on_its_sheet(doc):
    doc.execute(AddSheet(S2, "Sheet2"), author="ana")
    fill(doc, {"A1": 1, "B1": "=Rate"})
    fill(doc, {"A1": 100, "B1": "=Rate"}, sheet=S2)
    define(doc, "Rate", "A1")  # workbook-wide: Sheet1!A1
    define(doc, "Rate", "A1", sheet=S2, scope=S2)  # only on Sheet2
    assert shown(doc, "B1") == 1
    assert shown(doc, "B1", S2) == 100


def test_a_sheet_scoped_name_is_unknown_on_other_sheets(doc):
    doc.execute(AddSheet(S2, "Sheet2"), author="ana")
    fill(doc, {"A1": 1})
    fill(doc, {"B1": "=Local"}, sheet=S2)
    define(doc, "Local", "A1", scope=S1)
    assert code(doc, "B1", S2) == "#NAME?"


def test_removing_a_sheet_takes_its_scoped_names_and_undo_brings_them_back(doc):
    doc.execute(AddSheet(S2, "Sheet2"), author="ana")
    fill(doc, {"A1": 7}, sheet=S2)
    define(doc, "Mine", "A1", sheet=S2, scope=S2)
    define(doc, "Theirs", "A1", sheet=S2)
    doc.execute(RemoveSheet(S2), author="ana")
    assert len(doc.model.names) == 0
    doc.undo("ana")
    assert region_of(doc, "Mine", S2) == "Sheet2!A1:A1"
    assert region_of(doc, "Theirs") == "Sheet2!A1:A1"


# ------------------------------------------------------------------------------------ tables
def test_a_column_of_a_table_in_a_sum(sales):
    fill(sales, {"F1": "=SUM(Sales[Amount])", "F2": "=SUM(Sales[Units])", "F3": "=COUNTA(Sales)"})
    assert shown(sales, "F1") == 25 + 40 + 30
    assert shown(sales, "F2") == 20
    assert shown(sales, "F3") == 12  # every data cell, not the header


def test_a_column_name_may_hold_a_space_and_ignore_case(sales):
    fill(sales, {"F1": "=SUM(sales[unit price])"})
    assert shown(sales, "F1") == 17.5


def test_a_column_that_does_not_exist_is_a_ref_error(sales):
    fill(sales, {"F1": "=SUM(Sales[Nothing])"})
    assert code(sales, "F1") == "#REF!"


def test_the_headers_and_the_whole_table(sales):
    fill(sales, {"F1": "=COUNTA(Sales[#Headers])", "F2": "=COUNTA(Sales[#All])", "F3": "=ROWS(Sales[#Data])"})
    assert shown(sales, "F1") == 4
    assert shown(sales, "F2") == 16
    assert shown(sales, "F3") == 3


def test_a_span_of_columns(sales):
    fill(sales, {"F1": "=SUM(Sales[[Units]:[Unit price]])"})
    assert shown(sales, "F1") == 20 + 17.5


def test_the_row_of_the_formula_with_an_at_sign(sales):
    fill(sales, {"D2": "=Sales[@Units]*Sales[@[Unit price]]", "D3": "=Sales[@Units]*Sales[@[Unit price]]"})
    assert shown(sales, "D2") == 25
    assert shown(sales, "D3") == 40


def test_the_row_of_the_formula_is_an_error_outside_the_table(sales):
    fill(sales, {"F9": "=Sales[@Units]"})
    assert code(sales, "F9") == "#VALUE!"


def test_a_formula_in_a_column_may_read_its_own_row_without_a_cycle(sales):
    fill(sales, {"D2": "=Sales[@Units]*Sales[@[Unit price]]", "D3": "=Sales[@Units]*Sales[@[Unit price]]"})
    fill(sales, {"B2": 20})
    assert shown(sales, "D2") == 50
    assert shown(sales, "D3") == 40  # (the other rows did not move)


def test_a_table_formula_in_its_own_column_is_a_cycle(sales):
    fill(sales, {"D2": "=SUM(Sales[Amount])"})
    assert code(sales, "D2") == "#CIRC!"


def test_changing_a_header_changes_which_column_a_name_means(sales):
    fill(sales, {"F1": "=SUM(Sales[Units])"})
    assert shown(sales, "F1") == 20
    fill(sales, {"B1": "Pieces"})
    assert code(sales, "F1") == "#REF!"
    fill(sales, {"F1": "=SUM(Sales[Pieces])"})
    assert shown(sales, "F1") == 20


def test_a_table_name_alone_is_its_data_rows(sales):
    fill(sales, {"F1": "=SUM(Sales)"})
    assert shown(sales, "F1") == 20 + 17.5 + 95


# ------------------------------------------------------------------------------------ growing
def test_typing_below_a_table_makes_the_row_part_of_it(sales):
    fill(sales, {"F1": "=SUM(Sales[Units])", "A5": "West", "B5": 5})
    assert region_of(sales, "Sales") == "Sheet1!A1:D5"
    assert shown(sales, "F1") == 25


def test_a_pasted_block_below_a_table_grows_it_by_all_its_rows(sales):
    fill(sales, {"A5": "West", "B5": 1, "A6": "Nord", "B6": 2, "A7": "Sud", "B7": 3})
    assert region_of(sales, "Sales") == "Sheet1!A1:D7"


def test_typing_two_rows_below_does_not_grow_it(sales):
    fill(sales, {"A6": "West"})
    assert region_of(sales, "Sales") == "Sheet1!A1:D4"


def test_typing_beside_a_table_does_not_grow_it(sales):
    fill(sales, {"E5": "x"})
    assert region_of(sales, "Sales") == "Sheet1!A1:D4"


def test_a_table_that_does_not_grow_stays_the_same(doc):
    fill(doc, SALES)
    define(doc, "Sales", "A1:D4", header=True)
    fill(doc, {"A5": "West"})
    assert region_of(doc, "Sales") == "Sheet1!A1:D4"


def test_clearing_below_a_table_does_not_grow_it(sales):
    fill(sales, {"A5": ""})
    assert region_of(sales, "Sales") == "Sheet1!A1:D4"


def test_undoing_the_typing_takes_the_row_out_again(sales):
    fill(sales, {"F1": "=SUM(Sales[Units])"})
    fill(sales, {"A5": "West", "B5": 5})
    sales.undo("ana")
    assert region_of(sales, "Sales") == "Sheet1!A1:D4"
    assert shown(sales, "F1") == 20
    sales.redo("ana")
    assert region_of(sales, "Sales") == "Sheet1!A1:D5"
    assert shown(sales, "F1") == 25


# ------------------------------------------------------------------------------------ edits that move cells
def test_a_name_moves_with_inserted_rows(sales):
    fill(sales, {"F1": "=SUM(Sales[Units])"})
    sales.execute(Structure(InsertRows(S1, 0, 2)), author="ana")
    assert region_of(sales, "Sales") == "Sheet1!A3:D6"
    assert shown(sales, "F3") == 20


def test_a_name_grows_with_rows_inserted_inside_it(sales):
    sales.execute(Structure(InsertRows(S1, 2, 1)), author="ana")
    assert region_of(sales, "Sales") == "Sheet1!A1:D5"


def test_a_name_shrinks_with_rows_deleted_inside_it(sales):
    fill(sales, {"F1": "=SUM(Sales[Units])"})
    sales.execute(Structure(DeleteRows(S1, 2, 1)), author="ana")  # the South row
    assert region_of(sales, "Sales") == "Sheet1!A1:D3"
    assert shown(sales, "F1") == 16


def test_a_name_whose_cells_were_all_deleted_goes_and_undo_brings_it_back(sales):
    fill(sales, {"F6": "=SUM(Sales[Units])"})
    sales.execute(Structure(DeleteRows(S1, 0, 4)), author="ana")
    assert len(sales.model.names) == 0
    assert code(sales, "F2") == "#NAME?"
    sales.undo("ana")
    assert region_of(sales, "Sales") == "Sheet1!A1:D4"
    assert shown(sales, "F6") == 20


def test_undoing_an_edit_restores_the_name_exactly(sales):
    before = sales.model.names.to_data()
    sales.execute(Structure(DeleteRows(S1, 1, 2)), author="ana")
    sales.undo("ana")
    assert sales.model.names.to_data() == before


# ------------------------------------------------------------------------------------ renaming
def test_renaming_a_name_rewrites_the_formulas_that_use_it(sales):
    fill(sales, {"F1": "=SUM(Sales[Units])+COUNTA(sales)"})
    sales.execute(RenameName(None, "Sales", "Orders"), author="ana")
    assert sales.model.get(S1, *at("F1"))["v"] == "=SUM(Orders[Units])+COUNTA(Orders)"
    assert shown(sales, "F1") == 20 + 12
    assert region_of(sales, "Orders") == "Sheet1!A1:D4"


def test_undoing_a_rename_restores_the_formulas_as_typed(sales):
    fill(sales, {"F1": "=SUM(Sales[Units])+COUNTA(sales)"})
    typed = sales.model.get(S1, *at("F1"))
    sales.execute(RenameName(None, "Sales", "Orders"), author="ana")
    sales.undo("ana")
    assert sales.model.get(S1, *at("F1")) == typed
    assert region_of(sales, "Sales") == "Sheet1!A1:D4"


def test_a_name_cannot_be_renamed_to_one_that_exists_or_is_not_a_name(sales):
    define(sales, "Rate", "F1")
    with pytest.raises(ValueError):
        sales.execute(RenameName(None, "Sales", "rate"), author="ana")
    with pytest.raises(ValueError):
        sales.execute(RenameName(None, "Sales", "A1"), author="ana")
    with pytest.raises(ValueError):
        sales.execute(RenameName(None, "Nothing", "Other"), author="ana")


# ------------------------------------------------------------------------------------ purposes
def test_a_table_has_a_purpose_and_columns_may_have_their_own(doc):
    fill(doc, SALES)
    define(doc, "Sales", "A1:D4", header=True, purpose="input", column_purposes=((3, "calc"),))
    named = doc.model.names.get((None, "sales"))
    assert named.purpose_of(0) == "input"
    assert named.purpose_of(3) == "calc"


def test_an_unknown_purpose_is_refused():
    with pytest.raises(ValueError):
        NamedRange("T", None, parse_range_ref("A1:B2").resolved(SheetId(S1)), purpose="loud")


# ------------------------------------------------------------------------------------ the document
def test_names_survive_reopening_and_a_snapshot(sales):
    fill(sales, {"F1": "=SUM(Sales[Units])"})
    again = reopen(sales)
    assert again.model.names.to_data() == sales.model.names.to_data()
    assert shown(again, "F1") == 20
    restored = WorkbookModel.restore(sales.model.serialize())
    assert restored.names.to_data() == sales.model.names.to_data()
    assert restored.value(S1, *at("F1")) == 20


def test_a_replayed_log_gives_the_same_names_after_undo_and_redo(sales):
    fill(sales, {"A5": "West", "B5": 1})
    sales.execute(RenameName(None, "Sales", "Orders"), author="ana")
    sales.undo("ana")
    sales.undo("ana")
    sales.redo("ana")
    again = Document.open(WorkbookModel, CommandLog.from_data(sales.log.to_data(), WorkbookModel.registry))
    assert again.model.names.to_data() == sales.model.names.to_data()
