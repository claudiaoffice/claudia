"""SQL(): a query over the named tables of the workbook (E4.9, E6.5)."""

from __future__ import annotations

from ... import sql as engine
from ...spill import Table
from ...values import NA, VALUE, FormulaError
from ..compiler import Compiler, Evaluator
from ..nodes import Node
from ..operators import single
from . import form, wrong_count


@form("SQL")
def sql_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """SQL(query, value...): the result of a SQL query (SQLite's SELECT) over the named ranges and tables of this
    workbook, written ``FROM Sales``; quote a name with a space as ``"Unit price"``. A ``?`` in the query is the
    next value after it. As the whole formula it fills the cells below and beside it, header row first; inside
    another formula it gives the first value of the first row."""
    if not args:
        return wrong_count("SQL", 0, 1, None)
    spills = args is compiler.top_args
    query = compiler.compile(args[0])
    values = [compiler.compile(arg) for arg in args[1:]]

    def evaluate(scope):
        text = single(query(scope))
        if not isinstance(text, str) or not text.strip():
            raise FormulaError(VALUE, "SQL needs the query as text")
        bound = [engine.parameter(single(value(scope))) for value in values]
        table = engine.run_query(text, bound, scope.table_data)
        if spills:
            return table
        if not table.rows:
            raise FormulaError(NA, "the query gave no rows")
        return first_value(table)

    return evaluate


def first_value(table: Table):
    """The value in the first column of the first row."""
    return table.rows[0][0]
