"""The values a formula works with, and the errors it can end in.

A cell holds one of: ``None`` (empty), ``int``, ``float``, ``str``, ``bool`` or an ``ErrorValue``. ``FormulaError`` is
the exception that carries an error up through an expression until a cell (or ``IFERROR``) takes it as a value.
Errors use Excel's codes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

DIV0 = "#DIV/0!"
VALUE = "#VALUE!"
NAME = "#NAME?"
REF = "#REF!"
NUM = "#NUM!"
NA = "#N/A"
NULL = "#NULL!"
SYNTAX = "#ERROR!"  # the text is not a formula at all
CIRC = "#CIRC!"  # the formula depends on itself

ERROR_CODES = frozenset({DIV0, VALUE, NAME, REF, NUM, NA, NULL, SYNTAX, CIRC})
INT_LIMIT = 2**53  # beyond this a float holds the number as exactly as a person can use it


@dataclass(frozen=True, slots=True)
class ErrorValue:
    """An error as a cell's value. ``detail`` says why, in words, where that helps the person."""

    code: str
    detail: str = ""

    def __str__(self) -> str:
        return self.code

    def raised(self) -> FormulaError:
        """The same error as an exception, to carry it through an expression."""
        return FormulaError(self.code, self.detail)


class FormulaError(Exception):
    """An error while evaluating: ``code`` is the Excel-style code, ``detail`` the reason in words."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.detail = detail

    def value(self) -> ErrorValue:
        """The error as the value a cell shows."""
        return ErrorValue(self.code, self.detail)


Value = int | float | str | bool | ErrorValue | None


def fits_int(number: int) -> bool:
    """Does the whole number stay exact when it is shown as a float?"""
    return -INT_LIMIT <= number <= INT_LIMIT


def format_value(value: Value) -> str:
    """A value as text, the way ``&`` and the text functions see it (``2.0`` is ``2``, ``TRUE`` is ``TRUE``)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e15:
            return str(int(value))
        return format(value, ".15g")
    return str(value)


def finite(value: float) -> float:
    """``value`` if it is a number a cell can show, else ``#NUM!``."""
    if not math.isfinite(value):
        raise FormulaError(NUM, "the result is too large to be a number")
    return value
