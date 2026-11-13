"""RANDOM and alternatives in other programs' files: the formulas Excel would use, read back as RANDOM (D292, D294).

The Excel text is checked by running it: a small evaluator knows the Excel functions the export uses and answers them
from the model's own distributions, with ``RAND()`` fixed, so the order of every parameter is tested."""

from __future__ import annotations

import math

import pytest
from claudia_computes_io import Untranslatable
from claudia_computes_io.extensions import from_excel, restore_alternatives, to_excel, with_note

from claudia_computes import parse_input
from claudia_computes.distributions import quantile

U = 0.3


def run(excel: str, u: float = U) -> float:
    """The value of an Excel formula text made of the functions the export uses (a test-only evaluator)."""
    body = (
        excel[1:]
        .replace("^", "**")
        .replace("RAND()", repr(u))
        .replace("TRUE", "True")
        .replace("{", "[")
        .replace("}", "]")
    )
    cumulative = {
        "NORMDIST": lambda x, m, s, _: statistics_cdf("normal", x, m, s),
        "LOGNORMDIST": lambda x, m, s: statistics_cdf("lognormal", x, m, s),
        "WEIBULL": lambda x, k, s, _: statistics_cdf("weibull", x, k, s),
        "BETADIST": lambda x, a, b: statistics_cdf("beta", x, a, b),
        "GAMMADIST": lambda x, k, s, _: statistics_cdf("gamma", x, k, s),
    }
    functions = {
        "NORMINV": lambda p, m, s: quantile("normal", p, (m, s)),
        "LOGINV": lambda p, m, s: quantile("lognormal", p, (m, s)),
        "BETAINV": lambda p, a, b: quantile("beta", p, (a, b)),
        "GAMMAINV": lambda p, k, s: quantile("gamma", p, (k, s)),
        "CRITBINOM": lambda n, c, p: quantile("binomial", p, (n, c)),
        "LN": math.log,
        "EXP": math.exp,
        "MAX": max,
        "MEDIAN": lambda *v: sorted(v)[len(v) // 2],
        "LOOKUP": lambda x, edges, values: values[max(i for i, e in enumerate(edges) if e <= x)],
        **cumulative,
    }
    return eval(body, {"__builtins__": {}}, functions)  # noqa: S307 (the text is written by the exporter, in a test)


def statistics_cdf(name: str, x: float, *p: float) -> float:
    from claudia_computes.distributions import DISTRIBUTIONS

    cdf = DISTRIBUTIONS[name].cdf
    assert cdf is not None
    return cdf(x, p)


CASES = [
    ('=RANDOM("uniform",10,20)', "uniform", (10, 20)),
    ('=RANDOM("normal",1000,150)', "normal", (1000, 150)),
    ('=RANDOM("lognormal",0,0.5)', "lognormal", (0, 0.5)),
    ('=RANDOM("exponential",2)', "exponential", (2,)),
    ('=RANDOM("weibull",1.5,10)', "weibull", (1.5, 10)),
    ('=RANDOM("beta",2,5)', "beta", (2, 5)),
    ('=RANDOM("gamma",3,2)', "gamma", (3, 2)),
    ('=RANDOM("pert",10,12,20)', "pert", (10, 12, 20)),
    ('=RANDOM("binomial",20,0.3)', "binomial", (20, 0.3)),
    ('=RANDOM("discrete",1,1,2,2,5,1)', "discrete", (1, 1, 2, 2, 5, 1)),
]


@pytest.mark.parametrize(("formula", "name", "parameters"), CASES)
def test_a_distribution_is_written_as_the_formula_excel_uses(formula, name, parameters):
    excel = to_excel(formula)
    assert "RANDOM" not in excel and "RAND()" in excel
    assert run(excel) == pytest.approx(quantile(name, U, parameters), rel=1e-9)


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ('=RANDOM("normal",1000,150)', "=NORMINV(RAND(),1000,150)"),
        ('=RANDOM("lognormal",0,0.5)', "=LOGINV(RAND(),0,0.5)"),
        ('=RANDOM("binomial",20,0.3)', "=CRITBINOM(20,0.3,RAND())"),
        ('=RANDOM("uniform",10,20)', "=10+(20-10)*RAND()"),
    ],
)
def test_the_usual_ones_read_the_way_a_person_would_write_them(formula, expected):
    assert to_excel(formula) == expected


def test_the_parameters_may_be_cells_and_formulas():
    excel = to_excel('=RANDOM("normal",B2*1.1,Sheet1!C3)+1')
    assert excel == "=NORMINV(RAND(),(B2*1.1),Sheet1!C3)+1".replace("(B2*1.1)", "B2*1.1") or "NORMINV(RAND()" in excel
    assert "RANDOM" not in excel


def test_an_expression_that_is_more_than_a_call_is_put_in_brackets_where_it_is_used():
    assert to_excel('=2*RANDOM("exponential",2)') == "=2*(-LN(1-RAND())/2)"


def test_without_arguments_it_is_rand():
    assert to_excel("=RANDOM()+1") == "=RAND()+1"


@pytest.mark.parametrize(
    ("formula", "name", "parameters", "low", "high"),
    [
        ('=RANDOM("normal",1000,150,700,1400)', "normal", (1000, 150), 700, 1400),
        ('=RANDOM("normal",1000,150,700)', "normal", (1000, 150), 700, None),
        ('=RANDOM("normal",1000,150,,1400)', "normal", (1000, 150), None, 1400),
        ('=RANDOM("lognormal",0,0.5,0.5,3)', "lognormal", (0, 0.5), 0.5, 3),
        ('=RANDOM("exponential",2,0.1,1)', "exponential", (2,), 0.1, 1),
        ('=RANDOM("weibull",1.5,10,2,20)', "weibull", (1.5, 10), 2, 20),
        ('=RANDOM("beta",2,5,0.1,0.6)', "beta", (2, 5), 0.1, 0.6),
        ('=RANDOM("gamma",3,2,1,10)', "gamma", (3, 2), 1, 10),
        ('=RANDOM("pert",10,12,20,11,15)', "pert", (10, 12, 20), 11, 15),
        ('=RANDOM("uniform",10,20,12,15)', "uniform", (10, 20), 12, 15),
    ],
)
def test_a_cut_distribution_is_squeezed_the_way_the_model_does_it(formula, name, parameters, low, high):
    excel = to_excel(formula)
    assert run(excel) == pytest.approx(quantile(name, U, parameters, low=low, high=high), rel=1e-6)


@pytest.mark.parametrize(
    "formula",
    ['=RANDOM("triangular",1,2,3)', '=RANDOM("poisson",4)', '=RANDOM("discrete",A1,1,B1,2)', "=RANDOM(A1,1,2)"],
)
def test_what_has_no_formula_that_draws_once_is_untranslatable(formula):
    with pytest.raises(Untranslatable) as why:
        to_excel(formula)
    assert why.value.reason == "random"


def test_a_distribution_that_does_not_exist_is_a_function_the_other_side_lacks():
    with pytest.raises(Untranslatable) as why:
        to_excel('=RANDOM("zipf",1)')
    assert why.value.reason == "function"


def test_formulas_without_random_are_left_alone():
    assert to_excel("=SUM(A1:A3)+RAND()") == "=SUM(A1:A3)+RAND()"


# ------------------------------------------------------------------ and back
@pytest.mark.parametrize(
    ("excel", "model"),
    [
        ("=NORMINV(RAND(),1000,150)", '=RANDOM("normal",1000,150)'),
        ("=NORM.INV(RAND(),B2,B3)", '=RANDOM("normal",B2,B3)'),
        ("=_xlfn.NORM.INV(RAND(),1,2)", '=RANDOM("normal",1,2)'),
        ("=NORMSINV(RAND())", '=RANDOM("normal",0,1)'),
        ("=LOGINV(RAND(),0,0.5)*2", '=RANDOM("lognormal",0,0.5)*2'),
        ("=BETAINV(RAND(),2,5)", '=RANDOM("beta",2,5)'),
        ("=GAMMA.INV(RAND(),3,2)", '=RANDOM("gamma",3,2)'),
        ("=CRITBINOM(20,0.3,RAND())", '=RANDOM("binomial",20,0.3)'),
        ("=BINOM.INV(20,0.3,RAND())", '=RANDOM("binomial",20,0.3)'),
    ],
)
def test_the_inverse_functions_of_a_draw_become_random(excel, model):
    assert from_excel(excel) == model


@pytest.mark.parametrize(
    "excel", ["=NORMINV(0.5,1,2)", "=NORMINV(A1,1,2)", "=NORMINV(RAND()*0.5,1,2)", "=1+RAND()", "=SUM(A1)"]
)
def test_other_formulas_are_not_touched(excel):
    assert from_excel(excel) == excel


@pytest.mark.parametrize(
    ("formula", "_name", "_parameters"),
    [c for c in CASES if c[1] in ("normal", "lognormal", "beta", "gamma", "binomial")],
)
def test_what_is_written_for_excel_comes_back_as_random(formula, _name, _parameters):
    assert from_excel(to_excel(formula)) == formula


# ------------------------------------------------------------------ alternatives
def test_alternatives_are_written_as_the_first_one_and_a_note():
    written = with_note(parse_input("{800, 1000, 1300}"))
    assert written.content == {"t": "int", "v": 800}
    assert written.note == "claudia alternatives: {800, 1000, 1300}"


def test_named_and_formula_alternatives_are_in_the_note_and_the_first_is_a_formula_when_it_is_one():
    written = with_note(parse_input("{=B2*0.9, base: =B2}"))
    assert written.content == {"t": "formula", "v": "=B2*0.9"}
    assert written.note == "claudia alternatives: {alt 1: =B2*0.9, base: =B2}"


def test_other_cells_have_no_note():
    for text in ("5", "=A1+1", "hello", "=ALTERNATIVES(1)"):
        content = parse_input(text)
        assert with_note(content).content == content and with_note(content).note is None
    assert with_note(None).note is None


def test_the_note_gives_the_alternatives_back_when_the_cell_still_has_the_first():
    written = with_note(parse_input("{800, 1000, 1300}"))
    assert restore_alternatives(written.content, written.note) == parse_input("{800, 1000, 1300}")
    named = with_note(parse_input("{low: 1, high: 2}"))
    assert restore_alternatives(named.content, named.note) == parse_input("{low: 1, high: 2}")


def test_a_cell_that_was_changed_in_the_other_program_keeps_its_new_content():
    written = with_note(parse_input("{800, 1000, 1300}"))
    assert restore_alternatives({"t": "int", "v": 5}, written.note) == {"t": "int", "v": 5}


def test_a_note_that_is_not_ours_is_left_alone():
    content = {"t": "int", "v": 800}
    assert restore_alternatives(content, "check this number") == content
    assert restore_alternatives(content, None) == content
    assert restore_alternatives(content, "claudia alternatives: not a list") == content
