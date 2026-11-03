"""Functions of numbers: rounding, powers and roots, logarithms, trigonometry."""

from __future__ import annotations

import math
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_UP, ROUND_UP, Decimal

from ...values import DIV0, NUM, fits_int
from ..base import Example, FunctionError, UserFunction
from .catalog import builtin


def rounded(number: float, digits: int, mode: str) -> int | float:
    """``number`` rounded to ``digits`` decimals (negative: tens, hundreds ...) by a ``decimal`` rounding mode.

    The decimal is read from the shortest text of the float (``2.675``, not ``2.67499999999999982...``), which is what
    the person sees and means."""
    if not math.isfinite(number) or abs(digits) > 400:
        raise FunctionError(NUM)
    exponent = Decimal(1).scaleb(-digits)
    result = Decimal(repr(number)).quantize(exponent, rounding=mode)
    if digits <= 0:
        whole = int(result)
        return whole if fits_int(whole) else float(whole)
    return float(result)


def multiple(number: float, significance: float, mode: str) -> float:
    """``number`` rounded to a multiple of ``significance`` (up or down by ``mode``), computed in decimals."""
    if significance == 0:
        return 0.0
    step = abs(Decimal(repr(significance)))
    return float((Decimal(repr(number)) / step).to_integral_value(mode) * step)


@builtin
class ABS(UserFunction):
    description = "The size of a number without its sign."
    examples = (Example("=ABS(-4.5)", 4.5),)

    def call(self, number: float):
        return abs(number)


@builtin
class SIGN(UserFunction):
    description = "1 for a positive number, -1 for a negative one, 0 for 0."
    examples = (Example("=SIGN(-12)", -1),)

    def call(self, number: float):
        return (number > 0) - (number < 0)


@builtin
class ROUND(UserFunction):
    description = "Rounds to a number of decimals (negative: to tens, hundreds ...); halves go away from zero."
    examples = (Example("=ROUND(2.675, 2)", 2.68), Example("=ROUND(1234, -2)", 1200))

    def call(self, number: float, digits: int = 0):
        return rounded(number, digits, ROUND_HALF_UP)


@builtin
class ROUNDUP(UserFunction):
    description = "Rounds away from zero to a number of decimals."
    examples = (Example("=ROUNDUP(2.121, 2)", 2.13),)

    def call(self, number: float, digits: int = 0):
        return rounded(number, digits, ROUND_UP)


@builtin
class ROUNDDOWN(UserFunction):
    description = "Rounds towards zero to a number of decimals."
    examples = (Example("=ROUNDDOWN(-2.129, 2)", -2.12),)

    def call(self, number: float, digits: int = 0):
        return rounded(number, digits, ROUND_DOWN)


@builtin
class TRUNC(UserFunction):
    description = "Cuts a number off after a number of decimals."
    examples = (Example("=TRUNC(8.97)", 8),)

    def call(self, number: float, digits: int = 0):
        return rounded(number, digits, ROUND_DOWN)


@builtin
class INT(UserFunction):
    description = "Rounds down to the next whole number (-1.5 gives -2)."
    examples = (Example("=INT(-1.5)", -2),)

    def call(self, number: float):
        return rounded(number, 0, ROUND_FLOOR)


@builtin
class CEILING(UserFunction):
    description = "Rounds up to a multiple of the significance (1 unless given; its sign is ignored)."
    examples = (Example("=CEILING(2.1, 0.5)", 2.5), Example("=CEILING(-2.1)", -2))

    def call(self, number: float, significance: float = 1.0):
        return multiple(number, significance, ROUND_CEILING)


@builtin
class FLOOR(UserFunction):
    description = "Rounds down to a multiple of the significance (1 unless given; its sign is ignored)."
    examples = (Example("=FLOOR(2.6, 0.5)", 2.5), Example("=FLOOR(-2.1)", -3))

    def call(self, number: float, significance: float = 1.0):
        return multiple(number, significance, ROUND_FLOOR)


@builtin
class MOD(UserFunction):
    description = "The remainder of a division; it has the sign of the divisor."
    examples = (Example("=MOD(-7, 3)", 2),)

    def call(self, number: float, divisor: float):
        if divisor == 0:
            raise FunctionError(DIV0)
        return number % divisor


@builtin
class SQRT(UserFunction):
    description = "The square root of a number that is not negative."
    examples = (Example("=SQRT(16)", 4),)

    def call(self, number: float):
        return math.sqrt(number)


@builtin
class POWER(UserFunction):
    description = "A number raised to a power (the same as the operator ^)."
    examples = (Example("=POWER(2, 10)", 1024),)

    def call(self, number: float, power: float):
        if number == 0 and power < 0:
            raise FunctionError(DIV0)
        return math.pow(number, power)


@builtin
class EXP(UserFunction):
    description = "e raised to a power."
    examples = (Example("=EXP(0)", 1),)

    def call(self, power: float):
        return math.exp(power)


@builtin
class LN(UserFunction):
    description = "The natural logarithm of a positive number."
    examples = (Example("=LN(1)", 0),)

    def call(self, number: float):
        return math.log(number)


@builtin
class LOG(UserFunction):
    description = "The logarithm of a positive number to a base (10 unless given)."
    examples = (Example("=LOG(8, 2)", 3), Example("=LOG(1000)", 3))

    def call(self, number: float, base: float = 10.0):
        if base == 10:  # (log(x, 10) gives 2.9999999999999996 for 1000: these two are exact for powers of the base)
            return math.log10(number)
        if base == 2:
            return math.log2(number)
        return math.log(number, base)


@builtin
class LOG10(UserFunction):
    description = "The base 10 logarithm of a positive number."
    examples = (Example("=LOG10(100)", 2),)

    def call(self, number: float):
        return math.log10(number)


@builtin
class FACT(UserFunction):
    description = "The factorial of a whole number (1 * 2 * ... * n)."
    examples = (Example("=FACT(5)", 120),)

    def call(self, number: int):
        if number < 0 or number > 170:
            raise FunctionError(NUM, "the factorial is defined from 0 to 170 here")
        return math.factorial(number)


@builtin
class PI(UserFunction):
    description = "The number pi."
    examples = (Example("=ROUND(PI(), 5)", 3.14159),)

    def call(self):
        return math.pi


@builtin
class SIN(UserFunction):
    description = "The sine of an angle in radians."
    examples = (Example("=SIN(0)", 0),)

    def call(self, angle: float):
        return math.sin(angle)


@builtin
class COS(UserFunction):
    description = "The cosine of an angle in radians."
    examples = (Example("=COS(0)", 1),)

    def call(self, angle: float):
        return math.cos(angle)


@builtin
class TAN(UserFunction):
    description = "The tangent of an angle in radians."
    examples = (Example("=TAN(0)", 0),)

    def call(self, angle: float):
        return math.tan(angle)


@builtin
class RADIANS(UserFunction):
    description = "An angle in degrees as radians."
    examples = (Example("=ROUND(RADIANS(180), 5)", 3.14159),)

    def call(self, degrees: float):
        return math.radians(degrees)


@builtin
class DEGREES(UserFunction):
    description = "An angle in radians as degrees."
    examples = (Example("=DEGREES(PI())", 180),)

    def call(self, radians: float):
        return math.degrees(radians)
