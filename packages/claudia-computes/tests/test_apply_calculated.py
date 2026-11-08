"""``ApplyCalculated``: a worker's result landing on the cell that deferred it -- recalculated readers, an event,
a log entry, round-tripping through the log -- except undo, since nobody undoes the server's own continuation of
a formula (PERF review 2026-11-08, D37, D177).
"""

from __future__ import annotations

import pytest
from conftest import S1

from claudia_computes import AddSheet, ApplyCalculated, SetCells, WorkbookModel, parse_input
from claudia_computes.functions.base import Example, UserFunction
from claudia_computes.functions.builtin import builtin_registry
from claudia_computes.functions.range import Range
from claudia_computes.refs import parse_cell_ref
from claudia_computes.values import ErrorValue
from claudia_core import Document, MemoryStore
from claudia_core.testing import FakeClock


class COUNT_HEAVY(UserFunction):
    description = "Counts the cells of a range (heavy above 3)"
    examples = (Example("=COUNT_HEAVY(A1:A1)", 1),)
    heavy = True
    heavy_above = 3

    def call(self, values: Range) -> int:
        return len(list(values.present()))


@pytest.fixture
def registry():
    registry = builtin_registry()
    registry.register(COUNT_HEAVY)
    return registry


@pytest.fixture
def doc(registry):
    clock = FakeClock()
    d = Document(WorkbookModel(registry), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)
    d.execute(AddSheet(S1, "Sheet1"), author="ana")
    return d


def at(address):
    ref = parse_cell_ref(address)
    return ref.row, ref.col


def fill(doc, cells: dict, *, sheet=S1):
    items = tuple((*at(address), parse_input(str(text))) for address, text in cells.items())
    return doc.execute(SetCells(sheet, items), author="ana")


def shown(doc, address, sheet=S1):
    row, col = at(address)
    return doc.model.value(sheet, row, col)


def test_applying_lands_the_value_and_wakes_readers(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)", "C1": "=B1*10"})
    row, col = at("B1")

    doc.execute(ApplyCalculated(S1, row, col, 5), author="ai")

    assert shown(doc, "B1") == 5
    assert shown(doc, "C1") == 50


def test_applying_an_error_value_lands_it_too(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
    row, col = at("B1")

    doc.execute(ApplyCalculated(S1, row, col, ErrorValue("#NUM!", "overflowed")), author="ai")

    assert shown(doc, "B1") == ErrorValue("#NUM!", "overflowed")


@pytest.mark.parametrize("value", [5, 2.5, "text", True, None, ErrorValue("#NUM!", "overflowed")])
def test_to_data_and_from_data_round_trip_every_kind_of_value(value):
    original = ApplyCalculated(S1, 0, 1, value)
    restored = ApplyCalculated.from_data(original.to_data(), WorkbookModel.registry)
    assert restored == original


def test_it_is_not_on_the_authors_undo_stack(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
    row, col = at("B1")

    doc.execute(ApplyCalculated(S1, row, col, 5), author="ai")
    doc.undo("ai")  # nothing of "ai"'s own to undo: must not strip the just-applied result

    assert shown(doc, "B1") == 5


def test_a_stale_apply_for_a_formula_already_edited_away_changes_nothing(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
    row, col = at("B1")
    fill(doc, {"B1": "=1+1"})  # edited away before the worker answered

    doc.execute(ApplyCalculated(S1, row, col, 999), author="ai")

    assert shown(doc, "B1") == 2
