"""Follow the computation: which cells take part in a calculation with the clicked one, and in what role (E6.23, D297).

The cells are the pricing model of the mock-ups: price, units, variable cost and fixed cost give revenue, costs, profit
and margin. Roles are relative to the connected cells: an *input* reads none of them, an *output* is read by none, a
*calc* is in the middle."""

from __future__ import annotations

import pytest
from conftest import S1
from test_workbook_formulas import at, fill

import claudia_computes.trace as trace_module
from claudia_computes import AddSheet, SetCells, parse_input

S2 = "s2"


def pricing(doc):
    fill(
        doc,
        {
            "B2": 24,
            "B3": 1000,
            "B4": 11,
            "B5": 8500,
            "B7": "=B2*B3",
            "B8": "=B5+B3*B4",
            "B9": "=B7-B8",
            "B10": "=B9/B7",
            "D1": 1,
            "D2": "=D1*2",
        },
    )


def follow(doc, address, **options):
    row, col = at(address)
    return doc.model.trace(S1, row, col, **options)


def roles(result):
    names = {(r, c): role for (r, c), role in result.cells.items()}
    return {
        address: names.get(at(address)) for address in ("B2", "B3", "B4", "B5", "B7", "B8", "B9", "B10", "D1", "D2")
    }


GROUP = {
    "B2": "input",
    "B3": "input",
    "B4": "input",
    "B5": "input",
    "B7": "calc",
    "B8": "calc",
    "B9": "calc",
    "B10": "output",
    "D1": None,
    "D2": None,
}


def test_a_group_is_everything_connected_whichever_cell_was_clicked(doc):
    pricing(doc)
    for address in ("B2", "B7", "B9", "B10"):
        assert roles(follow(doc, address)) == GROUP, address


def test_an_unconnected_island_is_a_group_of_its_own(doc):
    pricing(doc)
    result = follow(doc, "D1")
    assert roles(result)["D1"] == "input" and roles(result)["D2"] == "output"
    assert roles(result)["B9"] is None


def test_a_chain_is_what_the_cell_reads_and_what_reads_it(doc):
    pricing(doc)
    shown = roles(follow(doc, "B7", reach="chain"))
    assert shown == {**dict.fromkeys(GROUP), "B2": "input", "B3": "input", "B7": "calc", "B9": "calc", "B10": "output"}


def test_the_clicked_cell_is_part_of_the_result(doc):
    pricing(doc)
    result = follow(doc, "B8")
    assert result.focus == (S1, *at("B8")) and result.connected is True and result.total == 8


def test_cells_outside_the_window_are_not_listed_but_still_count_for_roles(doc):
    pricing(doc)
    rows_1_to_9 = (0, 0, 8, 5)
    result = follow(doc, "B9", window=rows_1_to_9)
    shown = roles(result)
    assert shown["B10"] is None and shown["B9"] == "calc"  # B9 is read by B10, which is below the window
    assert result.total == 8


def test_a_range_lights_the_cells_that_hold_something_in_it(doc):
    fill(doc, {"A1": 1, "A2": 2, "A4": 4, "B1": "=SUM(A1:A5)"})
    result = follow(doc, "A2")
    assert set(result.cells) == {at("A1"), at("A2"), at("A4"), at("B1")}


def test_a_cell_nobody_reads_and_that_reads_nothing_is_not_connected(doc):
    fill(doc, {"A1": 5})
    result = follow(doc, "A1")
    assert result.connected is False and result.cells == {} and result.total == 1


def test_an_empty_cell_is_not_connected(doc):
    pricing(doc)
    assert follow(doc, "H20").connected is False


def test_a_reference_to_an_empty_cell_does_not_light_it(doc):
    fill(doc, {"A1": 1, "B1": "=A1+C1"})
    assert set(follow(doc, "B1").cells) == {at("A1"), at("B1")}


def test_cells_of_other_sheets_are_counted_not_listed(doc):
    pricing(doc)
    doc.execute(AddSheet(S2, "Second"), author="ana")
    row, col = at("A1")
    doc.execute(SetCells(S2, ((row, col, parse_input("=Sheet1!B9*2")), (1, 0, parse_input("=A1+1")))), author="ana")
    result = follow(doc, "B9")
    assert result.other_sheets == {S2: 2}
    assert at("A1") not in result.cells  # (that is the other sheet's A1)
    assert result.total == 10


def test_a_cycle_does_not_run_forever(doc):
    fill(doc, {"A1": "=B1+1", "B1": "=A1+1"})
    result = follow(doc, "A1")
    assert set(result.cells) == {at("A1"), at("B1")}


def test_a_very_large_group_stops_at_the_limit_and_says_so(doc, monkeypatch):
    monkeypatch.setattr(trace_module, "MAX_CELLS", 50)
    fill(doc, {"A1": 1, **{f"A{n}": f"=A{n - 1}+1" for n in range(2, 121)}})
    result = follow(doc, "A60")
    assert result.truncated is True and len(result.cells) <= 50
    assert at("A60") in result.cells


def test_the_data_form_is_what_a_client_gets(doc):
    pricing(doc)
    data = follow(doc, "B9", window=(0, 0, 20, 5)).to_data()
    assert data["sheet"] == S1 and data["row"] == 8 and data["col"] == 1 and data["reach"] == "group"
    assert [1, 1, "input"] in data["cells"] and [9, 1, "output"] in data["cells"]
    assert data["total"] == 8 and data["connected"] is True and data["truncated"] is False and data["other"] == {}


def test_an_unknown_reach_is_refused(doc):
    pricing(doc)
    with pytest.raises(ValueError, match="reach"):
        follow(doc, "B9", reach="everything")
