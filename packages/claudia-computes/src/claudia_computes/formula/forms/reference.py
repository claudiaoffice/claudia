"""Forms about where cells are: ROW, COLUMN, ROWS, COLUMNS, INDEX, OFFSET, INDIRECT.

They work on ``Range`` values, which know their place on the sheet and are not read until somebody asks; ``ROW(A5)``
is 5 whatever A5 holds, even an error."""

from __future__ import annotations

from ...functions.range import Range
from ...limits import MAX_COLS, MAX_ROWS
from ...values import NUM, REF, VALUE, ErrorValue, FormulaError
from ..compiler import MISSING, Compiler, Evaluator, failing
from ..nodes import Area, Node, Ref
from ..operators import single, to_number
from ..syntax import parse_formula
from . import form, wrong_count


def whole_number(value: object, what: str) -> int:
    """``value`` as a whole number (cut at the decimal point), for a position or a size."""
    number = to_number(single(None if value is MISSING else value))
    try:
        return int(number)
    except (OverflowError, ValueError):
        raise FormulaError(NUM, f"{what} is not a usable number") from None


def result_of(area: Range) -> object:
    """What a function that picked part of a range gives: the cell's value for one cell, else the part itself."""
    if len(area) != 1:
        return area
    value = area.at(0, 0)
    if value.__class__ is ErrorValue:
        raise value.raised()
    return value


def _position(name: str, pick):
    @form(name)
    def make(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
        if len(args) > 1:
            return wrong_count(name, len(args), 0, 1)
        if not args:

            def here(scope):
                return pick(scope.row, scope.col, 1, 1)

            return here
        target = compiler.compile_range(args[0])

        def evaluate(scope):
            area = target(scope)
            return pick(area.row0, area.col0, area.n_rows, area.n_cols)

        return evaluate

    return make


_position(
    "ROW", lambda row, col, rows, cols: row + 1
).__doc__ = "ROW(reference): the row number of the reference, or of this cell."
_position("COLUMN", lambda row, col, rows, cols: col + 1).__doc__ = "COLUMN(reference): the column number."
_position("ROWS", lambda row, col, rows, cols: rows).__doc__ = "ROWS(range): how many rows the range has."
_position("COLUMNS", lambda row, col, rows, cols: cols).__doc__ = "COLUMNS(range): how many columns the range has."


@form("INDEX")
def index_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """INDEX(range, row, column): the cell ``row`` rows down and ``column`` columns across (counting from 1). A row or
    a column of 0 gives the whole column or row; a single row or column needs only one number."""
    if not 2 <= len(args) <= 3:
        return wrong_count("INDEX", len(args), 2, 3)
    source = compiler.compile_range(args[0])
    row_arg = compiler.compile(args[1])
    col_arg = compiler.compile(args[2]) if len(args) == 3 else None

    def evaluate(scope):
        area = source(scope)
        row = whole_number(row_arg(scope), "the row")
        col = None if col_arg is None else whole_number(col_arg(scope), "the column")
        if col is None:
            if area.n_cols == 1:
                col = 1
            elif area.n_rows == 1:
                row, col = 1, row  # (a single row: the one number counts along it)
            else:
                col = 0
        if row < 0 or col < 0:
            raise FormulaError(VALUE, "INDEX needs row and column numbers of 0 or more")
        if row > area.n_rows or col > area.n_cols:
            raise FormulaError(REF, "that position is outside the range")
        return result_of(
            area.sub(
                0 if row == 0 else row - 1,
                0 if col == 0 else col - 1,
                area.n_rows - 1 if row == 0 else row - 1,
                area.n_cols - 1 if col == 0 else col - 1,
            )
        )

    return evaluate


@form("OFFSET")
def offset_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """OFFSET(reference, rows, columns, height, width): the cells ``rows`` down and ``columns`` across from the
    reference, with the reference's size unless a height and a width are given. Its dependencies are found while it
    runs."""
    if not 3 <= len(args) <= 5:
        return wrong_count("OFFSET", len(args), 3, 5)
    base = compiler.compile_range(args[0])
    shifts = [compiler.compile(a) for a in args[1:]]

    def evaluate(scope):
        area = base(scope)
        values = [shift(scope) for shift in shifts]
        rows, cols = whole_number(values[0], "rows"), whole_number(values[1], "columns")
        height = whole_number(values[2], "height") if len(values) > 2 and values[2] is not MISSING else area.n_rows
        width = whole_number(values[3], "width") if len(values) > 3 and values[3] is not MISSING else area.n_cols
        if height < 1 or width < 1:
            raise FormulaError(REF, "OFFSET needs a height and a width of at least 1")
        row0, col0 = area.row0 + rows, area.col0 + cols
        if row0 < 0 or col0 < 0 or row0 + height > MAX_ROWS or col0 + width > MAX_COLS:
            raise FormulaError(REF, "that is outside the sheet")
        return scope.area(area.sheet_id, row0, col0, row0 + height - 1, col0 + width - 1)

    return evaluate


@form("INDIRECT")
def indirect_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """INDIRECT(text): the cells that the text names (``"B"&A1``, ``"Sheet2!A1:A5"``). Its dependencies are found while
    it runs."""
    if not 1 <= len(args) <= 2:
        return wrong_count("INDIRECT", len(args), 1, 2)
    if len(args) == 2:
        return failing(VALUE, "INDIRECT reads addresses like A1 only (not the R1C1 style)")
    text_arg = compiler.compile(args[0])

    def evaluate(scope):
        text = single(text_arg(scope))
        if not isinstance(text, str):
            raise FormulaError(REF, "INDIRECT needs text that names cells")
        found = parse_formula("=" + text.strip(), scope.sheet_id).ast
        if isinstance(found, Ref):
            ref = found.ref
            return scope.area(ref.sheet, ref.row, ref.col, ref.row, ref.col)
        if isinstance(found, Area):
            first, last = found.ref.first, found.ref.last
            return scope.area(first.sheet, first.row, first.col, last.row, last.col)
        raise FormulaError(REF, f"{text!r} does not name cells")

    return evaluate
