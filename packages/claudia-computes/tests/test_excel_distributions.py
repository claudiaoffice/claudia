"""The normal and t distributions, tests and confidence intervals; values from Microsoft's documentation or scipy."""

from __future__ import annotations

from excel_helpers import cases, check, code, column

NORMAL = (
    ("=NORM.DIST(42, 40, 1.5, TRUE)", 0.9087887802741321),
    ("=NORM.DIST(42, 40, 1.5, FALSE)", 0.10934004978399577),
    ("=NORMDIST(42, 40, 1.5, TRUE)", 0.9087887802741321),
    ("=NORM.DIST(40, 40, 1.5, TRUE)", 0.5),
    ("=NORM.DIST(1, 0, 0, TRUE)", "#NUM!"),
    ("=NORM.S.DIST(1, TRUE)", 0.8413447460685429),
    ("=NORM.S.DIST(0.5, FALSE)", 0.35206532676429947),
    ("=NORMSDIST(-1.96)", 0.024997895148220435),
    ("=NORM.INV(0.9, 40, 1.5)", 41.9223273483169),
    ("=NORMINV(0.9, 40, 1.5)", 41.9223273483169),
    ("=NORM.INV(0.5, 3, 2)", 3),
    ("=NORM.INV(0, 40, 1.5)", "#NUM!"),
    ("=NORM.INV(1, 40, 1.5)", "#NUM!"),
    ("=NORM.INV(0.5, 40, -1)", "#NUM!"),
    ("=NORM.S.INV(0.975)", 1.959963984540054),
    ("=NORMSINV(0.025)", -1.9599639845400545),
    ("=NORM.S.INV(0.908789)", 1.3333346730441076),
    ("=NORM.S.INV(0.5)", 0),
    ("=NORM.S.INV(1.5)", "#NUM!"),
)


@cases(*NORMAL)
def test_normal_distribution(formula, expected, cells):
    check(formula, expected, cells)


def test_the_inverse_undoes_the_distribution():
    for p in (0.001, 0.05, 0.3, 0.5, 0.77, 0.999):
        check(f"=NORM.DIST(NORM.INV({p}, 5, 2), 5, 2, TRUE)", p)


T_DIST = (
    ("=T.DIST(1.5, 5, TRUE)", 0.9030481598787634),
    ("=T.DIST(1.5, 5, FALSE)", 0.12451734464635511),
    ("=T.DIST(-2, 10, TRUE)", 0.03669401738537018),
    ("=T.DIST(0, 3, TRUE)", 0.5),
    ("=T.DIST(60, 1, TRUE)", 0.99469533),
    ("=T.DIST(8, 3, FALSE)", 0.00073691),
    ("=T.DIST(1, 0, TRUE)", "#NUM!"),
    ("=T.DIST.2T(2.5, 8)", 0.03694203771362412),
    ("=T.DIST.2T(1.959999998, 60)", 0.0546449299759209),
    ("=T.DIST.2T(-1, 8)", "#NUM!"),
    ("=T.DIST.RT(2.5, 8)", 0.01847101885681206),
    ("=T.DIST.RT(-1, 3)", 0.8044988905221148),
    ("=T.DIST.RT(1.959999998, 60)", 0.02732246498796045),
    ("=TDIST(2.5, 8, 2)", 0.03694203771362412),
    ("=TDIST(2.5, 8, 1)", 0.01847101885681206),
    ("=TDIST(2.5, 8, 3)", "#NUM!"),
    ("=TDIST(-1, 8, 1)", "#NUM!"),
    ("=T.INV(0.75, 2)", 0.8164965809277261),
    ("=T.INV(0.025, 10)", -2.2281388519862753),
    ("=T.INV(0.9, 1)", 3.0776835371752544),
    ("=T.INV(0.5, 7)", 0),
    ("=T.INV(0, 7)", "#NUM!"),
    ("=T.INV(1, 7)", "#NUM!"),
    ("=T.INV.2T(0.05, 10)", 2.228138851986274),
    ("=T.INV.2T(0.05, 60)", 2.0002978220142604),
    ("=TINV(0.05, 10)", 2.228138851986274),
    ("=T.INV.2T(0, 10)", "#NUM!"),
    ("=T.INV.2T(1.5, 10)", "#NUM!"),
)


@cases(*T_DIST)
def test_t_distribution(formula, expected, cells):
    # (the two numbers from the documentation are given to 8 digits only)
    check(formula, expected, cells, tol=1e-6 if ("60, 1," in formula or "8, 3, FALSE" in formula) else 1e-9)


def test_the_t_inverse_undoes_the_distribution():
    for df in (1, 2, 5, 30, 200):
        for p in (0.01, 0.2, 0.5, 0.9, 0.995):
            check(f"=T.DIST(T.INV({p}, {df}), {df}, TRUE)", p)


A1 = [3, 4, 5, 8, 9, 1, 2, 4, 5]
A2 = [6, 19, 3, 2, 14, 4, 5, 17, 1]
SAMPLES = {**column("A1", A1), **column("B1", A2)}
T_TEST = (
    ("=T.TEST(A1:A9, B1:B9, 2, 1)", 0.19601578492528204),
    ("=TTEST(A1:A9, B1:B9, 2, 1)", 0.19601578492528204),
    ("=T.TEST(A1:A9, B1:B9, 2, 2)", 0.19199588676039622),
    ("=T.TEST(A1:A9, B1:B9, 2, 3)", 0.20229392336867796),
    ("=T.TEST(A1:A9, B1:B9, 1, 1)", 0.09800789246264102),  # (one tail: the smaller of the two)
    ("=T.TEST(B1:B9, A1:A9, 1, 1)", 0.09800789246264102),
    ("=T.TEST(A1:A9, B1:B9, 3, 1)", "#NUM!"),
    ("=T.TEST(A1:A9, B1:B9, 2, 4)", "#NUM!"),
    ("=T.TEST(A1:A9, B1:B8, 2, 1)", "#N/A"),
)


@cases(*[(f, e, SAMPLES) for f, e in T_TEST])
def test_t_test(formula, expected, cells):
    check(formula, expected, cells)


def test_t_test_of_samples_of_different_sizes_by_type_2_and_3():
    cells = {**column("A1", [1, 2, 3, 4, 5, 6]), **column("B1", [2, 4, 6, 8])}
    # scipy: ttest_ind([1..6], [2,4,6,8]) with equal_var True / False
    check("=T.TEST(A1:A6, B1:B4, 2, 2)", 0.3144361658733588, cells)
    check("=T.TEST(A1:A6, B1:B4, 2, 3)", 0.3624233327162579, cells)


def test_confidence_intervals_from_the_documentation():
    check("=CONFIDENCE.NORM(0.05, 2.5, 50)", 0.6929519121748389)
    check("=CONFIDENCE(0.05, 2.5, 50)", 0.6929519121748389)
    check("=CONFIDENCE.T(0.05, 1, 50)", 0.28419685549572987)
    assert code("=CONFIDENCE.NORM(0, 2.5, 50)") == "#NUM!"
    assert code("=CONFIDENCE.NORM(1, 2.5, 50)") == "#NUM!"
    assert code("=CONFIDENCE.NORM(0.05, 0, 50)") == "#NUM!"
    assert code("=CONFIDENCE.NORM(0.05, 2.5, 0)") == "#NUM!"
    assert code("=CONFIDENCE.T(0.05, 1, 1)") == "#DIV/0!"
    assert code("=CONFIDENCE.T(0.05, 0, 10)") == "#NUM!"


def test_the_chi_squared_test_from_the_documentation():
    actual = {"A1": 58, "B1": 35, "A2": 11, "B2": 25, "A3": 10, "B3": 23}
    expected = {"D1": 45.35, "E1": 47.65, "D2": 17.56, "E2": 18.44, "D3": 16.09, "E3": 16.91}
    check("=CHISQ.TEST(A1:B3, D1:E3)", 0.0003081920170083095, {**actual, **expected})
    assert code("=CHISQ.TEST(A1:B3, D1:E2)", {**actual, **expected}) == "#N/A"


def test_the_chi_squared_test_of_a_single_row_uses_n_minus_1_degrees_of_freedom():
    # scipy: chisquare([18, 22, 20, 40], [25, 25, 25, 25]) -> p = 0.00636
    cells = {**column("A1", [18, 22, 20, 40]), **column("B1", [25, 25, 25, 25])}
    check("=CHISQ.TEST(A1:A4, B1:B4)", 0.006363629995195269, cells)
    assert code("=CHISQ.TEST(A1:A2, B1:B2)", {**column("A1", [1, 2]), **column("B1", [0, 3])}) == "#DIV/0!"
