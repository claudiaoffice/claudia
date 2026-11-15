"""PIVOT(): the cells of a pivot table (E6.30, D620)."""

from __future__ import annotations

from ...pivot import PivotError
from ...pivot_render import compute_pivot
from ...values import NAME, SQL, VALUE, FormulaError
from ..compiler import Compiler, Evaluator
from ..nodes import Node
from ..operators import single
from . import form, wrong_count


@form("PIVOT")
def pivot_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """PIVOT(name): the pivot table called ``name`` — the summary of a table the field panel of Tools ▸ Pivot Table
    describes. Written by the pivot's own commands, not by hand: change the pivot in its panel, not this formula. As
    the whole formula it fills the cells below and beside it; inside another formula it gives the first cell."""
    if len(args) != 1:
        return wrong_count("PIVOT", len(args), 1, 1)
    spills = args is compiler.top_args
    wanted = compiler.compile(args[0])

    def evaluate(scope):
        name = single(wanted(scope))
        if not isinstance(name, str) or not name.strip():
            raise FormulaError(VALUE, "PIVOT needs the name of a pivot table as text")
        entry = scope.pivots.get(name)
        if entry is None:
            scope.pivots.record(name, None)
            raise FormulaError(NAME, f"there is no pivot table called {name}")
        try:
            result = compute_pivot(entry.definition, scope.table_data, entry.labels)
        except PivotError as problem:
            scope.pivots.record(name, None)
            raise FormulaError(SQL, str(problem)) from None
        except FormulaError:
            scope.pivots.record(name, None)
            raise
        scope.pivots.record(name, result if result.rows else None)
        if not result.rows:
            return ""  # (no value field yet: the cell stays empty)
        return result.as_matrix() if spills else result.value_at(0, 0)

    return evaluate
