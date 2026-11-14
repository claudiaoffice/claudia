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
from ..spill import Matrix
from ..values import DIV0, NA, NUM, VALUE, ErrorValue, FormulaError, Value, finite, fits_int, format_value

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
    if value.__class__ is Matrix:
        if value.height * value.width != 1:
            raise FormulaError(VALUE, "several cells were used where one value is needed")
        found = value.value_at(0, 0)
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
    if isinstance(value, Range | Matrix):
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
    except (ValueError, OverflowError):
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


# -------------------------------------------------------------------------------- cell by cell
def _grid(operand: object) -> list[list[Value]] | None:
    """The cells of a range or matrix as rows when it has more than one cell, else ``None`` (it is a single value)."""
    if operand.__class__ is Range:
        if len(operand) <= 1:
            return None
        return [list(row) for row in operand.dense()]
    if operand.__class__ is Matrix:
        if operand.height * operand.width <= 1:
            return None
        return [list(row) for row in operand.rows]
    return None


def _cell(function: Callable[..., Value], *operands: Value) -> Value:
    for operand in operands:
        if operand.__class__ is ErrorValue:
            return operand
    try:
        return function(*operands)
    except FormulaError as problem:
        return problem.value()


def _at(grid: list[list[Value]], row: int, col: int) -> Value:
    """The cell of ``grid`` for a position of the result: a single row or column is repeated, beyond the end of a
    longer one there is nothing (``#N/A``), as in Excel."""
    rows, cols = len(grid), len(grid[0])
    if (rows > 1 and row >= rows) or (cols > 1 and col >= cols):
        return ErrorValue(NA)
    return grid[0 if rows == 1 else row][0 if cols == 1 else col]


def elementwise(function: Callable[..., Value], arity: int) -> Callable[..., Value | Matrix]:
    """``function`` for operands that may be ranges or matrices of several cells: it is applied to each cell (a single
    row or column is repeated against the other operand), and gives a ``Matrix``. With single values only, it is
    ``function`` itself, as fast as it was."""
    if arity == 1:

        def unary(a: Value) -> Value | Matrix:
            if a.__class__ is not Range and a.__class__ is not Matrix:
                return function(a)
            grid = _grid(a)
            if grid is None:
                return function(a)
            return Matrix(tuple(tuple(_cell(function, cell) for cell in row) for row in grid))

        return unary

    def binary(a: Value, b: Value) -> Value | Matrix:
        ca, cb = a.__class__, b.__class__
        if ca is not Range and ca is not Matrix and cb is not Range and cb is not Matrix:
            return function(a, b)
        grid_a, grid_b = _grid(a), _grid(b)
        if grid_a is None and grid_b is None:
            return function(a, b)
        left = grid_a if grid_a is not None else [[single(a)]]
        right = grid_b if grid_b is not None else [[single(b)]]
        height, width = max(len(left), len(right)), max(len(left[0]), len(right[0]))
        return Matrix(
            tuple(
                tuple(_cell(function, _at(left, i, j), _at(right, i, j)) for j in range(width)) for i in range(height)
            )
        )

    return binary


BINARY: dict[str, Callable[[Value, Value], Value | Matrix]] = {
    op: elementwise(function, 2)
    for op, function in {
        "+": add,
        "-": subtract,
        "*": multiply,
        "/": divide,
        "^": power,
        "&": join,
        **COMPARISONS,
    }.items()
}
NEGATE = elementwise(negate, 1)
PERCENT = elementwise(percent, 1)
