"""The registry with the built-in functions, and the check that their examples tell the truth."""

from __future__ import annotations

import math

from ..formula.forms import CORE_NAMES
from ..refs import SheetId
from ..values import ErrorValue, FormulaError, Value
from .base import Bound, Example
from .library import builtin_classes
from .registry import FunctionRegistry


def builtin_registry() -> FunctionRegistry:
    """A new registry holding every built-in function. The names of the core's own functions are reserved in it."""
    registry = FunctionRegistry(reserved=CORE_NAMES)
    for cls in builtin_classes():
        registry.register(cls)
    return registry


class ScratchSheet:
    """A sheet made of a few given cells, for running an example."""

    def __init__(self, cells: dict[str, Value]):
        from ..refs import parse_cell_ref

        self.grid: dict[tuple[int, int], Value] = {}
        self.rows_used = self.cols_used = 0
        for address, value in cells.items():
            ref = parse_cell_ref(address)
            self.grid[(ref.row, ref.col)] = value
            self.rows_used = max(self.rows_used, ref.row + 1)
            self.cols_used = max(self.cols_used, ref.col + 1)

    def column_version(self, col: int) -> int:
        return 0

    def version(self) -> int:
        return 0


def run_example(registry: FunctionRegistry, example: Example) -> Value:
    """What the example's formula gives, evaluated against its cells alone (errors come back as values)."""
    from ..formula import parse_formula
    from ..formula.compiler import Compiler
    from ..formula.operators import single
    from ..formula.scope import Scope

    scope = Scope({SheetId("s1"): ScratchSheet(dict(example.cells))}, lambda name: None)
    scope.enter(SheetId("s1"), 50, 50)  # (away from the example's cells)
    parsed = parse_formula(example.formula)
    if parsed.ast is None:
        return parsed.error
    try:
        return single(Compiler(registry).compile(parsed.ast)(scope))
    except FormulaError as problem:
        return problem.value()


def agrees(actual: Value, expected: Value) -> bool:
    if isinstance(expected, ErrorValue) or isinstance(actual, ErrorValue):
        return isinstance(expected, ErrorValue) and isinstance(actual, ErrorValue) and expected.code == actual.code
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual is expected
    if isinstance(expected, float) and isinstance(actual, (int, float)):
        return math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    return actual == expected


def check_examples(registry: FunctionRegistry, only: list[Bound] | None = None) -> list[str]:
    """Run the examples of the functions (all in the registry unless ``only``) and say what is wrong, one line each:
    the list is empty when every example gives the result it states."""
    problems = []
    for bound in only if only is not None else registry:
        for example in bound.examples:
            actual = run_example(registry, example)
            if not agrees(actual, example.result):
                problems.append(f"{example.formula} gave {actual!r}, the example says {example.result!r}")
    return problems
