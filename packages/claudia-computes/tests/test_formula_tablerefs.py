"""Excel's structured references (``Sales[Amount]``, ``Sales[@[Unit price]]``) and names in other alphabets: read
into a tree, printed back in one canonical way, and followed when a table or a column is renamed (E6.5, D600)."""

import pytest

from claudia_computes.formula import Binary, Call, Name, Num, TableRef, parse_formula, print_formula
from claudia_computes.formula.rewrite import renamed_column, renamed_name


def ast(text: str):
    formula = parse_formula(text)
    assert formula.error is None, formula.error
    return formula.ast


def shown(text: str) -> str:
    return print_formula(parse_formula(text))


# ------------------------------------------------------------------------------------ reading
def test_a_column_of_a_table():
    assert ast("=Sales[Amount]") == TableRef("Sales", (), "Amount", None)


def test_a_column_with_a_space_needs_no_extra_brackets():
    assert ast("=Sales[Unit price]") == TableRef("Sales", (), "Unit price", None)


def test_a_column_in_double_brackets_is_the_same_column():
    assert ast("=Sales[[Amount]]") == ast("=Sales[Amount]")


def test_the_row_of_the_formula_with_an_at_sign():
    assert ast("=Sales[@Amount]") == TableRef("Sales", ("#This Row",), "Amount", None)


def test_the_row_of_the_formula_with_a_column_in_brackets():
    assert ast("=Sales[@[Unit price]]") == TableRef("Sales", ("#This Row",), "Unit price", None)


def test_the_row_of_the_formula_spelled_out():
    assert ast("=Sales[[#This Row],[Amount]]") == ast("=Sales[@Amount]")


@pytest.mark.parametrize("item", ["Headers", "Data", "All"])
def test_the_parts_of_a_table(item):
    assert ast(f"=Sales[#{item}]") == TableRef("Sales", (f"#{item}",), None, None)


def test_a_part_of_a_column():
    assert ast("=Sales[[#Headers],[Amount]]") == TableRef("Sales", ("#Headers",), "Amount", None)


def test_several_columns_in_a_row():
    assert ast("=Sales[[Units]:[Amount]]") == TableRef("Sales", (), "Units", "Amount")


def test_the_parts_are_not_case_sensitive():
    assert ast("=Sales[[#headers],[Amount]]") == ast("=Sales[[#Headers],[Amount]]")


def test_a_quote_escapes_a_bracket_inside_a_column_name():
    assert ast("=Sales[Odd '[name']]") == TableRef("Sales", (), "Odd [name]", None)


def test_a_table_ref_works_inside_a_function_and_an_operation():
    assert ast("=SUM(Sales[Amount])*2") == Binary(
        "*", Call("SUM", (TableRef("Sales", (), "Amount", None),)), Num(2, "2")
    )


def test_a_table_ref_is_not_confused_with_a_cell_or_a_name():
    assert ast("=Rate") == Name("Rate")
    assert ast("=Sales[Amount]") != Name("Sales")


def test_an_unclosed_bracket_is_a_syntax_error():
    assert parse_formula("=Sales[Amount").error is not None


def test_an_empty_bracket_is_a_syntax_error():
    assert parse_formula("=Sales[]").error is not None


def test_an_unknown_part_is_a_syntax_error():
    assert parse_formula("=Sales[#Nothing]").error is not None


# ------------------------------------------------------------------------------------ printing
@pytest.mark.parametrize(
    "text",
    [
        "=Sales[Amount]",
        "=Sales[Unit price]",
        "=Sales[@Amount]",
        "=Sales[@[Unit price]]",
        "=Sales[#Headers]",
        "=Sales[#All]",
        "=Sales[[#Headers],[Unit price]]",
        "=Sales[[Units]:[Amount]]",
        "=SUM(Sales[Amount])+Sales[@Units]",
    ],
)
def test_printing_a_canonical_formula_changes_nothing(text):
    assert shown(text) == text


def test_printing_chooses_one_spelling():
    assert shown("=Sales[[Amount]]") == "=Sales[Amount]"
    assert shown("=Sales[[#This Row],[Unit price]]") == "=Sales[@[Unit price]]"
    assert shown("=Sales[[#headers],[Amount]]") == "=Sales[[#Headers],[Amount]]"


def test_printing_escapes_a_bracket_in_a_column_name():
    assert shown("=Sales[Odd '[name']]") == "=Sales[Odd '[name']]"


# ------------------------------------------------------------------------------------ names in any alphabet
def test_a_name_may_use_letters_of_any_alphabet():
    assert ast("=Größe") == Name("Größe")
    assert ast("=SUM(Umsätze[Betrag])") == Call("SUM", (TableRef("Umsätze", (), "Betrag", None),))


# ------------------------------------------------------------------------------------ renaming
def test_renaming_a_table_changes_every_use_of_it():
    formula = parse_formula("=SUM(Sales[Amount])+COUNT(sales)+Rate")
    renamed = renamed_name(formula, "sales", "Orders")
    assert renamed.source == "=SUM(Orders[Amount])+COUNT(Orders)+Rate"


def test_renaming_leaves_the_same_formula_when_nothing_matches():
    formula = parse_formula("=SUM(Sales[Amount])")
    assert renamed_name(formula, "Other", "Orders") is formula


def test_renaming_a_column_changes_the_ones_that_name_it():
    formula = parse_formula("=SUM(Sales[Amount])+Sales[@Units]+Other[Amount]")
    renamed = renamed_column(formula, "Sales", "Amount", "Revenue")
    assert renamed.source == "=SUM(Sales[Revenue])+Sales[@Units]+Other[Amount]"


def test_renaming_a_column_reaches_the_ends_of_a_span():
    formula = parse_formula("=Sales[[Units]:[Amount]]")
    assert renamed_column(formula, "Sales", "Amount", "Revenue").source == "=Sales[[Units]:[Revenue]]"
