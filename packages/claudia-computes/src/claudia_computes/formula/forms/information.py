"""Forms that look at what a value is, including whether it is an error: ISBLANK, ISERROR, ISNUMBER ..."""

from __future__ import annotations

from collections.abc import Callable

from ...values import NA, FormulaError
from ..compiler import MISSING, Compiler, Evaluator
from ..nodes import Node
from ..operators import single
from . import form, wrong_count


def _test(name: str, test: Callable[[object], bool], on_error: Callable[[FormulaError], bool]) -> None:
    @form(name)
    def make(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
        if len(args) != 1:
            return wrong_count(name, len(args), 1, 1)
        inner = compiler.compile(args[0])

        def evaluate(scope):
            try:
                value = single(inner(scope))
            except FormulaError as error:
                return on_error(error)
            return test(None if value is MISSING else value)

        return evaluate

    make.__doc__ = f"{name}(value): TRUE or FALSE; an error in the value is an answer, not a failure."


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


_test("ISBLANK", lambda v: v is None, lambda e: False)
_test("ISERROR", lambda v: False, lambda e: True)
_test("ISERR", lambda v: False, lambda e: e.code != NA)
_test("ISNA", lambda v: False, lambda e: e.code == NA)
_test("ISNUMBER", _number, lambda e: False)
_test("ISTEXT", lambda v: isinstance(v, str), lambda e: False)
_test("ISNONTEXT", lambda v: not isinstance(v, str), lambda e: True)
_test("ISLOGICAL", lambda v: isinstance(v, bool), lambda e: False)
