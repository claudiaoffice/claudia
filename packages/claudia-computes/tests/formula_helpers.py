"""A small stand-in for a workbook, so formulas can be evaluated without the model."""

from __future__ import annotations

from claudia_computes.formula import parse_formula
from claudia_computes.formula.compiler import Compiler
from claudia_computes.formula.scope import Scope
from claudia_computes.functions import Range
from claudia_computes.functions.registry import FunctionRegistry
from claudia_computes.refs import parse_cell_ref
from claudia_computes.values import ErrorValue, FormulaError


class FakeSheet:
    """Values by position; ``set`` bumps the versions the lookup index depends on."""

    def __init__(self, cells: dict[str, object] | None = None):
        self.grid: dict[tuple[int, int], object] = {}
        self._columns: dict[int, int] = {}
        self._version = 0
        self.rows_used = self.cols_used = 0
        for address, value in (cells or {}).items():
            self.set(address, value)

    def set(self, address: str, value: object) -> None:
        ref = parse_cell_ref(address)
        row, col = ref.row, ref.col
        self.grid[(row, col)] = value
        self._columns[col] = self._columns.get(col, 0) + 1
        self._version += 1
        self.rows_used = max(self.rows_used, row + 1)
        self.cols_used = max(self.cols_used, col + 1)

    def column_version(self, col: int) -> int:
        return self._columns.get(col, 0)

    def version(self) -> int:
        return self._version


def evaluate(text: str, cells: dict[str, object] | None = None, *, at: str = "Z99", sheets: dict | None = None):
    """The value of the formula ``text`` on a sheet holding ``cells`` (an error comes back as an ``ErrorValue``)."""
    home = FakeSheet(cells)
    all_sheets = {"s1": home, **(sheets or {})}
    names = {"sheet1": "s1", **{key: key for key in all_sheets}}
    scope = Scope(all_sheets, lambda name: names.get(name.casefold()))
    ref = parse_cell_ref(at)
    row, col = ref.row, ref.col
    scope.enter("s1", row, col)
    parsed = parse_formula(text, scope.sheet_id)
    if parsed.ast is None:
        return parsed.error
    try:
        value = Compiler(FunctionRegistry()).compile(parsed.ast)(scope)
        if value.__class__ is Range:
            value = single_of(value)
        return value
    except FormulaError as problem:
        return problem.value()


def single_of(area: Range):
    if len(area) != 1:
        return area
    return area.at(0, 0)


def code(text: str, cells: dict[str, object] | None = None, **kw) -> str:
    """The error code a formula ends in (the test fails if it does not end in an error)."""
    result = evaluate(text, cells, **kw)
    assert isinstance(result, ErrorValue), f"{text} gave {result!r}"
    return result.code
