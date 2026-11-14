"""Helpers for the tests of the Excel functions: evaluate a formula against a few cells, read arrays, compare."""

from __future__ import annotations

import datetime as dt
import math

import pytest

from claudia_computes.formula import parse_formula
from claudia_computes.formula.compiler import Compiler
from claudia_computes.formula.scope import Scope
from claudia_computes.functions.builtin import ScratchSheet, builtin_registry
from claudia_computes.refs import SheetId, parse_cell_ref
from claudia_computes.spill import Matrix
from claudia_computes.values import ErrorValue, FormulaError

REGISTRY = builtin_registry()
NOW = dt.datetime(2026, 11, 13, 14, 30, 15)  # (the moment every test thinks it is: a Friday)


def put(top_left: str, rows: list[list]) -> dict:
    """``{address: value}`` for a block of values whose first cell is ``top_left`` (``None`` leaves a cell empty)."""
    start = parse_cell_ref(top_left)
    out = {}
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            if value is not None:
                out[f"{_col(start.col + j)}{start.row + i + 1}"] = value
    return out


def column(top_left: str, values: list) -> dict:
    return put(top_left, [[v] for v in values])


def row(top_left: str, values: list) -> dict:
    return put(top_left, [list(values)])


def _col(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def raw(formula: str, cells: dict | None = None, *, at: str = "Z99", sheets: dict | None = None, now=NOW):
    """What the formula evaluates to, untouched: a value, a ``Range`` or a ``Matrix`` (errors come back as values)."""
    sheet = ScratchSheet(dict(cells or {}))
    scope = Scope(
        {SheetId("s1"): sheet, **(sheets or {})}, lambda name: SheetId("s1") if name.casefold() == "sheet1" else None
    )
    scope.clock = lambda: now
    ref = parse_cell_ref(at)
    scope.enter(SheetId("s1"), ref.row, ref.col)
    parsed = parse_formula(formula)
    if parsed.ast is None:
        return parsed.error
    try:
        return Compiler(REGISTRY).compile(parsed.ast)(scope)
    except FormulaError as problem:
        return problem.value()


def value(formula: str, cells: dict | None = None, **kw):
    """The single value of a formula (a one-cell matrix or range is its cell)."""
    from claudia_computes.formula.operators import single

    result = raw(formula, cells, **kw)
    if isinstance(result, ErrorValue):
        return result
    try:
        return single(result)
    except FormulaError as problem:
        return problem.value()


def array(formula: str, cells: dict | None = None, **kw) -> list[list]:
    """The rows of a formula that gives several cells."""
    result = raw(formula, cells, **kw)
    assert isinstance(result, Matrix), f"{formula} gave {result!r}"
    return [list(r) for r in result.rows]


def code(formula: str, cells: dict | None = None, **kw) -> str:
    result = value(formula, cells, **kw)
    assert isinstance(result, ErrorValue), f"{formula} gave {result!r}"
    return result.code


def same(actual, expected, *, tol: float = 1e-9) -> bool:
    if isinstance(actual, ErrorValue):  # (an error inside a result is written as its code)
        return isinstance(expected, str) and actual.code == expected
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual is expected
    if isinstance(expected, float) or isinstance(actual, float):
        return isinstance(actual, (int, float)) and math.isclose(actual, expected, rel_tol=tol, abs_tol=tol)
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(same(a, e, tol=tol) for a, e in zip(actual, expected, strict=True))
        )
    return actual == expected


def check(formula: str, expected, cells: dict | None = None, *, tol: float = 1e-9, **kw) -> None:
    """The formula gives ``expected``: an error code (text starting ``#``), a number (to 1e-9), text, TRUE/FALSE, or
    a list of lists for several cells."""
    if isinstance(expected, list):
        actual = array(formula, cells, **kw)
    elif isinstance(expected, str) and expected.startswith("#") and expected.endswith(("!", "?", "A")):
        assert code(formula, cells, **kw) == expected, formula
        return
    else:
        actual = value(formula, cells, **kw)
    assert same(actual, expected, tol=tol), f"{formula} gave {actual!r}, expected {expected!r}"


def cases(*items):
    """``pytest.mark.parametrize`` over (formula, expected) or (formula, expected, cells)."""
    rows = [(i[0], i[1], i[2] if len(i) > 2 else None) for i in items]
    return pytest.mark.parametrize("formula, expected, cells", rows, ids=[r[0] for r in rows])
