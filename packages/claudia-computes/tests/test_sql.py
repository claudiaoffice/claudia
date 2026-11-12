"""SQL() and spilling (E4.9/E6.5, D600): a query over named tables fills the cells below and beside its formula, the
result is a table of its own, and the engine refuses to do anything but read."""

from __future__ import annotations

import time

import pytest
from conftest import S1
from names_helpers import SALES, at, code, define, fill, shown

from claudia_computes import (
    DefineName,
    DeleteRows,
    InsertRows,
    NamedRange,
    RemoveName,
    SetCells,
    Structure,
    WorkbookModel,
)
from claudia_computes import sql as sql_engine
from claudia_computes.values import ErrorValue

BY_REGION = "SELECT Region, SUM(Amount) AS Revenue FROM Sales GROUP BY Region ORDER BY Revenue DESC"
QUERY = f'=SQL("{BY_REGION}")'


@pytest.fixture
def sales(doc):
    fill(doc, SALES)
    define(doc, "Sales", "A1:D4", header=True, grows=True)
    return doc


def result_name(doc, text, address, *, scope=None):
    row, col = at(address)
    return doc.execute(
        DefineName(NamedRange(text, scope, None, header=True, purpose="result", anchor=(S1, row, col))), author="ana"
    )


def block(doc, first, last):
    """The values of a rectangle of cells, as rows."""
    (r0, c0), (r1, c1) = at(first), at(last)
    return [[doc.model.value(S1, r, c) for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)]


# ------------------------------------------------------------------------------------ spilling
def test_a_query_fills_the_cells_below_and_beside_its_formula(sales):
    fill(sales, {"F1": QUERY})
    rows = block(sales, "F1", "G4")
    assert rows[0] == ["Region", "Revenue"]
    assert {tuple(row) for row in rows[1:]} == {("South", 40), ("North", 25), ("East", 30)}
    assert [r[1] for r in rows[1:]] == [40, 30, 25]  # (ORDER BY Revenue DESC)


def test_the_formula_cell_keeps_its_formula_and_the_other_cells_are_not_stored(sales):
    fill(sales, {"F1": QUERY})
    sheet = sales.model.sheet(S1)
    assert sheet.cells[at("F1")]["t"] == "formula"
    assert at("F2") not in sheet.cells
    assert at("G3") not in sheet.cells
    assert at("F2") in sheet.spilled


def test_a_client_sees_the_spilled_cells_as_values_that_are_not_to_be_edited(sales):
    fill(sales, {"F1": QUERY})
    sheet = sales.model.sheet(S1)
    assert sheet.view(at("F2")) == {"t": "text", "v": "South", "spill": True, "from": [0, 5]}
    assert sheet.view(at("F1"))["f"] == QUERY


def test_a_window_and_the_extent_include_the_spilled_cells(sales):
    fill(sales, {"F1": QUERY})
    sheet = sales.model.sheet(S1)
    assert at("G4") in sheet.cells_in(0, 10, 5, 6)
    assert sheet.extent() == (4, 7)


def test_the_result_changes_when_the_table_does(sales):
    fill(sales, {"F1": QUERY})
    fill(sales, {"B2": 100})
    assert shown(sales, "F2") == "North"
    assert shown(sales, "G2") == 250


def test_the_result_grows_and_shrinks_with_the_data(sales):
    fill(sales, {"F1": QUERY})
    fill(sales, {"A5": "West", "B5": 1, "C5": 7, "D5": "=B5*C5"})  # (a fifth row grows the table)
    assert block(sales, "F1", "G5")[4] == ["West", 7]
    sales.execute(Structure(DeleteRows(S1, 4, 1)), author="ana")  # (and taking it away shrinks the table again)
    assert shown(sales, "F5") is None
    assert at("F5") not in sales.model.sheet(S1).spilled


def test_formulas_that_read_the_spilled_cells_follow_them(sales):
    fill(sales, {"I1": "=SUM(G2:G10)", "F1": QUERY})  # (I1 comes before the query in the order of cells)
    assert shown(sales, "I1") == 95
    fill(sales, {"B2": 100})
    assert shown(sales, "I1") == 320


def test_a_spilled_cell_cannot_be_written(sales):
    fill(sales, {"F1": QUERY})
    with pytest.raises(ValueError, match="SQL"):
        fill(sales, {"F2": "mine"})
    assert shown(sales, "F2") == "South"
    with pytest.raises(ValueError):
        fill(sales, {"G3": ""})


def test_something_in_the_way_blocks_the_result(sales):
    fill(sales, {"G3": "mine", "F1": QUERY})
    assert code(sales, "F1") == "#SPILL!"
    assert "G3" in shown(sales, "F1").detail
    assert shown(sales, "F2") is None
    assert shown(sales, "G3") == "mine"
    fill(sales, {"G3": ""})
    assert shown(sales, "F1") == "Region"
    assert shown(sales, "G3") == 30


def test_a_result_that_does_not_fit_below_the_sheet_is_a_spill_error(sales):
    fill(sales, {"F1048575": QUERY})  # (two rows from the bottom)
    assert code(sales, "F1048575") == "#SPILL!"


def test_a_formula_in_the_way_blocks_the_result_and_keeps_its_own_value(sales):
    fill(sales, {"F1": QUERY, "F2": '=SQL("SELECT 1 AS one")'})
    assert code(sales, "F1") == "#SPILL!"
    assert "F2" in shown(sales, "F1").detail
    assert shown(sales, "F2") == "one"
    assert shown(sales, "F3") == 1


def test_clearing_the_formula_clears_the_result_and_undo_brings_it_back(sales):
    fill(sales, {"F1": QUERY})
    fill(sales, {"F1": ""})
    assert shown(sales, "F2") is None
    assert sales.model.sheet(S1).spilled == {}
    sales.undo("ana")
    assert shown(sales, "F2") == "South"


def test_inserting_a_row_above_moves_the_result_with_its_formula(sales):
    fill(sales, {"F1": QUERY})
    sales.execute(Structure(InsertRows(S1, 0, 1)), author="ana")
    assert shown(sales, "F2") == "Region"
    assert shown(sales, "F3") == "South"
    assert shown(sales, "F1") is None
    sales.undo("ana")
    assert shown(sales, "F1") == "Region"


def test_the_result_is_there_again_when_the_document_is_reopened(sales):
    fill(sales, {"F1": QUERY})
    again = WorkbookModel.restore(sales.model.serialize())
    assert again.value(S1, *at("G2")) == 40


# ------------------------------------------------------------------------------------ the query language
def test_a_column_with_a_space_is_quoted(sales):
    fill(sales, {"F1": '=SQL("SELECT ""Unit price"" FROM Sales WHERE Units > 5 ORDER BY 1")'})
    assert block(sales, "F1", "F3") == [["Unit price"], [2.5], [5]]


def test_a_parameter_is_a_value_from_the_sheet(sales):
    fill(sales, {"H1": 5, "F1": '=SQL("SELECT Region FROM Sales WHERE Units > ? ORDER BY Region", H1)'})
    assert block(sales, "F1", "F3") == [["Region"], ["East"], ["North"]]


def test_a_formula_with_the_query_inside_a_calculation_gives_its_first_value(sales):
    fill(sales, {"F1": '=SQL("SELECT COUNT(*) FROM Sales")*2'})
    assert shown(sales, "F1") == 6
    assert shown(sales, "F2") is None


def test_a_query_may_join_tables_and_use_text_and_numbers(sales):
    fill(sales, {"A8": "Region", "B8": "Manager", "A9": "North", "B9": "Ines", "A10": "East", "B10": "Omar"})
    define(sales, "Managers", "A8:B10", header=True)
    join = "SELECT s.Region, m.Manager, s.Units FROM Sales s JOIN Managers m ON m.Region = s.Region ORDER BY 1"
    fill(sales, {"F1": f'=SQL("{join}")'})
    assert block(sales, "F1", "H3") == [["Region", "Manager", "Units"], ["East", "Omar", 6], ["North", "Ines", 10]]


def test_a_range_without_a_header_names_its_columns_by_letter(doc):
    fill(doc, {"A1": 3, "B1": "x", "A2": 4, "B2": "y"})
    define(doc, "Pairs", "A1:B2")
    fill(doc, {"D1": '=SQL("SELECT B FROM Pairs WHERE A > 3")'})
    assert block(doc, "D1", "D2") == [["B"], ["y"]]


def test_a_column_with_a_blank_or_repeated_header_still_gets_a_name(doc):
    fill(doc, {"A1": "n", "B1": "", "C1": "n", "A2": 1, "B2": 2, "C2": 3})
    define(doc, "T", "A1:C2", header=True)
    fill(doc, {"E1": '=SQL("SELECT * FROM T")'})
    assert block(doc, "E1", "G1") == [["n", "Column2", "n_2"]]
    assert block(doc, "E2", "G2") == [[1, 2, 3]]


def test_the_result_of_a_query_is_a_table_other_formulas_can_name(sales):
    fill(sales, {"F1": QUERY, "I1": "=SUM(SalesByRegion[Revenue])", "I2": "=COUNTA(SalesByRegion)"})
    result_name(sales, "SalesByRegion", "F1")
    assert shown(sales, "I1") == 95
    assert shown(sales, "I2") == 6
    fill(sales, {"B2": 100})
    assert shown(sales, "I1") == 320


def test_a_query_may_read_the_result_of_another(sales):
    fill(sales, {"F1": QUERY, "I1": '=SQL("SELECT MAX(Revenue) AS best FROM SalesByRegion")'})
    result_name(sales, "SalesByRegion", "F1")
    assert block(sales, "I1", "I2") == [["best"], [40]]
    fill(sales, {"B2": 100})
    assert shown(sales, "I2") == 250


def test_a_result_without_a_formula_is_a_reference_error(sales):
    result_name(sales, "Ghost", "F1")
    fill(sales, {"I1": "=SUM(Ghost[Revenue])"})
    assert code(sales, "I1") == "#REF!"


def test_a_name_of_a_result_is_gone_with_its_formula_but_not_its_definition(sales):
    fill(sales, {"F1": QUERY, "I1": "=SUM(SalesByRegion[Revenue])"})
    result_name(sales, "SalesByRegion", "F1")
    sales.execute(RemoveName(None, "SalesByRegion"), author="ana")
    assert code(sales, "I1") == "#NAME?"
    assert shown(sales, "F2") == "South"


# ------------------------------------------------------------------------------------ errors
@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("SELEKT 1", "syntax error"),
        ("SELECT * FROM Nowhere", "no such table"),
        ("SELECT Revnue FROM Sales", "no such column"),
        ("SELECT 1; SELECT 2", "one statement"),
        ("DELETE FROM Sales", "not authorized"),
        ("INSERT INTO Sales VALUES (1,2,3,4)", "not authorized"),
        ("DROP TABLE Sales", "not authorized"),
        ("CREATE TABLE x (a)", "not authorized"),
        ("PRAGMA table_info(Sales)", "not authorized"),
        ("ATTACH DATABASE ':memory:' AS other", "not authorized"),
        ("SELECT random()", "not authorized"),
        ("SELECT load_extension('x')", "not authorized"),
    ],
)
def test_only_reading_is_allowed_and_a_wrong_query_is_an_sql_error(sales, query, message):
    fill(sales, {"F1": f'=SQL("{query}")'})
    value = shown(sales, "F1")
    assert isinstance(value, ErrorValue)
    assert value.code == "#SQL!"
    assert message in value.detail


def test_the_data_is_not_changed_by_a_query_that_tried(sales):
    fill(sales, {"F1": '=SQL("DELETE FROM Sales")'})
    assert shown(sales, "B2") == 10


def test_a_query_that_runs_too_long_is_stopped(sales, monkeypatch):
    monkeypatch.setattr(sql_engine, "TIME_LIMIT", 0.05)
    started = time.monotonic()
    fill(sales, {"F1": '=SQL("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT count(*) FROM c")'})
    assert time.monotonic() - started < 5
    value = shown(sales, "F1")
    assert isinstance(value, ErrorValue) and value.code == "#SQL!"
    assert "longer" in value.detail


def test_a_result_with_too_many_rows_is_an_error(sales, monkeypatch):
    monkeypatch.setattr(sql_engine, "MAX_RESULT_ROWS", 2)
    fill(sales, {"F1": '=SQL("SELECT Region FROM Sales")'})
    value = shown(sales, "F1")
    assert isinstance(value, ErrorValue) and value.code == "#SQL!"
    assert "rows" in value.detail


def test_a_query_that_is_not_text_is_a_value_error(sales):
    fill(sales, {"F1": "=SQL(42)"})
    assert code(sales, "F1") == "#VALUE!"


def test_an_error_in_a_parameter_is_the_error_of_the_formula(sales):
    fill(sales, {"H1": "=1/0", "F1": '=SQL("SELECT ?", H1)'})
    assert code(sales, "F1") == "#DIV/0!"


def test_a_query_over_a_table_that_is_removed_is_an_error_until_it_is_back(sales):
    fill(sales, {"F1": QUERY})
    sales.execute(RemoveName(None, "Sales"), author="ana")
    assert code(sales, "F1") == "#SQL!"
    sales.undo("ana")
    assert shown(sales, "G2") == 40


def test_setting_cells_through_a_batch_with_a_query_calculates_once_and_correctly(sales):
    sales.execute(
        SetCells(S1, ((0, 5, {"t": "formula", "v": QUERY}), (1, 1, {"t": "int", "v": 100}))),
        author="ana",
    )
    assert shown(sales, "G2") == 250
