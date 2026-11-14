"""The normal and t distributions, the t test, confidence intervals and the chi-squared test.

Every name that Excel has twice (``NORMDIST`` and ``NORM.DIST``, ``TINV`` and ``T.INV.2T`` ...) is here under both.
"""

from __future__ import annotations

import math
from statistics import NormalDist

from ...special import regularized_beta, regularized_gamma_q
from ...values import DIV0, NA, NUM
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .aggregate import mean, number_pairs, spread
from .catalog import builtin

_STANDARD = NormalDist()


def _positive(value: float, what: str) -> float:
    if value <= 0:
        raise FunctionError(NUM, f"{what} must be above 0")
    return value


def _probability(p: float) -> float:
    if not 0 < p < 1:
        raise FunctionError(NUM, "the probability must be above 0 and below 1")
    return p


# -- the normal distribution --------------------------------------------------------------------------------------------
def _cdf(x: float, mu: float, sigma: float) -> float:
    return 0.5 * math.erfc(-(x - mu) / (sigma * math.sqrt(2)))


def _normal_dist(x: float, mean_: float, standard_dev: float, cumulative: bool) -> float:
    _positive(standard_dev, "the standard deviation")
    return _cdf(x, mean_, standard_dev) if cumulative else NormalDist(mean_, standard_dev).pdf(x)


@builtin
class NORM_DIST(UserFunction):
    name = "NORM.DIST"
    description = "The normal distribution at x: the share below x (cumulative TRUE) or the density (FALSE)."
    examples = (Example("=ROUND(NORM.DIST(42, 40, 1.5, TRUE), 4)", 0.9088),)

    def call(self, x: float, mean: float, standard_dev: float, cumulative: bool):
        return _normal_dist(x, mean, standard_dev, cumulative)


@builtin
class NORMDIST(UserFunction):
    description = "The normal distribution at x (the old name of NORM.DIST)."
    examples = (Example("=ROUND(NORMDIST(42, 40, 1.5, FALSE), 4)", 0.1093),)

    def call(self, x: float, mean: float, standard_dev: float, cumulative: bool):
        return _normal_dist(x, mean, standard_dev, cumulative)


@builtin
class NORM_S_DIST(UserFunction):
    name = "NORM.S.DIST"
    description = "The standard normal distribution (mean 0, deviation 1) at z: the share below z or the density."
    examples = (Example("=ROUND(NORM.S.DIST(1, TRUE), 4)", 0.8413),)

    def call(self, z: float, cumulative: bool):
        return _cdf(z, 0, 1) if cumulative else _STANDARD.pdf(z)


@builtin
class NORMSDIST(UserFunction):
    description = "The share of the standard normal distribution below z (the old name of NORM.S.DIST)."
    examples = (Example("=ROUND(NORMSDIST(1.96), 4)", 0.975),)

    def call(self, z: float):
        return _cdf(z, 0, 1)


def _norm_inv(p: float, mu: float, sigma: float) -> float:
    return mu + _positive(sigma, "the standard deviation") * _STANDARD.inv_cdf(_probability(p))


@builtin
class NORM_INV(UserFunction):
    name = "NORM.INV"
    description = "The value below which the share p of a normal distribution lies."
    examples = (Example("=ROUND(NORM.INV(0.9, 40, 1.5), 4)", 41.9223),)

    def call(self, probability: float, mean: float, standard_dev: float):
        return _norm_inv(probability, mean, standard_dev)


@builtin
class NORMINV(UserFunction):
    description = "The value below which the share p of a normal distribution lies (the old name of NORM.INV)."
    examples = (Example("=NORMINV(0.5, 3, 2)", 3),)

    def call(self, probability: float, mean: float, standard_dev: float):
        return _norm_inv(probability, mean, standard_dev)


@builtin
class NORM_S_INV(UserFunction):
    name = "NORM.S.INV"
    description = "The z for which the share p of the standard normal distribution lies below."
    examples = (Example("=ROUND(NORM.S.INV(0.975), 4)", 1.96),)

    def call(self, probability: float):
        return _norm_inv(probability, 0, 1)


@builtin
class NORMSINV(UserFunction):
    description = "The z for which the share p of the standard normal distribution lies below (the old name of NORM.S.INV)."
    examples = (Example("=NORMSINV(0.5)", 0),)

    def call(self, probability: float):
        return _norm_inv(probability, 0, 1)


# -- the t distribution --------------------------------------------------------------------------------------------------
def _degrees(df: float) -> int:
    if df < 1:
        raise FunctionError(NUM, "the degrees of freedom must be 1 or more")
    return int(df)


def two_tails(t: float, df: float) -> float:
    """The share of a t distribution with ``df`` degrees of freedom (a real number is fine) beyond ±|t|."""
    return regularized_beta(df / (df + t * t), df / 2, 0.5)


def right_tail(t: float, df: float) -> float:
    """The share of a t distribution above ``t``."""
    tail = two_tails(t, df) / 2
    return tail if t >= 0 else 1 - tail


def _t_density(x: float, df: int) -> float:
    return math.exp(math.lgamma((df + 1) / 2) - math.lgamma(df / 2) - 0.5 * math.log(df * math.pi)) * (1 + x * x / df) ** (-(df + 1) / 2)


def _t_inverse(tail: float, df: int) -> float:
    """The t above which the share ``tail`` (up to 0.5) of the distribution lies."""
    if tail >= 0.5:
        return 0.0
    low, high = 0.0, 1.0
    while right_tail(high, df) > tail:
        low, high = high, high * 2
        if high > 1e300:
            raise FunctionError(NUM, "the probability is too small")
    for _ in range(200):
        middle = (low + high) / 2
        if right_tail(middle, df) > tail:
            low = middle
        else:
            high = middle
    return (low + high) / 2


@builtin
class T_DIST(UserFunction):
    name = "T.DIST"
    description = "The Student t distribution at x: the share below x (cumulative TRUE) or the density (FALSE)."
    examples = (Example("=ROUND(T.DIST(1.5, 5, TRUE), 4)", 0.9030),)

    def call(self, x: float, deg_freedom: float, cumulative: bool):
        df = _degrees(deg_freedom)
        return 1 - right_tail(x, df) if cumulative else _t_density(x, df)


@builtin
class T_DIST_2T(UserFunction):
    name = "T.DIST.2T"
    description = "The share of the Student t distribution beyond x or -x (x is not negative)."
    examples = (Example("=ROUND(T.DIST.2T(2.5, 8), 4)", 0.0369),)

    def call(self, x: float, deg_freedom: float):
        if x < 0:
            raise FunctionError(NUM, "x must not be negative")
        return two_tails(x, _degrees(deg_freedom))


@builtin
class T_DIST_RT(UserFunction):
    name = "T.DIST.RT"
    description = "The share of the Student t distribution above x."
    examples = (Example("=ROUND(T.DIST.RT(2.5, 8), 4)", 0.0185),)

    def call(self, x: float, deg_freedom: float):
        return right_tail(x, _degrees(deg_freedom))


@builtin
class TDIST(UserFunction):
    description = "The share of the Student t distribution beyond x in one tail (1) or both (2); x is not negative."
    examples = (Example("=ROUND(TDIST(2.5, 8, 2), 4)", 0.0369),)

    def call(self, x: float, deg_freedom: float, tails: float):
        if x < 0 or tails not in (1, 2):
            raise FunctionError(NUM, "x must not be negative and tails is 1 or 2")
        df = _degrees(deg_freedom)
        return two_tails(x, df) / (2 if tails == 1 else 1)


@builtin
class T_INV(UserFunction):
    name = "T.INV"
    description = "The t below which the share p of the Student t distribution lies."
    examples = (Example("=ROUND(T.INV(0.75, 2), 4)", 0.8165),)

    def call(self, probability: float, deg_freedom: float):
        df, p = _degrees(deg_freedom), _probability(probability)
        t = _t_inverse(min(p, 1 - p), df)
        return t if p > 0.5 else -t


def _inverse_two_tails(probability: float, deg_freedom: float) -> float:
    return _t_inverse(_probability(probability) / 2, _degrees(deg_freedom))


@builtin
class T_INV_2T(UserFunction):
    name = "T.INV.2T"
    description = "The t beyond which, in both directions together, the share p of the Student t distribution lies."
    examples = (Example("=ROUND(T.INV.2T(0.05, 10), 4)", 2.2281),)

    def call(self, probability: float, deg_freedom: float):
        return _inverse_two_tails(probability, deg_freedom)


@builtin
class TINV(UserFunction):
    description = "The t beyond which, in both directions together, the share p lies (the old name of T.INV.2T)."
    examples = (Example("=ROUND(TINV(0.05, 10), 4)", 2.2281),)

    def call(self, probability: float, deg_freedom: float):
        return _inverse_two_tails(probability, deg_freedom)


# -- the t test ------------------------------------------------------------------------------------------------------------
def t_test(first: Range, second: Range, tails: float, kind: float) -> float:
    if tails not in (1, 2) or kind not in (1, 2, 3):
        raise FunctionError(NUM, "tails is 1 or 2 and type is 1, 2 or 3")
    if kind == 1:
        if (first.n_rows, first.n_cols) != (second.n_rows, second.n_cols):
            raise FunctionError(NA, "paired samples need the same size")
        pairs = number_pairs(first, second)
        differences = [a - b for a, b in pairs]
        n = len(differences)
        if n < 2:
            raise FunctionError(DIV0, "this needs at least 2 pairs")
        variance = spread(differences, sample=True)
        if variance == 0:
            raise FunctionError(DIV0, "the differences do not vary")
        t, df = mean(differences) / math.sqrt(variance / n), n - 1
    else:
        a, b = first.numbers(), second.numbers()
        if len(a) < 2 or len(b) < 2:
            raise FunctionError(DIV0, "each sample needs at least 2 numbers")
        va, vb = spread(a, sample=True), spread(b, sample=True)
        na, nb = len(a), len(b)
        if kind == 2:
            df = na + nb - 2
            pooled = ((na - 1) * va + (nb - 1) * vb) / df
            error = math.sqrt(pooled * (1 / na + 1 / nb))
        else:
            error = math.sqrt(va / na + vb / nb)
            df = error**4 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)) if error else 1
        if error == 0:
            raise FunctionError(DIV0, "the samples do not vary")
        t = (mean(a) - mean(b)) / error
    return two_tails(abs(t), df) / (2 if tails == 1 else 1)


@builtin
class T_TEST(UserFunction):
    name = "T.TEST"
    description = "The probability that two samples have the same mean: type 1 paired, 2 same variance, 3 different variances; tails 1 or 2."
    examples = (Example("=ROUND(T.TEST(A1:A3, B1:B3, 2, 1), 4)", 0.0351, {"A1": 3, "A2": 4, "A3": 5, "B1": 6, "B2": 8, "B3": 7}),)

    def call(self, array1: Range, array2: Range, tails: float, type: float):
        return t_test(array1, array2, tails, type)


@builtin
class TTEST(UserFunction):
    description = "The probability that two samples have the same mean (the old name of T.TEST)."
    examples = (Example("=ROUND(TTEST(A1:A3, B1:B3, 2, 1), 4)", 0.0351, {"A1": 3, "A2": 4, "A3": 5, "B1": 6, "B2": 8, "B3": 7}),)

    def call(self, array1: Range, array2: Range, tails: float, type: float):
        return t_test(array1, array2, tails, type)


# -- confidence intervals -----------------------------------------------------------------------------------------------
def _confidence(alpha: float, standard_dev: float, size: float) -> tuple[float, int]:
    _probability(alpha)
    _positive(standard_dev, "the standard deviation")
    if size < 1:
        raise FunctionError(NUM, "the sample size must be 1 or more")
    return standard_dev, int(size)


def _confidence_norm(alpha: float, standard_dev: float, size: float) -> float:
    standard_dev, n = _confidence(alpha, standard_dev, size)
    return _STANDARD.inv_cdf(1 - alpha / 2) * standard_dev / math.sqrt(n)


@builtin
class CONFIDENCE_NORM(UserFunction):
    name = "CONFIDENCE.NORM"
    description = "Half the width of the confidence interval for a mean (known standard deviation, normal distribution); alpha is 1 minus the confidence level."
    examples = (Example("=ROUND(CONFIDENCE.NORM(0.05, 2.5, 50), 4)", 0.693),)

    def call(self, alpha: float, standard_dev: float, size: float):
        return _confidence_norm(alpha, standard_dev, size)


@builtin
class CONFIDENCE(UserFunction):
    description = "Half the width of the confidence interval for a mean (the old name of CONFIDENCE.NORM)."
    examples = (Example("=ROUND(CONFIDENCE(0.05, 2.5, 50), 4)", 0.693),)

    def call(self, alpha: float, standard_dev: float, size: float):
        return _confidence_norm(alpha, standard_dev, size)


@builtin
class CONFIDENCE_T(UserFunction):
    name = "CONFIDENCE.T"
    description = "Half the width of the confidence interval for a mean from a sample (Student t distribution)."
    examples = (Example("=ROUND(CONFIDENCE.T(0.05, 1, 50), 4)", 0.2842),)

    def call(self, alpha: float, standard_dev: float, size: float):
        standard_dev, n = _confidence(alpha, standard_dev, size)
        if n == 1:
            raise FunctionError(DIV0, "a sample of 1 has no spread")
        return _inverse_two_tails(alpha, n - 1) * standard_dev / math.sqrt(n)


# -- the chi-squared test --------------------------------------------------------------------------------------------------
@builtin
class CHISQ_TEST(UserFunction):
    name = "CHISQ.TEST"
    description = "The probability that the observed counts come from the expected ones (chi-squared test of independence or fit)."
    examples = (Example("=ROUND(CHISQ.TEST(A1:A4, B1:B4), 4)", 0.0064, {"A1": 18, "A2": 22, "A3": 20, "A4": 40, "B1": 25, "B2": 25, "B3": 25, "B4": 25}),)

    def call(self, actual_range: Range, expected_range: Range):
        rows, cols = actual_range.n_rows, actual_range.n_cols
        if (rows, cols) != (expected_range.n_rows, expected_range.n_cols):
            raise FunctionError(NA, "the observed and expected counts must have the same size")
        pairs = []
        for r in range(rows):
            for c in range(cols):
                a, e = actual_range.at(r, c), expected_range.at(r, c)
                if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (a, e)):
                    continue
                pairs.append((a, e))
        df = (rows - 1) * (cols - 1) if rows > 1 and cols > 1 else max(rows, cols) - 1
        if df < 1 or not pairs:
            raise FunctionError(DIV0, "there are too few counts")
        if any(e == 0 for _, e in pairs):
            raise FunctionError(DIV0, "an expected count is 0")
        chi = math.fsum((a - e) ** 2 / e for a, e in pairs)
        return regularized_gamma_q(df / 2, chi / 2)
