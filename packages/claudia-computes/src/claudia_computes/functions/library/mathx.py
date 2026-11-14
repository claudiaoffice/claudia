"""More functions of numbers: the inverse and hyperbolic trigonometry, whole-number functions (parity, GCD, counting),
rounding to multiples, number systems (ROMAN, BASE) and sums of squares.

They follow Excel where it differs from the textbook: ``ATAN2`` takes x first, ``ACOT`` runs from 0 to pi, and the
rounding functions work in decimals (``numeric.multiple``) so that ``MROUND(1.3, 0.2)`` is 1.4 and not
1.4000000000000001.
"""

from __future__ import annotations

import math
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP

from ...values import DIV0, NUM, VALUE, fits_int
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .aggregate import number_pairs, numbers_of
from .catalog import builtin
from .numeric import multiple


def whole(number: float) -> int:
    """A number cut at the decimal point, as the whole-number functions read their arguments."""
    return int(number)


def exact(result: int) -> int | float:
    """A whole result: an int while a float holds it exactly, else the float next to it."""
    return result if fits_int(result) else float(result)


def _guard(compute):
    """Run ``compute``; a domain error (``ValueError``) is ``#NUM!`` and a division by zero ``#DIV/0!``."""
    try:
        return compute()
    except ZeroDivisionError:
        raise FunctionError(DIV0) from None
    except (ValueError, OverflowError):
        raise FunctionError(NUM) from None


# -- inverse and hyperbolic trigonometry -----------------------------------------------------------------------------
@builtin
class ASIN(UserFunction):
    description = "The angle in radians (from -pi/2 to pi/2) whose sine is the number, which must be from -1 to 1."
    examples = (Example("=ROUND(ASIN(1), 5)", 1.5708),)

    def call(self, number: float):
        return math.asin(number)


@builtin
class ACOS(UserFunction):
    description = "The angle in radians (from 0 to pi) whose cosine is the number, which must be from -1 to 1."
    examples = (Example("=ROUND(ACOS(0.5), 5)", 1.0472),)

    def call(self, number: float):
        return math.acos(number)


@builtin
class ATAN(UserFunction):
    description = "The angle in radians (from -pi/2 to pi/2) whose tangent is the number."
    examples = (Example("=ROUND(ATAN(1), 5)", 0.7854),)

    def call(self, number: float):
        return math.atan(number)


@builtin
class ATAN2(UserFunction):
    description = "The angle in radians from the x axis to the point (x, y): x comes first, as in Excel."
    examples = (Example("=ROUND(ATAN2(1, 1), 5)", 0.7854), Example("=ATAN2(-1, 0)", math.pi))

    def call(self, x: float, y: float):
        if x == 0 and y == 0:
            raise FunctionError(DIV0, "the angle of the point (0, 0) is not defined")
        return math.atan2(y, x)


@builtin
class SINH(UserFunction):
    description = "The hyperbolic sine of a number."
    examples = (Example("=ROUND(SINH(1), 5)", 1.1752),)

    def call(self, number: float):
        return _guard(lambda: math.sinh(number))


@builtin
class COSH(UserFunction):
    description = "The hyperbolic cosine of a number."
    examples = (Example("=ROUND(COSH(1), 5)", 1.54308),)

    def call(self, number: float):
        return _guard(lambda: math.cosh(number))


@builtin
class TANH(UserFunction):
    description = "The hyperbolic tangent of a number."
    examples = (Example("=ROUND(TANH(1), 5)", 0.76159),)

    def call(self, number: float):
        return math.tanh(number)


@builtin
class ASINH(UserFunction):
    description = "The inverse hyperbolic sine of a number."
    examples = (Example("=ROUND(ASINH(1), 5)", 0.88137),)

    def call(self, number: float):
        return math.asinh(number)


@builtin
class ACOSH(UserFunction):
    description = "The inverse hyperbolic cosine of a number that is 1 or more."
    examples = (Example("=ACOSH(1)", 0), Example("=ROUND(ACOSH(10), 5)", 2.99322))

    def call(self, number: float):
        return math.acosh(number)


@builtin
class ATANH(UserFunction):
    description = "The inverse hyperbolic tangent of a number between -1 and 1 (not including them)."
    examples = (Example("=ROUND(ATANH(0.5), 5)", 0.54931),)

    def call(self, number: float):
        return math.atanh(number)


@builtin
class COT(UserFunction):
    description = "The cotangent of an angle in radians (1 / TAN)."
    examples = (Example("=ROUND(COT(1), 5)", 0.64209),)

    def call(self, angle: float):
        tangent = math.tan(angle)
        if tangent == 0:
            raise FunctionError(DIV0, "the cotangent of 0 is not defined")
        return 1 / tangent


@builtin
class COTH(UserFunction):
    description = "The hyperbolic cotangent of a number (1 / TANH)."
    examples = (Example("=ROUND(COTH(1), 5)", 1.31304),)

    def call(self, number: float):
        if number == 0:
            raise FunctionError(DIV0, "the hyperbolic cotangent of 0 is not defined")
        return 1 / math.tanh(number)


@builtin
class ACOT(UserFunction):
    description = "The angle in radians, from 0 to pi, whose cotangent is the number."
    examples = (Example("=ROUND(ACOT(2), 5)", 0.46365),)

    def call(self, number: float):
        return math.pi / 2 - math.atan(number)


@builtin
class ACOTH(UserFunction):
    description = "The inverse hyperbolic cotangent of a number whose size is more than 1."
    examples = (Example("=ROUND(ACOTH(2), 5)", 0.54931),)

    def call(self, number: float):
        if abs(number) <= 1:
            raise FunctionError(NUM, "this needs a number below -1 or above 1")
        return math.atanh(1 / number)


@builtin
class CSC(UserFunction):
    description = "The cosecant of an angle in radians (1 / SIN)."
    examples = (Example("=ROUND(CSC(1), 5)", 1.1884),)

    def call(self, angle: float):
        sine = math.sin(angle)
        if sine == 0:
            raise FunctionError(DIV0, "the cosecant of 0 is not defined")
        return 1 / sine


@builtin
class CSCH(UserFunction):
    description = "The hyperbolic cosecant of a number (1 / SINH)."
    examples = (Example("=ROUND(CSCH(1), 5)", 0.85092),)

    def call(self, number: float):
        if number == 0:
            raise FunctionError(DIV0, "the hyperbolic cosecant of 0 is not defined")
        return _guard(lambda: 1 / math.sinh(number))


@builtin
class SEC(UserFunction):
    description = "The secant of an angle in radians (1 / COS)."
    examples = (Example("=ROUND(SEC(1), 5)", 1.85082),)

    def call(self, angle: float):
        cosine = math.cos(angle)
        if cosine == 0:
            raise FunctionError(DIV0)
        return 1 / cosine


@builtin
class SECH(UserFunction):
    description = "The hyperbolic secant of a number (1 / COSH)."
    examples = (Example("=ROUND(SECH(1), 5)", 0.64805),)

    def call(self, number: float):
        return _guard(lambda: 1 / math.cosh(number))


# -- even, odd, quotient, divisors ------------------------------------------------------------------------------------
@builtin
class EVEN(UserFunction):
    description = "Rounds away from zero to the next even whole number."
    examples = (Example("=EVEN(1.5)", 2), Example("=EVEN(-1)", -2))

    def call(self, number: float):
        steps = math.ceil(abs(number) / 2)
        return int(math.copysign(2 * steps, number)) if number else 0


@builtin
class ODD(UserFunction):
    description = "Rounds away from zero to the next odd whole number."
    examples = (Example("=ODD(1.5)", 3), Example("=ODD(2)", 3))

    def call(self, number: float):
        magnitude = math.ceil(abs(number))
        magnitude += 1 - magnitude % 2
        return int(math.copysign(magnitude, number)) if number else 1


@builtin
class ISEVEN(UserFunction):
    description = "TRUE when the whole part of the number is even."
    examples = (Example("=ISEVEN(-2)", True), Example("=ISEVEN(3)", False))

    def call(self, number: float):
        return whole(number) % 2 == 0


@builtin
class ISODD(UserFunction):
    description = "TRUE when the whole part of the number is odd."
    examples = (Example("=ISODD(3)", True), Example("=ISODD(2)", False))

    def call(self, number: float):
        return whole(number) % 2 == 1


@builtin
class QUOTIENT(UserFunction):
    description = "The whole part of a division, cut towards zero (the remainder is left out)."
    examples = (Example("=QUOTIENT(5, 2)", 2), Example("=QUOTIENT(-10, 3)", -3))

    def call(self, numerator: float, denominator: float):
        if denominator == 0:
            raise FunctionError(DIV0)
        return int(numerator / denominator) if abs(numerator) < 2**52 else int(math.trunc(numerator / denominator))


def _whole_numbers(ranges: tuple[Range, ...]) -> list[int]:
    found = [whole(n) for n in numbers_of(ranges)]
    if any(n < 0 for n in found):
        raise FunctionError(NUM, "this needs numbers of 0 or more")
    return found


@builtin
class GCD(UserFunction):
    description = "The greatest common divisor of whole numbers (the decimals are cut off)."
    examples = (Example("=GCD(24, 36)", 12),)

    def call(self, *numbers: Range):
        return math.gcd(*_whole_numbers(numbers))


@builtin
class LCM(UserFunction):
    description = "The least common multiple of whole numbers (the decimals are cut off)."
    examples = (Example("=LCM(24, 36)", 72),)

    def call(self, *numbers: Range):
        return exact(math.lcm(*_whole_numbers(numbers)))


# -- counting ----------------------------------------------------------------------------------------------------------
def _counts(n: float, k: float) -> tuple[int, int]:
    n, k = whole(n), whole(k)
    if n < 0 or k < 0:
        raise FunctionError(NUM, "this needs numbers of 0 or more")
    return n, k


@builtin
class COMBIN(UserFunction):
    description = "The number of ways to choose k of n items when the order does not matter."
    examples = (Example("=COMBIN(8, 2)", 28),)

    def call(self, n: float, k: float):
        n, k = _counts(n, k)
        if k > n:
            raise FunctionError(NUM, "cannot choose more items than there are")
        return exact(math.comb(n, k))


@builtin
class COMBINA(UserFunction):
    description = "The number of ways to choose k of n items when the order does not matter and items can repeat."
    examples = (Example("=COMBINA(4, 3)", 20),)

    def call(self, n: float, k: float):
        n, k = _counts(n, k)
        if n == 0:
            return 1 if k == 0 else 0
        return exact(math.comb(n + k - 1, k))


@builtin
class PERMUT(UserFunction):
    description = "The number of ways to arrange k of n items when the order matters."
    examples = (Example("=PERMUT(100, 3)", 970200),)

    def call(self, n: float, k: float):
        n, k = _counts(n, k)
        if k > n:
            raise FunctionError(NUM, "cannot arrange more items than there are")
        return exact(math.perm(n, k))


@builtin
class PERMUTATIONA(UserFunction):
    description = "The number of ways to arrange k of n items when the order matters and items can repeat (n to the k)."
    examples = (Example("=PERMUTATIONA(3, 2)", 9),)

    def call(self, n: float, k: float):
        n, k = _counts(n, k)
        return exact(n**k) if k * max(n, 1).bit_length() < 4096 else _guard(lambda: float(n) ** k)


@builtin
class FACTDOUBLE(UserFunction):
    description = "The double factorial of a whole number: n * (n-2) * (n-4) ... down to 1 or 2."
    examples = (Example("=FACTDOUBLE(7)", 105),)

    def call(self, number: float):
        n = whole(number)
        if n < -1 or n > 300:
            raise FunctionError(NUM, "the double factorial is defined from 0 to 300 here")
        result = 1
        for factor in range(n, 1, -2):
            result *= factor
        return exact(result)


@builtin
class MULTINOMIAL(UserFunction):
    description = "The factorial of the sum of the numbers divided by the product of their factorials."
    examples = (Example("=MULTINOMIAL(2, 3, 4)", 1260),)

    def call(self, *numbers: Range):
        parts = _whole_numbers(numbers)
        result = math.factorial(sum(parts))
        for part in parts:
            result //= math.factorial(part)
        return exact(result)


@builtin
class SQRTPI(UserFunction):
    description = "The square root of a number times pi."
    examples = (Example("=ROUND(SQRTPI(2), 5)", 2.50663),)

    def call(self, number: float):
        if number < 0:
            raise FunctionError(NUM, "this needs a number of 0 or more")
        return math.sqrt(number * math.pi)


# -- rounding to a multiple --------------------------------------------------------------------------------------------
@builtin
class CEILING_MATH(UserFunction):
    name = "CEILING.MATH"
    description = (
        "Rounds up to a multiple of the significance (1 unless given). For a negative number the mode decides: "
        "0 rounds towards zero, anything else away from it."
    )
    examples = (Example("=CEILING.MATH(24.3, 5)", 25), Example("=CEILING.MATH(-5.5, 2, -1)", -6))

    def call(self, number: float, significance: float = 1.0, mode: float = 0.0):
        mode_rounding = ROUND_FLOOR if (number < 0 and mode != 0) else ROUND_CEILING
        return multiple(number, significance, mode_rounding)


@builtin
class FLOOR_MATH(UserFunction):
    name = "FLOOR.MATH"
    description = (
        "Rounds down to a multiple of the significance (1 unless given). For a negative number the mode decides: "
        "0 rounds away from zero, anything else towards it."
    )
    examples = (Example("=FLOOR.MATH(24.3, 5)", 20), Example("=FLOOR.MATH(-5.5, 2, -1)", -4))

    def call(self, number: float, significance: float = 1.0, mode: float = 0.0):
        mode_rounding = ROUND_CEILING if (number < 0 and mode != 0) else ROUND_FLOOR
        return multiple(number, significance, mode_rounding)


@builtin
class CEILING_PRECISE(UserFunction):
    name = "CEILING.PRECISE"
    description = "Rounds up (towards plus infinity) to a multiple of the significance; its sign is ignored."
    examples = (Example("=CEILING.PRECISE(4.3)", 5), Example("=CEILING.PRECISE(-4.3, 2)", -4))

    def call(self, number: float, significance: float = 1.0):
        return multiple(number, significance, ROUND_CEILING)


@builtin
class ISO_CEILING(UserFunction):
    name = "ISO.CEILING"
    description = "The same as CEILING.PRECISE: rounds up to a multiple of the significance; its sign is ignored."
    examples = (Example("=ISO.CEILING(4.3)", 5),)

    def call(self, number: float, significance: float = 1.0):
        return multiple(number, significance, ROUND_CEILING)


@builtin
class FLOOR_PRECISE(UserFunction):
    name = "FLOOR.PRECISE"
    description = "Rounds down (towards minus infinity) to a multiple of the significance; its sign is ignored."
    examples = (Example("=FLOOR.PRECISE(3.2)", 3), Example("=FLOOR.PRECISE(-3.2, -1)", -4))

    def call(self, number: float, significance: float = 1.0):
        return multiple(number, significance, ROUND_FLOOR)


@builtin
class MROUND(UserFunction):
    description = "Rounds to the nearest multiple of another number; halves go away from zero."
    examples = (Example("=MROUND(10, 3)", 9), Example("=MROUND(1.3, 0.2)", 1.4))

    def call(self, number: float, multiple_of: float):
        if multiple_of == 0:
            return 0
        if number * multiple_of < 0:
            raise FunctionError(NUM, "the number and the multiple need the same sign")
        rounded = multiple(abs(number), multiple_of, ROUND_HALF_UP)  # (``multiple`` ignores the sign of the step)
        return -rounded if number < 0 else rounded


# -- number systems ---------------------------------------------------------------------------------------------------
_NUMERALS = (("M", 1000), ("D", 500), ("C", 100), ("L", 50), ("X", 10), ("V", 5), ("I", 1))
#: how far a numeral may stand before a bigger one in each ROMAN form: the largest ratio of the two (form 0 only lets
#: I, X and C do it, and only before the next two numerals).
_SUBTRACTION_RATIO = {0: 10, 1: 10, 2: 50, 3: 100, 4: 500}


def _roman_symbols(form: int) -> list[tuple[str, int]]:
    symbols = list(_NUMERALS)
    ratio = _SUBTRACTION_RATIO[form]
    for small, small_value in _NUMERALS:
        if form == 0 and small not in "IXC":
            continue
        for big, big_value in _NUMERALS:
            if big_value > small_value and 5 <= big_value / small_value <= ratio:
                symbols.append((small + big, big_value - small_value))
    return sorted(symbols, key=lambda item: -item[1])


@builtin
class ROMAN(UserFunction):
    description = "A number from 0 to 3999 as a Roman numeral; the form 0 to 4 makes it more concise the higher it is."
    examples = (Example("=ROMAN(1994)", "MCMXCIV"), Example("=ROMAN(499, 4)", "ID"))

    def call(self, number: float, form: float = 0.0):
        n, which = whole(number), whole(form)
        if not 0 <= n <= 3999 or not 0 <= which <= 4:
            raise FunctionError(VALUE, "ROMAN reads numbers from 0 to 3999 and forms from 0 to 4")
        out = []
        for text, value in _roman_symbols(which):
            while n >= value:
                out.append(text)
                n -= value
        return "".join(out)


_ROMAN_VALUE = dict(_NUMERALS)


@builtin
class ARABIC(UserFunction):
    description = "A Roman numeral as a number (capitals or not; a leading minus sign is kept)."
    examples = (Example('=ARABIC("MCMXCIV")', 1994),)

    def call(self, text: str):
        text = text.strip().upper()
        sign = -1 if text.startswith("-") else 1
        text = text.lstrip("-")
        if any(char not in _ROMAN_VALUE for char in text):
            raise FunctionError(VALUE, "this is not a Roman numeral")
        values = [_ROMAN_VALUE[char] for char in text]
        total = sum(-v if i + 1 < len(values) and v < values[i + 1] else v for i, v in enumerate(values))
        return sign * total


_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@builtin
class BASE(UserFunction):
    description = "A whole number as text in another base (2 to 36), padded with zeros to a minimum length."
    examples = (Example("=BASE(255, 16)", "FF"), Example("=BASE(15, 2, 10)", "0000001111"))

    def call(self, number: float, radix: int, min_length: int = 0):
        n = whole(number)
        if n < 0 or n >= 2**53 or not 2 <= radix <= 36 or not 0 <= min_length <= 255:
            raise FunctionError(NUM, "BASE needs a number of 0 or more, a base from 2 to 36 and a length up to 255")
        out = ""
        while n:
            n, digit = divmod(n, radix)
            out = _DIGITS[digit] + out
        return (out or "0").rjust(min_length, "0")


@builtin
class DECIMAL(UserFunction):
    description = "Text in a base (2 to 36) as a number."
    examples = (Example('=DECIMAL("FF", 16)', 255),)

    def call(self, text: str, radix: int):
        if not 2 <= radix <= 36:
            raise FunctionError(NUM, "the base is from 2 to 36")
        total = 0
        for char in text.strip().upper():
            digit = _DIGITS.find(char)
            if digit < 0 or digit >= radix:
                raise FunctionError(NUM, f"{char!r} is not a digit in base {radix}")
            total = total * radix + digit
        return exact(total)


# -- sums of squares and series ----------------------------------------------------------------------------------------
@builtin
class SUMSQ(UserFunction):
    description = "The sum of the squares of the numbers in the ranges. Text and empty cells are skipped."
    examples = (Example("=SUMSQ(3, 4)", 25),)

    def call(self, *values: Range):
        numbers = numbers_of(values)
        if all(n.__class__ is int for n in numbers):
            return sum(n * n for n in numbers)
        return math.fsum(n * n for n in numbers)


@builtin
class SUMX2MY2(UserFunction):
    description = "The sum of x squared minus y squared over pairs of two ranges of the same size."
    examples = (Example("=SUMX2MY2(A1:A2, B1:B2)", -3, {"A1": 1, "A2": 2, "B1": 2, "B2": 2}),)

    def call(self, x: Range, y: Range):
        return math.fsum(a * a - b * b for a, b in number_pairs(x, y))


@builtin
class SUMX2PY2(UserFunction):
    description = "The sum of x squared plus y squared over pairs of two ranges of the same size."
    examples = (Example("=SUMX2PY2(A1:A2, B1:B2)", 13, {"A1": 1, "A2": 2, "B1": 2, "B2": 2}),)

    def call(self, x: Range, y: Range):
        return math.fsum(a * a + b * b for a, b in number_pairs(x, y))


@builtin
class SUMXMY2(UserFunction):
    description = "The sum of the squares of x minus y over pairs of two ranges of the same size."
    examples = (Example("=SUMXMY2(A1:A2, B1:B2)", 1, {"A1": 1, "A2": 2, "B1": 2, "B2": 2}),)

    def call(self, x: Range, y: Range):
        return math.fsum((a - b) ** 2 for a, b in number_pairs(x, y))


@builtin
class SERIESSUM(UserFunction):
    description = "The sum of a power series: each coefficient times x to a power that starts at n and grows by m."
    examples = (Example("=SERIESSUM(2, 0, 1, A1:A3)", 7, {"A1": 1, "A2": 1, "A3": 1}),)

    def call(self, x: float, n: float, m: float, coefficients: Range):
        if not all(c.__class__ in (int, float) for c in coefficients.present()):
            raise FunctionError(VALUE, "the coefficients must be numbers")
        terms = [c * x ** (n + i * m) for i, c in enumerate(coefficients.vector() or [])]
        return _guard(lambda: math.fsum(t for t in terms))
