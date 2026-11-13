"""The two special functions the beta and gamma distributions need: the regularised incomplete beta and gamma.

Standard series and continued-fraction expansions (Numerical Recipes, chapter 6), accurate to about 1e-14 over the
range a spreadsheet uses. They are tested against the closed forms that exist for whole parameters."""

from __future__ import annotations

import math

_TINY = 1e-300
_EPSILON = 1e-15
_MAX_ITERATIONS = 500


def regularized_gamma_p(a: float, x: float) -> float:
    """P(a, x): the share of a Gamma(a, 1) variable that lies below ``x``."""
    if x <= 0:
        return 0.0
    if x < a + 1:
        return _gamma_series(a, x)
    return 1.0 - _gamma_fraction(a, x)


def _gamma_series(a: float, x: float) -> float:
    term = total = 1.0 / a
    n = a
    for _ in range(_MAX_ITERATIONS):
        n += 1
        term *= x / n
        total += term
        if abs(term) < abs(total) * _EPSILON:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gamma_fraction(a: float, x: float) -> float:
    """Q(a, x) by Lentz's continued fraction (for x above a + 1)."""
    b = x + 1 - a
    c = 1 / _TINY
    d = 1 / b
    h = d
    for i in range(1, _MAX_ITERATIONS):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = _TINY if abs(d) < _TINY else d
        c = b + an / c
        c = _TINY if abs(c) < _TINY else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < _EPSILON:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def regularized_beta(x: float, a: float, b: float) -> float:
    """I_x(a, b): the share of a Beta(a, b) variable that lies below ``x``."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return front * _beta_fraction(x, a, b) / a
    return 1.0 - front * _beta_fraction(1 - x, b, a) / b


def _beta_fraction(x: float, a: float, b: float) -> float:
    qab, qap, qam = a + b, a + 1, a - 1
    c = 1.0
    d = 1 - qab * x / qap
    d = _TINY if abs(d) < _TINY else d
    d = 1 / d
    h = d
    for m in range(1, _MAX_ITERATIONS):
        m2 = 2 * m
        step = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + step * d
        d = _TINY if abs(d) < _TINY else d
        c = 1 + step / c
        c = _TINY if abs(c) < _TINY else c
        d = 1 / d
        h *= d * c
        step = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + step * d
        d = _TINY if abs(d) < _TINY else d
        c = 1 + step / c
        c = _TINY if abs(c) < _TINY else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < _EPSILON:
            break
    return h
