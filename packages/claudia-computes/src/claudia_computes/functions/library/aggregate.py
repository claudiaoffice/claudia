"""Functions that take ranges and give one number: SUM, AVERAGE, COUNT, MEDIAN, STDEV ...

They read only the cells that hold something, so ``SUM(A:A)`` costs what the column holds. Sums of decimals use
``math.fsum``: the result does not depend on the order the cells are visited in (a sparse sheet is not visited
row by row), and does not drift the way a running ``+`` does.
"""

from __future__ import annotations

import math
import statistics
from typing import Any

from ...values import DIV0, NUM, VALUE, ErrorValue, Value
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .catalog import builtin

LIST: dict[str, Value] = {"A1": 10, "A2": 20, "A3": 30}


def numbers_of(ranges: tuple[Range, ...]) -> list[int | float]:
    """The numbers in all the ranges (text, TRUE/FALSE and empty cells are skipped; an error is raised)."""
    found: list[int | float] = []
    for area in ranges:
        found.extend(area.numbers())
    return found


def total(numbers: list[int | float]) -> int | float:
    """The sum: exact for whole numbers, correctly rounded for decimals, in whatever order they come."""
    if all(n.__class__ is int for n in numbers):
        return sum(numbers)
    return math.fsum(numbers)


def mean(numbers: list[int | float]) -> float:
    if not numbers:
        raise FunctionError(DIV0, "there are no numbers to average")
    return total(numbers) / len(numbers)


def spread(numbers: list[int | float], *, sample: bool) -> float:
    """The variance of the numbers (``sample``: divided by n-1, else by n)."""
    needed = 2 if sample else 1
    if len(numbers) < needed:
        raise FunctionError(DIV0, f"this needs at least {needed} number{'s' if needed > 1 else ''}")
    centre = mean(numbers)
    return math.fsum((x - centre) ** 2 for x in numbers) / (len(numbers) - (1 if sample else 0))


@builtin
class SUM(UserFunction):
    description = "The sum of the numbers in the ranges. Text and empty cells are skipped."
    examples = (Example("=SUM(A1:A3)", 60, LIST), Example("=SUM(A1:A3, 5)", 65, LIST))

    def call(self, *values: Range):
        return total(numbers_of(values))


@builtin
class PRODUCT(UserFunction):
    description = "The product of the numbers in the ranges."
    examples = (Example("=PRODUCT(A1:A3)", 6000, LIST),)

    def call(self, *values: Range):
        result: int | float = 1
        for area in values:  # (cell by cell in sheet order: a product of decimals depends on the order)
            for _, _, value in area.cells():
                if value.__class__ is ErrorValue:
                    raise value.raised()
                if value.__class__ in (int, float):
                    result *= value
        return result


@builtin
class AVERAGE(UserFunction):
    description = "The mean of the numbers in the ranges. Text and empty cells are skipped."
    examples = (Example("=AVERAGE(A1:A3)", 20, LIST),)

    def call(self, *values: Range):
        return mean(numbers_of(values))


@builtin
class MIN(UserFunction):
    description = "The smallest number in the ranges, 0 if there is none."
    examples = (Example("=MIN(A1:A3)", 10, LIST),)

    def call(self, *values: Range):
        return min(numbers_of(values), default=0)


@builtin
class MAX(UserFunction):
    description = "The largest number in the ranges, 0 if there is none."
    examples = (Example("=MAX(A1:A3)", 30, LIST),)

    def call(self, *values: Range):
        return max(numbers_of(values), default=0)


@builtin
class COUNT(UserFunction):
    description = "How many numbers the ranges hold (text, TRUE/FALSE, errors and empty cells are not counted)."
    examples = (Example("=COUNT(A1:A4)", 2, {"A1": 1, "A2": "x", "A3": 3}),)

    def call(self, *values: Range):
        return sum(len(area.numbers(strict=False)) for area in values)


@builtin
class COUNTA(UserFunction):
    description = "How many cells in the ranges hold anything (numbers, text, TRUE/FALSE, even errors)."
    examples = (Example("=COUNTA(A1:A4)", 3, {"A1": 1, "A2": "x", "A3": True}),)

    def call(self, *values: Range):
        return sum(1 for area in values for _ in area.present())


@builtin
class COUNTBLANK(UserFunction):
    description = "How many cells in the range are empty."
    examples = (Example("=COUNTBLANK(A1:A4)", 2, {"A1": 1, "A3": 3}),)

    def call(self, values: Range):
        return len(values) - sum(1 for _ in values.present())


@builtin
class MEDIAN(UserFunction):
    description = (
        "The middle number of the numbers in the ranges (the mean of the two middle ones if their count is even)."
    )
    examples = (Example("=MEDIAN(A1:A4)", 25, {"A1": 10, "A2": 20, "A3": 30, "A4": 40}),)

    def call(self, *values: Range):
        found = numbers_of(values)
        if not found:
            raise FunctionError(NUM, "there are no numbers")
        return statistics.median(found)


@builtin
class VAR(UserFunction):
    description = "The variance of a sample (the numbers are a part of a larger whole)."
    examples = (Example("=VAR(A1:A3)", 100, LIST),)

    def call(self, *values: Range):
        return spread(numbers_of(values), sample=True)


@builtin
class VAR_P(UserFunction):
    name = "VAR.P"
    description = "The variance of a whole population (the numbers are all there is)."
    examples = (Example("=VAR.P(A1:A3)", 200 / 3, LIST),)

    def call(self, *values: Range):
        return spread(numbers_of(values), sample=False)


@builtin
class STDEV(UserFunction):
    description = "The standard deviation of a sample (the numbers are a part of a larger whole)."
    examples = (Example("=STDEV(A1:A3)", 10, LIST),)

    def call(self, *values: Range):
        return math.sqrt(spread(numbers_of(values), sample=True))


@builtin
class STDEV_P(UserFunction):
    name = "STDEV.P"
    description = "The standard deviation of a whole population (the numbers are all there is)."
    examples = (Example("=STDEV.P(A1:A3)", math.sqrt(200 / 3), LIST),)

    def call(self, *values: Range):
        return math.sqrt(spread(numbers_of(values), sample=False))


@builtin
class LARGE(UserFunction):
    description = "The k-th largest number in the range (1 is the largest)."
    examples = (Example("=LARGE(A1:A3, 2)", 20, LIST),)

    def call(self, values: Range, k: int):
        found = sorted(values.numbers(), reverse=True)
        if not 1 <= k <= len(found):
            raise FunctionError(NUM, f"k must be from 1 to {len(found)}")
        return found[k - 1]


@builtin
class SMALL(UserFunction):
    description = "The k-th smallest number in the range (1 is the smallest)."
    examples = (Example("=SMALL(A1:A3, 2)", 20, LIST),)

    def call(self, values: Range, k: int):
        found = sorted(values.numbers())
        if not 1 <= k <= len(found):
            raise FunctionError(NUM, f"k must be from 1 to {len(found)}")
        return found[k - 1]


@builtin
class SUMPRODUCT(UserFunction):
    description = "Multiplies the ranges cell by cell (they must have the same shape) and adds up the products."
    examples = (Example("=SUMPRODUCT(A1:A3, B1:B3)", 140, {**LIST, "B1": 1, "B2": 2, "B3": 3}),)

    def call(self, first: Range, *others: Range):
        shape = (first.n_rows, first.n_cols)
        if any((o.n_rows, o.n_cols) != shape for o in others):
            raise FunctionError(VALUE, "the ranges must have the same shape")
        columns = [{(r, c): v for r, c, v in area.cells()} for area in (first, *others)]
        products: list[int | float] = []
        for position in set.intersection(*(set(column) for column in columns)):  # (a missing cell is 0: no product)
            factors: list[Any] = [column[position] for column in columns]
            for factor in factors:
                if factor.__class__ is ErrorValue:
                    raise factor.raised()
            if all(f.__class__ in (int, float) for f in factors):  # (text and TRUE/FALSE count as 0)
                products.append(math.prod(factors))
        return total(products)
