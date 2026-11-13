"""Deferring a heavy ``UserFunction`` call through ``calc.py``: the cell keeps showing whatever it showed before,
the deferral is kept in ``Calculator.pending_heavy`` for the caller to dispatch, and resolving it lands the result
and wakes its readers on the next settle, the same as any other change (PERF review 2026-11-08, D37, D291).

These tests go through a real ``Document``/``WorkbookModel`` (not ``Calculator`` in isolation) because the point is
that a heavy call behaves like any other formula everywhere except the one place it must not: it never reaches
``Round._store``.
"""

from __future__ import annotations

import pytest
from conftest import S1

from claudia_computes import AddSheet, SetCells, WorkbookModel, parse_input
from claudia_computes.functions.base import Example, UserFunction
from claudia_computes.functions.builtin import builtin_registry
from claudia_computes.functions.range import FrozenGrid, Range
from claudia_computes.refs import parse_cell_ref
from claudia_core import Document, MemoryStore
from claudia_core.testing import FakeClock


class COUNT_HEAVY(UserFunction):
    """Heavy above 3 present cells -- small enough ranges run inline so the tests stay simple."""

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


def key_of(doc, address, sheet=S1):
    row, col = at(address)
    return sheet, row, col


def calc(doc):
    return doc.model.calc


def test_a_heavy_call_past_its_threshold_is_deferred_not_calculated(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
    assert key_of(doc, "B1") in calc(doc).pending_heavy
    assert shown(doc, "B1") is None  # it never ran, so nothing was ever stored for it


def test_a_deferred_calls_range_argument_is_frozen_against_later_edits(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
    key = key_of(doc, "B1")
    deferred = calc(doc).pending_heavy[key]
    (only_arg,) = deferred.call_args
    assert isinstance(only_arg.sheet, FrozenGrid)  # not the live sheet: later edits must not reach it

    fill(doc, {"A3": 999})  # a later command changes a cell inside the very range the deferred call read

    assert sorted(only_arg.present()) == [0, 1, 2, 3, 4]  # the snapshot from before the edit, untouched


def test_a_call_under_the_threshold_still_runs_inline(doc):
    fill(doc, {"A1": 1, "A2": 2})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A2)"})
    assert shown(doc, "B1") == 2
    assert not calc(doc).pending_heavy


def test_editing_the_deferred_formula_away_clears_its_pending_entry(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
    key = key_of(doc, "B1")
    assert key in calc(doc).pending_heavy
    fill(doc, {"B1": "=1+1"})
    assert key not in calc(doc).pending_heavy
    assert shown(doc, "B1") == 2


def test_clearing_the_deferred_cell_entirely_clears_its_pending_entry(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
    key = key_of(doc, "B1")
    assert key in calc(doc).pending_heavy
    fill(doc, {"B1": ""})
    assert key not in calc(doc).pending_heavy


def test_resolving_a_deferred_call_stores_its_value_at_once(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
    key = key_of(doc, "B1")

    calc(doc).resolve_heavy(key, 5)

    assert shown(doc, "B1") == 5
    assert key not in calc(doc).pending_heavy


def test_resolving_a_deferred_call_wakes_its_readers_on_the_next_settle(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
    fill(doc, {"C1": "=B1*10"})
    key = key_of(doc, "B1")

    calc(doc).resolve_heavy(key, 5)
    fill(doc, {"D1": 1})  # any further command settles the whole workbook, waking C1

    assert shown(doc, "C1") == 50


def test_resolving_a_call_that_is_no_longer_pending_is_a_harmless_no_op(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
    key = key_of(doc, "B1")
    fill(doc, {"B1": "=1+1"})  # edited away before the worker answered: no longer pending
    assert shown(doc, "B1") == 2

    calc(doc).resolve_heavy(key, 999)  # a late, stale answer must not stomp on the new formula's value

    assert shown(doc, "B1") == 2


def test_discarding_a_call_that_is_no_longer_pending_is_a_harmless_no_op(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
    key = key_of(doc, "B1")
    fill(doc, {"B1": "=1+1"})  # edited away: no longer pending

    calc(doc).discard_heavy(key)  # must not force the new, already-resolved formula to be tried again

    assert key not in calc(doc).forced


def test_discarding_a_stale_deferred_call_stores_nothing_but_forces_another_try(doc):
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": "=COUNT_HEAVY(A1:A5)"})
    key = key_of(doc, "B1")

    calc(doc).discard_heavy(key)

    assert key not in calc(doc).pending_heavy
    assert shown(doc, "B1") is None  # still nothing stored

    fill(doc, {"D1": 1})  # the forced retry happens on the next settle
    assert key in calc(doc).pending_heavy  # still too big: deferred again, not an infinite loop of errors


def test_a_deferred_formula_that_reads_where_it_likes_is_deferred_again_when_what_it_read_changes(doc):
    """``INDIRECT`` looks where its text says, which only the evaluation knows: what it read must be recorded even
    when the call defers, or a later edit of those cells would never make the formula run again (D291)."""
    fill(doc, {f"A{r + 1}": r for r in range(5)})
    fill(doc, {"B1": '=COUNT_HEAVY(INDIRECT("A1:A5"))'})
    key = key_of(doc, "B1")
    (first,) = calc(doc).pending_heavy[key].call_args
    assert sorted(first.present()) == [0, 1, 2, 3, 4]

    fill(doc, {"A3": 999})

    (again,) = calc(doc).pending_heavy[key].call_args
    assert again is not first, "the formula was not calculated again after a cell it read changed"
    assert 999 in set(again.present())
