"""A scratch copy of a workbook (E7.8, D263): formulas recalculate on it, the live workbook does not notice.

This is the check the AI proposal preview stands on: a throwaway document built from a live workbook must run
``SetCells``, ``Structure`` and friends with the formula engine alive, tell its own subscribers what changed
(dependents included), and stay apart from the original in both directions.
"""

from __future__ import annotations

from conftest import S1
from test_workbook_formulas import at, fill, type_in

from claudia_computes import AddSheet, InsertRows, Structure
from claudia_computes.events import CellsChanged
from claudia_computes.values import ErrorValue


def shown(doc, address, *, sheet=S1):
    row, col = at(address)
    return doc.model.value(sheet, row, col)


def budget(doc):
    """B2 x C2 = yearly total, half of it, and a per-week figure that divides by an empty cell (#DIV/0!)."""
    fill(doc, {"B2": 1200, "C2": 12, "D2": "=B2*C2", "D3": "=D2/2", "B7": "=D3/C7"})


def test_the_fixture_has_the_error_the_tests_below_fix(doc):
    budget(doc)
    assert shown(doc, "D2") == 14400 and shown(doc, "D3") == 7200
    assert isinstance(shown(doc, "B7"), ErrorValue)


def test_formulas_calculate_on_the_copy_and_the_live_workbook_stays_as_it_was(doc):
    budget(doc)
    live_before = doc.model.serialize()
    copy = doc.scratch()
    type_in(copy, "B2", "2400")
    assert shown(copy, "D2") == 28800
    assert shown(copy, "D3") == 14400
    assert doc.model.serialize() == live_before
    assert shown(doc, "D2") == 14400


def test_the_copy_reports_the_dependents_of_the_cell_it_changed(doc):
    budget(doc)
    copy = doc.scratch()
    heard: list[CellsChanged] = []
    copy.subscribe(lambda event: heard.append(event) if isinstance(event, CellsChanged) else None)
    type_in(copy, "B2", "2400")
    touched = {pos for event in heard for pos in event.positions}
    assert at("D2") in touched and at("D3") in touched


def test_a_fix_can_be_tried_and_checked_on_the_copy_before_anyone_sees_it(doc):
    budget(doc)
    copy = doc.scratch()
    type_in(copy, "B7", "=D3/52")
    assert round(shown(copy, "B7"), 2) == 138.46
    assert isinstance(shown(doc, "B7"), ErrorValue)


def test_structure_commands_run_on_the_copy_and_formulas_follow_them(doc):
    budget(doc)
    copy = doc.scratch()
    copy.execute(Structure(InsertRows(S1, 1, 1)), author="ai")  # a new row 2: everything moves down
    assert shown(copy, "D3") == 14400 and shown(copy, "D4") == 7200
    assert shown(doc, "D2") == 14400 and shown(doc, "D3") == 7200


def test_a_copy_at_an_older_revision_has_working_formulas_too(doc):
    budget(doc)
    earlier = doc.revision
    type_in(doc, "B2", "10")
    copy = doc.scratch(earlier)
    assert shown(copy, "D2") == 14400
    type_in(copy, "B2", "100")
    assert shown(copy, "D2") == 1200
    assert shown(doc, "D2") == 120


def test_a_copy_does_not_see_what_happens_live_afterwards(doc):
    budget(doc)
    copy = doc.scratch()
    type_in(doc, "B2", "1")
    assert shown(copy, "D2") == 14400


def test_a_sheet_added_on_the_copy_stays_there(doc):
    copy = doc.scratch()
    copy.execute(AddSheet("s2", "Notes"), author="ai")
    assert len(copy.model.serialize()["sheets"]) == 2
    assert len(doc.model.serialize()["sheets"]) == 1
