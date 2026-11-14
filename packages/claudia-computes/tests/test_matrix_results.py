"""Functions that answer with several cells (SORT, SEQUENCE, TRANSPOSE ...): the ``Matrix`` result (D-array-results).

A ``Matrix`` spills exactly like the table of ``SQL()``: it fills the cells below and beside its formula, which the
formula owns. Used as an argument, it is a range of those values; where a single value is wanted, a matrix of one
cell is that cell and a bigger one is ``#VALUE!``.
"""

from __future__ import annotations

import pytest
from conftest import S1
from names_helpers import at, code, fill, shown

from claudia_computes.formula.operators import single
from claudia_computes.functions import Range
from claudia_computes.spill import Matrix
from claudia_computes.values import ErrorValue, FormulaError


def block(doc, first, last):
    (r0, c0), (r1, c1) = at(first), at(last)
    return [[doc.model.value(S1, r, c) for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)]


# -- the type itself
def test_a_matrix_knows_its_size_and_its_cells():
    m = Matrix(((1, 2, 3), ("a", "b", "c")))
    assert (m.height, m.width) == (2, 3)
    assert m.value_at(0, 2) == 3
    assert m.value_at(1, 0) == "a"


def test_a_matrix_must_be_rectangular_and_not_empty():
    with pytest.raises(ValueError):
        Matrix(((1, 2), (3,)))
    with pytest.raises(ValueError):
        Matrix(())
    with pytest.raises(ValueError):
        Matrix(((),))


def test_a_matrix_as_a_range_reads_like_cells():
    area = Matrix(((1, 2), (3, None))).as_range()
    assert isinstance(area, Range)
    assert (area.n_rows, area.n_cols) == (2, 2)
    assert area.at(1, 0) == 3
    assert sorted(area.numbers()) == [1, 2, 3]
    assert area.dense() == ((1, 2), (3, None))


def test_a_matrix_of_one_cell_is_a_single_value_and_a_bigger_one_is_not():
    assert single(Matrix(((7,),))) == 7
    with pytest.raises(FormulaError) as problem:
        single(Matrix(((1, 2),)))
    assert problem.value.value().code == "#VALUE!"


# -- in a workbook
def test_a_matrix_result_fills_the_cells_below_and_beside_its_formula(doc):
    fill(doc, {"A1": 3, "A2": 1, "A3": 2, "C1": "=SORT(A1:A3)"})
    assert block(doc, "C1", "C3") == [[1], [2], [3]]
    sheet = doc.model.sheet(S1)
    assert at("C2") in sheet.spilled
    assert at("C2") not in sheet.cells  # (not stored: the formula owns them)


def test_the_matrix_follows_its_inputs_and_shrinks_and_grows(doc):
    fill(doc, {"A1": 3, "A2": 1, "A3": 2, "C1": "=SORT(A1:A3)"})
    fill(doc, {"A1": 0})
    assert block(doc, "C1", "C3") == [[0], [1], [2]]
    fill(doc, {"C1": "=SORT(A1:A2)"})
    assert shown(doc, "C3") is None
    assert at("C3") not in doc.model.sheet(S1).spilled


def test_a_matrix_of_several_columns_spills_sideways(doc):
    fill(doc, {"A1": "=SEQUENCE(2, 3)"})
    assert block(doc, "A1", "C2") == [[1, 2, 3], [4, 5, 6]]


def test_something_in_the_way_gives_a_spill_error(doc):
    fill(doc, {"B2": "mine", "A1": "=SEQUENCE(2, 2)"})
    assert code(doc, "A1") == "#SPILL!"
    assert shown(doc, "B2") == "mine"
    fill(doc, {"B2": ""})
    assert block(doc, "A1", "B2") == [[1, 2], [3, 4]]


def test_formulas_can_read_the_cells_of_a_matrix_result(doc):
    fill(doc, {"E1": "=SUM(C1:C3)", "A1": 3, "A2": 1, "A3": 2, "C1": "=SORT(A1:A3)"})
    assert shown(doc, "E1") == 6
    fill(doc, {"A1": 10})
    assert shown(doc, "E1") == 13


def test_a_spilled_cell_cannot_be_written(doc):
    fill(doc, {"A1": "=SEQUENCE(3)"})
    with pytest.raises(ValueError, match="A1"):
        fill(doc, {"A2": "mine"})


def test_a_matrix_of_one_cell_shows_as_a_plain_value(doc):
    fill(doc, {"A1": "=SEQUENCE(1)"})
    assert shown(doc, "A1") == 1
    assert at("A1") not in doc.model.sheet(S1).spilled


def test_a_matrix_where_a_single_value_is_wanted_is_an_error(doc):
    fill(doc, {"A1": "=ABS(SEQUENCE(3))"})
    assert code(doc, "A1") == "#VALUE!"


def test_a_matrix_can_be_the_argument_of_another_function(doc):
    fill(doc, {"A1": "=SUM(SEQUENCE(4))", "A2": "=ROWS(SEQUENCE(4, 2))", "A3": "=INDEX(SEQUENCE(3), 2)"})
    assert shown(doc, "A1") == 10
    assert shown(doc, "A2") == 4
    assert shown(doc, "A3") == 2


def test_errors_inside_a_matrix_are_values_of_its_cells(doc):
    fill(doc, {"A1": "=SEQUENCE(2)", "B1": "=IFERROR(A2, 0)"})
    assert shown(doc, "B1") == 2


# -- operators on ranges work cell by cell ----------------------------------------------------------------------------
def test_an_operator_on_a_range_works_on_every_cell(doc):
    fill(doc, {"A1": 1, "A2": 2, "A3": 3, "C1": "=A1:A3*10", "E1": "=SUM(A1:A3*A1:A3)"})
    assert block(doc, "C1", "C3") == [[10], [20], [30]]
    assert shown(doc, "E1") == 14


def test_comparisons_give_a_matrix_of_truth_values(doc):
    fill(doc, {"A1": 1, "A2": 5, "A3": 9, "C1": "=A1:A3>4"})
    assert block(doc, "C1", "C3") == [[False], [True], [True]]


def test_a_row_and_a_column_make_a_table(doc):
    fill(doc, {"A1": 1, "A2": 2, "B3": 10, "C3": 20, "D1": "=A1:A2*B3:C3"})
    assert block(doc, "D1", "E2") == [[10, 20], [20, 40]]


def test_ranges_of_different_sizes_leave_na_where_one_is_missing(doc):
    fill(doc, {"A1": 1, "A2": 2, "A3": 3, "B1": 10, "B2": 20, "D1": "=A1:A3+B1:B2"})
    assert block(doc, "D1", "D2") == [[11], [22]]
    assert code(doc, "D3") == "#N/A"


def test_an_error_in_one_cell_is_the_error_of_that_cell_only(doc):
    fill(doc, {"A1": 1, "A2": "x", "A3": 3, "C1": "=A1:A3+1"})
    assert shown(doc, "C1") == 2
    assert code(doc, "C2") == "#VALUE!"
    assert shown(doc, "C3") == 4


def test_negation_percent_and_joining_work_on_ranges_too(doc):
    fill(doc, {"A1": 1, "A2": 2, "C1": "=-A1:A2", "D1": "=A1:A2%", "E1": '=A1:A2&"x"'})
    assert block(doc, "C1", "C2") == [[-1], [-2]]
    assert block(doc, "D1", "D2") == [[0.01], [0.02]]
    assert block(doc, "E1", "E2") == [["1x"], ["2x"]]


def test_a_range_of_one_cell_is_still_a_single_value(doc):
    fill(doc, {"A1": 4, "C1": "=A1:A1+1", "D1": "=SUM(A1:A1*2)"})
    assert shown(doc, "C1") == 5
    assert at("C1") not in doc.model.sheet(S1).spilled
    assert shown(doc, "D1") == 8
