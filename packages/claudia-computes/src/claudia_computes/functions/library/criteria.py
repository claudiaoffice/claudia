"""SUMIF, COUNTIF, AVERAGEIF and their plural forms: functions of ranges and a *criterion*.

A criterion is a number or text to equal, or text starting with a comparison: ``">5"``, ``"<=10"``, ``"<>done"``,
``"=x"``. Text compares without regard to case and understands ``*`` (any text), ``?`` (one character) and ``~`` to
escape them. They are functions of ranges, so they are user functions like SUM; they read only the cells that hold
something in the range they add up, never a whole column of empty cells.
"""

from __future__ import annotations

import math
import operator
import re
from collections.abc import Callable, Iterator
from typing import Any

from ...values import DIV0, VALUE, ErrorValue, Value
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .aggregate import mean, total
from .catalog import builtin

_COMPARISONS: dict[str, Callable[[Any, Any], bool]] = {
    "=": operator.eq,
    "<>": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}
TABLE: dict[str, Value] = {"A1": "north", "A2": "south", "A3": "north", "B1": 10, "B2": 20, "B3": 30}
Test = Callable[[Value], bool]
_COMPARISON = re.compile(r"(<>|>=|<=|=|>|<)?(.*)", re.DOTALL)


class Criterion:
    """A test for one cell, made from the criterion a formula passes. ``accepts_empty``: do empty cells pass?"""

    def __init__(self, spec: Value):
        self.test, self.accepts_empty = self._make(spec)

    @staticmethod
    def _make(spec: Value) -> tuple[Test, bool]:
        if isinstance(spec, ErrorValue):
            raise spec.raised()
        if spec is None:
            spec = 0  # (an empty cell as a criterion means 0)
        if not isinstance(spec, str):
            return Criterion._equals(spec)
        operator, operand = _COMPARISON.fullmatch(spec).groups()  # type: ignore[union-attr]
        operator = operator or "="
        number = _number(operand)
        if number is not None and operand.strip():
            return Criterion._compare(operator, number)
        if operator in ("=", "<>"):
            if operand == "":  # "=" matches the empty cells, "<>" the cells that hold something
                return (lambda value: value is None) if operator == "=" else (
                    lambda value: value is not None
                ), operator == "="
            same = Criterion._same_text(operand)
            if operator == "=":
                return same, False
            return (lambda value: not same(value)), True
        return Criterion._compare(operator, operand)

    @staticmethod
    def _equals(spec: Value) -> tuple[Test, bool]:
        if spec.__class__ is bool:
            return (lambda value: value.__class__ is bool and value == spec), False
        return (lambda value: value.__class__ in (int, float) and value == spec), False

    @staticmethod
    def _same_text(pattern: str) -> Test:
        if not any(c in pattern for c in "*?~"):
            wanted = pattern.casefold()
            return lambda value: value.__class__ is str and value.casefold() == wanted
        from ...formula.forms.lookup import _pattern

        compiled = _pattern(pattern)
        return lambda value: value.__class__ is str and compiled.fullmatch(value) is not None

    @staticmethod
    def _compare(symbol: str, operand: int | float | str) -> tuple[Test, bool]:
        kind = str if isinstance(operand, str) else (int, float)
        wanted = operand.casefold() if isinstance(operand, str) else operand
        holds = _COMPARISONS[symbol]

        def test(value: Value) -> bool:
            if value.__class__ is bool or not isinstance(value, kind):
                return symbol == "<>"  # (a different kind of value is "not equal" and nothing else)
            here = value.casefold() if isinstance(value, str) else value
            return holds(here, wanted)

        return test, symbol == "<>"

    def __call__(self, value: Value) -> bool:
        return self.test(value)


def _number(text: str) -> int | float | None:
    try:
        return int(text)
    except ValueError:
        pass
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _pairs(args: tuple, shape_of: Range | None = None) -> list[tuple[Range, Criterion]]:
    if len(args) % 2:
        raise FunctionError(VALUE, "give each range its criterion")
    pairs = [
        (args[i], Criterion(args[i + 1].at(0, 0) if isinstance(args[i + 1], Range) else args[i + 1]))
        for i in range(0, len(args), 2)
    ]
    first = shape_of or pairs[0][0]
    if any((area.n_rows, area.n_cols) != (first.n_rows, first.n_cols) for area, _ in pairs):
        raise FunctionError(VALUE, "the ranges must have the same shape")
    return pairs


def selected_numbers(sums: Range, pairs: list[tuple[Range, Criterion]]) -> Iterator[int | float]:
    """The numbers of ``sums`` whose position passes every criterion (only cells holding something are visited)."""
    for row, col, value in sums.cells():
        if value.__class__ is ErrorValue:
            continue
        if value.__class__ in (int, float) and all(test(area.at(row, col)) for area, test in pairs):
            yield value


def count_matching(pairs: list[tuple[Range, Criterion]]) -> int:
    """How many positions pass every criterion."""
    driver = next((p for p in pairs if not p[1].accepts_empty), None)
    if driver is None:  # every criterion accepts empty cells: count everything, less the positions that fail
        looked_at = {(r, c) for area, _ in pairs for r, c, _ in area.cells()}  # (empty everywhere: passes)
        failing = sum(1 for r, c in looked_at if not all(test(a.at(r, c)) for a, test in pairs))
        return len(pairs[0][0]) - failing
    area, test = driver
    others = [p for p in pairs if p is not driver]
    return sum(1 for r, c, v in area.cells() if test(v) and all(t(a.at(r, c)) for a, t in others))


def _sum_range(match: Range, sums: Range | None) -> Range:
    """The cells to add up: the ones of ``sums`` in the shape of ``match`` (as Excel, from the corner of ``sums``)."""
    if sums is None:
        return match
    return sums.sub(0, 0, match.n_rows - 1, match.n_cols - 1)


@builtin
class COUNTIF(UserFunction):
    description = 'How many cells of the range meet the criterion (a value, or text like ">5", "<>x", "a*").'
    examples = (Example('=COUNTIF(A1:A3, "north")', 2, TABLE), Example('=COUNTIF(B1:B3, ">15")', 2, TABLE))

    def call(self, values: Range, criterion: Range):
        return count_matching(_pairs((values, criterion)))


@builtin
class COUNTIFS(UserFunction):
    description = "How many positions meet all the criteria: pairs of a range and its criterion, all of the same shape."
    examples = (Example('=COUNTIFS(A1:A3, "north", B1:B3, ">15")', 1, TABLE),)

    def call(self, *pairs: Range):
        return count_matching(_pairs(pairs))


@builtin
class SUMIF(UserFunction):
    description = (
        "Adds the numbers of the cells that meet the criterion; sums the range itself unless a sum range is given."
    )
    examples = (
        Example('=SUMIF(A1:A3, "north", B1:B3)', 40, TABLE),
        Example('=SUMIF(B1:B3, ">15")', 50, TABLE),
    )

    def call(self, values: Range, criterion: Range, sums: Range | None = None):
        pairs = _pairs((values, criterion))
        return total(list(selected_numbers(_sum_range(values, sums), pairs)))


@builtin
class SUMIFS(UserFunction):
    description = (
        "Adds the numbers of the sum range wherever all criteria are met (pairs of a range and its criterion)."
    )
    examples = (Example('=SUMIFS(B1:B3, A1:A3, "north", B1:B3, "<25")', 10, TABLE),)

    def call(self, sums: Range, *pairs: Range):
        return total(list(selected_numbers(sums, _pairs(pairs, shape_of=sums))))


@builtin
class AVERAGEIF(UserFunction):
    description = (
        "The mean of the numbers of the cells that meet the criterion (of the average range, if one is given)."
    )
    examples = (Example('=AVERAGEIF(A1:A3, "north", B1:B3)', 20, TABLE),)

    def call(self, values: Range, criterion: Range, averages: Range | None = None):
        found = list(selected_numbers(_sum_range(values, averages), _pairs((values, criterion))))
        if not found:
            raise FunctionError(DIV0, "no cell meets the criterion")
        return mean(found)


@builtin
class AVERAGEIFS(UserFunction):
    description = "The mean of the numbers of the average range wherever all criteria are met."
    examples = (Example('=AVERAGEIFS(B1:B3, A1:A3, "north")', 20, TABLE),)

    def call(self, averages: Range, *pairs: Range):
        found = list(selected_numbers(averages, _pairs(pairs, shape_of=averages)))
        if not found:
            raise FunctionError(DIV0, "no cell meets the criteria")
        return mean(found)


@builtin
class MAXIFS(UserFunction):
    description = "The largest number of the range wherever all criteria are met, 0 if none is."
    examples = (Example('=MAXIFS(B1:B3, A1:A3, "north")', 30, TABLE),)

    def call(self, values: Range, *pairs: Range):
        return max(selected_numbers(values, _pairs(pairs, shape_of=values)), default=0)


@builtin
class MINIFS(UserFunction):
    description = "The smallest number of the range wherever all criteria are met, 0 if none is."
    examples = (Example('=MINIFS(B1:B3, A1:A3, "north")', 10, TABLE),)

    def call(self, values: Range, *pairs: Range):
        return min(selected_numbers(values, _pairs(pairs, shape_of=values)), default=0)
