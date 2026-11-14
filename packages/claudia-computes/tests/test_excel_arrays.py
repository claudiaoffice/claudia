"""Functions that answer with several cells: building, reshaping, sorting, filtering and matrix algebra."""

from __future__ import annotations

import math

import pytest
from excel_helpers import array, cases, check, code, column, put, row

from claudia_computes.values import ErrorValue

NA = "#N/A"


# -- SEQUENCE -------------------------------------------------------------------------------------------------------
SEQUENCE = (
    ("=SEQUENCE(3)", [[1], [2], [3]]),
    ("=SEQUENCE(2, 3)", [[1, 2, 3], [4, 5, 6]]),
    ("=SEQUENCE(2, 2, 10, 5)", [[10, 15], [20, 25]]),
    ("=SEQUENCE(3, 1, 5, -2)", [[5], [3], [1]]),
    ("=SEQUENCE(1, 3, 0, 0.5)", [[0, 0.5, 1]]),
    ("=SEQUENCE(0)", "#VALUE!"),
    ("=SEQUENCE(2, 0)", "#VALUE!"),
    ("=SEQUENCE(-1)", "#VALUE!"),
)


@cases(*SEQUENCE)
def test_sequence(formula, expected, cells):
    check(formula, expected, cells)


# -- TRANSPOSE, VSTACK, HSTACK ----------------------------------------------------------------------------------------
GRID = put("A1", [[1, 2, 3], [4, 5, 6]])


def test_transpose_swaps_rows_and_columns():
    check("=TRANSPOSE(A1:C2)", [[1, 4], [2, 5], [3, 6]], GRID)
    check("=TRANSPOSE(A1:C1)", [[1], [2], [3]], GRID)
    check("=TRANSPOSE(5)", 5)


def test_transposing_twice_gives_the_start():
    check("=TRANSPOSE(TRANSPOSE(A1:C2))", [[1, 2, 3], [4, 5, 6]], GRID)


def test_an_empty_cell_in_a_result_is_zero():
    check("=TRANSPOSE(A1:B1)", [[1], [0]], {"A1": 1})


def test_vstack_puts_ranges_one_below_the_other():
    cells = {**put("A1", [[1, 2], [3, 4]]), **put("A4", [[5, 6]])}
    check("=VSTACK(A1:B2, A4:B4)", [[1, 2], [3, 4], [5, 6]], cells)


def test_vstack_pads_the_narrower_range_with_na():
    cells = {**put("A1", [[1, 2]]), **put("A4", [[3]])}
    check("=VSTACK(A1:B1, A4)", [[1, 2], [3, NA]], cells)


def test_hstack_puts_ranges_side_by_side_and_pads_the_shorter_with_na():
    cells = {**put("A1", [[1], [2]]), **put("C1", [[3], [4], [5]])}
    check("=HSTACK(A1:A2, C1:C3)", [[1, 3], [2, 4], [NA, 5]], cells)


def test_stacking_values_and_results():
    check("=VSTACK(1, 2)", [[1], [2]])
    check('=HSTACK("a", SEQUENCE(2))', [["a", 1], [NA, 2]])


# -- SORT, SORTBY -----------------------------------------------------------------------------------------------------
ROWS = put("A1", [["b", 2], ["a", 3], ["c", 1]])


def test_sort_orders_by_the_first_column_by_default():
    check("=SORT(A1:B3)", [["a", 3], ["b", 2], ["c", 1]], ROWS)


def test_sort_by_another_column_and_descending():
    check("=SORT(A1:B3, 2)", [["c", 1], ["b", 2], ["a", 3]], ROWS)
    check("=SORT(A1:B3, 2, -1)", [["a", 3], ["b", 2], ["c", 1]], ROWS)
    check("=SORT(A1:B3, , -1)", [["c", 1], ["b", 2], ["a", 3]], ROWS)


def test_sort_by_column_sorts_the_columns():
    check("=SORT(A1:C1, 1, 1, TRUE)", [[1, 2, 3]], row("A1", [3, 1, 2]))
    check("=SORT(A1:C2, 1, -1, TRUE)", [[3, 2, 1], ["c", "b", "a"]], put("A1", [[2, 3, 1], ["b", "c", "a"]]))


def test_sort_puts_numbers_before_text_before_logicals_and_ignores_case():
    cells = column("A1", ["b", True, 5, "A", -1])
    check("=SORT(A1:A5)", [[-1], [5], ["A"], ["b"], [True]], cells)


def test_sort_is_stable():
    cells = put("A1", [[1, "x"], [0, "y"], [1, "z"], [0, "w"]])
    check("=SORT(A1:B4)", [[0, "y"], [0, "w"], [1, "x"], [1, "z"]], cells)


def test_sort_keeps_an_error_and_puts_it_last():
    cells = column("A1", [3, 1])
    cells["A3"] = ErrorValue("#DIV/0!")
    result = array("=SORT(A1:A3)", cells)
    assert result[0] == [1] and result[1] == [3] and result[2][0].code == "#DIV/0!"


@pytest.mark.parametrize("formula", ["=SORT(A1:B3, 3)", "=SORT(A1:B3, 0)", "=SORT(A1:B3, 1, 2)", "=SORT(A1:B3, 1, 0)"])
def test_sort_refuses_a_column_or_an_order_that_does_not_exist(formula):
    assert code(formula, ROWS) == "#VALUE!"


def test_sortby_orders_by_another_range():
    cells = {**column("A1", ["x", "y", "z"]), **column("B1", [3, 1, 2])}
    check("=SORTBY(A1:A3, B1:B3)", [["y"], ["z"], ["x"]], cells)
    check("=SORTBY(A1:A3, B1:B3, -1)", [["x"], ["z"], ["y"]], cells)


def test_sortby_with_two_keys():
    cells = {**column("A1", ["p", "q", "r", "s"]), **column("B1", [1, 1, 2, 2]), **column("C1", [9, 8, 7, 6])}
    check("=SORTBY(A1:A4, B1:B4, 1, C1:C4, 1)", [["q"], ["p"], ["s"], ["r"]], cells)
    check("=SORTBY(A1:A4, B1:B4, -1, C1:C4, 1)", [["s"], ["r"], ["q"], ["p"]], cells)


def test_sortby_needs_keys_of_the_same_length():
    cells = {**column("A1", [1, 2, 3]), **column("B1", [1, 2])}
    assert code("=SORTBY(A1:A3, B1:B2)", cells) == "#VALUE!"


# -- UNIQUE ------------------------------------------------------------------------------------------------------------
def test_unique_keeps_the_first_of_each_value_in_order():
    check("=UNIQUE(A1:A6)", [[1], [2], [3]], column("A1", [1, 2, 2, 3, 1, 3]))


def test_unique_ignores_the_case_of_text():
    check("=UNIQUE(A1:A3)", [["a"], ["b"]], column("A1", ["a", "A", "b"]))


def test_unique_exactly_once_keeps_only_values_that_occur_once():
    check("=UNIQUE(A1:A6, FALSE, TRUE)", [[3]], column("A1", [1, 2, 2, 3, 1, 1]))


def test_unique_of_rows_and_of_columns():
    check("=UNIQUE(A1:B4)", [[1, "a"], [2, "b"], [1, "b"]], put("A1", [[1, "a"], [2, "b"], [1, "a"], [1, "b"]]))
    check("=UNIQUE(A1:D1, TRUE)", [[1, 2]], row("A1", [1, 2, 1, 2]))


def test_unique_with_nothing_once_has_no_result():
    assert code("=UNIQUE(A1:A2, FALSE, TRUE)", column("A1", [1, 1])) == NA


# -- FILTER ------------------------------------------------------------------------------------------------------------
PEOPLE = put("A1", [["ann", 30], ["bob", 25], ["cy", 41]])


def test_filter_keeps_the_rows_where_the_condition_is_true():
    check("=FILTER(A1:B3, B1:B3>28)", [["ann", 30], ["cy", 41]], PEOPLE)


def test_filter_reads_numbers_as_conditions():
    check("=FILTER(A1:A3, B1:B3-25)", [["ann"], ["cy"]], PEOPLE)


def test_filter_keeps_columns_when_the_condition_is_a_row():
    check("=FILTER(A1:C1, A2:C2)", [[1, 3]], {**row("A1", [1, 2, 3]), **row("A2", [True, False, True])})


def test_filter_says_what_to_give_when_nothing_matches():
    check('=FILTER(A1:A3, B1:B3>99, "none")', "none", PEOPLE)
    assert code("=FILTER(A1:A3, B1:B3>99)", PEOPLE) == NA


def test_filter_needs_a_condition_that_fits():
    assert code("=FILTER(A1:B3, B1:B2>0)", PEOPLE) == "#VALUE!"
    assert code("=FILTER(A1:B3, A1:A3)", PEOPLE) == "#VALUE!"  # (text is not a condition)


# -- TEXTSPLIT --------------------------------------------------------------------------------------------------------
SPLITS = (
    ('=TEXTSPLIT("a,b,c", ",")', [["a", "b", "c"]]),
    ('=TEXTSPLIT("a,b;c,d", ",", ";")', [["a", "b"], ["c", "d"]]),
    ('=TEXTSPLIT("a,b;c", ",", ";")', [["a", "b"], ["c", NA]]),
    ('=TEXTSPLIT("a,b;c", ",", ";", FALSE, 0, "-")', [["a", "b"], ["c", "-"]]),
    ('=TEXTSPLIT("a;b;c", , ";")', [["a"], ["b"], ["c"]]),
    ('=TEXTSPLIT("a,,b", ",")', [["a", "", "b"]]),
    ('=TEXTSPLIT("a,,b", ",", , TRUE)', [["a", "b"]]),
    ('=TEXTSPLIT("aXbxc", "x", , FALSE, 1)', [["a", "b", "c"]]),
    ('=TEXTSPLIT("aXbxc", "x")', [["aXb", "c"]]),
    ('=TEXTSPLIT("a, b", ", ")', [["a", "b"]]),
    ('=TEXTSPLIT("none", ",")', "none"),
    ('=TEXTSPLIT("a-b_c", A1:B1)', [["a", "b", "c"]]),
)
SPLIT_CELLS = row("A1", ["-", "_"])


@pytest.mark.parametrize("formula, expected", SPLITS, ids=[s[0] for s in SPLITS])
def test_textsplit(formula, expected):
    check(formula, expected, SPLIT_CELLS)


def test_textsplit_needs_a_delimiter():
    assert code('=TEXTSPLIT("abc")') == "#VALUE!"
    assert code('=TEXTSPLIT("abc", "")') == "#VALUE!"


# -- matrices ----------------------------------------------------------------------------------------------------------
A = put("A1", [[1, 2], [3, 4]])
B = put("D1", [[5, 6], [7, 8]])


def test_mmult_multiplies_matrices():
    check("=MMULT(A1:B2, D1:E2)", [[19, 22], [43, 50]], {**A, **B})
    check("=MMULT(A1:B2, G1:G2)", [[17], [39]], {**A, **column("G1", [5, 6])})
    check("=MMULT(A1:C1, E1:E3)", 14, {**row("A1", [1, 2, 3]), **column("E1", [1, 2, 3])})


def test_mmult_needs_matching_sizes_and_numbers():
    assert code("=MMULT(A1:B2, G1:G3)", {**A, **column("G1", [1, 2, 3])}) == "#VALUE!"
    assert code("=MMULT(A1:B2, D1:E2)", {**A, **put("D1", [["x", 6], [7, 8]])}) == "#VALUE!"
    assert code("=MMULT(A1:B2, D1:E2)", A) == "#VALUE!"  # (empty cells are not numbers here)


def test_mdeterm():
    check("=MDETERM(A1:B2)", -2, A)
    check("=MDETERM(A1:C3)", 24, put("A1", [[2, 0, 0], [0, 3, 0], [0, 0, 4]]))
    check("=MDETERM(A1:B2)", 0, put("A1", [[1, 2], [2, 4]]))
    check("=MDETERM(A1:C3)", 1, put("A1", [[3, 6, 1], [1, 1, 0], [3, 10, 2]]))
    check("=MDETERM(A1:B2)", -1.25, put("A1", [[0.5, 1], [2, 1.5]]))
    assert code("=MDETERM(A1:C2)", put("A1", [[1, 2, 3], [4, 5, 6]])) == "#VALUE!"


def test_minverse():
    check("=MINVERSE(A1:B2)", [[-2, 1], [1.5, -0.5]], A)
    inverse = array("=MINVERSE(A1:B2)", put("A1", [[4, -1], [2, 3]]))
    expected = [[3 / 14, 1 / 14], [-2 / 14, 4 / 14]]
    for got, want in zip(inverse, expected, strict=True):
        assert got == pytest.approx(want, rel=1e-12)


def test_minverse_of_a_singular_matrix_is_num():
    assert code("=MINVERSE(A1:B2)", put("A1", [[1, 2], [2, 4]])) == "#NUM!"
    assert code("=MINVERSE(A1:C2)", put("A1", [[1, 2, 3], [4, 5, 6]])) == "#VALUE!"


def test_a_matrix_times_its_inverse_is_the_identity():
    cells = put("A1", [[2, 1, 0], [1, 3, 1], [0, 1, 4]])
    result = array("=MMULT(A1:C3, MINVERSE(A1:C3))", cells)
    for i, line in enumerate(result):
        for j, got in enumerate(line):
            assert got == pytest.approx(1.0 if i == j else 0.0, abs=1e-12)


def test_munit_is_the_identity():
    check("=MUNIT(3)", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    check("=MUNIT(1)", 1)
    assert code("=MUNIT(0)") == "#VALUE!"


# -- FREQUENCY, MODE.MULT ---------------------------------------------------------------------------------------------
def test_frequency_from_the_documentation():
    data = column("A1", [79, 85, 78, 85, 50, 81, 95, 88, 97])
    bins = column("B1", [70, 79, 89])
    check("=FREQUENCY(A1:A9, B1:B3)", [[1], [2], [4], [2]], {**data, **bins})


def test_frequency_skips_text_and_counts_values_equal_to_a_limit_in_that_bin():
    check("=FREQUENCY(A1:A6, B1:B2)", [[2], [1], [2]], {**column("A1", [1, "x", 4, 5, 9, 10]), **column("B1", [4, 6])})


def test_mode_mult_gives_every_mode_in_order_of_first_appearance():
    check("=MODE.MULT(A1:A7)", [[2], [3]], column("A1", [1, 2, 3, 2, 3, 4, 5]))
    check("=MODE.MULT(A1:A4)", 7, column("A1", [7, 7, 8, 9]))
    assert code("=MODE.MULT(A1:A3)", column("A1", [1, 2, 3])) == NA


# -- regression: TREND, GROWTH, LINEST, LOGEST -------------------------------------------------------------------------
Y = [2, 4, 5, 4, 5]
X = [1, 2, 3, 4, 5]
FIT = {**column("A1", Y), **column("B1", X)}  # y = 2.2 + 0.6 x


def test_trend_continues_the_straight_line():
    check("=TREND(A1:A5, B1:B5, 6)", 5.8, FIT)
    check("=TREND(A1:A5, B1:B5)", [[2.8], [3.4], [4.0], [4.6], [5.2]], FIT)
    check("=TREND(A1:A5)", [[2.8], [3.4], [4.0], [4.6], [5.2]], FIT)  # (x is 1, 2, 3 ... when left out)
    check("=TREND(A1:A5, B1:B5, SEQUENCE(2, 1, 6))", [[5.8], [6.4]], FIT)


def test_trend_through_the_origin():
    check("=TREND(A1:A5, B1:B5, 6, FALSE)", 66 / 55 * 6, FIT)


def test_linest_gives_slope_and_intercept():
    check("=LINEST(A1:A5, B1:B5)", [[0.6, 2.2]], FIT)
    check("=LINEST(A1:A5, B1:B5, FALSE)", [[1.2, 0]], FIT)


def test_linest_statistics_match_the_textbook_values():
    stats = array("=LINEST(A1:A5, B1:B5, TRUE, TRUE)", FIT)
    assert len(stats) == 5 and all(len(line) == 2 for line in stats)
    assert stats[0] == pytest.approx([0.6, 2.2])
    assert stats[1] == pytest.approx([0.282842712474619, 0.938083151964686])  # standard errors of slope and intercept
    assert stats[2][0] == pytest.approx(0.6)  # r squared
    assert stats[2][1] == pytest.approx(0.894427190999916)  # standard error of y
    assert stats[3] == pytest.approx([4.5, 3])  # F and the degrees of freedom
    assert stats[4] == pytest.approx([3.6, 2.4])  # regression and residual sums of squares


def test_linest_with_two_variables_gives_the_coefficients_in_reverse_order():
    xs = put("B1", [[1, 1], [2, 1], [3, 2], [4, 3], [5, 5]])  # y = 1 + 2 x1 + 3 x2
    ys = column("A1", [1 + 2 * a + 3 * b for a, b in [(1, 1), (2, 1), (3, 2), (4, 3), (5, 5)]])
    result = array("=LINEST(A1:A5, B1:C5)", {**xs, **ys})
    assert result[0] == pytest.approx([3, 2, 1])


def test_linest_needs_matching_data():
    assert code("=LINEST(A1:A5, B1:B4)", FIT) == "#REF!"
    assert code("=LINEST(A1:A2, B1:B2)", {"A1": "x", "A2": 1, "B1": 1, "B2": 2}) == "#VALUE!"
    assert code("=LINEST(A1:A1, B1:B1)", {"A1": 1, "B1": 1}) == "#DIV/0!"


def test_growth_and_logest_fit_an_exponential_curve():
    cells = {**column("A1", [6, 18, 54]), **column("B1", [1, 2, 3])}  # y = 2 * 3^x
    check("=GROWTH(A1:A3, B1:B3, 4)", 162, cells)
    check("=GROWTH(A1:A3, B1:B3)", [[6], [18], [54]], cells)
    check("=LOGEST(A1:A3, B1:B3)", [[3, 2]], cells)
    assert code("=GROWTH(A1:A3, B1:B3)", {**cells, "A2": -1}) == "#NUM!"


def test_logest_statistics_are_those_of_the_straight_line_through_the_logs():
    cells = {**column("A1", [3, 5, 12, 20]), **column("B1", [1, 2, 3, 4])}
    stats = array("=LOGEST(A1:A4, B1:B4, TRUE, TRUE)", cells)
    logs = [math.log(v) for v in (3, 5, 12, 20)]
    n, mean_x, mean_y = 4, 2.5, sum(logs) / 4
    sxx = sum((x - mean_x) ** 2 for x in (1, 2, 3, 4))
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip((1, 2, 3, 4), logs, strict=True)) / sxx
    intercept = mean_y - slope * mean_x
    assert stats[0] == pytest.approx([math.exp(slope), math.exp(intercept)])
    residual = sum((y - (intercept + slope * x)) ** 2 for x, y in zip((1, 2, 3, 4), logs, strict=True))
    se_slope = math.sqrt(residual / (n - 2) / sxx)
    assert stats[1][0] == pytest.approx(se_slope)
    assert stats[3][1] == 2
