"""More statistics: the A versions of the aggregates, ranks and percentiles, modes, regression and correlation, shape.

The names that say *sample* or *population* (``STDEV.S``, ``VARP`` ...) are the same functions as ``STDEV`` and
``VAR.P``. Pairs of ranges (``CORREL``, ``SLOPE`` ...) must have the same size; a position where either range holds
no number is left out of the pair, as in Excel.
"""

from __future__ import annotations

import math
from fractions import Fraction

from ...values import DIV0, NA, NUM, ErrorValue
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .aggregate import mean, number_pairs, numbers_of, ordered_numbers, spread
from .catalog import builtin

DATA = {"A1": 3, "A2": 7, "A3": 8, "A4": 5, "A5": 12, "A6": 14, "A7": 21, "A8": 13, "A9": 18}
XY = {"A1": 1, "A2": 2, "A3": 3, "A4": 4, "B1": 2, "B2": 4, "B3": 6, "B4": 8}


def _sample(sample: bool, numbers: list[int | float]) -> float:
    return spread(numbers, sample=sample)


# -- the names that say sample or population ------------------------------------------------------------------------
@builtin
class STDEV_S(UserFunction):
    name = "STDEV.S"
    description = "The standard deviation of a sample (the same as STDEV)."
    examples = (Example("=ROUND(STDEV.S(A1:A9), 4)", 5.9954, DATA),)

    def call(self, *values: Range):
        return math.sqrt(_sample(True, numbers_of(values)))


@builtin
class VAR_S(UserFunction):
    name = "VAR.S"
    description = "The variance of a sample (the same as VAR)."
    examples = (Example("=ROUND(VAR.S(A1:A9), 4)", 35.9444, DATA),)

    def call(self, *values: Range):
        return _sample(True, numbers_of(values))


@builtin
class STDEVP(UserFunction):
    description = "The standard deviation of a whole population (the old name of STDEV.P)."
    examples = (Example("=ROUND(STDEVP(A1:A9), 4)", 5.6525, DATA),)

    def call(self, *values: Range):
        return math.sqrt(_sample(False, numbers_of(values)))


@builtin
class VARP(UserFunction):
    description = "The variance of a whole population (the old name of VAR.P)."
    examples = (Example("=ROUND(VARP(A1:A9), 4)", 31.9506, DATA),)

    def call(self, *values: Range):
        return _sample(False, numbers_of(values))


# -- the A versions: text counts as 0, TRUE as 1 and FALSE as 0 -----------------------------------------------------
def values_a(ranges: tuple[Range, ...]) -> list[float]:
    """The numbers of the ranges as the A functions read them: text is 0, TRUE is 1, FALSE is 0, empty cells are left
    out and an error is raised."""
    found: list[float] = []
    for area in ranges:
        for value in area.present():
            if isinstance(value, ErrorValue):
                raise value.raised()
            if isinstance(value, bool):  # (before the numbers: a bool is an int)
                found.append(int(value))
            elif isinstance(value, (int, float)):
                found.append(value)
            elif isinstance(value, str):
                found.append(0)
    return found


@builtin
class AVERAGEA(UserFunction):
    description = "The mean of the cells with text counted as 0 and TRUE as 1 (empty cells are skipped)."
    examples = (Example("=AVERAGEA(A1:A3)", 1.0, {"A1": 3, "A2": "x", "A3": 0}),)

    def call(self, *values: Range):
        return mean(values_a(values))


@builtin
class MAXA(UserFunction):
    description = "The largest of the cells with text counted as 0 and TRUE as 1; 0 if there are none."
    examples = (Example("=MAXA(A1:A3)", 1, {"A1": -2, "A2": True, "A3": 0}),)

    def call(self, *values: Range):
        return max(values_a(values), default=0)


@builtin
class MINA(UserFunction):
    description = "The smallest of the cells with text counted as 0 and TRUE as 1; 0 if there are none."
    examples = (Example("=MINA(A1:A3)", 0, {"A1": 5, "A2": "x", "A3": True}),)

    def call(self, *values: Range):
        return min(values_a(values), default=0)


@builtin
class STDEVA(UserFunction):
    description = "The standard deviation of a sample, text counted as 0 and TRUE as 1."
    examples = (Example("=STDEVA(A1:A3)", 1.0, {"A1": 1, "A2": 2, "A3": 3}),)

    def call(self, *values: Range):
        return math.sqrt(_sample(True, values_a(values)))


@builtin
class STDEVPA(UserFunction):
    description = "The standard deviation of a population, text counted as 0 and TRUE as 1."
    examples = (Example("=STDEVPA(A1:A2)", 0.5, {"A1": 1, "A2": 2}),)

    def call(self, *values: Range):
        return math.sqrt(_sample(False, values_a(values)))


@builtin
class VARA(UserFunction):
    description = "The variance of a sample, text counted as 0 and TRUE as 1."
    examples = (Example("=VARA(A1:A3)", 1.0, {"A1": 1, "A2": 2, "A3": 3}),)

    def call(self, *values: Range):
        return _sample(True, values_a(values))


@builtin
class VARPA(UserFunction):
    description = "The variance of a population, text counted as 0 and TRUE as 1."
    examples = (Example("=VARPA(A1:A2)", 0.25, {"A1": 1, "A2": 2}),)

    def call(self, *values: Range):
        return _sample(False, values_a(values))


# -- rank --------------------------------------------------------------------------------------------------------------
def _rank(number: float, ref: Range, order: float, *, average: bool) -> float:
    found = ref.numbers()
    if number not in found:
        raise FunctionError(NA, "the number is not in the range")
    ahead = sum(1 for v in found if (v < number if order else v > number))
    ties = sum(1 for v in found if v == number)
    rank = ahead + 1
    return rank + (ties - 1) / 2 if average else rank


@builtin
class RANK_EQ(UserFunction):
    name = "RANK.EQ"
    description = (
        "The rank of a number in a range, largest first (smallest first if order is not 0); equal numbers share the "
        "top rank."
    )
    examples = (Example("=RANK.EQ(3, A1:A3)", 2, {"A1": 1, "A2": 3, "A3": 5}),)

    def call(self, number: float, ref: Range, order: float = 0.0):
        return _rank(number, ref, order, average=False)


@builtin
class RANK(UserFunction):
    description = "The rank of a number in a range (the old name of RANK.EQ)."
    examples = (Example("=RANK(3, A1:A3, 1)", 2, {"A1": 1, "A2": 3, "A3": 5}),)

    def call(self, number: float, ref: Range, order: float = 0.0):
        return _rank(number, ref, order, average=False)


@builtin
class RANK_AVG(UserFunction):
    name = "RANK.AVG"
    description = (
        "The rank of a number in a range, largest first (smallest first if order is not 0); equal numbers get the "
        "average of their ranks."
    )
    examples = (Example("=RANK.AVG(3, A1:A4)", 1.5, {"A1": 3, "A2": 3, "A3": 1, "A4": 0}),)

    def call(self, number: float, ref: Range, order: float = 0.0):
        return _rank(number, ref, order, average=True)


# -- percentiles and quartiles -----------------------------------------------------------------------------------------
def _interpolated(ordered: list[int | float], position: float) -> float:
    low = math.floor(position)
    if low >= len(ordered) - 1:
        return ordered[-1]
    return ordered[low] + (position - low) * (ordered[low + 1] - ordered[low])


def percentile(numbers: list[int | float], k: float, *, exclusive: bool) -> float:
    """The k-th percentile (k from 0 to 1) by Excel's inclusive or exclusive definition."""
    ordered = sorted(numbers)
    n = len(ordered)
    if n == 0:
        raise FunctionError(NUM, "there are no numbers")
    if exclusive:
        if not (1 / (n + 1) - 1e-12 <= k <= n / (n + 1) + 1e-12):
            raise FunctionError(NUM, f"k must be from {1 / (n + 1):.4g} to {n / (n + 1):.4g} for {n} numbers")
        return _interpolated(ordered, min(max(k * (n + 1) - 1, 0), n - 1))
    if not 0 <= k <= 1:
        raise FunctionError(NUM, "k must be from 0 to 1")
    return _interpolated(ordered, k * (n - 1))


def quartile(numbers: list[int | float], quart: float, *, exclusive: bool) -> float:
    which = int(quart)
    low, high = (1, 3) if exclusive else (0, 4)
    if not low <= which <= high:
        raise FunctionError(NUM, f"the quartile is a number from {low} to {high}")
    return percentile(numbers, which / 4, exclusive=exclusive)


@builtin
class PERCENTILE_INC(UserFunction):
    name = "PERCENTILE.INC"
    description = "The k-th percentile (k from 0 to 1) of the numbers, 0 being the smallest and 1 the largest."
    examples = (Example("=PERCENTILE.INC(A1:A9, 0.25)", 7, DATA),)

    def call(self, array: Range, k: float):
        return percentile(array.numbers(), k, exclusive=False)


@builtin
class PERCENTILE(UserFunction):
    description = "The k-th percentile of the numbers (the old name of PERCENTILE.INC)."
    examples = (Example("=PERCENTILE(A1:A9, 0.9)", 18.6, DATA),)

    def call(self, array: Range, k: float):
        return percentile(array.numbers(), k, exclusive=False)


@builtin
class PERCENTILE_EXC(UserFunction):
    name = "PERCENTILE.EXC"
    description = "The k-th percentile of the numbers, leaving out 0 and 1: k must lie between 1/(n+1) and n/(n+1)."
    examples = (Example("=PERCENTILE.EXC(A1:A9, 0.25)", 6, DATA),)

    def call(self, array: Range, k: float):
        return percentile(array.numbers(), k, exclusive=True)


@builtin
class QUARTILE_INC(UserFunction):
    name = "QUARTILE.INC"
    description = "A quartile of the numbers: 0 the smallest, 1, 2 (the median), 3, 4 the largest."
    examples = (Example("=QUARTILE.INC(A1:A9, 3)", 14, DATA),)

    def call(self, array: Range, quart: float):
        return quartile(array.numbers(), quart, exclusive=False)


@builtin
class QUARTILE(UserFunction):
    description = "A quartile of the numbers (the old name of QUARTILE.INC)."
    examples = (Example("=QUARTILE(A1:A9, 1)", 7, DATA),)

    def call(self, array: Range, quart: float):
        return quartile(array.numbers(), quart, exclusive=False)


@builtin
class QUARTILE_EXC(UserFunction):
    name = "QUARTILE.EXC"
    description = "A quartile of the numbers, leaving out the smallest and the largest: 1, 2 (the median) or 3."
    examples = (Example("=QUARTILE.EXC(A1:A9, 1)", 6, DATA),)

    def call(self, array: Range, quart: float):
        return quartile(array.numbers(), quart, exclusive=True)


def percent_rank(numbers: list[int | float], x: float, significance: int, *, exclusive: bool) -> float:
    ordered = sorted(numbers)
    n = len(ordered)
    if significance < 1:
        raise FunctionError(NUM, "the significance is 1 or more")
    if n == 0 or x < ordered[0] or x > ordered[-1]:
        raise FunctionError(NA, "the value is outside the numbers")
    below = max(i for i, v in enumerate(ordered) if v <= x)  # the last number not above x
    first = ordered.index(ordered[below])  # (its first occurrence: equal numbers share a rank)
    base = (
        Fraction(first + (1 if exclusive else 0), n + (1 if exclusive else -1)) if n > 1 or exclusive else Fraction(1)
    )
    if ordered[below] == x or below == n - 1:
        rank = base
    else:
        step = Fraction(1, n + (1 if exclusive else -1))
        rank = base + step * (Fraction(x) - Fraction(ordered[below])) / (
            Fraction(ordered[below + 1]) - Fraction(ordered[below])
        ) * (below + 1 - first)
        # (between two different numbers that sit next to each other, the rank moves in proportion to the distance)
    scale = 10**significance
    return float(Fraction(math.floor(rank * scale), scale))


@builtin
class PERCENTRANK_INC(UserFunction):
    name = "PERCENTRANK.INC"
    description = (
        "The rank of a value among the numbers as a share from 0 to 1, cut (not rounded) to the significance in digits "
        "(3)."
    )
    examples = (Example("=PERCENTRANK.INC(A1:A4, 2)", 0.333, {"A1": 1, "A2": 2, "A3": 3, "A4": 4}),)

    def call(self, array: Range, x: float, significance: int = 3):
        return percent_rank(array.numbers(), x, significance, exclusive=False)


@builtin
class PERCENTRANK(UserFunction):
    description = "The rank of a value among the numbers as a share from 0 to 1 (the old name of PERCENTRANK.INC)."
    examples = (Example("=PERCENTRANK(A1:A4, 3)", 0.666, {"A1": 1, "A2": 2, "A3": 3, "A4": 4}),)

    def call(self, array: Range, x: float, significance: int = 3):
        return percent_rank(array.numbers(), x, significance, exclusive=False)


@builtin
class PERCENTRANK_EXC(UserFunction):
    name = "PERCENTRANK.EXC"
    description = (
        "The rank of a value among the numbers as a share between 0 and 1 (not including them), cut to the "
        "significance in digits (3)."
    )
    examples = (Example("=PERCENTRANK.EXC(A1:A4, 2)", 0.4, {"A1": 1, "A2": 2, "A3": 3, "A4": 4}),)

    def call(self, array: Range, x: float, significance: int = 3):
        return percent_rank(array.numbers(), x, significance, exclusive=True)


# -- modes -------------------------------------------------------------------------------------------------------------
def _mode(ranges: tuple[Range, ...]) -> float:
    counts: dict[float, int] = {}
    for area in ranges:
        for n in ordered_numbers(area):
            counts[n] = counts.get(n, 0) + 1
    top = max(counts.values(), default=0)
    if top < 2:
        raise FunctionError(NA, "no number occurs more than once")
    return next(n for n, c in counts.items() if c == top)  # (a tie: the one that came first)


@builtin
class MODE_SNGL(UserFunction):
    name = "MODE.SNGL"
    description = "The number that occurs most often (the first of them if there is a tie); #N/A if none occurs twice."
    examples = (Example("=MODE.SNGL(A1:A4)", 2, {"A1": 1, "A2": 2, "A3": 2, "A4": 3}),)

    def call(self, *values: Range):
        return _mode(values)


@builtin
class MODE(UserFunction):
    description = "The number that occurs most often (the old name of MODE.SNGL)."
    examples = (Example("=MODE(A1:A4)", 2, {"A1": 1, "A2": 2, "A3": 2, "A4": 3}),)

    def call(self, *values: Range):
        return _mode(values)


# -- means and deviations ---------------------------------------------------------------------------------------------
@builtin
class AVEDEV(UserFunction):
    description = "The average of the distances of the numbers from their mean."
    examples = (Example("=AVEDEV(A1:A4)", 1.0, {"A1": 1, "A2": 2, "A3": 3, "A4": 4}),)

    def call(self, *values: Range):
        numbers = numbers_of(values)
        centre = mean(numbers)
        return math.fsum(abs(n - centre) for n in numbers) / len(numbers)


@builtin
class DEVSQ(UserFunction):
    description = "The sum of the squared distances of the numbers from their mean."
    examples = (Example("=DEVSQ(A1:A3)", 2, {"A1": 1, "A2": 2, "A3": 3}),)

    def call(self, *values: Range):
        numbers = numbers_of(values)
        centre = mean(numbers)
        return math.fsum((n - centre) ** 2 for n in numbers)


def _positive(values: tuple[Range, ...]) -> list[int | float]:
    numbers = numbers_of(values)
    if not numbers or any(n <= 0 for n in numbers):
        raise FunctionError(NUM, "this needs numbers above 0 (and at least one)")
    return numbers


@builtin
class GEOMEAN(UserFunction):
    description = "The geometric mean of positive numbers."
    examples = (Example("=GEOMEAN(A1:A3)", 2, {"A1": 1, "A2": 2, "A3": 4}),)

    def call(self, *values: Range):
        numbers = _positive(values)
        return math.exp(math.fsum(math.log(n) for n in numbers) / len(numbers))


@builtin
class HARMEAN(UserFunction):
    description = "The harmonic mean of positive numbers."
    examples = (Example("=HARMEAN(A1:A2)", 4 / 3, {"A1": 1, "A2": 2}),)

    def call(self, *values: Range):
        numbers = _positive(values)
        return len(numbers) / math.fsum(1 / n for n in numbers)


@builtin
class TRIMMEAN(UserFunction):
    description = (
        "The mean of the numbers without the share (0 up to, not including, 1) of the smallest and largest, half cut "
        "from each end."
    )
    examples = (Example("=TRIMMEAN(A1:A5, 0.4)", 3, {"A1": 1, "A2": 3, "A3": 3, "A4": 3, "A5": 100}),)

    def call(self, array: Range, percent: float):
        numbers = sorted(array.numbers())
        if not 0 <= percent < 1 or not numbers:
            raise FunctionError(NUM, "the share to cut is from 0 up to (not including) 1")
        cut = int(len(numbers) * percent + 1e-9) // 2
        return mean(numbers[cut : len(numbers) - cut])


def _moments(numbers: list[int | float], needed: int):
    if len(numbers) < needed:
        raise FunctionError(DIV0, f"this needs at least {needed} numbers")
    return len(numbers), mean(numbers)


@builtin
class SKEW(UserFunction):
    description = "The skewness of a sample: how lopsided the numbers are around their mean."
    examples = (Example("=ROUND(SKEW(A1:A4), 4)", 1.7792, {"A1": 1, "A2": 1, "A3": 2, "A4": 6}),)

    def call(self, *values: Range):
        numbers = numbers_of(values)
        n, centre = _moments(numbers, 3)
        sd = math.sqrt(spread(numbers, sample=True))
        if sd == 0:
            raise FunctionError(DIV0, "all the numbers are the same")
        return n / ((n - 1) * (n - 2)) * math.fsum(((x - centre) / sd) ** 3 for x in numbers)


@builtin
class SKEW_P(UserFunction):
    name = "SKEW.P"
    description = "The skewness of a whole population."
    examples = (Example("=ROUND(SKEW.P(A1:A4), 4)", 1.0272, {"A1": 1, "A2": 1, "A3": 2, "A4": 6}),)

    def call(self, *values: Range):
        numbers = numbers_of(values)
        n, centre = _moments(numbers, 1)
        sd = math.sqrt(spread(numbers, sample=False))
        if sd == 0:
            raise FunctionError(DIV0, "all the numbers are the same")
        return math.fsum(((x - centre) / sd) ** 3 for x in numbers) / n


@builtin
class KURT(UserFunction):
    description = "The kurtosis of a sample (0 for a normal distribution): how heavy the tails are."
    examples = (Example("=ROUND(KURT(A1:A5), 4)", -1.2, {"A1": 1, "A2": 2, "A3": 3, "A4": 4, "A5": 5}),)

    def call(self, *values: Range):
        numbers = numbers_of(values)
        n, centre = _moments(numbers, 4)
        sd = math.sqrt(spread(numbers, sample=True))
        if sd == 0:
            raise FunctionError(DIV0, "all the numbers are the same")
        fourth = math.fsum(((x - centre) / sd) ** 4 for x in numbers)
        return n * (n + 1) / ((n - 1) * (n - 2) * (n - 3)) * fourth - 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))


@builtin
class STANDARDIZE(UserFunction):
    description = "How many standard deviations a value is from the mean."
    examples = (Example("=STANDARDIZE(42, 40, 2)", 1),)

    def call(self, x: float, mean: float, standard_dev: float):
        if standard_dev <= 0:
            raise FunctionError(NUM, "the standard deviation must be above 0")
        return (x - mean) / standard_dev


@builtin
class PROB(UserFunction):
    description = (
        "The probability that a value lies between two limits (or equals the lower one if there is no upper): values "
        "and their probabilities, which must add up to 1."
    )
    examples = (Example("=PROB(A1:A3, B1:B3, 2)", 0.5, {"A1": 1, "A2": 2, "A3": 3, "B1": 0.25, "B2": 0.5, "B3": 0.25}),)

    def call(self, x_range: Range, prob_range: Range, lower: float, upper: float | None = None):
        if (x_range.n_rows, x_range.n_cols) != (prob_range.n_rows, prob_range.n_cols):
            raise FunctionError(NA, "the values and their probabilities must have the same size")
        pairs = number_pairs(x_range, prob_range)
        if (
            not pairs
            or any(p <= 0 or p > 1 for _, p in pairs)
            or not math.isclose(math.fsum(p for _, p in pairs), 1, abs_tol=1e-9)
        ):
            raise FunctionError(NUM, "the probabilities must be from 0 up to 1 and add up to 1")
        high = lower if upper is None else upper
        return math.fsum(p for x, p in pairs if lower <= x <= high)


# -- regression and correlation ----------------------------------------------------------------------------------------
def _sums(first: Range, second: Range, *, minimum: int = 2):
    """For pairs (y, x): n, the means, and the sums of squares and products of the distances from the means."""
    pairs = number_pairs(first, second)
    n = len(pairs)
    if n < minimum:
        raise FunctionError(DIV0, f"this needs at least {minimum} pairs of numbers")
    my, mx = math.fsum(y for y, _ in pairs) / n, math.fsum(x for _, x in pairs) / n
    syy = math.fsum((y - my) ** 2 for y, _ in pairs)
    sxx = math.fsum((x - mx) ** 2 for _, x in pairs)
    sxy = math.fsum((y - my) * (x - mx) for y, x in pairs)
    return n, my, mx, syy, sxx, sxy


@builtin
class SLOPE(UserFunction):
    description = "The slope of the straight line that fits the known y and x values best."
    examples = (Example("=SLOPE(B1:B4, A1:A4)", 2, XY),)

    def call(self, known_y: Range, known_x: Range):
        _, _, _, _, sxx, sxy = _sums(known_y, known_x)
        if sxx == 0:
            raise FunctionError(DIV0, "the x values are all the same")
        return sxy / sxx


@builtin
class INTERCEPT(UserFunction):
    description = "Where the straight line that fits the known y and x values best crosses the y axis (x = 0)."
    examples = (Example("=INTERCEPT(B1:B4, A1:A4)", 0, XY),)

    def call(self, known_y: Range, known_x: Range):
        _, my, mx, _, sxx, sxy = _sums(known_y, known_x)
        if sxx == 0:
            raise FunctionError(DIV0, "the x values are all the same")
        return my - sxy / sxx * mx


@builtin
class RSQ(UserFunction):
    description = "The square of the correlation: how much of the variation of y the straight line explains (0 to 1)."
    examples = (Example("=RSQ(B1:B4, A1:A4)", 1, XY),)

    def call(self, known_y: Range, known_x: Range):
        _, _, _, syy, sxx, sxy = _sums(known_y, known_x)
        if sxx == 0 or syy == 0:
            raise FunctionError(DIV0, "the values do not vary")
        return sxy * sxy / (sxx * syy)


def _correlation(first: Range, second: Range) -> float:
    _, _, _, syy, sxx, sxy = _sums(first, second)
    if sxx == 0 or syy == 0:
        raise FunctionError(DIV0, "the values do not vary")
    return sxy / math.sqrt(sxx * syy)


@builtin
class CORREL(UserFunction):
    description = "The correlation of two ranges: -1 to 1, 0 when they are not related."
    examples = (Example("=CORREL(A1:A4, B1:B4)", 1, XY),)

    def call(self, array1: Range, array2: Range):
        return _correlation(array1, array2)


@builtin
class PEARSON(UserFunction):
    description = "The Pearson correlation of two ranges (the same as CORREL)."
    examples = (Example("=PEARSON(A1:A4, B1:B4)", 1, XY),)

    def call(self, array1: Range, array2: Range):
        return _correlation(array1, array2)


@builtin
class STEYX(UserFunction):
    description = "The standard error of the y values predicted by the straight line fitted to y and x."
    examples = (Example("=STEYX(B1:B4, A1:A4)", 0, XY),)

    def call(self, known_y: Range, known_x: Range):
        n, _, _, syy, sxx, sxy = _sums(known_y, known_x, minimum=3)
        if sxx == 0:
            raise FunctionError(DIV0, "the x values are all the same")
        return math.sqrt(max(syy - sxy * sxy / sxx, 0.0) / (n - 2))


def _forecast(x: float, known_y: Range, known_x: Range) -> float:
    _, my, mx, _, sxx, sxy = _sums(known_y, known_x)
    if sxx == 0:
        raise FunctionError(DIV0, "the x values are all the same")
    slope = sxy / sxx
    return my + slope * (x - mx)


@builtin
class FORECAST(UserFunction):
    description = "The y value the straight line fitted to the known y and x values gives at x."
    examples = (Example("=FORECAST(5, B1:B4, A1:A4)", 10, XY),)

    def call(self, x: float, known_y: Range, known_x: Range):
        return _forecast(x, known_y, known_x)


@builtin
class FORECAST_LINEAR(UserFunction):
    name = "FORECAST.LINEAR"
    description = "The y value the straight line fitted to the known y and x values gives at x (the same as FORECAST)."
    examples = (Example("=FORECAST.LINEAR(5, B1:B4, A1:A4)", 10, XY),)

    def call(self, x: float, known_y: Range, known_x: Range):
        return _forecast(x, known_y, known_x)


def _covariance(first: Range, second: Range, *, sample: bool) -> float:
    n, _, _, _, _, sxy = _sums(first, second, minimum=2 if sample else 1)
    return sxy / (n - 1 if sample else n)


@builtin
class COVARIANCE_P(UserFunction):
    name = "COVARIANCE.P"
    description = "The covariance of two ranges for a whole population."
    examples = (Example("=COVARIANCE.P(A1:A4, B1:B4)", 2.5, XY),)

    def call(self, array1: Range, array2: Range):
        return _covariance(array1, array2, sample=False)


@builtin
class COVAR(UserFunction):
    description = "The covariance of two ranges for a whole population (the old name of COVARIANCE.P)."
    examples = (Example("=COVAR(A1:A4, B1:B4)", 2.5, XY),)

    def call(self, array1: Range, array2: Range):
        return _covariance(array1, array2, sample=False)


@builtin
class COVARIANCE_S(UserFunction):
    name = "COVARIANCE.S"
    description = "The covariance of two ranges for a sample."
    examples = (Example("=ROUND(COVARIANCE.S(A1:A4, B1:B4), 4)", 3.3333, XY),)

    def call(self, array1: Range, array2: Range):
        return _covariance(array1, array2, sample=True)
