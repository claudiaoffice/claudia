"""A formula follows its cells: rows inserted, rows deleted, a copy somewhere else, a sheet removed."""

from claudia_computes.formula import parse_formula, print_formula
from claudia_computes.formula.rewrite import adjusted, shifted, without_sheet
from claudia_computes.limits import MAX_ROWS
from claudia_computes.refs import DeleteCols, DeleteRows, InsertCols, InsertRows

SHEETS = {"Other": "s2", "Sheet1": "s1"}
NAMES = {"s1": "Sheet1", "s2": "Other"}.get


def parse(text):
    return parse_formula(text, SHEETS.get)


def text_of(formula):
    return print_formula(formula, NAMES)


def after(edit, text, home="s1"):
    return text_of(adjusted(parse(text), edit, home, NAMES))


# ------------------------------------------------------------------------------------ rows and columns edited
def test_references_below_an_inserted_row_move_down_and_those_above_stay():
    assert after(InsertRows("s1", 2, 3), "=A1+A3+B$5") == "=A1+A6+B$8"


def test_inserting_inside_a_range_grows_it_and_before_it_moves_it():
    assert after(InsertRows("s1", 2, 1), "=SUM(A1:A5)") == "=SUM(A1:A6)"
    assert after(InsertRows("s1", 0, 1), "=SUM(A1:A5)") == "=SUM(A2:A6)"


def test_deleting_a_row_that_is_referenced_breaks_the_reference():
    assert after(DeleteRows("s1", 2, 1), "=A3+A4") == "=#REF!+A3"


def test_deleting_part_of_a_range_shrinks_it_and_all_of_it_breaks_it():
    assert after(DeleteRows("s1", 1, 2), "=SUM(A1:A5)") == "=SUM(A1:A3)"
    assert after(DeleteRows("s1", 0, 5), "=SUM(A1:A5)") == "=SUM(#REF!)"


def test_columns_work_like_rows():
    assert after(InsertCols("s1", 1, 1), "=A1+B1") == "=A1+C1"
    assert after(DeleteCols("s1", 0, 1), "=A1+B1") == "=#REF!+A1"


def test_another_sheet_is_only_touched_when_the_formula_names_it():
    edit = InsertRows("s2", 0, 1)
    assert after(edit, "=A1+Other!A1", home="s1") == "=A1+Other!A2"
    assert after(edit, "=A1", home="s2") == "=A2"  # (on the edited sheet itself A1 means that sheet's A1)


def test_whole_columns_stay_whole_columns():
    assert after(InsertRows("s1", 3, 2), "=SUM(A:A)") == "=SUM(A:A)"
    assert after(DeleteRows("s1", 3, 2), "=SUM(A:A)") == "=SUM(A:A)"
    assert after(InsertCols("s1", 0, 1), "=SUM(A:A)") == "=SUM(B:B)"
    assert after(InsertRows("s1", 0, 1), "=SUM(A:A)") == "=SUM(A:A)"  # (also at the very top)
    assert after(DeleteRows("s1", 0, 1), "=SUM(A:A)") == "=SUM(A:A)"
    assert after(InsertCols("s1", 0, 1), "=SUM(1:1)") == "=SUM(1:1)"  # (and a whole row, at the very left)


def test_a_reference_pushed_off_the_sheet_breaks():
    last = f"A{MAX_ROWS}"
    assert after(InsertRows("s1", 0, 1), f"={last}+A1") == "=#REF!+A2"


def test_a_formula_that_does_not_change_is_the_same_object():
    formula = parse("=A1+B2")
    assert adjusted(formula, InsertRows("s1", 10, 1), "s1", NAMES) is formula
    assert adjusted(parse("=1+"), InsertRows("s1", 0, 1), "s1", NAMES).error is not None


def test_the_references_of_a_rewritten_formula_are_up_to_date():
    rewritten = adjusted(parse("=A3+SUM(B1:B3)"), InsertRows("s1", 0, 2), "s1", NAMES)
    assert [(r.first.row, r.last.row) for r in rewritten.refs] == [(4, 4), (2, 4)]


def test_a_very_long_chain_is_rewritten_without_recursion():
    chain = "=" + "+".join(["A1"] * 2000)
    assert after(InsertRows("s1", 0, 1), chain) == "=" + "+".join(["A2"] * 2000)


# ------------------------------------------------------------------------------------ copying
def test_a_copy_moves_relative_references_and_keeps_absolute_ones():
    assert text_of(shifted(parse("=A1+$B$2+C$3+$D4"), 2, 1, NAMES)) == "=B3+$B$2+D$3+$D6"


def test_a_copy_moves_ranges_as_a_whole():
    assert text_of(shifted(parse("=SUM(A1:A3)"), 0, 1, NAMES)) == "=SUM(B1:B3)"


def test_a_copy_moved_off_the_sheet_breaks_and_a_copy_in_place_is_the_same_object():
    assert text_of(shifted(parse("=B2"), -2, 0, NAMES)) == "=#REF!"
    formula = parse("=B2")
    assert shifted(formula, 0, 0, NAMES) is formula


def test_whole_columns_do_not_slide_down_in_a_copy():
    assert text_of(shifted(parse("=SUM(A:A)"), 5, 1, NAMES)) == "=SUM(B:B)"
    assert text_of(shifted(parse("=SUM(3:3)"), 5, 1, NAMES)) == "=SUM(8:8)"


# ------------------------------------------------------------------------------------ a sheet removed
def test_references_to_a_removed_sheet_break():
    assert text_of(without_sheet(parse("=Other!A1+B1+SUM(Other!A1:A3)"), "s2", NAMES)) == "=#REF!+B1+SUM(#REF!)"


def test_a_formula_without_that_sheet_is_the_same_object():
    formula = parse("=A1+Sheet1!B2")
    assert without_sheet(formula, "s2", NAMES) is formula
