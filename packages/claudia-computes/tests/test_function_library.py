"""The built-in functions: that they are all documented and their examples true, and the cases examples do not cover."""

from __future__ import annotations

import pytest

from claudia_computes.formula.forms import CORE_NAMES
from claudia_computes.functions.base import Example
from claudia_computes.functions.builtin import builtin_registry, check_examples, run_example
from claudia_computes.values import ErrorValue

REGISTRY = builtin_registry()


def run(formula: str, cells: dict | None = None):
    return run_example(REGISTRY, Example(formula, None, cells or {}))


def code(formula: str, cells: dict | None = None) -> str:
    result = run(formula, cells)
    assert isinstance(result, ErrorValue), f"{formula} gave {result!r}"
    return result.code


def test_every_builtin_has_a_description_an_example_and_a_true_one():
    assert len(REGISTRY) > 60
    for bound in REGISTRY:
        assert bound.description, bound.name
        assert bound.examples, bound.name
    assert check_examples(REGISTRY) == []


def test_the_core_names_are_not_taken_by_the_library():
    assert not {bound.name for bound in REGISTRY} & CORE_NAMES


def test_tooltips_and_help_come_from_the_signature_and_the_examples():
    bound = REGISTRY.get("ROUND")
    assert bound.get_tooltip().startswith("ROUND(number, digits?): ")
    assert "=ROUND(2.675, 2)  gives  2.68" in bound.get_help()


# -- aggregates ------------------------------------------------------------------------------------------------
def test_sum_skips_text_and_blanks_and_raises_errors():
    cells = {"A1": 1, "A2": "x", "A4": 2.5}
    assert run("=SUM(A1:A9)", cells) == 3.5
    assert run("=SUM(A:A)", cells) == 3.5  # (a whole column costs what it holds)
    assert code("=SUM(A1:A2)", {"A1": ErrorValue("#N/A")}) == "#N/A"


def test_sum_of_decimals_does_not_depend_on_the_order():
    cells = {"A1": 0.1, "A2": 0.2, "A3": 0.3}
    assert run("=SUM(A1:A3)", cells) == 0.6000000000000001 or run("=SUM(A1:A3)", cells) == 0.6
    assert run("=SUM(A1:A3)", cells) == run("=SUM(A3, A2, A1)", cells)


def test_whole_number_sums_stay_whole():
    assert type(run("=SUM(A1:A2)", {"A1": 1, "A2": 2})) is int


def test_empty_aggregates():
    assert run("=SUM(A1:A3)") == 0
    assert run("=MAX(A1:A3)") == 0
    assert code("=AVERAGE(A1:A3)") == "#DIV/0!"
    assert code("=MEDIAN(A1:A3)") == "#NUM!"
    assert code("=STDEV(A1)", {"A1": 1}) == "#DIV/0!"
    assert run("=STDEV.P(A1)", {"A1": 1}) == 0


def test_counting():
    cells = {"A1": 1, "A2": "x", "A3": True, "A4": ErrorValue("#N/A")}
    assert run("=COUNT(A1:A5)", cells) == 1
    assert run("=COUNTA(A1:A5)", cells) == 4
    assert run("=COUNTBLANK(A1:A5)", cells) == 1


def test_large_small_and_product_and_sumproduct():
    cells = {"A1": 3, "A2": 1, "A3": 2, "B1": 10, "B2": 10, "B3": 10}
    assert run("=LARGE(A1:A3, 1)", cells) == 3
    assert run("=SMALL(A1:A3, 1)", cells) == 1
    assert code("=LARGE(A1:A3, 4)", cells) == "#NUM!"
    assert run("=PRODUCT(A1:A3)", cells) == 6
    assert run("=SUMPRODUCT(A1:A3, B1:B3)", cells) == 60
    assert code("=SUMPRODUCT(A1:A3, B1:B2)", cells) == "#VALUE!"


# -- criteria --------------------------------------------------------------------------------------------------
DATA = {"A1": "North", "A2": "south", "A3": "NORTH", "A4": 5, "B1": 1, "B2": 2, "B3": 3, "B4": 4}


@pytest.mark.parametrize(
    ("criterion", "count"),
    [
        ('"north"', 2),  # (without regard to case)
        ('"n*"', 2),
        ('"?outh"', 1),
        ('"<>north"', 3),  # south, 5, and the empty A5: a cell that is not "north" passes
        ('">4"', 1),
        ('"<=5"', 1),
        ("5", 1),
        ('"=5"', 1),
        ('"="', 1),  # the empty cell
        ('"<>"', 4),  # the cells that hold something
    ],
)
def test_countif_criteria(criterion, count):
    assert run(f"=COUNTIF(A1:A5, {criterion})", DATA) == count


def test_criteria_that_accept_empty_cells_count_them_without_listing_a_column():
    import time

    started = time.perf_counter()
    assert run('=COUNTIF(A1:A1000000, "<>north")', DATA) == 1_000_000 - 2
    assert time.perf_counter() - started < 0.05


def test_sumif_and_friends():
    assert run('=SUMIF(A1:A4, "north", B1:B4)', DATA) == 4
    assert run('=SUMIF(B1:B4, ">1")', DATA) == 9
    assert run('=SUMIFS(B1:B4, A1:A4, "north", B1:B4, ">1")', DATA) == 3
    assert run('=AVERAGEIF(A1:A4, "north", B1:B4)', DATA) == 2
    assert run('=AVERAGEIFS(B1:B4, A1:A4, "north")', DATA) == 2
    assert run('=MAXIFS(B1:B4, A1:A4, "north")', DATA) == 3
    assert run('=MINIFS(B1:B4, A1:A4, "north")', DATA) == 1
    assert code('=AVERAGEIF(A1:A4, "none", B1:B4)', DATA) == "#DIV/0!"
    assert run('=COUNTIFS(A1:A4, "north", B1:B4, ">1")', DATA) == 1


def test_sumif_over_whole_columns_is_sparse():
    assert run('=SUMIF(A:A, "north", B:B)', DATA) == 4


def test_mismatched_shapes_and_odd_arguments():
    assert code('=SUMIFS(B1:B4, A1:A3, "north")', DATA) == "#VALUE!"
    assert code('=COUNTIFS(A1:A4, "north", B1:B4)', DATA) == "#VALUE!"


# -- numbers ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("=ROUND(2.5)", 3),
        ("=ROUND(-2.5)", -3),
        ("=ROUND(1.005, 2)", 1.01),
        ("=ROUND(1234.5678, -2)", 1200),
        ("=ROUNDUP(-1.1)", -2),
        ("=ROUNDDOWN(1.99, 1)", 1.9),
        ("=TRUNC(-1.9)", -1),
        ("=INT(5)", 5),
        ("=CEILING(-2.1, -1)", -2),
        ("=FLOOR(-2.1)", -3),
        ("=FLOOR(7, 2)", 6),
        ("=MOD(7, -3)", -2),
        ("=SIGN(0)", 0),
        ("=LOG(1000)", 3),
        ("=LOG(8, 2)", 3),
        ("=FACT(0)", 1),
        ("=POWER(2, -1)", 0.5),
    ],
)
def test_number_functions(formula, expected):
    assert run(formula) == expected


def test_number_function_errors():
    assert code("=SQRT(-1)") == "#NUM!"
    assert code("=LN(0)") == "#NUM!"
    assert code("=MOD(1, 0)") == "#DIV/0!"
    assert code("=POWER(0, -1)") == "#DIV/0!"
    assert code("=FACT(-1)") == "#NUM!"
    assert code("=ABS()") == "#VALUE!"
    assert code("=ABS(1, 2)") == "#VALUE!"
    assert code('=ABS("x")') == "#VALUE!"


def test_rounding_gives_whole_numbers_as_ints():
    assert type(run("=ROUND(2.6)")) is int
    assert type(run("=ROUND(2.6, 1)")) is float


# -- logic -----------------------------------------------------------------------------------------------------
def test_logic():
    assert run("=AND(TRUE, 1, 2)") is True
    assert run("=OR(FALSE, 0)") is False
    assert run("=XOR(TRUE, FALSE)") is True
    assert run("=NOT(0)") is True
    assert run("=AND(A1:A3)", {"A1": True, "A2": "text"}) is True  # (text in a range is skipped)
    assert code("=AND(A1:A3)", {"A2": "text"}) == "#VALUE!"
    assert run("=TRUE()") is True


# -- text ------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ('=LEFT("abc")', "a"),
        ('=RIGHT("abc")', "c"),
        ('=RIGHT("abc", 0)', ""),
        ('=RIGHT("abc", 9)', "abc"),
        ('=MID("abcdef", 3, 100)', "cdef"),
        ('=TRIM("  a   b  ")', "a b"),
        ('=SUBSTITUTE("aaa", "a", "b", 2)', "aba"),
        ('=SUBSTITUTE("aaa", "a", "b", 9)', "aaa"),
        ('=PROPER("o\'neil is here")', "O'Neil Is Here"),
        ("=UPPER(12)", "12"),
        ("=LEN(A1)", 3),
        ('=TEXTJOIN("-", FALSE, A1:A3)', "abc--x"),
        ('=CONCAT(A1, "!", 1.5)', "abc!1.5"),
        ('=VALUE("  12 ")', 12),
        ('=VALUE("1e3")', 1000.0),
        ('=SEARCH("B", "abc")', 2),
        ('=EXACT("a", "a")', True),
    ],
)
def test_text_functions(formula, expected):
    assert run(formula, {"A1": "abc", "A3": "x"}) == expected


def test_text_errors_and_limits():
    assert code('=FIND("z", "abc")') == "#VALUE!"
    assert code('=FIND("a", "abc", 9)') == "#VALUE!"
    assert code('=VALUE("nan")') == "#VALUE!"
    assert code('=VALUE("inf")') == "#VALUE!"
    assert code('=LEFT("abc", -1)') == "#VALUE!"
    assert code('=REPT("ab", 100000)') == "#VALUE!"
    assert code('=MID("abc", 0, 1)') == "#VALUE!"
