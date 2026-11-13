"""The distributions RANDOM can draw from (D292).

Each one is a quantile function: a uniform number in, a value of the distribution out. That is what makes every
distribution except Poisson a formula Excel can run (``NORM.INV(RAND(), ...)``), and what lets two alternatives of an
input see the same random draw. Closed forms are used as the independent check wherever one exists."""

from __future__ import annotations

import math
import statistics

import pytest

from claudia_computes.distributions import DISTRIBUTIONS, quantile
from claudia_computes.values import FormulaError


def test_uniform_runs_from_the_first_to_the_second_parameter():
    assert quantile("uniform", 0.0, (10, 20)) == 10
    assert quantile("uniform", 0.5, (10, 20)) == 15
    assert quantile("uniform", 0.25, (-1, 1)) == -0.5


def test_normal_agrees_with_the_standard_library():
    reference = statistics.NormalDist(1000, 150)
    for u in (0.001, 0.2, 0.5, 0.9, 0.999):
        assert quantile("normal", u, (1000, 150)) == pytest.approx(reference.inv_cdf(u), rel=1e-12)
    assert quantile("normal", 0.975, (0, 1)) == pytest.approx(1.959963984540054)


def test_lognormal_is_the_exponential_of_a_normal():
    assert quantile("lognormal", 0.5, (1.0, 0.4)) == pytest.approx(math.e)
    assert quantile("lognormal", 0.9, (0.0, 1.0)) == pytest.approx(math.exp(1.2815515655446004))


def test_triangular_peaks_at_its_mode():
    low, mode, high = 9, 11, 14
    at_mode = (mode - low) / (high - low)
    assert quantile("triangular", at_mode, (low, mode, high)) == pytest.approx(11)
    assert quantile("triangular", 0.0, (low, mode, high)) == 9
    assert quantile("triangular", 1.0, (low, mode, high)) == pytest.approx(14)
    # the rising side: F(x) = (x - a)^2 / ((b - a)(c - a))
    assert quantile("triangular", 0.1, (low, mode, high)) == pytest.approx(9 + math.sqrt(0.1 * 5 * 2))


def test_exponential_takes_a_rate():
    assert quantile("exponential", 0.5, (2,)) == pytest.approx(math.log(2) / 2)
    assert quantile("exponential", 0.0, (2,)) == 0


def test_weibull_takes_shape_then_scale():
    assert quantile("weibull", 0.5, (1, 3)) == pytest.approx(3 * math.log(2))  # shape 1 is exponential
    assert quantile("weibull", 0.5, (2, 10)) == pytest.approx(10 * math.sqrt(math.log(2)))


def test_beta_with_equal_parameters_is_symmetric_and_matches_its_closed_form():
    assert quantile("beta", 0.5, (2, 2)) == pytest.approx(0.5)
    for u in (0.1, 0.35, 0.8):
        x = quantile("beta", u, (2, 2))
        assert 3 * x**2 - 2 * x**3 == pytest.approx(u, abs=1e-10)  # the CDF of Beta(2, 2)


def test_beta_one_one_is_uniform():
    assert quantile("beta", 0.3, (1, 1)) == pytest.approx(0.3)


def test_gamma_matches_closed_forms_for_whole_shapes():
    for u in (0.05, 0.5, 0.95):
        x = quantile("gamma", u, (2, 1))
        assert 1 - math.exp(-x) * (1 + x) == pytest.approx(u, abs=1e-10)  # the CDF of Gamma(2, 1)
        y = quantile("gamma", u, (3, 2))
        z = y / 2
        assert 1 - math.exp(-z) * (1 + z + z * z / 2) == pytest.approx(u, abs=1e-10)  # Gamma(3, scale 2)


def test_gamma_with_shape_one_is_exponential_with_that_scale():
    assert quantile("gamma", 0.5, (1, 4)) == pytest.approx(4 * math.log(2))


def test_pert_stays_between_its_bounds_and_peaks_near_its_mode():
    low, mode, high = 10, 14, 30
    draws = [quantile("pert", i / 1000, (low, mode, high)) for i in range(1, 1000)]
    assert min(draws) >= low and max(draws) <= high
    assert statistics.mean(draws) == pytest.approx((low + 4 * mode + high) / 6, rel=0.01)  # PERT's mean


def test_binomial_is_the_smallest_count_whose_cumulative_probability_reaches_u():
    assert quantile("binomial", 0.3, (1, 0.5)) == 0
    assert quantile("binomial", 0.5, (1, 0.5)) == 0
    assert quantile("binomial", 0.51, (1, 0.5)) == 1
    assert quantile("binomial", 0.999999, (10, 0.5)) == 10
    assert quantile("binomial", 0.5, (10, 0.5)) == 5


def test_poisson_counts_events():
    assert quantile("poisson", 0.30, (1,)) == 0  # P(0) = e^-1 = 0.3679
    assert quantile("poisson", 0.40, (1,)) == 1  # P(<=1) = 0.7358
    assert quantile("poisson", 0.8, (1,)) == 2


def test_discrete_picks_from_the_listed_values_by_weight():
    parameters = (10, 1, 20, 1, 30, 2)  # value, weight, value, weight ...
    assert quantile("discrete", 0.1, parameters) == 10
    assert quantile("discrete", 0.3, parameters) == 20
    assert quantile("discrete", 0.6, parameters) == 30
    assert quantile("discrete", 0.9999, parameters) == 30


def test_limits_cut_the_distribution_instead_of_clamping_it():
    # Normal(1000, 150) kept at 0 or above: every u gives a value >= 0, and the median moves up a little.
    values = [quantile("normal", i / 100, (1000, 150), low=1000) for i in range(0, 100)]
    assert min(values) >= 1000
    assert quantile("normal", 0.5, (1000, 150), low=1000) == pytest.approx(
        statistics.NormalDist(1000, 150).inv_cdf(0.75)
    )


def test_limits_on_both_sides():
    for u in (0.0, 0.3, 0.9999):
        value = quantile("normal", u, (0, 1), low=-1, high=1)
        assert -1 <= value <= 1


@pytest.mark.parametrize(
    ("name", "parameters"),
    [
        ("normal", (0, 0)),  # a spread of 0
        ("normal", (0, -1)),
        ("uniform", (5, 1)),
        ("triangular", (1, 5, 3)),  # the mode is outside
        ("exponential", (0,)),
        ("weibull", (0, 1)),
        ("beta", (0, 1)),
        ("gamma", (1, 0)),
        ("binomial", (3.5, 0.5)),
        ("binomial", (3, 1.5)),
        ("poisson", (-1,)),
        ("discrete", (1, 0, 2, 0)),  # no weight at all
    ],
)
def test_impossible_parameters_are_a_number_error(name, parameters):
    with pytest.raises(FormulaError) as caught:
        quantile(name, 0.5, parameters)
    assert caught.value.code == "#NUM!"


def test_a_wrong_number_of_parameters_says_how_many_are_wanted():
    with pytest.raises(FormulaError) as caught:
        quantile("normal", 0.5, (1,))
    assert caught.value.code == "#VALUE!"
    assert "normal" in caught.value.detail and "2" in caught.value.detail


def test_discrete_wants_pairs_of_a_value_and_a_weight():
    with pytest.raises(FormulaError) as caught:
        quantile("discrete", 0.5, (1, 1, 2))  # a value without a weight
    assert caught.value.code == "#VALUE!"


def test_an_unknown_distribution_names_the_known_ones():
    with pytest.raises(FormulaError) as caught:
        quantile("cauchy", 0.5, (0, 1))
    assert caught.value.code == "#VALUE!"
    assert "normal" in caught.value.detail


def test_the_table_lists_what_the_dialog_and_the_exporter_need():
    names = set(DISTRIBUTIONS)
    assert names == {
        "uniform",
        "normal",
        "lognormal",
        "triangular",
        "pert",
        "exponential",
        "weibull",
        "beta",
        "gamma",
        "binomial",
        "poisson",
        "discrete",
    }
    assert DISTRIBUTIONS["normal"].arity == 2
    assert DISTRIBUTIONS["discrete"].arity is None
    assert DISTRIBUTIONS["poisson"].continuous is False
