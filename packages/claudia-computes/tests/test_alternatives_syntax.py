"""Typing ``{800, 1000, 1300}`` into a cell (E6.21, D294): what counts as alternatives and what they become."""

from __future__ import annotations

import pytest

from claudia_computes import parse_input
from claudia_computes.alternatives import Alternative, formula_for, parse_alternatives


def items(text):
    found = parse_alternatives(text)
    assert found is not None, text
    return [(a.label, a.source) for a in found]


def test_a_list_of_values():
    assert items("{800, 1000, 1300}") == [(None, "800"), (None, "1000"), (None, "1300")]


def test_blanks_around_and_inside_do_not_matter():
    assert items("  {  800 ,1000,   1300 }  ") == items("{800,1000,1300}")


def test_a_single_alternative_is_still_alternatives():
    assert items("{5}") == [(None, "5")]


def test_a_range_with_a_step():
    assert items("{800..1300 step 250}") == [(None, "800"), (None, "1050"), (None, "1300")]


def test_a_range_without_a_step_counts_by_one():
    assert [s for _, s in items("{1..4}")] == ["1", "2", "3", "4"]


def test_a_range_of_decimals_has_no_rounding_noise():
    assert [s for _, s in items("{0.05..0.15 step 0.05}")] == ["0.05", "0.1", "0.15"]


def test_a_range_can_count_down():
    assert [s for _, s in items("{3..1 step -1}")] == ["3", "2", "1"]


def test_a_range_and_single_values_can_be_mixed():
    assert [s for _, s in items("{1, 5..7, 10}")] == ["1", "5", "6", "7", "10"]


def test_named_scenarios_keep_their_names():
    assert items("{low: 800, base: 1000, high: 1300}") == [("low", "800"), ("base", "1000"), ("high", "1300")]


def test_a_name_may_have_blanks_in_it():
    assert items("{very low: 1, high: 2}") == [("very low", "1"), ("high", "2")]


def test_alternatives_may_be_formulas_with_or_without_the_equals_sign():
    assert [s for _, s in items("{=B2*0.9, =B2, B2*1.1}")] == ["B2*0.9", "B2", "B2*1.1"]


def test_commas_inside_a_function_or_a_text_do_not_split():
    assert [s for _, s in items('{MAX(1,2), "a, b", 3}')] == ["MAX(1,2)", '"a, b"', "3"]


def test_a_range_of_cells_is_not_mistaken_for_a_name():
    assert items("{A1:B2}") == [(None, "A1:B2")]
    assert items("{Sheet2!A1}") == [(None, "Sheet2!A1")]


@pytest.mark.parametrize(
    "text",
    [
        "800, 1000",  # no braces
        "{800, 1000",  # not closed
        "{}",  # nothing in it
        "{800,,1000}",  # an empty one
        "{1..5 step 0}",  # never ends
        "{1..5 step -1}",  # runs the wrong way
        "{1..100000}",  # too many
        "= {1,2}",
        "{1, 2} extra",
        "hello",
        "",
    ],
)
def test_other_text_is_not_alternatives(text):
    assert parse_alternatives(text) is None


def test_the_formula_a_list_is_stored_as():
    assert formula_for(parse_alternatives("{800, 1000, 1300}")) == "=ALTERNATIVES(800,1000,1300)"


def test_the_formula_for_named_scenarios_alternates_names_and_values():
    found = parse_alternatives("{low: 800, high: 1300}")
    assert formula_for(found) == '=SCENARIOS("low",800,"high",1300)'


def test_a_name_with_a_quote_in_it_is_escaped():
    assert formula_for((Alternative('say "hi"', "1"),)) == '=SCENARIOS("say ""hi""",1)'


def test_typing_alternatives_makes_a_formula_cell():
    assert parse_input("{800, 1000, 1300}") == {"t": "formula", "v": "=ALTERNATIVES(800,1000,1300)"}
    assert parse_input("{a: 1, b: 2}") == {"t": "formula", "v": '=SCENARIOS("a",1,"b",2)'}


def test_a_leading_apostrophe_keeps_the_braces_as_text():
    assert parse_input("'{1, 2}") == {"t": "text", "v": "{1, 2}"}


def test_text_in_braces_that_is_not_alternatives_stays_text():
    assert parse_input("{not closed") == {"t": "text", "v": "{not closed"}


def test_an_unnamed_alternative_among_named_ones_is_named_by_its_position_in_a_way_that_reads_back():
    typed = "{low: 1, 2, high: 3}"
    stored = parse_input(typed)
    assert stored == {"t": "formula", "v": '=SCENARIOS("low",1,"alt 2",2,"high",3)'}
    assert parse_alternatives("{low: 1, alt 2: 2, high: 3}") is not None
