"""More functions of numbers (trigonometry, rounding, number theory, combinatorics, number systems, sums of squares)
with results from Microsoft's documentation, from mathematical identities or from known constants."""

from __future__ import annotations

import math

from excel_helpers import cases, check, column

PI = math.pi

# -- trigonometry -------------------------------------------------------------------------------------------------
TRIG = (
    ("=ASIN(1)", PI / 2),
    ("=ASIN(-0.5)", -PI / 6),
    ("=ASIN(2)", "#NUM!"),
    ("=ACOS(1)", 0.0),
    ("=ACOS(0.5)", PI / 3),
    ("=ACOS(-2)", "#NUM!"),
    ("=ATAN(1)", PI / 4),
    ("=ATAN(0)", 0.0),
    ("=ATAN2(1, 1)", PI / 4),  # (x first, then y)
    ("=ATAN2(-1, 0)", PI),
    ("=ATAN2(0, 1)", PI / 2),
    ("=ATAN2(0, 0)", "#DIV/0!"),
    ("=SINH(1)", 1.1752011936438014),
    ("=COSH(1)", 1.5430806348152437),
    ("=TANH(1)", 0.7615941559557649),
    ("=ASINH(1)", 0.881373587019543),
    ("=ACOSH(1)", 0.0),
    ("=ACOSH(10)", 2.993222846126381),
    ("=ACOSH(0.5)", "#NUM!"),
    ("=ATANH(0.5)", 0.5493061443340548),
    ("=ATANH(1)", "#NUM!"),
    ("=COT(1)", 0.6420926159343306),
    ("=COT(0)", "#DIV/0!"),
    ("=COTH(1)", 1.3130352854993315),
    ("=COTH(0)", "#DIV/0!"),
    ("=ACOT(2)", 0.4636476090008061),
    ("=ACOT(0)", PI / 2),
    ("=ACOT(-2)", PI - 0.4636476090008061),  # (Excel's ACOT runs from 0 to pi)
    ("=ACOTH(2)", 0.5493061443340548),
    ("=ACOTH(0.5)", "#NUM!"),
    ("=CSC(1)", 1.1883951057781212),
    ("=CSC(0)", "#DIV/0!"),
    ("=CSCH(1)", 0.8509181282393216),
    ("=CSCH(0)", "#DIV/0!"),
    ("=SEC(1)", 1.8508157176809255),
    ("=SECH(1)", 0.6480542736638855),
    ("=SECH(0)", 1.0),
)


@cases(*TRIG)
def test_trigonometry(formula, expected, cells):
    check(formula, expected, cells)


# -- even, odd, quotient, gcd ----------------------------------------------------------------------------------------
INTEGERS = (
    ("=EVEN(1.5)", 2),
    ("=EVEN(3)", 4),
    ("=EVEN(2)", 2),
    ("=EVEN(-1)", -2),
    ("=EVEN(0)", 0),
    ("=ODD(1.5)", 3),
    ("=ODD(3)", 3),
    ("=ODD(2)", 3),
    ("=ODD(-1)", -1),
    ("=ODD(-2)", -3),
    ("=ODD(0)", 1),
    ("=ISEVEN(-1)", False),
    ("=ISEVEN(2.5)", True),
    ("=ISEVEN(0)", True),
    ('=ISEVEN("x")', "#VALUE!"),
    ("=ISODD(3)", True),
    ("=ISODD(-2)", False),
    ("=ISODD(2.9)", False),
    ("=QUOTIENT(5, 2)", 2),
    ("=QUOTIENT(-10, 3)", -3),
    ("=QUOTIENT(4.5, 3.1)", 1),
    ("=QUOTIENT(5, 0)", "#DIV/0!"),
    ("=GCD(24, 36)", 12),
    ("=GCD(5, 0)", 5),
    ("=GCD(7, 1)", 1),
    ("=GCD(24.9, 36.1)", 12),
    ("=GCD(12, 18, 30)", 6),
    ("=GCD(-1, 2)", "#NUM!"),
    ("=LCM(5, 2)", 10),
    ("=LCM(24, 36)", 72),
    ("=LCM(4, 6, 10)", 60),
    ("=LCM(0, 5)", 0),
    ("=LCM(-1, 5)", "#NUM!"),
)


@cases(*INTEGERS)
def test_even_odd_quotient_gcd_lcm(formula, expected, cells):
    check(formula, expected, cells)


def test_gcd_and_lcm_read_ranges():
    cells = column("A1", [24, 36, 60])
    check("=GCD(A1:A3)", 12, cells)
    check("=LCM(A1:A3)", 360, cells)


# -- counting ---------------------------------------------------------------------------------------------------------
COUNTING = (
    ("=COMBIN(8, 2)", 28),
    ("=COMBIN(5, 0)", 1),
    ("=COMBIN(5, 5)", 1),
    ("=COMBIN(52, 5)", 2598960),
    ("=COMBIN(3, 5)", "#NUM!"),
    ("=COMBIN(-1, 0)", "#NUM!"),
    ("=COMBINA(4, 3)", 20),
    ("=COMBINA(10, 3)", 220),
    ("=COMBINA(3, 0)", 1),
    ("=COMBINA(0, 0)", 1),
    ("=COMBINA(0, 2)", 0),
    ("=PERMUT(100, 3)", 970200),
    ("=PERMUT(3, 2)", 6),
    ("=PERMUT(3, 0)", 1),
    ("=PERMUT(2, 3)", "#NUM!"),
    ("=PERMUTATIONA(3, 2)", 9),
    ("=PERMUTATIONA(2, 3)", 8),
    ("=PERMUTATIONA(-1, 2)", "#NUM!"),
    ("=FACTDOUBLE(6)", 48),
    ("=FACTDOUBLE(7)", 105),
    ("=FACTDOUBLE(0)", 1),
    ("=FACTDOUBLE(-2)", "#NUM!"),
    ("=MULTINOMIAL(2, 3, 4)", 1260),
    ("=MULTINOMIAL(1, 1)", 2),
    ("=MULTINOMIAL(-1, 2)", "#NUM!"),
    ("=SQRTPI(1)", 1.7724538509055159),
    ("=SQRTPI(2)", 2.5066282746310002),
    ("=SQRTPI(0)", 0),
    ("=SQRTPI(-1)", "#NUM!"),
)


@cases(*COUNTING)
def test_counting(formula, expected, cells):
    check(formula, expected, cells)


# -- rounding ---------------------------------------------------------------------------------------------------------
ROUNDING = (
    ("=CEILING.MATH(24.3, 5)", 25),
    ("=CEILING.MATH(6.7)", 7),
    ("=CEILING.MATH(-8.1, 2)", -8),
    ("=CEILING.MATH(-5.5, 2, 0)", -4),
    ("=CEILING.MATH(-5.5, 2, -1)", -6),
    ("=CEILING.MATH(5.5, 0)", 0),
    ("=FLOOR.MATH(24.3, 5)", 20),
    ("=FLOOR.MATH(6.7)", 6),
    ("=FLOOR.MATH(-8.1, 2)", -10),
    ("=FLOOR.MATH(-5.5, 2, 0)", -6),
    ("=FLOOR.MATH(-5.5, 2, -1)", -4),
    ("=CEILING.PRECISE(4.3)", 5),
    ("=CEILING.PRECISE(-4.3)", -4),
    ("=CEILING.PRECISE(4.3, -2)", 6),
    ("=CEILING.PRECISE(-4.3, -2)", -4),
    ("=ISO.CEILING(4.3)", 5),
    ("=ISO.CEILING(-4.3, 2)", -4),
    ("=FLOOR.PRECISE(3.2, 1)", 3),
    ("=FLOOR.PRECISE(-3.2, -1)", -4),
    ("=FLOOR.PRECISE(3.2, -1)", 3),
    ("=FLOOR.PRECISE(-3.2, 1)", -4),
    ("=MROUND(10, 3)", 9),
    ("=MROUND(-10, -3)", -9),
    ("=MROUND(1.3, 0.2)", 1.4),
    ("=MROUND(7.5, 5)", 10),
    ("=MROUND(10, 0)", 0),
    ("=MROUND(5, -2)", "#NUM!"),
)


@cases(*ROUNDING)
def test_rounding_to_multiples(formula, expected, cells):
    check(formula, expected, cells)


# -- number systems ---------------------------------------------------------------------------------------------------
SYSTEMS = (
    ("=ROMAN(499)", "CDXCIX"),
    ("=ROMAN(499, 0)", "CDXCIX"),
    ("=ROMAN(499, 1)", "LDVLIV"),
    ("=ROMAN(499, 2)", "XDIX"),
    ("=ROMAN(499, 3)", "VDIV"),
    ("=ROMAN(499, 4)", "ID"),
    ("=ROMAN(2013)", "MMXIII"),
    ("=ROMAN(1994)", "MCMXCIV"),
    ("=ROMAN(3999)", "MMMCMXCIX"),
    ("=ROMAN(4)", "IV"),
    ("=ROMAN(0)", ""),
    ("=ROMAN(4000)", "#VALUE!"),
    ("=ROMAN(-1)", "#VALUE!"),
    ('=ARABIC("LVII")', 57),
    ('=ARABIC("mcmxii")', 1912),
    ('=ARABIC("MCMXCIV")', 1994),
    ('=ARABIC("-IV")', -4),
    ('=ARABIC("")', 0),
    ('=ARABIC("X1")', "#VALUE!"),
    ("=BASE(7, 2)", "111"),
    ("=BASE(100, 16)", "64"),
    ("=BASE(255, 16)", "FF"),
    ("=BASE(15, 2, 10)", "0000001111"),
    ("=BASE(0, 2)", "0"),
    ("=BASE(-1, 2)", "#NUM!"),
    ("=BASE(7, 1)", "#NUM!"),
    ("=BASE(7, 37)", "#NUM!"),
    ('=DECIMAL("FF", 16)', 255),
    ('=DECIMAL("111", 2)', 7),
    ('=DECIMAL("zap", 36)', 45745),
    ('=DECIMAL("11", 1)', "#NUM!"),
    ('=DECIMAL("2", 2)', "#NUM!"),
    ('=DECIMAL("", 10)', 0),
)


@cases(*SYSTEMS)
def test_roman_arabic_base_decimal(formula, expected, cells):
    check(formula, expected, cells)


def test_base_and_decimal_are_inverse():
    for number in (0, 1, 35, 36, 1295, 123456):
        for radix in (2, 8, 16, 36):
            check(f"=DECIMAL(BASE({number}, {radix}), {radix})", number)


def test_roman_and_arabic_are_inverse():
    for number in range(1, 4000, 37):
        check(f"=ARABIC(ROMAN({number}))", number)


# -- sums of squares and series ---------------------------------------------------------------------------------------
X = [2, 3, 9, 1, 8, 7, 5]
Y = [6, 5, 11, 7, 5, 4, 4]
PAIRS = {**column("A1", X), **column("B1", Y)}


def test_sums_of_squares():
    check("=SUMSQ(3, 4)", 25)
    check("=SUMSQ(A1:A7)", sum(v * v for v in X), PAIRS)
    check("=SUMSQ(A1:A2, 1)", 14, column("A1", [2, 3]))
    check("=SUMSQ(A1:A2)", 4, {"A1": 2, "A2": "text"})  # (text in a range is skipped, as SUM does)


def test_sums_of_squared_differences_of_two_arrays_from_the_documentation():
    check("=SUMX2MY2(A1:A7, B1:B7)", -55, PAIRS)
    check("=SUMX2PY2(A1:A7, B1:B7)", 521, PAIRS)
    check("=SUMXMY2(A1:A7, B1:B7)", 79, PAIRS)


def test_sums_of_two_arrays_need_the_same_size():
    check("=SUMXMY2(A1:A3, B1:B2)", "#N/A", {**column("A1", [1, 2, 3]), **column("B1", [1, 2])})


def test_series_sum():
    coefficients = column("A1", [1, 1, 1])
    check("=SERIESSUM(2, 0, 1, A1:A3)", 7, coefficients)
    check("=SERIESSUM(3, 1, 2, A1:A2)", 57, column("A1", [1, 2]))
    check("=SERIESSUM(2, 0, 2, A1:A3)", 1 + 4 + 16, coefficients)
    x = PI / 4
    taylor = column("A1", [1, -0.5, 1 / 24, -1 / 720])
    check(
        "=SERIESSUM(PI()/4, 0, 2, A1:A4)",
        sum(c * x ** (2 * k) for k, c in enumerate([1, -0.5, 1 / 24, -1 / 720])),
        taylor,
    )
    check('=SERIESSUM(2, 0, 1, "x")', "#VALUE!")
