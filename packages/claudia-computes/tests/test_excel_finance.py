"""NPER, RATE, IPMT, PPMT, XNPV and XIRR; values from Microsoft's documentation, or checked against each other."""

from __future__ import annotations

from excel_helpers import cases, check, code, column

FLOWS = {**column("A1", [-10000, 2750, 4250, 3250, 2750]), **column("B1", [39448, 39508, 39751, 39859, 39904])}
# (1 Jan 2008, 1 Mar 2008, 30 Oct 2008, 15 Feb 2009, 1 Apr 2009: Microsoft's example for XNPV and XIRR)

FINANCE = (
    ("=NPER(0.12/12,-100,-1000,10000,1)", 59.67386567429457),
    ("=NPER(0.12/12,-100,-1000,10000)", 60.08212285),
    ("=NPER(0,-100,1000)", 10),
    ("=NPER(0,0,1000)", "#NUM!"),
    ("=NPER(0.01,-5,1000)", "#NUM!"),  # (the payment does not even cover the interest)
    ("=RATE(4*12,-200,8000)", 0.007701472488246008),  # Microsoft: 0.77% a month
    ("=RATE(4*12,-200,8000)*12", 0.09241766985895209),
    ("=RATE(10,0,-100,200)", 0.07177346253629313),  # 100 doubling in 10 periods
    ("=RATE(12,-100,1000,0,1,0.05)", 0.0350315303622702),  # (payments at the start; scipy brentq)
    ("=RATE(0,-100,1000)", "#NUM!"),
    ("=IPMT(0.1/12,1,36,8000)", -66.66666666666667),  # Microsoft: -66.67
    ("=IPMT(0.1,3,3,8000)", -292.44712990936555),  # Microsoft: -292.45
    ("=IPMT(0.1/12,1,36,8000,0,1)", 0),  # a payment at the start of the first period has no interest yet
    ("=IPMT(0.1/12,0,36,8000)", "#NUM!"),
    ("=IPMT(0.1/12,37,36,8000)", "#NUM!"),
    ("=PPMT(0.1/12,1,24,2000)", -75.62318600013725),  # Microsoft: -75.62
    ("=PPMT(0.08,10,10,200000)", -27598.05346),  # Microsoft: -27,598.05
    ("=XNPV(0.09,A1:A5,B1:B5)", 2086.6476020315354),  # Microsoft: 2,086.65
    ("=XIRR(A1:A5,B1:B5)", 0.37336253351883136),  # Microsoft: 37.34%
    ("=XIRR(A1:A5,B1:B5,0.5)", 0.37336253351883136),
    ("=XNPV(0.09,A1:A5,B1:B4)", "#NUM!"),
    ("=XNPV(-1,A1:A5,B1:B5)", "#NUM!"),
    ("=XIRR(A2:A5,B2:B5)", "#NUM!"),  # (no payment: only receipts)
)


@cases(*[(f, e, FLOWS) for f, e in FINANCE])
def test_money_over_time(formula, expected, cells):
    check(formula, expected, cells, tol=1e-6)


def test_the_interest_and_the_principal_add_up_to_the_payment():
    for kind in (0, 1):
        for period in (1, 2, 7, 36):
            check(
                f"=IPMT(0.07/12,{period},36,8000,0,{kind})+PPMT(0.07/12,{period},36,8000,0,{kind})",
                _payment(kind),
                tol=1e-6,
            )


def _payment(kind: int) -> float:
    rate, periods, loan = 0.07 / 12, 36, 8000
    growth = (1 + rate) ** periods
    return -(rate * loan * growth) / ((1 + rate * kind) * (growth - 1))


def test_the_principal_parts_pay_off_the_loan():
    for kind in (0, 1):
        total = "+".join(f"PPMT(0.05/12,{p},12,1200,0,{kind})" for p in range(1, 13))
        check(f"={total}", -1200, tol=1e-6)


def test_the_remaining_loan_is_what_the_interest_is_charged_on():
    # after the first period (payment at the end) the loan is 1200 + PPMT(1): the second period's interest is on that
    check("=IPMT(0.05/12,2,12,1200)", -(1200 + _ppmt1()) * 0.05 / 12, tol=1e-9)


def _ppmt1() -> float:
    rate, n, loan = 0.05 / 12, 12, 1200
    payment = -(rate * loan * (1 + rate) ** n) / ((1 + rate) ** n - 1)
    return payment + loan * rate  # the payment minus the first interest (a negative number plus a positive one)


def test_rate_undoes_pmt_and_nper_undoes_both():
    check("=RATE(36,PMT(0.06/12,36,10000),10000)", 0.005, tol=1e-9)
    check("=NPER(0.005,PMT(0.005,36,10000),10000)", 36, tol=1e-6)


def test_xnpv_of_a_single_year_and_xirr_agree():
    cells = {
        **column("A1", [-1000, 1100]),
        **column("B1", [46023, 46388]),
        **column("C1", [46388, 46023]),
    }  # a year (365 days) later
    check("=XIRR(A1:A2,B1:B2)", 0.1, cells, tol=1e-8)
    check("=XNPV(0.1,A1:A2,B1:B2)", 0, cells, tol=1e-8)
    check("=XNPV(0,A1:A2,B1:B2)", 100, cells)
    assert code("=XIRR(A1:A2,B1:B1)", cells) == "#NUM!"
    assert code("=XNPV(0.1,A1:A2,C1:C2)", cells) == "#NUM!"
