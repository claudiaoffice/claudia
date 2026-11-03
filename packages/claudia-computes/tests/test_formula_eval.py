"""The core of the formula language, evaluated: operators, the conditional forms, references and lookups."""

from __future__ import annotations

import pytest
from formula_helpers import FakeSheet, code, evaluate

from claudia_computes.values import ErrorValue, FormulaError


# -- operators -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("=1+2", 3),
        ("=7-10", -3),
        ("=6*7", 42),
        ("=7/2", 3.5),
        ("=2^10", 1024),
        ("=2^-1", 0.5),
        ("=-2^2", 4),  # (as in Excel: the minus binds tighter than ^)
        ("=1+2*3", 7),
        ("=(1+2)*3", 9),
        ("=50%", 0.5),
        ("=200*10%", 20.0),
        ('="a"&"b"&1', "ab1"),
        ("=1<2", True),
        ('="a"="A"', True),
        ("=1=TRUE", False),
        ("=2<>3", True),
    ],
)
def test_operators(text, expected):
    result = evaluate(text)
    assert result == expected
    assert type(result) is type(expected)


def test_whole_numbers_stay_exact_up_to_2_to_the_53_and_are_floats_beyond():
    assert evaluate("=2^52+1") == 2**52 + 1
    assert type(evaluate("=2^52+1")) is int
    assert type(evaluate("=2^62+1")) is float
    assert code("=9^9^9^9") == "#NUM!"


def test_errors_of_operators():
    assert code("=1/0") == "#DIV/0!"
    assert code('=1+"a"') == "#VALUE!"
    assert code("=(-8)^0.5") == "#NUM!"


def test_cells_are_read_and_text_is_not_a_number():
    assert evaluate("=A1+B1", {"A1": 2, "B1": 3}) == 5
    assert code('=A1+"3"', {"A1": 2}) == "#VALUE!"  # (text is not coerced to a number: open question E6.4)
    assert evaluate("=A1+1") == 1  # (an empty cell counts as 0)


def test_an_error_in_a_cell_travels_through_a_formula():
    assert code("=A1+1", {"A1": ErrorValue("#N/A")}) == "#N/A"


def test_a_long_chain_does_not_recurse():
    assert evaluate("=" + "+".join(["1"] * 3000)) == 3000
    cells = {"A1": 1}
    assert evaluate("=" + "+".join(["A1"] * 2000), cells) == 2000


def test_constants_are_folded_but_their_errors_wait_for_evaluation():
    assert code("=1/0") == "#DIV/0!"


# -- conditionals ----------------------------------------------------------------------------------------------
def test_if_evaluates_only_the_branch_it_takes():
    assert evaluate("=IF(TRUE, 1, 1/0)") == 1
    assert evaluate("=IF(FALSE, 1/0, 2)") == 2
    assert evaluate("=IF(FALSE, 1)") is False
    assert evaluate('=IF(A1>1, "big", "small")', {"A1": 5}) == "big"


def test_if_takes_numbers_as_conditions_and_rejects_text():
    assert evaluate("=IF(2, 1, 0)") == 1
    assert evaluate("=IF(0, 1, 0)") == 0
    assert code('=IF("x", 1, 0)') == "#VALUE!"


def test_ifs_and_switch_and_choose():
    assert evaluate("=IFS(A1>5, 1, A1>1, 2, TRUE, 3)", {"A1": 3}) == 2
    assert code("=IFS(FALSE, 1)") == "#N/A"
    assert evaluate('=SWITCH(A1, 1, "one", 2, "two", "many")', {"A1": 2}) == "two"
    assert evaluate('=SWITCH(A1, 1, "one", "many")', {"A1": 9}) == "many"
    assert evaluate('=CHOOSE(2, "a", "b", "c")') == "b"
    assert code('=CHOOSE(4, "a", "b")') == "#VALUE!"


def test_iferror_and_ifna_catch_only_what_they_name():
    assert evaluate("=IFERROR(1/0, 7)") == 7
    assert evaluate("=IFERROR(3, 7)") == 3
    assert code("=IFNA(1/0, 7)") == "#DIV/0!"
    assert evaluate("=IFNA(MATCH(9, A1:A2, 0), 0)", {"A1": 1, "A2": 2}) == 0


def test_information_forms_see_errors_and_blanks():
    cells = {"A1": ErrorValue("#N/A"), "A2": "x", "A3": 4, "A4": True}
    assert evaluate("=ISERROR(A1)", cells) is True
    assert evaluate("=ISNA(A1)", cells) is True
    assert evaluate("=ISERR(A1)", cells) is False
    assert evaluate("=ISTEXT(A2)", cells) is True
    assert evaluate("=ISNUMBER(A3)", cells) is True
    assert evaluate("=ISNUMBER(A4)", cells) is False
    assert evaluate("=ISLOGICAL(A4)", cells) is True
    assert evaluate("=ISBLANK(B9)", cells) is True
    assert evaluate("=ISNONTEXT(A3)", cells) is True


def test_wrong_argument_counts_are_errors_not_crashes():
    assert code("=IF()") == "#VALUE!"
    assert code("=INDEX(A1:A3)") == "#VALUE!"


def test_unknown_functions_are_name_errors():
    assert code("=NOSUCH(1)") == "#NAME?"


# -- references ------------------------------------------------------------------------------------------------
def test_row_and_column_give_places_even_of_error_cells():
    assert evaluate("=ROW(C5)", {"C5": ErrorValue("#N/A")}) == 5
    assert evaluate("=COLUMN(C5)") == 3
    assert evaluate("=ROW()", at="B7") == 7
    assert evaluate("=COLUMN()", at="D1") == 4
    assert evaluate("=ROWS(A1:C10)") == 10
    assert evaluate("=COLUMNS(A1:C10)") == 3


GRID = {"A1": "a", "B1": 1, "C1": 10, "A2": "b", "B2": 2, "C2": 20, "A3": "c", "B3": 3, "C3": 30}


def test_index():
    assert evaluate("=INDEX(A1:C3, 2, 3)", GRID) == 20
    assert evaluate("=INDEX(B1:B3, 3)", GRID) == 3
    assert evaluate("=INDEX(A1:C1, 2)", GRID) == 1  # (a single row: one number counts along it)
    assert code("=INDEX(A1:C3, 4, 1)", GRID) == "#REF!"
    assert code("=INDEX(A1:C3, -1, 1)", GRID) == "#VALUE!"


def test_index_with_zero_gives_the_whole_row_or_column():
    whole = evaluate("=INDEX(A1:C3, 0, 2)", GRID)
    assert (whole.n_rows, whole.n_cols) == (3, 1)
    assert whole.vector() == [1, 2, 3]
    row = evaluate("=INDEX(A1:C3, 2, 0)", GRID)
    assert row.vector() == ["b", 2, 20]


def test_offset():
    assert evaluate("=OFFSET(A1, 1, 2)", GRID) == 20
    area = evaluate("=OFFSET(A1, 0, 1, 3, 1)", GRID)
    assert area.vector() == [1, 2, 3]
    assert code("=OFFSET(A1, -1, 0)", GRID) == "#REF!"
    assert code("=OFFSET(A1, 0, 0, 0, 1)", GRID) == "#REF!"


def test_indirect():
    assert evaluate('=INDIRECT("B"&2)', GRID) == 2
    assert evaluate('=INDIRECT("B1:B3")', GRID).vector() == [1, 2, 3]
    assert code('=INDIRECT("nonsense")', GRID) == "#REF!"
    assert code("=INDIRECT(5)", GRID) == "#REF!"
    other = FakeSheet({"A1": 99})
    assert evaluate('=INDIRECT("s2!A1")', GRID, sheets={"s2": other}) == 99


# -- lookups ---------------------------------------------------------------------------------------------------
NAMES = {"A1": "Ann", "A2": "bob", "A3": "Cy", "B1": 10, "B2": 20, "B3": 30}


def test_match_exact_ignores_case_and_uses_wildcards():
    assert evaluate('=MATCH("BOB", A1:A3, 0)', NAMES) == 2
    assert evaluate('=MATCH("c*", A1:A3, 0)', NAMES) == 3
    assert evaluate('=MATCH("?n?", A1:A3, 0)', NAMES) == 1
    assert evaluate('=MATCH("~*", A1:A3, 0)', {"A1": "x", "A2": "*"}) == 2
    assert code('=MATCH("zed", A1:A3, 0)', NAMES) == "#N/A"


def test_match_does_not_confuse_true_with_one():
    assert code("=MATCH(TRUE, A1:A2, 0)", {"A1": 1, "A2": 0}) == "#N/A"
    assert evaluate("=MATCH(TRUE, A1:A2, 0)", {"A1": 1, "A2": True}) == 2


def test_match_sorted_modes():
    data = {"A1": 10, "A2": 20, "A3": 30}
    assert evaluate("=MATCH(25, A1:A3)", data) == 2
    assert evaluate("=MATCH(25, A1:A3, 1)", data) == 2
    assert code("=MATCH(5, A1:A3, 1)", data) == "#N/A"
    desc = {"A1": 30, "A2": 20, "A3": 10}
    assert evaluate("=MATCH(25, A1:A3, -1)", desc) == 1
    assert evaluate("=MATCH(30, A1:A3, 1)", {"A1": 10, "A2": 30, "A3": 50}) == 2


def test_match_across_a_row():
    assert evaluate("=MATCH(3, A1:C1, 0)", {"A1": 1, "B1": 2, "C1": 3}) == 3


def test_xmatch_modes():
    data = {"A1": 10, "A2": 20, "A3": 30, "A4": 20}
    assert evaluate("=XMATCH(20, A1:A4)", data) == 2
    assert evaluate("=XMATCH(20, A1:A4, 0, -1)", data) == 4
    assert evaluate("=XMATCH(25, A1:A4, -1)", data) == 2
    assert evaluate("=XMATCH(25, A1:A4, 1)", data) == 3
    assert evaluate('=XMATCH("b*", A1:A2, 2)', {"A1": "abc", "A2": "bcd"}) == 2
    assert code("=XMATCH(5, A1:A4)", data) == "#N/A"
    assert code("=XMATCH(5, A1:A4, 7)", data) == "#VALUE!"
    assert code("=XMATCH(5, A1:A4, 0, 9)", data) == "#VALUE!"


def test_xlookup():
    assert evaluate('=XLOOKUP("bob", A1:A3, B1:B3)', NAMES) == 20
    assert evaluate('=XLOOKUP("zed", A1:A3, B1:B3, "none")', NAMES) == "none"
    assert code('=XLOOKUP("zed", A1:A3, B1:B3)', NAMES) == "#N/A"
    assert evaluate("=XLOOKUP(25, B1:B3, A1:A3, , -1)", NAMES) == "bob"
    assert code("=XLOOKUP(1, A1:A3, B1:B2)", NAMES) == "#VALUE!"
    assert code("=XLOOKUP(1, A1:B3, B1:B3)", NAMES) == "#VALUE!"


def test_xlookup_fallback_is_only_evaluated_when_needed():
    assert evaluate('=XLOOKUP("bob", A1:A3, B1:B3, 1/0)', NAMES) == 20
    assert code('=XLOOKUP("zed", A1:A3, B1:B3, 1/0)', NAMES) == "#DIV/0!"


def test_xlookup_with_wide_results_gives_the_whole_row():
    row = evaluate('=XLOOKUP("bob", A1:A3, A1:B3)', NAMES)
    assert row.vector() == ["bob", 20]


def test_vlookup_and_hlookup():
    assert evaluate('=VLOOKUP("Cy", A1:B3, 2, FALSE)', NAMES) == 30
    assert evaluate('=VLOOKUP("c*", A1:B3, 2, FALSE)', NAMES) == 30
    assert code('=VLOOKUP("zed", A1:B3, 2, FALSE)', NAMES) == "#N/A"
    assert code('=VLOOKUP("Cy", A1:B3, 3, FALSE)', NAMES) == "#REF!"
    assert code('=VLOOKUP("Cy", A1:B3, 0, FALSE)', NAMES) == "#VALUE!"
    table = {"A1": 0, "A2": 60, "A3": 90, "B1": "F", "B2": "C", "B3": "A"}
    assert evaluate("=VLOOKUP(75, A1:B3, 2)", table) == "C"
    wide = {"A1": "x", "B1": "y", "A2": 1, "B2": 2}
    assert evaluate('=HLOOKUP("y", A1:B2, 2, FALSE)', wide) == 2


def test_lookup_in_a_long_column_uses_an_index_that_follows_changes():
    cells = {f"A{i}": i for i in range(1, 201)}
    sheet = FakeSheet(cells)
    from claudia_computes.formula import parse_formula
    from claudia_computes.formula.compiler import Compiler
    from claudia_computes.formula.scope import Scope
    from claudia_computes.functions.registry import FunctionRegistry

    scope = Scope({"s1": sheet}, lambda name: None)
    scope.enter("s1", 0, 5)
    run = Compiler(FunctionRegistry()).compile(parse_formula("=MATCH(150, A1:A200, 0)").ast)
    assert run(scope) == 150
    assert len(scope.indexes) == 1
    sheet.set("A150", "moved")
    with pytest.raises(FormulaError):
        run(scope)  # (#N/A: the cached index noticed that the column changed)
    sheet.set("A10", 150)
    assert run(scope) == 10
