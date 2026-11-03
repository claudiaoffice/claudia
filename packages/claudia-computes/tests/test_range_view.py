"""A range reads a sparse sheet without listing its empty cells."""

import pytest

from claudia_computes.functions.range import Range
from claudia_computes.limits import MAX_ROWS
from claudia_computes.values import ErrorValue, FormulaError


class FakeSheet:
    def __init__(self, cells):
        self.grid = dict(cells)
        self.rows_used = max((r for r, _ in self.grid), default=-1) + 1
        self.cols_used = max((c for _, c in self.grid), default=-1) + 1


@pytest.fixture
def sheet():
    return FakeSheet({(0, 0): 1, (1, 0): 2.5, (2, 0): "x", (3, 0): True, (1, 1): 10, (5, 0): 7})


def test_present_gives_what_is_there_and_numbers_only_numbers(sheet):
    area = Range(sheet, 0, 0, 5, 1)
    assert sorted(map(str, area.present())) == sorted(["1", "2.5", "x", "True", "10", "7"])
    assert sorted(area.numbers()) == [1, 2.5, 7, 10]  # (TRUE and the text are not numbers)


def test_a_range_beyond_the_sheet_costs_what_the_sheet_holds_not_what_the_range_spans(sheet):
    whole_column = Range(sheet, 0, 0, MAX_ROWS - 1, 0)
    assert len(whole_column) == MAX_ROWS
    assert sorted(whole_column.numbers()) == [1, 2.5, 7]
    assert Range(sheet, 100, 100, 200, 200).numbers() == []


def test_an_error_inside_the_range_is_raised_with_the_first_one_row_by_row():
    broken = FakeSheet({(0, 0): 1, (3, 0): ErrorValue("#N/A"), (1, 0): ErrorValue("#DIV/0!")})
    with pytest.raises(FormulaError) as raised:
        Range(broken, 0, 0, 5, 0).numbers()
    assert raised.value.code == "#DIV/0!"
    assert Range(broken, 0, 0, 5, 0).numbers(strict=False) == [1]


def test_dense_lists_every_position_row_by_row(sheet):
    assert Range(sheet, 0, 0, 1, 1).dense() == ((1, None), (2.5, 10))
    assert list(Range(sheet, 0, 0, 1, 1)) == [1, None, 2.5, 10]


def test_dense_refuses_a_range_too_big_to_list(sheet):
    with pytest.raises(FormulaError):
        Range(sheet, 0, 0, MAX_ROWS - 1, 100).dense()


def test_a_vector_ends_where_the_sheet_ends(sheet):
    assert Range(sheet, 0, 0, MAX_ROWS - 1, 0).vector() == [1, 2.5, "x", True, None, 7]
    assert Range(sheet, 1, 0, 1, 1).vector() == [2.5, 10]
    with pytest.raises(FormulaError):
        Range(sheet, 0, 0, 1, 1).vector()


def test_parts_are_counted_from_the_corner(sheet):
    area = Range(sheet, 1, 0, 3, 1)
    assert area.at(0, 1) == 10
    assert area.column(0).vector() == [2.5, "x", True]
    assert area.row(0).dense() == ((2.5, 10),)
    assert area.sub(1, 0, 2, 0).numbers() == []


def test_a_single_value_is_a_range_of_one_cell():
    assert Range.of_value(5).numbers() == [5]
    assert Range.of_value(None).dense() == ((None,),)
    assert (Range.of_value("a").n_rows, Range.of_value("a").n_cols) == (1, 1)


def test_cells_come_row_by_row_with_positions_relative_to_the_range(sheet):
    assert Range(sheet, 1, 0, 2, 1).cells() == [(0, 0, 2.5), (0, 1, 10), (1, 0, "x")]
