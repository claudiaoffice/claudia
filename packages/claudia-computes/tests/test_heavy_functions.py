"""UserFunction's ``heavy``/``heavy_above`` contract: which calls must not run on the event loop (PERF review
2026-11-08, D37, D177). The decision is made where the call is about to happen -- ``Bound`` -- so ``calc.py`` can
catch :class:`Deferred` and hand the call to a worker instead, without ``functions`` knowing anything about pools.
"""

from __future__ import annotations

import pytest
from formula_helpers import FakeSheet

from claudia_computes.formula import parse_formula
from claudia_computes.formula.compiler import Compiler
from claudia_computes.formula.scope import Scope
from claudia_computes.functions.base import Deferred, Example, UserFunction
from claudia_computes.functions.range import Range
from claudia_computes.functions.registry import FunctionRegistry
from claudia_computes.values import FormulaError


class COUNT_IT(UserFunction):
    """A trivial function, made heavy only by its declaration -- the point here is the gate, not the math."""

    description = "Counts the cells of a range"
    examples = (Example("=COUNT_IT(A1:A1)", 1),)
    heavy = True

    def call(self, values: Range) -> int:
        return len(list(values.present()))


class LIGHT_COUNT(UserFunction):
    description = "Counts the cells of a range (never heavy)"
    examples = (Example("=LIGHT_COUNT(A1:A1)", 1),)

    def call(self, values: Range) -> int:
        return len(list(values.present()))


def _registry(*functions: type[UserFunction]) -> FunctionRegistry:
    registry = FunctionRegistry()
    for cls in functions:
        registry.register(cls)
    return registry


def _try(text: str, cells: dict[str, object], registry: FunctionRegistry):
    """Compiles and evaluates ``text`` against ``cells`` with ``registry``; returns the value, or the raised
    ``Deferred``."""
    sheet = FakeSheet(cells)
    scope = Scope({"s1": sheet}, lambda name: "s1" if name.casefold() == "sheet1" else None)
    scope.enter("s1", 98, 25)  # Z99, matching formula_helpers.evaluate's default
    parsed = parse_formula(text, scope.sheet_id)
    evaluator = Compiler(registry).compile(parsed.ast)
    try:
        return evaluator(scope)
    except Deferred as deferred:
        return deferred


def test_heavy_with_no_threshold_always_defers():
    registry = _registry(COUNT_IT)
    result = _try("=COUNT_IT(A1:A1)", {"A1": 1}, registry)
    assert isinstance(result, Deferred)


def test_a_non_heavy_function_never_defers_however_big_its_input():
    registry = _registry(LIGHT_COUNT)
    cells = {f"A{r + 1}": r for r in range(500)}
    result = _try("=LIGHT_COUNT(A1:A500)", cells, registry)
    assert result == 500


def test_heavy_above_keeps_a_small_call_inline():
    class SOMETIMES_HEAVY(UserFunction):
        description = "Heavy only above 10 present cells"
        examples = (Example("=SOMETIMES_HEAVY(A1:A1)", 1),)
        heavy = True
        heavy_above = 10

        def call(self, values: Range) -> int:
            return len(list(values.present()))

    registry = _registry(SOMETIMES_HEAVY)
    cells = {f"A{r + 1}": r for r in range(5)}
    result = _try("=SOMETIMES_HEAVY(A1:A5)", cells, registry)
    assert result == 5


def test_heavy_above_defers_a_call_past_the_threshold():
    class SOMETIMES_HEAVY(UserFunction):
        description = "Heavy only above 10 present cells"
        examples = (Example("=SOMETIMES_HEAVY(A1:A1)", 1),)
        heavy = True
        heavy_above = 10

        def call(self, values: Range) -> int:
            return len(list(values.present()))

    registry = _registry(SOMETIMES_HEAVY)
    cells = {f"A{r + 1}": r for r in range(20)}
    result = _try("=SOMETIMES_HEAVY(A1:A20)", cells, registry)
    assert isinstance(result, Deferred)


def test_heavy_above_counts_present_cells_not_the_nominal_rectangle():
    """A sparse range of a million rows with two cells filled is cheap; the nominal size must not decide this."""

    class SOMETIMES_HEAVY(UserFunction):
        description = "Heavy only above 10 present cells"
        examples = (Example("=SOMETIMES_HEAVY(A1:A1)", 1),)
        heavy = True
        heavy_above = 10

        def call(self, values: Range) -> int:
            return len(list(values.present()))

    registry = _registry(SOMETIMES_HEAVY)
    result = _try("=SOMETIMES_HEAVY(A1:A1000000)", {"A1": 1, "A2": 2}, registry)
    assert result == 2


def test_deferred_carries_the_bound_and_the_already_converted_arguments():
    registry = _registry(COUNT_IT)
    result = _try("=COUNT_IT(A1:A3)", {"A1": 1, "A2": 2}, registry)
    assert isinstance(result, Deferred)
    assert result.bound.name == "COUNT_IT"
    (only_arg,) = result.call_args
    assert isinstance(only_arg, Range)
    assert sorted(only_arg.present()) == [1, 2]


def test_a_heavy_function_is_still_refused_with_the_wrong_number_of_arguments():
    """The arity check must happen before the heavy gate, not after: a bad call is a formula error, not a deferral."""
    registry = _registry(COUNT_IT)
    with pytest.raises(FormulaError) as raised:
        _try("=COUNT_IT()", {}, registry)
    assert "takes 1 argument" in raised.value.detail
