"""Reading formula text: what it means, what it refuses, and that printing it again changes nothing."""

import pytest

from claudia_computes.formula import (
    Area,
    BadRef,
    Binary,
    Bool,
    Call,
    ErrorLit,
    Formula,
    Missing,
    Name,
    Num,
    Paren,
    Percent,
    Ref,
    Str,
    Unary,
    parse_formula,
    print_formula,
)
from claudia_computes.limits import MAX_ROWS
from claudia_computes.refs import CellRef, RangeRef

SHEETS = {"Sheet2": "s2", "My Sheet": "s3", "Data.1": "s4"}


def parse(text: str) -> Formula:
    return parse_formula(text, SHEETS.get)


def ast(text: str):
    formula = parse(text)
    assert formula.error is None, formula.error
    return formula.ast


def names(sheet_id):
    return {v: k for k, v in SHEETS.items()}.get(sheet_id)


def shown(text: str) -> str:
    return print_formula(parse(text), names)


# ------------------------------------------------------------------------------------ literals
def test_numbers_keep_the_way_they_were_typed():
    assert ast("=42") == Num(42, "42")
    assert ast("=1.50") == Num(1.5, "1.50")
    assert ast("=1e3") == Num(1000.0, "1e3")
    assert ast("=.5") == Num(0.5, ".5")
    assert isinstance(ast("=7").value, int)
    assert isinstance(ast("=7.0").value, float)


def test_a_whole_number_too_big_to_be_exact_is_a_float():
    assert isinstance(ast("=12345678901234567890").value, float)


def test_text_and_booleans():
    assert ast('="a""b"') == Str('a"b')
    assert ast("=true") == Bool(True)
    assert ast("=False") == Bool(False)


# ------------------------------------------------------------------------------------ precedence
def test_multiplication_binds_tighter_than_addition():
    assert ast("=1+2*3") == Binary("+", Num(1, "1"), Binary("*", Num(2, "2"), Num(3, "3")))


def test_operators_of_one_level_group_from_the_left():
    assert ast("=8-3-2") == Binary("-", Binary("-", Num(8, "8"), Num(3, "3")), Num(2, "2"))
    assert ast("=2^3^2") == Binary("^", Binary("^", Num(2, "2"), Num(3, "3")), Num(2, "2"))  # as in Excel


def test_a_minus_sign_binds_tighter_than_power_as_in_excel():
    assert ast("=-2^2") == Binary("^", Unary("-", Num(2, "2")), Num(2, "2"))
    assert ast("=2^-2") == Binary("^", Num(2, "2"), Unary("-", Num(2, "2")))


def test_percent_follows_its_operand():
    assert ast("=50%") == Percent(Num(50, "50"))
    assert ast("=-50%") == Percent(Unary("-", Num(50, "50")))
    assert ast("=2^50%") == Binary("^", Num(2, "2"), Percent(Num(50, "50")))


def test_text_joining_is_looser_than_addition_and_comparison_loosest():
    assert ast('=1+2&"x"') == Binary("&", Binary("+", Num(1, "1"), Num(2, "2")), Str("x"))
    assert ast("=1+1=2") == Binary("=", Binary("+", Num(1, "1"), Num(1, "1")), Num(2, "2"))


@pytest.mark.parametrize("op", ["=", "<>", "<", ">", "<=", ">="])
def test_all_comparisons_read(op):
    assert ast(f"=1{op}2") == Binary(op, Num(1, "1"), Num(2, "2"))


def test_parentheses_are_kept_for_printing():
    assert ast("=(1+2)*3") == Binary("*", Paren(Binary("+", Num(1, "1"), Num(2, "2"))), Num(3, "3"))


# ------------------------------------------------------------------------------------ references
def test_cell_references_with_dollars():
    assert ast("=B3") == Ref(CellRef(2, 1))
    assert ast("=$B$3") == Ref(CellRef(2, 1, None, row_abs=True, col_abs=True))
    assert ast("=b$3") == Ref(CellRef(2, 1, None, row_abs=True))


def test_references_to_other_sheets():
    assert ast("=Sheet2!A1") == Ref(CellRef(0, 0, "s2"))
    assert ast("='My Sheet'!A1:B3") == Area(RangeRef(CellRef(0, 0, "s3"), CellRef(2, 1, "s3")))
    assert ast("=Data.1!C2") == Ref(CellRef(1, 2, "s4"))


def test_a_reference_to_an_unknown_sheet_is_a_broken_reference():
    assert ast("=Nope!A1") == BadRef()
    assert ast("=Nope!A1:B2") == BadRef()


def test_a_range_may_be_written_from_any_corner_and_stays_on_one_sheet():
    assert ast("=C3:A1") == Area(RangeRef(CellRef(0, 0), CellRef(2, 2)))
    assert ast("=Sheet2!A1:Sheet2!B2") == Area(RangeRef(CellRef(0, 0, "s2"), CellRef(1, 1, "s2")))
    assert ast("=Sheet2!A1:'My Sheet'!B2") == BadRef()


def test_whole_columns_and_rows():
    last = MAX_ROWS - 1
    assert ast("=A:A") == Area(RangeRef(CellRef(0, 0), CellRef(last, 0)))
    assert ast("=$A:C") == Area(RangeRef(CellRef(0, 0, None, col_abs=True), CellRef(last, 2)))
    assert ast("=2:4").ref.first.row == 1
    assert ast("=2:4").ref.last.row == 3
    assert ast("=2:4").ref.first.col == 0


def test_error_values_can_be_typed():
    assert ast("=#N/A") == ErrorLit("#N/A")
    assert ast("=#REF!") == BadRef()


def test_references_outside_the_sheet_are_names():
    assert ast("=ZZZ1") == Name("ZZZ1")
    assert ast("=A0") == Name("A0")
    assert ast("=A1048577") == Name("A1048577")


def test_long_chains_do_not_exhaust_the_stack():
    chain = "=" + "+".join(["1"] * 3000)
    formula = parse(chain)
    assert formula.error is None
    assert print_formula(formula, names) == chain


def test_names_are_names_unless_they_look_like_cells():
    assert ast("=rate") == Name("rate")
    assert ast("=my_rate.2") == Name("my_rate.2")
    assert ast("=XFD1") == Ref(CellRef(0, 16383))


# ------------------------------------------------------------------------------------ calls
def test_function_calls_are_upper_cased_and_take_any_expression():
    assert ast("=sum(A1:A3, 2*B1)") == Call(
        "SUM",
        (Area(RangeRef(CellRef(0, 0), CellRef(2, 0))), Binary("*", Num(2, "2"), Ref(CellRef(0, 1)))),
    )


def test_calls_without_arguments_and_with_left_out_arguments():
    assert ast("=NOW()") == Call("NOW", ())
    assert ast("=IF(A1,,2)") == Call("IF", (Ref(CellRef(0, 0)), Missing(), Num(2, "2")))
    assert ast("=F(1,)") == Call("F", (Num(1, "1"), Missing()))


def test_a_space_before_the_bracket_and_around_operators_is_allowed():
    assert ast("= SUM (1 , 2) + 3 ") == ast("=SUM(1,2)+3")


# ------------------------------------------------------------------------------------ refusing
@pytest.mark.parametrize(
    "text",
    [
        "=",
        "=1+",
        "=)",
        "=(1",
        "=SUM(",
        "=SUM(1",
        "=1 2",
        "=A1 B",
        "=*2",
        "=1+*2",
        '="open',
        "=A1:",
        "=1..2",
        "=@",
        "=1;2",
    ],
)
def test_text_that_is_not_a_formula_is_refused_with_an_error_not_an_exception(text):
    formula = parse(text)
    assert formula.ast is None
    assert formula.error is not None
    assert formula.error.code == "#ERROR!"
    assert formula.source == text  # (so the person can see and fix what was typed)


def test_a_formula_that_is_too_long_or_too_deep_is_refused():
    assert parse("=" + "1+" * 5000 + "1").error is not None
    assert parse("=" + "(" * 100 + "1" + ")" * 100).error is not None
    assert parse("=" + "(" * 50 + "1" + ")" * 50).error is None


# ------------------------------------------------------------------------------------ what it reads
def test_the_references_are_collected_while_parsing():
    formula = parse("=SUM(A1:A3)+B2*Sheet2!C1")
    assert formula.refs == (
        RangeRef(CellRef(0, 0), CellRef(2, 0)),
        RangeRef(CellRef(1, 1), CellRef(1, 1)),
        RangeRef(CellRef(0, 2, "s2"), CellRef(0, 2, "s2")),
    )


def test_formulas_that_read_where_they_are_told_to_are_dynamic():
    assert not parse("=SUM(A1:A3)").dynamic
    assert parse("=OFFSET(A1,1,1)").dynamic
    assert parse("=1+indirect(A1)").dynamic


# ------------------------------------------------------------------------------------ printing
CORPUS = [
    "=1+2*3",
    "=(1+2)*3",
    "=-2^2",
    "=2^-2",
    "=50%",
    "=-50%",
    '="a""b"&"c"',
    "=A1<>B1",
    "=$A$1+B$2+$C3",
    "=Sheet2!A1:B3",
    "='My Sheet'!A1",
    "=SUM(A:A)",
    "=SUM($A:C)",
    "=SUM(2:4)",
    "=IF(A1,,2)",
    "=NOW()",
    "=TRUE",
    "=1.50+1e3+.5",
    "=#N/A",
    "=#REF!+1",
]


@pytest.mark.parametrize("text", CORPUS)
def test_printing_gives_the_text_back_and_reading_that_gives_the_same_formula(text):
    printed = shown(text)
    assert printed == text
    assert parse(printed).ast == parse(text).ast


def test_a_reference_to_an_unknown_sheet_prints_as_a_broken_one():
    assert shown("=Nope!A1+1") == "=#REF!+1"


def test_printing_normalises_spaces_and_function_names():
    assert shown("= sum( a1 : a3 ) +  2") == "=SUM(A1:A3)+2"


def test_printing_uses_the_current_name_of_a_sheet():
    formula = parse("=Sheet2!A1")
    assert print_formula(formula, lambda sheet_id: "Renamed" if sheet_id == "s2" else None) == "=Renamed!A1"


def test_an_unreadable_formula_prints_as_it_was_typed():
    assert print_formula(parse("=1+"), names) == "=1+"
