"""Forms that draw random numbers: RAND, RANDBETWEEN and RANDOM (D291, D292).

They are forms, not library functions, because they need to know *where* they are: a number is a function of the
document's seed and draw number and of the cell, so every person sees the same one and it does not move when
something else is edited. See ``claudia_computes.draws``."""

from __future__ import annotations

import math

from ...distributions import DISTRIBUTIONS, check_parameters, quantile
from ...values import NUM, VALUE, FormulaError
from ..compiler import MISSING, Compiler, Evaluator
from ..nodes import Node
from ..operators import single
from . import form, wrong_count


def _number(value: object) -> float:
    """``value`` as a number for a parameter: text and TRUE/FALSE are ``#VALUE!``, an empty cell is 0."""
    value = single(value)
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FormulaError(VALUE, "this is not a number")
    return value


@form("RAND")
def _rand(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """RAND(): a number from 0 up to, not including, 1. Fresh numbers come with Tools > Resample (F9)."""
    if args:
        return wrong_count("RAND", len(args), 0, 0)

    def evaluate(scope):
        return scope.next_uniform()

    return evaluate


@form("RANDBETWEEN")
def _randbetween(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """RANDBETWEEN(bottom, top): a whole number from bottom to top, both included."""
    if len(args) != 2:
        return wrong_count("RANDBETWEEN", len(args), 2, 2)
    bottom, top = (compiler.compile(arg) for arg in args)

    def evaluate(scope):
        low, high = math.ceil(_number(bottom(scope))), math.floor(_number(top(scope)))
        if low > high:
            raise FormulaError(NUM, "the bottom is above the top")
        return low + int(scope.next_uniform() * (high - low + 1))

    return evaluate


@form("RANDOM")
def _random(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """RANDOM(distribution, parameters..., [low], [high]): a random number from the named distribution, for example
    RANDOM("normal", 1000, 150). Without arguments it is RAND(). ``low`` and ``high`` cut the distribution (continuous
    ones only). Distributions: uniform, normal, lognormal, triangular, pert, exponential, weibull, beta, gamma,
    binomial, poisson, discrete."""
    if not args:
        return _rand(compiler, args)
    evaluators = [compiler.compile(arg) for arg in args]

    def evaluate(scope):
        name = single(evaluators[0](scope))
        if not isinstance(name, str):
            raise FormulaError(VALUE, "the first argument names the distribution, in quotes")
        distribution = DISTRIBUTIONS.get(name.casefold())
        rest = [evaluator(scope) for evaluator in evaluators[1:]]
        if distribution is None:
            return quantile(name, 0.5, ())  # (raises the error that names the choices)
        count = distribution.arity
        numbers = [_number(v) for v in rest[:count]] if count is not None else [_number(v) for v in rest]
        limits = [None if v is MISSING else _number(v) for v in rest[count:]] if count is not None else []
        if len(limits) > 2:
            raise FormulaError(VALUE, f"{distribution.name} takes {count} numbers and at most 2 limits after its name")
        check_parameters(distribution, numbers)
        low, high = (limits + [None, None])[:2]
        return quantile(distribution.name, scope.next_uniform(), numbers, low=low, high=high)

    return evaluate
