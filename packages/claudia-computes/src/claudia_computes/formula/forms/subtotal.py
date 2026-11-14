"""SUBTOTAL and AGGREGATE: a summary that leaves out the subtotals inside the range, so totals can be nested.

A cell whose formula uses SUBTOTAL or AGGREGATE is skipped, so a subtotal of a column that holds subtotals does not
count anything twice. The model has no hidden rows (yet), so SUBTOTAL 101-111 equal 1-11 and the AGGREGATE options
that skip hidden rows work like the ones that do not."""

from __future__ import annotations

import math
import statistics

from ...functions.library.statistics_more import percentile, quartile
from ...functions.range import Range
from ...values import DIV0, NUM, VALUE, ErrorValue, FormulaError
from ..compiler import Compiler, Evaluator
from ..nodes import Node
from ..operators import to_number
from . import form, wrong_count

_NESTED = ("SUBTOTAL(", "AGGREGATE(")


def _collect(scope, areas: list[Range], *, skip_errors: bool) -> list:
    """The values of the cells that hold something, without the nested subtotals; errors are raised or skipped."""
    found: list = []
    for area in areas:
        for row, col, value in area.cells():
            if (text := scope.formula_of(area.sheet_id, (area.row0 + row, area.col0 + col))) and any(
                word in text.upper() for word in _NESTED
            ):
                continue
            if value.__class__ is ErrorValue:
                if skip_errors:
                    continue
                raise value.raised()
            found.append(value)
    return found


def _numbers(values: list) -> list[int | float]:
    return [v for v in values if v.__class__ is int or v.__class__ is float]


def _product(numbers):
    return math.prod(numbers) if numbers else 0


def _deviation(sample: bool):
    def compute(numbers):
        if len(numbers) < (2 if sample else 1):
            raise FormulaError(DIV0, "this needs more numbers")
        return statistics.variance(numbers) if sample else statistics.pvariance(numbers)

    return compute


SUMMARIES = {
    1: lambda n: math.fsum(n) / len(n) if n else _raise(DIV0),
    4: lambda n: max(n, default=0),
    5: lambda n: min(n, default=0),
    6: _product,
    7: lambda n: math.sqrt(_deviation(True)(n)),
    8: lambda n: math.sqrt(_deviation(False)(n)),
    9: lambda n: math.fsum(n) if any(isinstance(x, float) for x in n) else sum(n),
    10: _deviation(True),
    11: _deviation(False),
    12: lambda n: statistics.median(n) if n else _raise(NUM),
}


def _raise(code: str):
    raise FormulaError(code, "there is nothing to calculate from")


def _mode(numbers):
    counts: dict = {}
    for n in numbers:
        counts[n] = counts.get(n, 0) + 1
    top = max(counts.values(), default=0)
    if top < 2:
        raise FormulaError("#N/A", "no number occurs more than once")
    return next(n for n, c in counts.items() if c == top)


SUMMARIES[13] = _mode


def _summary(number: int, values: list):
    if number == 2:
        return len(_numbers(values))
    if number == 3:
        return len(values)
    return SUMMARIES[number](_numbers(values))


@form("SUBTOTAL")
def subtotal(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """SUBTOTAL(function, range, ...): a summary (1 AVERAGE, 2 COUNT, 3 COUNTA, 4 MAX, 5 MIN, 6 PRODUCT, 7 STDEV,
    8 STDEV.P, 9 SUM, 10 VAR, 11 VAR.P; add 100 to skip hidden rows) that leaves out other SUBTOTAL cells."""
    if len(args) < 2:
        return wrong_count("SUBTOTAL", len(args), 2, None)
    number = compiler.compile(args[0])
    areas = [compiler.compile_range(arg) for arg in args[1:]]

    def evaluate(scope):
        which = int(to_number(number(scope)))
        which = which - 100 if 101 <= which <= 111 else which
        if not 1 <= which <= 11:
            raise FormulaError(VALUE, "the function number is 1 to 11 (or 101 to 111)")
        return _summary(which, _collect(scope, [a(scope) for a in areas], skip_errors=False))

    return evaluate


@form("AGGREGATE")
def aggregate(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """AGGREGATE(function, options, range, ..., [k]): like SUBTOTAL with more functions (1-13 as SUBTOTAL but with 12
    MEDIAN and 13 MODE.SNGL; 14 LARGE, 15 SMALL, 16 PERCENTILE.INC, 17 QUARTILE.INC, 18 PERCENTILE.EXC, 19 QUARTILE.EXC
    take a range and k) and a choice what to skip: options 2, 3, 6 and 7 skip errors, 4 skips nothing but the other
    subtotals."""
    if len(args) < 3:
        return wrong_count("AGGREGATE", len(args), 3, None)
    number, options = compiler.compile(args[0]), compiler.compile(args[1])
    areas = [compiler.compile_range(arg) for arg in args[2:]]
    last = compiler.compile(args[-1])

    def evaluate(scope):
        which = int(to_number(number(scope)))
        option = int(to_number(options(scope)))
        if not 1 <= which <= 19 or not 0 <= option <= 7:
            raise FormulaError(VALUE, "the function is 1 to 19 and the option 0 to 7")
        skip = option in (2, 3, 6, 7)
        if which <= 13:
            return _summary(which, _collect(scope, [a(scope) for a in areas], skip_errors=skip))
        if len(args) != 4:
            raise FormulaError(VALUE, "this function takes one range and k")
        k = to_number(last(scope))
        numbers = _numbers(_collect(scope, [areas[0](scope)], skip_errors=skip))
        if which in (14, 15):
            if not numbers or not 1 <= k <= len(numbers):
                raise FormulaError(NUM, "k is outside the numbers")
            return sorted(numbers, reverse=which == 14)[int(k) - 1]
        if which in (16, 18):
            return percentile(numbers, k, exclusive=which == 18)
        return quartile(numbers, k, exclusive=which == 19)

    return evaluate
