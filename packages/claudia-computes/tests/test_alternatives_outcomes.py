"""Alternatives in a workbook: every alternative runs through the cells that depend on the input (E6.21, D294-D296).

The model is the one the mock-ups use: price, units and variable cost give revenue, costs, profit and margin. Units
and variable cost have three alternatives each, so the profit has nine outcomes, revenue only three."""

from __future__ import annotations

import pytest
from conftest import S1, reopen
from names_helpers import define
from test_workbook_formulas import at, error_code, fill, shown, type_in

from claudia_computes import InsertRows, SetCells, Structure, WorkbookModel, parse_input
from claudia_computes.events import CellsChanged
from claudia_computes.outcomes import MAX_COMBINATIONS


def pricing(doc):
    fill(
        doc,
        {
            "A3": "Units sold",
            "B2": 24,
            "B3": "{800, 1000, 1300}",
            "B4": "{9.5, 11, 14}",
            "B5": 8500,
            "B7": "=B2*B3",
            "B8": "=B5+B3*B4",
            "B9": "=B7-B8",
            "B10": "=B9/B7",
        },
    )


def view(doc, address):
    return doc.model.sheet(S1).view(at(address))


def table(doc, address, combine="all"):
    row, col = at(address)
    return doc.model.outcome_table(S1, row, col, combine=combine)


# ------------------------------------------------------------------ the cell with alternatives
def test_an_input_with_alternatives_shows_the_first_one(doc):
    pricing(doc)
    assert shown(doc, "B3") == 800
    assert shown(doc, "B4") == 9.5


def test_the_formula_bar_gets_the_braces_back_and_a_client_gets_every_alternative(doc):
    pricing(doc)
    cell = view(doc, "B3")
    assert cell["f"] == "{800, 1000, 1300}"
    assert [a["v"] for a in cell["alts"]] == [800, 1000, 1300]
    assert all("l" not in a for a in cell["alts"])


def test_named_scenarios_show_their_names(doc):
    type_in(doc, "B3", "{low: 800, base: 1000}")
    cell = view(doc, "B3")
    assert cell["f"] == "{low: 800, base: 1000}"
    assert [(a["l"], a["v"]) for a in cell["alts"]] == [("low", 800), ("base", 1000)]
    assert shown(doc, "B3") == 800


def test_alternatives_may_be_formulas_and_follow_their_cells(doc):
    fill(doc, {"B2": 100, "B3": "{=B2*0.9, =B2, =B2*1.1}"})
    assert [a["v"] for a in view(doc, "B3")["alts"]] == [90, 100, 110.00000000000001]
    type_in(doc, "B2", "200")
    assert [a["v"] for a in view(doc, "B3")["alts"]][:2] == [180, 200]
    assert shown(doc, "B3") == 180


def test_typing_alternatives_again_in_the_formula_text_is_the_same_cell(doc):
    type_in(doc, "B3", "=ALTERNATIVES(1,2,3)")
    assert view(doc, "B3")["f"] == "{1, 2, 3}"


# ------------------------------------------------------------------ outcomes
def test_the_cells_below_an_input_with_alternatives_show_the_first_outcome(doc):
    pricing(doc)
    assert shown(doc, "B9") == 3100  # 800 units at 9.50
    assert shown(doc, "B7") == 19200


def test_a_cell_with_outcomes_says_how_many_and_where_they_lie(doc):
    pricing(doc)
    out = view(doc, "B9")["out"]
    assert out["n"] == 9 and out["errors"] == 0 and out["sampled"] is False
    assert (out["min"], out["max"], out["median"]) == (-500, 10350, 4500)
    assert out["mean"] == pytest.approx(39750 / 9)
    assert out["points"] == sorted(out["points"]) and len(out["points"]) == 9


def test_a_cell_depends_only_on_the_inputs_it_reads(doc):
    pricing(doc)
    assert view(doc, "B7")["out"]["n"] == 3  # revenue does not read the variable cost
    assert view(doc, "B8")["out"]["n"] == 9


def test_cells_that_do_not_depend_on_an_input_have_no_outcomes(doc):
    pricing(doc)
    assert "out" not in view(doc, "B5")
    assert "out" not in view(doc, "B2")
    assert "out" not in view(doc, "B3")


def test_the_table_lists_every_combination_the_first_input_changing_slowest(doc):
    pricing(doc)
    result = table(doc, "B9")
    assert [i.key for i in result.inputs] == [(S1, 2, 1), (S1, 3, 1)]
    assert result.inputs[0].label == "Units sold"  # the text of the cell to the left
    assert [r.choice for r in result.rows][:4] == [(0, 0), (0, 1), (0, 2), (1, 0)]
    assert [r.value for r in result.rows] == [3100, 1900, -500, 6000, 4500, 1500, 10350, 8400, 4500]
    assert result.sampled is False


def test_an_input_keeps_the_name_it_has_as_a_named_range(doc):
    pricing(doc)
    define(doc, "units", "B3")
    define(doc, "variable_cost", "B4", sheet=S1)
    result = table(doc, "B9")
    assert [i.label for i in result.inputs] == ["units", "variable_cost"]  # a name beats the text to the left


def test_a_name_that_covers_more_than_the_input_does_not_name_it(doc):
    pricing(doc)
    define(doc, "block", "B3:B4")
    result = table(doc, "B9")
    assert [i.label for i in result.inputs] == ["Units sold", None]


def test_a_sheets_own_name_is_found_too_and_a_changed_name_is_followed(doc):
    pricing(doc)
    define(doc, "units", "B3", scope=S1)
    assert table(doc, "B9").inputs[0].label == "units"
    define(doc, "units", "B2", scope=S1)  # the name moved to another cell
    assert table(doc, "B9").inputs[0].label == "Units sold"


def test_the_table_of_a_cell_with_one_input_has_one_choice_per_row(doc):
    pricing(doc)
    result = table(doc, "B7")
    assert [r.choice for r in result.rows] == [(0,), (1,), (2,)]
    assert [r.value for r in result.rows] == [19200, 24000, 31200]


def test_the_table_says_which_inputs_move_the_result_most(doc):
    pricing(doc)
    swings = {s.input: (s.low, s.high) for s in table(doc, "B9").sensitivity}
    assert swings[0] == (pytest.approx(1500), pytest.approx(7750))
    assert swings[1] == (pytest.approx(5500 / 3), pytest.approx(19450 / 3))


def test_pairing_by_position_uses_the_first_with_the_first(doc):
    pricing(doc)
    result = table(doc, "B9", combine="pair")
    assert [r.choice for r in result.rows] == [(0, 0), (1, 1), (2, 2)]
    assert [r.value for r in result.rows] == [3100, 4500, 4500]


def test_pairing_wants_the_same_number_of_alternatives(doc):
    fill(doc, {"B3": "{1, 2, 3}", "B4": "{1, 2}", "B5": "=B3*B4"})
    with pytest.raises(ValueError, match="same number"):
        table(doc, "B5", combine="pair")


def test_a_cell_without_outcomes_has_no_table(doc):
    pricing(doc)
    assert table(doc, "B5") is None


def test_independent_inputs_do_not_multiply(doc):
    fill(doc, {"A1": "{1, 2, 3}", "B1": "{10, 20, 30}", "A2": "=A1*2", "B2": "=B1*2"})
    assert view(doc, "A2")["out"]["n"] == 3
    assert view(doc, "B2")["out"]["n"] == 3
    assert shown(doc, "A2") == 2 and shown(doc, "B2") == 20


def test_changing_an_alternative_changes_the_outcomes(doc):
    pricing(doc)
    type_in(doc, "B3", "{800, 1000, 2000}")
    assert view(doc, "B9")["out"]["max"] == 2000 * 24 - (8500 + 2000 * 9.5)


def test_replacing_the_alternatives_by_a_number_takes_the_outcomes_away_and_tells_clients(doc):
    pricing(doc)
    heard: list[CellsChanged] = []
    doc.subscribe(lambda event: heard.append(event) if isinstance(event, CellsChanged) else None)
    type_in(doc, "B3", "1000")
    type_in(doc, "B4", "11")
    assert "out" not in view(doc, "B9")
    assert shown(doc, "B9") == 24 * 1000 - (8500 + 1000 * 11)
    touched = {pos for event in heard for pos in event.positions}
    assert at("B9") in touched and at("B7") in touched


def test_clients_are_told_about_the_outcomes_when_they_first_appear(doc):
    fill(doc, {"B3": 5, "B9": "=B3*2"})
    heard: list[CellsChanged] = []
    doc.subscribe(lambda event: heard.append(event) if isinstance(event, CellsChanged) else None)
    type_in(doc, "B3", "{5, 6}")
    shown_cells = {(r, c): content for event in heard for r, c, content in event.cells}
    assert shown_cells[at("B9")]["out"]["n"] == 2


def test_an_error_in_some_outcomes_is_counted_and_does_not_spoil_the_rest(doc):
    fill(doc, {"B3": "{800, 1000, 1300}", "B4": "=100/(B3-1000)"})
    out = view(doc, "B4")["out"]
    assert (out["n"], out["errors"]) == (3, 1)
    assert out["min"] == pytest.approx(-0.5) and out["max"] == pytest.approx(1 / 3)
    row = [r.value for r in table(doc, "B4").rows]
    assert row[0] == pytest.approx(-0.5) and getattr(row[1], "code", None) == "#DIV/0!"


def test_outcomes_that_are_not_numbers_have_no_summary_but_are_counted(doc):
    fill(doc, {"B3": "{1, 2}", "B4": '=IF(B3>1,"big","small")'})
    out = view(doc, "B4")["out"]
    assert out["n"] == 2 and out["median"] is None and out["points"] == []
    assert [r.value for r in table(doc, "B4").rows] == ["small", "big"]


def test_alternatives_see_the_same_random_draw(doc):
    fill(doc, {"B3": "{10, 20, 40}", "B4": "=B3*RAND()"})
    values = [r.value for r in table(doc, "B4").rows]
    assert values[1] == pytest.approx(values[0] * 2) and values[2] == pytest.approx(values[0] * 4)


def test_resampling_changes_the_outcomes_that_depend_on_random_numbers(doc):
    from claudia_computes import Resample

    fill(doc, {"B3": "{10, 20}", "B4": "=B3*RAND()"})
    before = view(doc, "B4")["out"]["points"]
    doc.execute(Resample(), author="ana")
    assert view(doc, "B4")["out"]["points"] != before


def test_too_many_combinations_are_sampled(doc):
    cells = {f"A{n}": "{1, 2, 3}" for n in range(1, 10)}  # 3 ** 9 = 19683
    cells["B1"] = "=" + "+".join(f"A{n}" for n in range(1, 10))
    fill(doc, cells)
    assert MAX_COMBINATIONS < 3**9
    out = view(doc, "B1")["out"]
    assert out["sampled"] is True and out["n"] < 3**9
    assert out["min"] >= 9 and out["max"] <= 27
    assert table(doc, "B1").sampled is True


def test_sampling_is_the_same_on_every_machine(doc):
    cells = {f"A{n}": "{1, 2, 3}" for n in range(1, 10)}
    cells["B1"] = "=" + "+".join(f"A{n}" for n in range(1, 10))
    fill(doc, cells)
    assert view(reopen(doc), "B1")["out"] == view(doc, "B1")["out"]


def test_outcomes_survive_rows_being_inserted_above(doc):
    pricing(doc)
    doc.execute(Structure(InsertRows(S1, 0, 2)), author="ana")
    assert view(doc, "B11")["out"]["n"] == 9  # the profit moved down with its row
    assert view(doc, "B9")["out"]["n"] == 3  # and the revenue is where the profit was


def test_outcomes_are_there_again_when_a_document_is_reopened(doc):
    pricing(doc)
    assert view(reopen(doc), "B9")["out"] == view(doc, "B9")["out"]
    restored = WorkbookModel.restore(doc.model.serialize())
    assert restored.sheet(S1).view(at("B9"))["out"]["n"] == 9


def test_a_workbook_without_alternatives_has_no_outcomes_anywhere(doc):
    fill(doc, {"A1": 1, "A2": "=A1*2"})
    assert all("out" not in (view(doc, a) or {}) for a in ("A1", "A2"))


def test_alternatives_in_the_middle_of_a_formula_count_as_their_first_value(doc):
    type_in(doc, "A1", "=ALTERNATIVES(5,6)*2")
    assert shown(doc, "A1") == 10
    assert "out" not in view(doc, "A1")


def test_alternatives_with_the_wrong_arguments_are_an_error(doc):
    type_in(doc, "A1", "=ALTERNATIVES()")
    assert error_code(doc, "A1") == "#VALUE!"
    type_in(doc, "A2", '=SCENARIOS("a",1,"b")')
    assert error_code(doc, "A2") == "#VALUE!"


def test_parse_input_is_how_a_client_types_them(doc):
    doc.execute(SetCells(S1, ((0, 0, parse_input("{1, 2}")),)), author="ana")
    assert shown(doc, "A1") == 1
