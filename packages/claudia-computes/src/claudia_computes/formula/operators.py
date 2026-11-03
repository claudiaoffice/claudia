"""The operators of the formula language: arithmetic, joining text and comparing. These are part of the core.

Whole numbers stay whole while they are exact (``2 + 3`` is the integer 5, ``2^10`` the integer 1024) and become
floats beyond 2^53; a division always gives a float. An empty cell counts as 0 in arithmetic. Text is not a number
here (``"3" + 1`` is ``#VALUE!``), and a range is not a single value. Numbers are compared by value, text without
regard to case, and values of different kinds are ordered number < text < TRUE/FALSE and are never equal. (Numeric
semantics are an open decision, E6.4: this module is the one place that would change.)
"""

from __future__ import annotations

import math
from collections.abc import Callable

from ..functions.range import Range
from ..values import DIV0, NUM, VALUE, ErrorValue, FormulaError, Value, finite, fits_int, format_value

Number = int | float


def single(value: object) -> Value:
    """The value a single value is wanted for: a range of one cell is its cell, a longer range is ``#VALUE!``."""
    if isinstance(value, Range):
        if len(value) != 1:
            raise FormulaError(VALUE, "a range was used where one value is needed")
        found = value.at(0, 0)
        if found.__class__ is ErrorValue:
            raise found.raised()
        return found
    return value  # type: ignore[return-value]


def to_number(value: object) -> Number:
    """A value as a number: empty is 0, TRUE is 1 and FALSE 0; text and errors are not numbers."""
    if value is None:
        return 0
    cls = value.__class__
    if cls is int or cls is float:
        return value  # type: ignore[return-value]
    if cls is bool:
        return int(value)  # type: ignore[call-overload]
    if isinstance(value, Range):
        return to_number(single(value))
    raise FormulaError(VALUE, "this is not a number")


def exact(result: int) -> Number:
    """A whole result: an int while it is exact, else the float next to it (or ``#NUM!`` when even that is too big)."""
    return result if fits_int(result) else finite(float(result))


def add(a: Value, b: Value) -> Number:
    if a.__class__ is int and b.__class__ is int:
        return exact(a + b)
    return _sum(to_number(a), to_number(b))


def _sum(a: Number, b: Number) -> Number:
    if a.__class__ is int and b.__class__ is int:
        return exact(a + b)
    return finite(a + b)


def subtract(a: Value, b: Value) -> Number:
    x, y = to_number(a), to_number(b)
    if x.__class__ is int and y.__class__ is int:
        return exact(x - y)
    return finite(x - y)


def multiply(a: Value, b: Value) -> Number:
    x, y = to_number(a), to_number(b)
    if x.__class__ is int and y.__class__ is int:
        return exact(x * y)
    return finite(x * y)


def divide(a: Value, b: Value) -> float:
    x, y = to_number(a), to_number(b)
    if y == 0:
        raise FormulaError(DIV0)
    return finite(x / y)  # (a division is always a float, also 6 / 3)


def power(a: Value, b: Value) -> Number:
    base, exponent = to_number(a), to_number(b)
    # Exact while the result can still be an int. If it certainly cannot (the bits needed are more than an int has), do
    # not build the huge number: 9^9^9 must not hang a server.
    if (
        base.__class__ is int
        and exponent.__class__ is int
        and exponent >= 0
        and (abs(base) < 2 or (abs(base).bit_length() - 1) * exponent <= 64)
    ):
        return exact(base**exponent)
    if base == 0 and exponent < 0:
        raise FormulaError(DIV0)
    try:
        return finite(math.pow(base, exponent))
    except ValueError, OverflowError:
        raise FormulaError(NUM) from None


def negate(a: Value) -> Number:
    x = to_number(a)
    return exact(-x) if x.__class__ is int else -x


def percent(a: Value) -> float:
    return finite(to_number(a) / 100)


def join(a: Value, b: Value) -> str:
    return format_value(single(a)) + format_value(single(b))


# -------------------------------------------------------------------------------- comparing
def rank(value: Value) -> int:
    """Kinds of value in the order Excel sorts them: numbers, then text, then TRUE/FALSE."""
    if value.__class__ is bool:
        return 2
    return 1 if value.__class__ is str else 0


def blank_like(other: Value) -> Value:
    """What an empty cell is when compared with ``other``."""
    return False if other.__class__ is bool else ("" if other.__class__ is str else 0)


def sort_key(value: Value):
    """The thing to compare for two values of the same rank."""
    return value.casefold() if value.__class__ is str else value


def compare(a: Value, b: Value) -> int:
    """-1, 0 or 1: how ``a`` orders against ``b``. Values of different kinds are never 0."""
    a, b = single(a), single(b)
    if a is None:
        a = blank_like(b) if b is not None else 0
    if b is None:
        b = blank_like(a)
    ra, rb = rank(a), rank(b)
    if ra != rb:
        return -1 if ra < rb else 1
    x, y = sort_key(a), sort_key(b)
    return -1 if x < y else (1 if x > y else 0)


def _equal(a: Value, b: Value) -> bool:
    return compare(a, b) == 0


COMPARISONS: dict[str, Callable[[Value, Value], bool]] = {
    "=": _equal,
    "<>": lambda a, b: compare(a, b) != 0,
    "<": lambda a, b: compare(a, b) < 0,
    "<=": lambda a, b: compare(a, b) <= 0,
    ">": lambda a, b: compare(a, b) > 0,
    ">=": lambda a, b: compare(a, b) >= 0,
}

BINARY: dict[str, Callable[[Value, Value], Value]] = {
    "+": add,
    "-": subtract,
    "*": multiply,
    "/": divide,
    "^": power,
    "&": join,
    **COMPARISONS,
}
