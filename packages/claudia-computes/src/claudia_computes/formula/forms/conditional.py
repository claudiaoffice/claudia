"""Forms that choose what to evaluate: IF, IFS, IFERROR, IFNA, CHOOSE, SWITCH."""

from __future__ import annotations

from typing import Any

from ...values import NA, VALUE, FormulaError
from ..compiler import MISSING, Compiler, Evaluator, failing
from ..nodes import Node
from ..operators import compare, single, to_number
from . import form, truth, wrong_count


def _present(value: Any) -> Any:
    """An argument that was left out is an empty cell."""
    return None if value is MISSING else value


@form("IF")
def if_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """IF(condition, then, else): only the branch taken is evaluated, so IF(B1=0, 0, A1/B1) never divides by zero."""
    if not 2 <= len(args) <= 3:
        return wrong_count("IF", len(args), 2, 3)
    condition, then = compiler.compile(args[0]), compiler.compile(args[1])
    otherwise = compiler.compile(args[2]) if len(args) == 3 else None

    def evaluate(scope):
        if truth(_present(condition(scope))):
            return _present(then(scope))
        return False if otherwise is None else _present(otherwise(scope))

    return evaluate


@form("IFS")
def ifs_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """IFS(condition1, value1, condition2, value2, ...): the value of the first condition that is TRUE, else #N/A."""
    if len(args) < 2 or len(args) % 2:
        return failing(VALUE, "IFS takes pairs of a condition and a value")
    pairs = [(compiler.compile(args[i]), compiler.compile(args[i + 1])) for i in range(0, len(args), 2)]

    def evaluate(scope):
        for condition, value in pairs:
            if truth(_present(condition(scope))):
                return _present(value(scope))
        raise FormulaError(NA, "no condition was TRUE")

    return evaluate


def _catching(name: str, args: tuple[Node, ...], compiler: Compiler, only_na: bool) -> Evaluator:
    if len(args) != 2:
        return wrong_count(name, len(args), 2, 2)
    value, alternative = compiler.compile(args[0]), compiler.compile(args[1])

    def evaluate(scope):
        try:
            return _present(single(value(scope)))
        except FormulaError as error:
            if only_na and error.code != NA:
                raise
            return _present(alternative(scope))

    return evaluate


@form("IFERROR")
def iferror_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """IFERROR(value, alternative): the value, or the alternative when the value is an error of any kind."""
    return _catching("IFERROR", args, compiler, only_na=False)


@form("IFNA")
def ifna_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """IFNA(value, alternative): the value, or the alternative when the value is #N/A (other errors stay)."""
    return _catching("IFNA", args, compiler, only_na=True)


@form("CHOOSE")
def choose_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """CHOOSE(index, value1, value2, ...): the value at position ``index`` (counting from 1); only that one is
    evaluated."""
    if len(args) < 2:
        return wrong_count("CHOOSE", len(args), 2, None)
    index, choices = compiler.compile(args[0]), [compiler.compile(a) for a in args[1:]]

    def evaluate(scope):
        position = int(to_number(single(index(scope))))
        if not 1 <= position <= len(choices):
            raise FormulaError(VALUE, f"CHOOSE has {len(choices)} values, there is no number {position}")
        return _present(choices[position - 1](scope))

    return evaluate


@form("SWITCH")
def switch_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """SWITCH(expression, case1, result1, case2, result2, ..., default): the result of the first case equal to the
    expression, else the default if there is one, else #N/A."""
    if len(args) < 3:
        return wrong_count("SWITCH", len(args), 3, None)
    expression = compiler.compile(args[0])
    rest = [compiler.compile(a) for a in args[1:]]
    default = rest.pop() if len(rest) % 2 else None
    pairs = [(rest[i], rest[i + 1]) for i in range(0, len(rest), 2)]

    def evaluate(scope):
        subject = _present(single(expression(scope)))
        for case, result in pairs:
            if compare(subject, _present(single(case(scope)))) == 0:
                return _present(result(scope))
        if default is None:
            raise FormulaError(NA, "no case matched and there is no default")
        return _present(default(scope))

    return evaluate
