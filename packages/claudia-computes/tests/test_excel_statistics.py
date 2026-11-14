"""Statistics: spread and averages (the A versions), ranks, percentiles, regression and correlation, shape.

The expected numbers come from Microsoft's documentation or were computed with scipy (hard-coded here: the tests need
no extra package)."""

from __future__ import annotations

import math

from excel_helpers import cases, check, code, column, put, row

D = column("A1", [3, 7, 8, 5, 12, 14, 21, 13, 18])  # mean 11.2222, sample variance 35.9444
S = column("A1", [3, 4, 5, 2, 3, 4, 5, 6, 4, 7])
Y = [2, 3, 9, 1, 8, 7, 5]
X = [6, 5, 11, 7, 5, 4, 4]
XY = {**column("A1", Y), **column("B1", X)}
CP = {**column("A1", [3, 2, 4, 5, 6]), **column("B1", [9, 7, 12, 15, 17])}

# -- the names that say sample or population, and the A functions ----------------------------------------------------
SPREAD = (
    ("=STDEV.S(A1:A9)", 5.995368582868316, D),
    ("=VAR.S(A1:A9)", 35.94444444444444, D),
    ("=STDEVP(A1:A9)", math.sqrt(35.94444444444444 * 8 / 9), D),
    ("=VARP(A1:A9)", 35.94444444444444 * 8 / 9, D),
    ("=STDEV.S(A1:A1)", "#DIV/0!", D),
    ("=VAR.S(5)", "#DIV/0!", None),
)


@cases(*SPREAD)
def test_sample_and_population_spread_by_their_other_names(formula, expected, cells):
    check(formula, expected, cells)


MIXED = {**column("A1", [10, 7, 9, 2]), "A5": "Not available"}
LOGICALS = {"A1": 0, "A2": 0.2, "A3": 0.5, "A4": 0.4, "A5": True}
THOUSANDS = column("A1", [1345, 1301, 1368, 1322, 1310, 1370, 1318, 1350, 1303, 1299])
A_FUNCTIONS = (
    ("=AVERAGEA(A1:A5)", 5.6, MIXED),  # (text counts as 0)
    ("=AVERAGEA(A1:A5)", (0 + 0.2 + 0.5 + 0.4 + 1) / 5, LOGICALS),  # (TRUE counts as 1)
    ("=MAXA(A1:A5)", 1, LOGICALS),
    ("=MINA(A1:A5)", 0, {**LOGICALS, "A5": False}),
    ("=MAXA(A1:A5)", 10, MIXED),
    ("=MINA(A1:A5)", 0, MIXED),
    ("=STDEVA(A1:A10)", 27.463915719843495, THOUSANDS),
    ("=STDEVPA(A1:A10)", math.sqrt(678.8399999999999), THOUSANDS),
    ("=VARA(A1:A10)", 27.463915719843495**2, THOUSANDS),
    ("=VARPA(A1:A10)", 678.8399999999999, THOUSANDS),
    ("=AVERAGEA(A1:A2)", "#DIV/0!", None),
)


@cases(*A_FUNCTIONS)
def test_the_a_functions_count_text_as_0_and_true_as_1(formula, expected, cells):
    check(formula, expected, cells)


def test_vara_counts_logicals():
    # 1, TRUE (1), FALSE (0): mean 2/3, squared deviations 1/9 + 1/9 + 4/9 = 6/9, divided by 2
    check("=VARA(A1:A3)", (6 / 9) / 2, {"A1": 1, "A2": True, "A3": False})


# -- rank -------------------------------------------------------------------------------------------------------------
RANKS = column("A1", [7, 3.5, 3.5, 1, 2])
RANKING = (
    ("=RANK.EQ(3.5, A1:A5, 1)", 3),
    ("=RANK.EQ(3.5, A1:A5)", 2),
    ("=RANK.EQ(7, A1:A5)", 1),
    ("=RANK.EQ(7, A1:A5, 1)", 5),
    ("=RANK(1, A1:A5)", 5),
    ("=RANK(2, A1:A5, 1)", 2),
    ("=RANK.AVG(3.5, A1:A5, 1)", 3.5),
    ("=RANK.AVG(3.5, A1:A5)", 2.5),
    ("=RANK.AVG(7, A1:A5)", 1),
    ("=RANK.EQ(99, A1:A5)", "#N/A"),
    ("=RANK.AVG(99, A1:A5)", "#N/A"),
)


@cases(*[(f, e, RANKS) for f, e in RANKING])
def test_rank(formula, expected, cells):
    check(formula, expected, cells)


# -- percentiles, quartiles, percent rank -------------------------------------------------------------------------------
PERCENTILES = (
    ("=PERCENTILE.INC(A1:A9, 0.25)", 7.0),
    ("=PERCENTILE(A1:A9, 0.9)", 18.6),
    ("=PERCENTILE.INC(A1:A9, 0.1)", 4.6),
    ("=PERCENTILE.INC(A1:A9, 0)", 3),
    ("=PERCENTILE.INC(A1:A9, 1)", 21),
    ("=PERCENTILE.INC(A1:A9, 1.1)", "#NUM!"),
    ("=PERCENTILE.EXC(A1:A9, 0.25)", 6.0),
    ("=PERCENTILE.EXC(A1:A9, 0.9)", 21.0),
    ("=PERCENTILE.EXC(A1:A9, 0.1)", 3.0),
    ("=PERCENTILE.EXC(A1:A9, 0.05)", "#NUM!"),
    ("=PERCENTILE.EXC(A1:A9, 0.95)", "#NUM!"),
    ("=QUARTILE.INC(A1:A9, 0)", 3),
    ("=QUARTILE(A1:A9, 1)", 7),
    ("=QUARTILE.INC(A1:A9, 2)", 12),
    ("=QUARTILE.INC(A1:A9, 3)", 14),
    ("=QUARTILE.INC(A1:A9, 4)", 21),
    ("=QUARTILE.INC(A1:A9, 5)", "#NUM!"),
    ("=QUARTILE.EXC(A1:A9, 1)", 6),
    ("=QUARTILE.EXC(A1:A9, 2)", 12),
    ("=QUARTILE.EXC(A1:A9, 3)", 16),
    ("=QUARTILE.EXC(A1:A9, 0)", "#NUM!"),
    ("=QUARTILE.EXC(A1:A9, 4)", "#NUM!"),
    ("=PERCENTILE.INC(B1:B2, 0.5)", "#NUM!"),
)


@cases(*[(f, e, D) for f, e in PERCENTILES])
def test_percentiles_and_quartiles(formula, expected, cells):
    check(formula, expected, cells)


def test_the_median_is_the_second_quartile_and_the_fiftieth_percentile():
    check("=MEDIAN(A1:A9)", 12, D)
    check("=PERCENTILE.INC(A1:A9, 0.5)", 12, D)


RANK_DATA = column("A1", [13, 12, 11, 8, 4, 3, 2, 1, 1, 1])
PERCENT_RANK = (
    ("=PERCENTRANK.INC(A1:A10, 2)", 0.333),
    ("=PERCENTRANK(A1:A10, 4)", 0.555),
    ("=PERCENTRANK.INC(A1:A10, 8)", 0.666),
    ("=PERCENTRANK.INC(A1:A10, 5)", 0.583),  # (between 4 and 8: interpolated)
    ("=PERCENTRANK.INC(A1:A10, 5, 1)", 0.5),  # (cut, not rounded, to one digit)
    ("=PERCENTRANK.INC(A1:A10, 13)", 1),
    ("=PERCENTRANK.INC(A1:A10, 1)", 0),
    ("=PERCENTRANK.INC(A1:A10, 14)", "#N/A"),
    ("=PERCENTRANK.INC(A1:A10, 0)", "#N/A"),
    ("=PERCENTRANK.INC(A1:A10, 2, 0)", "#NUM!"),
)


@cases(*[(f, e, RANK_DATA) for f, e in PERCENT_RANK])
def test_percent_rank_inclusive(formula, expected, cells):
    check(formula, expected, cells)


def test_percent_rank_exclusive():
    data = column("A1", [1, 2, 3, 6, 6, 6, 7, 8, 9])
    check("=PERCENTRANK.EXC(A1:A9, 8)", 0.8, data)
    check("=PERCENTRANK.EXC(A1:A9, 3)", 0.3, data)
    check("=PERCENTRANK.EXC(A1:A9, 5)", 0.366, data)
    check("=PERCENTRANK.EXC(A1:A9, 1)", 0.1, data)
    check("=PERCENTRANK.EXC(A1:A9, 0)", "#N/A", data)
    check("=PERCENTRANK.EXC(A1:A9, 20)", "#N/A", data)


# -- modes ------------------------------------------------------------------------------------------------------------
def test_mode_is_the_most_frequent_number_and_the_first_one_on_a_tie():
    check("=MODE(A1:A6)", 4, column("A1", [5.6, 4, 4, 3, 2, 4]))
    check("=MODE.SNGL(A1:A6)", 2, column("A1", [1, 2, 2, 3, 3, 4]))
    check("=MODE.SNGL(A1:A3)", "#N/A", column("A1", [1, 2, 3]))
    check("=MODE.SNGL(A1:A3)", 2, {"A1": 2, "A2": "x", "A3": 2})


# -- averages and deviations -----------------------------------------------------------------------------------------
def test_deviations_and_means_from_the_documentation():
    check("=AVEDEV(A1:A7)", 1.0204081632653061, column("A1", [4, 5, 6, 7, 5, 4, 3]))
    check("=DEVSQ(A1:A7)", 48, column("A1", [4, 5, 8, 7, 11, 4, 3]))
    check("=GEOMEAN(A1:A7)", 5.476986969656962, column("A1", [4, 5, 8, 7, 11, 4, 3]))
    check("=HARMEAN(A1:A7)", 5.028375962061728, column("A1", [4, 5, 8, 7, 11, 4, 3]))


def test_geometric_and_harmonic_means_need_positive_numbers():
    assert code("=GEOMEAN(A1:A2)", column("A1", [1, 0])) == "#NUM!"
    assert code("=HARMEAN(A1:A2)", column("A1", [1, -2])) == "#NUM!"
    assert code("=GEOMEAN(A1:A2)", column("A1", ["x", "y"])) == "#NUM!"


def test_trimmean_cuts_the_same_number_off_both_ends():
    data = column("A1", [4, 5, 6, 7, 2, 3, 4, 5, 1, 2, 3])
    check("=TRIMMEAN(A1:A11, 0.2)", 3.7777777777777777, data)
    check("=TRIMMEAN(A1:A11, 0)", sum([4, 5, 6, 7, 2, 3, 4, 5, 1, 2, 3]) / 11, data)
    check("=TRIMMEAN(A1:A11, 0.1)", sum([4, 5, 6, 7, 2, 3, 4, 5, 1, 2, 3]) / 11, data)  # (1.1 points: none, an even number only)
    assert code("=TRIMMEAN(A1:A11, 1)", data) == "#NUM!"
    assert code("=TRIMMEAN(A1:A11, -0.1)", data) == "#NUM!"


def test_skewness_and_kurtosis_from_the_documentation():
    check("=SKEW(A1:A10)", 0.3595430714067974, S)
    check("=SKEW.P(A1:A10)", 0.30319333935414394, S)
    check("=KURT(A1:A10)", -0.15179963720841405, S)
    assert code("=SKEW(A1:A2)", column("A1", [1, 2])) == "#DIV/0!"
    assert code("=KURT(A1:A3)", column("A1", [1, 2, 4])) == "#DIV/0!"
    assert code("=SKEW(A1:A3)", column("A1", [2, 2, 2])) == "#DIV/0!"


def test_standardize():
    check("=STANDARDIZE(42, 40, 1.5)", 1.3333333333333333)
    assert code("=STANDARDIZE(42, 40, 0)") == "#NUM!"


def test_prob():
    cells = {**column("A1", [0, 1, 2, 3]), **column("B1", [0.2, 0.3, 0.1, 0.4])}
    check("=PROB(A1:A4, B1:B4, 2)", 0.1, cells)
    check("=PROB(A1:A4, B1:B4, 1, 3)", 0.8, cells)
    check("=PROB(A1:A4, B1:B4, 5)", 0, cells)
    check("=PROB(A1:A4, B1:B4, 3, 1)", 0, cells)
    assert code("=PROB(A1:A4, B1:B4, 1)", {**cells, "B1": 0.5}) == "#NUM!"  # (the probabilities must add up to 1)
    assert code("=PROB(A1:A4, B1:B3, 1)", cells) == "#N/A"


# -- regression and correlation --------------------------------------------------------------------------------------------
REGRESSION = (
    ("=SLOPE(A1:A7, B1:B7)", 0.3055555555555555),
    ("=INTERCEPT(A1:A7, B1:B7)", 3.166666666666667),
    ("=RSQ(A1:A7, B1:B7)", 0.05795019157088121),
    ("=CORREL(A1:A7, B1:B7)", 0.24072846024282465),
    ("=PEARSON(A1:A7, B1:B7)", 0.24072846024282465),
    ("=STEYX(A1:A7, B1:B7)", 3.305718950210041),
    ("=FORECAST(30, A1:A7, B1:B7)", 12.333333333333332),
    ("=FORECAST.LINEAR(30, A1:A7, B1:B7)", 12.333333333333332),
    ("=FORECAST(6, A1:A7, B1:B7)", 3.166666666666667 + 0.3055555555555555 * 6),
)


@cases(*[(f, e, XY) for f, e in REGRESSION])
def test_regression_and_correlation(formula, expected, cells):
    check(formula, expected, cells)


def test_covariance_and_correlation_from_the_documentation():
    check("=COVARIANCE.P(A1:A5, B1:B5)", 5.2, CP)
    check("=COVAR(A1:A5, B1:B5)", 5.2, CP)
    check("=COVARIANCE.S(A1:A5, B1:B5)", 6.5, CP)
    check("=CORREL(A1:A5, B1:B5)", 0.9970544855015815, CP)


def test_regression_refuses_data_that_cannot_be_fitted():
    assert code("=SLOPE(A1:A3, B1:B2)", {**column("A1", [1, 2, 3]), **column("B1", [1, 2])}) == "#N/A"
    assert code("=SLOPE(A1:A3, B1:B3)", {**column("A1", [1, 2, 3]), **column("B1", [4, 4, 4])}) == "#DIV/0!"
    assert code("=CORREL(A1:A1, B1:B1)", {"A1": 1, "B1": 1}) == "#DIV/0!"
    assert code("=STEYX(A1:A2, B1:B2)", {**column("A1", [1, 2]), **column("B1", [1, 2])}) == "#DIV/0!"
    assert code("=RSQ(A1:A3, B1:B3)", {**column("A1", [1, 1, 1]), **column("B1", [1, 2, 3])}) == "#DIV/0!"


def test_pairs_with_text_or_gaps_are_left_out():
    cells = {**column("A1", [1, 2, "x", 4, 5]), **column("B1", [2, 4, 6, None, 10])}
    check("=SLOPE(A1:A5, B1:B5)", 0.5, cells)  # (the pairs (1,2), (2,4), (5,10) lie on y = x/2)
    check("=CORREL(A1:A5, B1:B5)", 1.0, cells)


# -- the subtotal and the aggregate ---------------------------------------------------------------------------------
LIST = column("A1", [10, 20, 30, 40])
SUBTOTALS = (
    ("=SUBTOTAL(1, A1:A4)", 25),
    ("=SUBTOTAL(2, A1:A4)", 4),
    ("=SUBTOTAL(3, A1:A4)", 4),
    ("=SUBTOTAL(4, A1:A4)", 40),
    ("=SUBTOTAL(5, A1:A4)", 10),
    ("=SUBTOTAL(6, A1:A4)", 240000),
    ("=SUBTOTAL(7, A1:A4)", 12.909944487358056),
    ("=SUBTOTAL(8, A1:A4)", 11.180339887498949),
    ("=SUBTOTAL(9, A1:A4)", 100),
    ("=SUBTOTAL(10, A1:A4)", 166.66666666666666),
    ("=SUBTOTAL(11, A1:A4)", 125),
    ("=SUBTOTAL(109, A1:A4)", 100),
    ("=SUBTOTAL(9, A1:A2, A3:A4)", 100),
    ("=SUBTOTAL(12, A1:A4)", "#VALUE!"),
    ("=SUBTOTAL(0, A1:A4)", "#VALUE!"),
)


@cases(*[(f, e, LIST) for f, e in SUBTOTALS])
def test_subtotal(formula, expected, cells):
    check(formula, expected, cells)


def test_subtotal_passes_on_an_error_in_the_range():
    from claudia_computes.values import ErrorValue

    assert code("=SUBTOTAL(9, A1:A2)", {"A1": 1, "A2": ErrorValue("#DIV/0!")}) in {"#DIV/0!", "#VALUE!"}


AGGREGATES = (
    ("=AGGREGATE(9, 4, A1:A4)", 100),
    ("=AGGREGATE(1, 6, A1:A4)", 25),
    ("=AGGREGATE(4, 4, A1:A4)", 40),
    ("=AGGREGATE(12, 4, A1:A4)", 25),
    ("=AGGREGATE(14, 4, A1:A4, 1)", 40),
    ("=AGGREGATE(14, 4, A1:A4, 2)", 30),
    ("=AGGREGATE(15, 4, A1:A4, 1)", 10),
    ("=AGGREGATE(16, 4, A1:A4, 0.5)", 25),
    ("=AGGREGATE(17, 4, A1:A4, 1)", 17.5),
    ("=AGGREGATE(18, 4, A1:A4, 0.5)", 25),
    ("=AGGREGATE(19, 4, A1:A4, 1)", 12.5),
    ("=AGGREGATE(14, 4, A1:A4)", "#VALUE!"),  # (these need k)
    ("=AGGREGATE(20, 4, A1:A4)", "#VALUE!"),
    ("=AGGREGATE(9, 8, A1:A4)", "#VALUE!"),
)


@cases(*[(f, e, LIST) for f, e in AGGREGATES])
def test_aggregate(formula, expected, cells):
    check(formula, expected, cells)


def test_aggregate_can_skip_errors():
    from claudia_computes.values import ErrorValue

    cells = {"A1": 1, "A2": ErrorValue("#N/A"), "A3": 5}
    check("=AGGREGATE(9, 6, A1:A3)", 6, cells)
    check("=AGGREGATE(9, 2, A1:A3)", 6, cells)
    assert code("=AGGREGATE(9, 4, A1:A3)", cells) == "#N/A"
    assert code("=SUBTOTAL(9, A1:A3)", cells) == "#N/A"
