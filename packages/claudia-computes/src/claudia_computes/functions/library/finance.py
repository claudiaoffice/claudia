"""Money over time: payments, present and future values, net present value and the internal rate of return.

The signs are Excel's: money paid out is negative, money received is positive. A loan of 10,000 received now
(``pv`` 10000) is paid back with negative payments, so ``PMT`` of it is negative. ``type`` 1 means the payments fall
at the start of each period, 0 (the default) at its end.

Cash flows for ``NPV`` and ``IRR`` are read row by row, left to right, in the order the cells stand -- the order is the
timeline, so it matters -- and only numbers count: text, TRUE/FALSE and empty cells are skipped, as Excel does.
"""

from __future__ import annotations

import math

from ...values import DIV0, NUM, ErrorValue, Value
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .catalog import builtin

FLOWS: dict[str, Value] = {"A1": -10000, "A2": 3000, "A3": 4200, "A4": 6800}
_IRR_STEPS = 100
_IRR_TOLERANCE = 1e-10


def _growth(rate: float, periods: float) -> float:
    try:
        return (1 + rate) ** periods
    except OverflowError:
        raise FunctionError(NUM, "the numbers grow too large") from None


def _when(kind: float) -> int:
    return 0 if kind == 0 else 1


def _flows(ranges: tuple[Range, ...]) -> list[float]:
    """The numbers of the ranges in the order they stand, row by row; an error in them is raised."""
    found: list[float] = []
    for area in ranges:
        for _, _, value in area.cells():
            if isinstance(value, ErrorValue):
                raise value.raised()
            if value.__class__ in (int, float):
                found.append(float(value))
    return found


@builtin
class PMT(UserFunction):
    description = "The payment per period that pays off a loan (or saves up a sum) at a fixed rate."
    examples = (Example("=ROUND(PMT(0.05/12,120,10000),2)", -106.07, note="10,000 over 10 years at 5% a year"),)

    def call(self, rate: float, periods: float, present: float, future: float = 0.0, kind: float = 0.0):
        if periods == 0:
            raise FunctionError(NUM, "the number of periods cannot be 0")
        if rate == 0:
            return -(present + future) / periods
        growth = _growth(rate, periods)
        return -(rate * (future + present * growth)) / ((1 + rate * _when(kind)) * (growth - 1))


@builtin
class FV(UserFunction):
    description = "What a sum and regular payments are worth after a number of periods at a fixed rate."
    examples = (Example("=ROUND(FV(0.04,10,-1000),2)", 12006.11, note="1,000 saved at the end of each of 10 years"),)

    def call(self, rate: float, periods: float, payment: float, present: float = 0.0, kind: float = 0.0):
        if rate == 0:
            return -(present + payment * periods)
        growth = _growth(rate, periods)
        return -(present * growth + payment * (1 + rate * _when(kind)) * (growth - 1) / rate)


@builtin
class PV(UserFunction):
    description = "What regular payments (and a sum at the end) are worth today at a fixed rate."
    examples = (Example("=ROUND(PV(0.05,10,-1000),2)", 7721.73, note="1,000 a year for 10 years"),)

    def call(self, rate: float, periods: float, payment: float, future: float = 0.0, kind: float = 0.0):
        if rate == 0:
            return -(future + payment * periods)
        growth = _growth(rate, periods)
        return -(future + payment * (1 + rate * _when(kind)) * (growth - 1) / rate) / growth


@builtin
class NPV(UserFunction):
    description = "The value today of cash flows at the end of each coming period, discounted at a rate."
    examples = (Example("=ROUND(NPV(0.08,A2:A4),2)", 11776.66, FLOWS),)

    def call(self, rate: float, *flows: Range):
        if rate == -1:
            raise FunctionError(DIV0, "a rate of -100% discounts by zero")
        values = _flows(flows)
        return math.fsum(value / _growth(rate, period) for period, value in enumerate(values, start=1))


def _npv_at(rate: float, values: list[float]) -> tuple[float, float]:
    """The net present value of ``values`` (the first at period 0) at ``rate``, and its derivative by the rate."""
    total = slope = 0.0
    for period, value in enumerate(values):
        factor = (1 + rate) ** period
        total += value / factor
        slope -= period * value / (factor * (1 + rate))
    return total, slope


@builtin
class IRR(UserFunction):
    description = "The rate at which cash flows (the first one now, one per period after it) are worth nothing today."
    examples = (Example("=ROUND(IRR(A1:A4),4)", 0.1634, FLOWS),)

    def call(self, flows: Range, guess: float = 0.1):
        values = _flows((flows,))
        if not any(v > 0 for v in values) or not any(v < 0 for v in values):
            raise FunctionError(NUM, "the cash flows need at least one payment and one receipt")
        rate = guess
        scale = max(1.0, *(abs(v) for v in values))
        for _ in range(_IRR_STEPS):
            if rate <= -1:
                break
            total, slope = _npv_at(rate, values)
            if abs(total) < _IRR_TOLERANCE * scale:
                return rate
            if slope == 0:
                break
            rate -= total / slope
        return _bisect(values)


def _bisect(values: list[float]) -> float:
    """The rate by halving an interval where the value changes sign, when Newton's steps do not settle."""
    low, high = -0.9999, 1.0
    while _npv_at(high, values)[0] * _npv_at(low, values)[0] > 0 and high < 1e6:
        high *= 2
    f_low = _npv_at(low, values)[0]
    if f_low * _npv_at(high, values)[0] > 0:
        raise FunctionError(NUM, "no rate makes these cash flows worth nothing")
    for _ in range(200):
        middle = (low + high) / 2
        f_middle = _npv_at(middle, values)[0]
        if abs(f_middle) < _IRR_TOLERANCE or high - low < 1e-12:
            return middle
        if f_low * f_middle < 0:
            high = middle
        else:
            low, f_low = middle, f_middle
    return (low + high) / 2
