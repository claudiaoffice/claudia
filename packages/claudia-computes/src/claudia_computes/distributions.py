"""The distributions ``RANDOM`` can draw from (D292).

Every distribution is a *quantile function*: a uniform number from the stream (``draws``) goes in, a value of the
distribution comes out. Two things follow. Excel can run nearly all of them as ``NORM.INV(RAND(), ...)`` and its
relatives, so documents survive a round trip through ``.xlsx``. And one random draw can serve every alternative of an
input, so differences between outcomes come from the alternatives and not from noise.

``quantile`` is the one entry point. Optional ``low`` and ``high`` *cut* a continuous distribution rather than clamp
it: the uniform number is squeezed into the part of the distribution between them, so no value piles up at a limit.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache

from .special import regularized_beta, regularized_gamma_p
from .values import NUM, VALUE, FormulaError

Parameters = Sequence[float]
_EDGE = 2.0**-53  # the closest to 0 and 1 that a draw can come: keeps a quantile finite


@dataclass(frozen=True, slots=True)
class Distribution:
    """What one distribution is: its name, how many parameters it takes (``None``: any even number, for
    ``discrete``), whether it is continuous, and how it is computed."""

    name: str
    arity: int | None
    continuous: bool
    parameter_names: tuple[str, ...]
    ppf: Callable[[float, Parameters], float]
    cdf: Callable[[float, Parameters], float] | None = None
    check: Callable[[Parameters], None] | None = None


def _bad(detail: str) -> FormulaError:
    return FormulaError(NUM, detail)


def _open(u: float) -> float:
    return min(max(u, _EDGE), 1.0 - _EDGE)


# ------------------------------------------------------------------------------ checks
def _check_uniform(p: Parameters) -> None:
    if not p[0] < p[1]:
        raise _bad("uniform needs the first number to be below the second")


def _check_spread(p: Parameters) -> None:
    if not p[1] > 0:
        raise _bad("the spread must be above 0")


def _check_triangular(p: Parameters) -> None:
    low, mode, high = p
    if not (low < high and low <= mode <= high):
        raise _bad("triangular needs low < high and the mode between them")


def _check_positive(p: Parameters) -> None:
    if not all(x > 0 for x in p):
        raise _bad("every parameter must be above 0")


def _check_binomial(p: Parameters) -> None:
    trials, chance = p
    if trials != int(trials) or not 0 <= trials <= 100_000 or not 0 <= chance <= 1:
        raise _bad("binomial needs a whole number of trials up to 100,000 and a chance between 0 and 1")


def _check_poisson(p: Parameters) -> None:
    if not 0 <= p[0] <= 100_000:
        raise _bad("poisson needs a mean between 0 and 100,000")


def _check_discrete(p: Parameters) -> None:
    weights = p[1::2]
    if len(p) % 2 or not p:
        raise FormulaError(VALUE, "discrete takes pairs: a value and its weight")
    if any(w < 0 for w in weights) or not sum(weights) > 0:
        raise _bad("the weights must not be negative and one must be above 0")


# ------------------------------------------------------------------------------ continuous
def _uniform_ppf(u: float, p: Parameters) -> float:
    return p[0] + u * (p[1] - p[0])


def _uniform_cdf(x: float, p: Parameters) -> float:
    return min(max((x - p[0]) / (p[1] - p[0]), 0.0), 1.0)


def _normal_ppf(u: float, p: Parameters) -> float:
    return statistics.NormalDist(p[0], p[1]).inv_cdf(_open(u))


def _normal_cdf(x: float, p: Parameters) -> float:
    return statistics.NormalDist(p[0], p[1]).cdf(x)


def _lognormal_ppf(u: float, p: Parameters) -> float:
    return math.exp(_normal_ppf(u, p))


def _lognormal_cdf(x: float, p: Parameters) -> float:
    return 0.0 if x <= 0 else _normal_cdf(math.log(x), p)


def _triangular_ppf(u: float, p: Parameters) -> float:
    low, mode, high = p
    at_mode = (mode - low) / (high - low)
    if u < at_mode:
        return low + math.sqrt(u * (high - low) * (mode - low))
    return high - math.sqrt((1 - u) * (high - low) * (high - mode))


def _triangular_cdf(x: float, p: Parameters) -> float:
    low, mode, high = p
    if x <= low:
        return 0.0
    if x >= high:
        return 1.0
    if x <= mode:
        return (x - low) ** 2 / ((high - low) * (mode - low))
    return 1 - (high - x) ** 2 / ((high - low) * (high - mode))


def _exponential_ppf(u: float, p: Parameters) -> float:
    return -math.log1p(-u) / p[0]


def _exponential_cdf(x: float, p: Parameters) -> float:
    return 0.0 if x <= 0 else -math.expm1(-p[0] * x)


def _weibull_ppf(u: float, p: Parameters) -> float:
    return p[1] * (-math.log1p(-u)) ** (1 / p[0])


def _weibull_cdf(x: float, p: Parameters) -> float:
    return 0.0 if x <= 0 else -math.expm1(-((x / p[1]) ** p[0]))


def _invert(
    u: float, cdf: Callable[[float], float], pdf: Callable[[float], float], low: float, high: float, start: float
) -> float:
    """The ``x`` between ``low`` and ``high`` where ``cdf`` reaches ``u``: Newton's method kept inside a bracket that
    bisection narrows, so it converges for every shape."""
    x = min(max(start, low), high)
    for _ in range(200):
        error = cdf(x) - u
        if error > 0:
            high = x
        else:
            low = x
        if abs(error) < 1e-15:
            return x
        slope = pdf(x)
        nxt = x - error / slope if slope > 0 else math.nan
        x = nxt if low < nxt < high else (low + high) / 2
        if high - low < 1e-15 * max(1.0, abs(x)):
            return x
    return x


def _beta_pdf(x: float, a: float, b: float) -> float:
    if x <= 0 or x >= 1:
        return 0.0
    return math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + (a - 1) * math.log(x) + (b - 1) * math.log1p(-x)
    )


@lru_cache(maxsize=8192)
def _beta_quantile(u: float, a: float, b: float) -> float:
    return _invert(u, lambda x: regularized_beta(x, a, b), lambda x: _beta_pdf(x, a, b), 0.0, 1.0, a / (a + b))


def _beta_ppf(u: float, p: Parameters) -> float:
    return _beta_quantile(_open(u), p[0], p[1])


def _beta_cdf(x: float, p: Parameters) -> float:
    return regularized_beta(x, p[0], p[1])


def _pert_shape(p: Parameters) -> tuple[float, float]:
    low, mode, high = p
    return 1 + 4 * (mode - low) / (high - low), 1 + 4 * (high - mode) / (high - low)


def _pert_ppf(u: float, p: Parameters) -> float:
    a, b = _pert_shape(p)
    return p[0] + (p[2] - p[0]) * _beta_quantile(_open(u), a, b)


def _pert_cdf(x: float, p: Parameters) -> float:
    a, b = _pert_shape(p)
    return regularized_beta((x - p[0]) / (p[2] - p[0]), a, b)


@lru_cache(maxsize=8192)
def _gamma_quantile(u: float, shape: float) -> float:
    def pdf(x: float) -> float:
        return math.exp((shape - 1) * math.log(x) - x - math.lgamma(shape)) if x > 0 else 0.0

    high = max(shape, 1.0)
    while regularized_gamma_p(shape, high) < u:
        high *= 2
    return _invert(u, lambda x: regularized_gamma_p(shape, x), pdf, 0.0, high, shape)


def _gamma_ppf(u: float, p: Parameters) -> float:
    return p[1] * _gamma_quantile(_open(u), p[0])


def _gamma_cdf(x: float, p: Parameters) -> float:
    return regularized_gamma_p(p[0], x / p[1])


# ------------------------------------------------------------------------------ discrete
def _binomial_ppf(u: float, p: Parameters) -> float:
    trials, chance = int(p[0]), p[1]
    if chance in (0, 1):
        return trials if chance == 1 else 0
    pmf = math.exp(trials * math.log1p(-chance))
    total = pmf
    count = 0
    ratio = chance / (1 - chance)
    while total < u and count < trials:
        pmf *= (trials - count) / (count + 1) * ratio
        count += 1
        total += pmf
    return count


def _poisson_ppf(u: float, p: Parameters) -> float:
    mean = p[0]
    if mean == 0:
        return 0
    pmf = math.exp(-mean)
    total = pmf
    count = 0
    while total < u and count < 10 * mean + 1_000:
        count += 1
        pmf *= mean / count
        total += pmf
    return count


def _discrete_ppf(u: float, p: Parameters) -> float:
    values, weights = p[0::2], p[1::2]
    total = sum(weights)
    running = 0.0
    for value, weight in zip(values, weights, strict=True):
        running += weight
        if running / total > u:
            return value
    return values[-1]


def _table() -> dict[str, Distribution]:
    d = Distribution
    return {
        entry.name: entry
        for entry in (
            d("uniform", 2, True, ("low", "high"), _uniform_ppf, _uniform_cdf, _check_uniform),
            d("normal", 2, True, ("mean", "spread"), _normal_ppf, _normal_cdf, _check_spread),
            d("lognormal", 2, True, ("mean of ln", "spread of ln"), _lognormal_ppf, _lognormal_cdf, _check_spread),
            d("triangular", 3, True, ("low", "mode", "high"), _triangular_ppf, _triangular_cdf, _check_triangular),
            d("pert", 3, True, ("low", "mode", "high"), _pert_ppf, _pert_cdf, _check_triangular),
            d("exponential", 1, True, ("rate",), _exponential_ppf, _exponential_cdf, _check_positive),
            d("weibull", 2, True, ("shape", "scale"), _weibull_ppf, _weibull_cdf, _check_positive),
            d("beta", 2, True, ("alpha", "beta"), _beta_ppf, _beta_cdf, _check_positive),
            d("gamma", 2, True, ("shape", "scale"), _gamma_ppf, _gamma_cdf, _check_positive),
            d("binomial", 2, False, ("trials", "chance"), _binomial_ppf, None, _check_binomial),
            d("poisson", 1, False, ("mean",), _poisson_ppf, None, _check_poisson),
            d("discrete", None, False, ("value", "weight"), _discrete_ppf, None, _check_discrete),
        )
    }


DISTRIBUTIONS: dict[str, Distribution] = _table()


def _lookup(name: str) -> Distribution:
    try:
        return DISTRIBUTIONS[name.casefold()]
    except KeyError:
        known = ", ".join(sorted(DISTRIBUTIONS))
        raise FormulaError(VALUE, f"there is no distribution {name!r}; the ones there are: {known}") from None


def check_parameters(distribution: Distribution, parameters: Parameters) -> None:
    """Raise ``#VALUE!`` for the wrong number of parameters and ``#NUM!`` for ones the distribution cannot have."""
    if distribution.arity is not None and len(parameters) != distribution.arity:
        names = ", ".join(distribution.parameter_names)
        raise FormulaError(
            VALUE,
            f"{distribution.name} takes {distribution.arity} numbers after its name ({names}), not {len(parameters)}",
        )
    if distribution.check is not None:
        distribution.check(parameters)


def quantile(
    name: str, u: float, parameters: Parameters, *, low: float | None = None, high: float | None = None
) -> float:
    """The value of distribution ``name`` with ``parameters`` at the uniform number ``u`` (0 <= u < 1). ``low`` and
    ``high`` keep the value between them by cutting the distribution there (continuous distributions only)."""
    distribution = _lookup(name)
    check_parameters(distribution, parameters)
    if low is None and high is None:
        return distribution.ppf(u, parameters)
    if distribution.cdf is None:
        raise _bad(f"limits only work with continuous distributions, and {distribution.name} is not")
    below = 0.0 if low is None else distribution.cdf(low, parameters)
    above = 1.0 if high is None else distribution.cdf(high, parameters)
    if not above > below:
        raise _bad("the limits leave no values of the distribution between them")
    return distribution.ppf(below + u * (above - below), parameters)
