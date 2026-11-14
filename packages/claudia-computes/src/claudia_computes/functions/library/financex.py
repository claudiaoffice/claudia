"""More money over time: the number of periods and the rate of a loan, the interest and principal parts of a payment,
and the net present value and rate of return of cash flows on given dates.

Signs are Excel's (see ``finance``)."""

from __future__ import annotations

import math

from ...values import NUM
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .catalog import builtin
from .finance import FV, PMT, _growth, _when

_STEPS = 200


def _value(rate: float, periods: float, payment: float, present: float, future: float, kind: int) -> float:
    """What is left over when ``present``, ``payment`` per period and ``future`` are put together at ``rate``
    (zero at the right rate)."""
    if rate == 0:
        return present + payment * periods + future
    growth = _growth(rate, periods)
    return present * growth + payment * (1 + rate * kind) * (growth - 1) / rate + future


@builtin
class NPER(UserFunction):
    description = "The number of periods it takes regular payments at a fixed rate to pay off a loan or save up a sum."
    examples = (
        Example(
            "=ROUND(NPER(0.12/12,-100,-1000,10000,1),2)",
            59.67,
            note="start 1,000, save 100 a month at 12% a year, to reach 10,000",
        ),
    )

    def call(self, rate: float, payment: float, present: float, future: float = 0.0, kind: float = 0.0):
        when = _when(kind)
        if rate == 0:
            if payment == 0:
                raise FunctionError(NUM, "with no payments and no interest nothing changes")
            return -(present + future) / payment
        due = payment * (1 + rate * when)
        top, bottom = due - future * rate, present * rate + due
        if bottom == 0 or top / bottom <= 0 or rate <= -1:
            raise FunctionError(NUM, "these numbers never reach the sum")
        return math.log(top / bottom) / math.log(1 + rate)


@builtin
class RATE(UserFunction):
    description = (
        "The interest rate per period of a loan or saving plan, found by trying rates from a guess (10% if none is "
        "given)."
    )
    examples = (Example("=ROUND(RATE(48,-200,8000)*12,4)", 0.0924, note="8,000 paid back in 48 payments of 200"),)

    def call(
        self, periods: float, payment: float, present: float, future: float = 0.0, kind: float = 0.0, guess: float = 0.1
    ):
        when = _when(kind)
        if periods <= 0:
            raise FunctionError(NUM, "the number of periods must be above 0")

        def f(rate: float) -> float:
            return _value(rate, periods, payment, present, future, when)

        rate = guess
        for _ in range(_STEPS):
            if rate <= -1:
                rate = -0.99
            step = 1e-7 * max(1.0, abs(rate))
            here = f(rate)
            if abs(here) < 1e-12 * max(1.0, abs(present), abs(payment * periods), abs(future)):
                return rate
            slope = (f(rate + step) - here) / step
            if slope == 0:
                break
            rate -= here / slope
        return _search(f)


def _search(f) -> float:
    """A rate where ``f`` changes sign, by halving, when Newton's steps do not settle."""
    low, high = -0.999, 1.0
    f_low = f(low)
    while f_low * f(high) > 0 and high < 1e6:
        high *= 2
    if f_low * f(high) > 0:
        raise FunctionError(NUM, "no rate fits these numbers")
    for _ in range(300):
        middle = (low + high) / 2
        f_middle = f(middle)
        if f_low * f_middle <= 0:
            high = middle
        else:
            low, f_low = middle, f_middle
    return (low + high) / 2


def _interest(rate: float, period: float, periods: float, present: float, future: float, kind: float) -> float:
    if not 1 <= period <= periods:
        raise FunctionError(NUM, "the period is from 1 to the number of periods")
    when = _when(kind)
    payment = PMT().call(rate, periods, present, future, kind)
    if when == 1:
        if period == 1:
            return 0.0
        return (FV().call(rate, period - 2, payment, present, 1) - payment) * rate
    return FV().call(rate, period - 1, payment, present, 0) * rate


@builtin
class IPMT(UserFunction):
    description = "The interest part of the payment in one period of a loan at a fixed rate."
    examples = (Example("=ROUND(IPMT(0.1/12,1,36,8000),2)", -66.67, note="the first month of 8,000 over 3 years"),)

    def call(self, rate: float, period: float, periods: float, present: float, future: float = 0.0, kind: float = 0.0):
        return _interest(rate, period, periods, present, future, kind)


@builtin
class PPMT(UserFunction):
    description = (
        "The part of the payment in one period that pays off the loan itself (the payment without the interest)."
    )
    examples = (Example("=ROUND(PPMT(0.1/12,1,24,2000),2)", -75.62, note="the first month of 2,000 over 2 years"),)

    def call(self, rate: float, period: float, periods: float, present: float, future: float = 0.0, kind: float = 0.0):
        return PMT().call(rate, periods, present, future, kind) - _interest(
            rate, period, periods, present, future, kind
        )


# -- cash flows on dates -----------------------------------------------------------------------------------------------
def _dated(values: Range, dates: Range) -> list[tuple[float, float]]:
    flows = [float(v) for v in values.numbers()]
    days = [math.floor(d) for d in dates.numbers()]
    if len(flows) != len(days) or len(flows) < 2 or len(flows) != len(values) or len(days) != len(dates):
        raise FunctionError(NUM, "the values and the dates must be numbers, the same many, at least 2")
    if any(d < days[0] for d in days):
        raise FunctionError(NUM, "no date may come before the first one")
    return [(flow, (day - days[0]) / 365) for flow, day in zip(flows, days, strict=True)]


def _xnpv(rate: float, dated: list[tuple[float, float]]) -> float:
    return math.fsum(flow / (1 + rate) ** years for flow, years in dated)


@builtin
class XNPV(UserFunction):
    description = (
        "The value today of cash flows on given dates (the first date is today), discounted at a yearly rate of 365 "
        "days."
    )
    examples = (
        Example(
            "=ROUND(XNPV(0.1,A1:A3,B1:B3),2)",
            2.24,
            {"A1": -100, "A2": 50, "A3": 60, "B1": 46023, "B2": 46204, "B3": 46388},
        ),
    )

    def call(self, rate: float, values: Range, dates: Range):
        if rate <= -1:
            raise FunctionError(NUM, "a rate of -100% or less discounts by zero")
        return _xnpv(rate, _dated(values, dates))


@builtin
class XIRR(UserFunction):
    description = (
        "The yearly rate at which cash flows on given dates are worth nothing today; needs a payment and a receipt."
    )
    examples = (
        Example(
            "=ROUND(XIRR(A1:A3,B1:B3),4)",
            0.1323,
            {"A1": -100, "A2": 50, "A3": 60, "B1": 46023, "B2": 46204, "B3": 46388},
        ),
    )

    def call(self, values: Range, dates: Range, guess: float = 0.1):
        dated = _dated(values, dates)
        if not any(f > 0 for f, _ in dated) or not any(f < 0 for f, _ in dated):
            raise FunctionError(NUM, "the cash flows need at least one payment and one receipt")
        rate = guess if guess > -1 else 0.1
        scale = max(abs(f) for f, _ in dated)
        for _ in range(_STEPS):
            total = _xnpv(rate, dated)
            if abs(total) < 1e-10 * scale:
                return rate
            slope = math.fsum(-years * flow / (1 + rate) ** (years + 1) for flow, years in dated)
            if slope == 0:
                break
            new = rate - total / slope
            if new <= -1:
                break
            rate = new
        return _search(lambda r: _xnpv(r, dated))
