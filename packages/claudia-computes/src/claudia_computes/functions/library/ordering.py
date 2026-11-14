"""How values order and compare for the functions that sort, rank and collect (the same rules as the operators: numbers
before text before TRUE/FALSE, text without regard to case; an empty cell or an error goes last)."""

from __future__ import annotations

from ...values import ErrorValue, Value


def rank(value: Value) -> int:
    """The kind of a value in sort order: numbers 0, text 1, TRUE/FALSE 2."""
    if value.__class__ is bool:
        return 2
    return 1 if value.__class__ is str else 0


def sort_key(value: Value):
    """What to compare for two values of the same kind."""
    return value.casefold() if value.__class__ is str else value


def group(value: Value) -> int:
    """0 for a value that has a place in the order, 1 for an empty cell, 2 for an error: those two go last."""
    if value is None:
        return 1
    return 2 if value.__class__ is ErrorValue else 0


def order_key(value: Value, descending: bool):
    """A key for ``sorted(..., reverse=descending)`` that puts empty cells and errors last, whichever way it sorts."""
    g = group(value)
    if g:
        return (-g if descending else g, 0, 0)
    return (0, rank(value), sort_key(value))


def identity(value: Value) -> object:
    """What two values must share to be the same value (text without regard to case, TRUE apart from 1)."""
    if value.__class__ is bool:
        return ("b", value)
    if value.__class__ is str:
        return value.casefold()
    if value.__class__ is ErrorValue:
        return ("e", value.code)
    return value
