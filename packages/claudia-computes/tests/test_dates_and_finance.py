"""Date and money functions as Excel computes them (D347): the 1900 day count with its 29 February, months that
carry over, and the payment, value and rate functions, checked against Excel's own documented results."""

from __future__ import annotations

import pytest

from claudia_computes import Sheet, SheetId, WorkbookModel


def evaluate(formula: str, cells: dict[tuple[int, int], object] | None = None):
    model = WorkbookModel()
    sheet = Sheet(SheetId("s1"), "S")
    model.sheets[sheet.id] = sheet
    for position, value in (cells or {}).items():
        kind = "int" if isinstance(value, int) else "float" if isinstance(value, float) else "text"
        sheet.cells[position] = {"t": kind, "v": value}
    sheet.cells[(99, 9)] = {"t": "formula", "v": formula}
    model.open_container("s1")
    model._calculate_loaded()  # noqa: SLF001
    value = sheet.grid.get((99, 9))
    return getattr(value, "code", value)


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("=DATE(2026,11,13)", 46339),
        ("=DATE(1900,1,1)", 1),
        ("=DATE(1900,2,28)", 59),
        ("=DATE(1900,2,29)", 60),  # the day Excel counts and the calendar does not
        ("=DATE(1900,3,1)", 61),
        ("=DATE(9999,12,31)", 2958465),
        ("=DATE(26,1,1)", 9498),  # 0 to 1899 count from 1900
        ("=DATE(2026,14,1)", 46419),  # month 14 is February of the next year
        ("=DATE(2026,1,0)", 46022),  # day 0 is the last day of the month before
        ("=DATE(2026,0,0)", 45991),
        ("=DATE(-1,1,1)", "#NUM!"),
        ("=DATE(10000,1,1)", "#NUM!"),
        ("=YEAR(46339)", 2026),
        ("=MONTH(46339.75)", 11),  # a time of day does not change the date
        ("=DAY(46339)", 13),
        ("=YEAR(60)", 1900),
        ("=MONTH(60)", 2),
        ("=DAY(60)", 29),
        ("=DAY(0)", 0),
        ("=MONTH(0)", 1),
        ("=YEAR(-1)", "#NUM!"),
        ("=YEAR(2958466)", "#NUM!"),
        ('=YEAR("2026-11-13")', "#VALUE!"),  # text is never read as a date (E6.4)
    ],
)
def test_dates_count_days_as_excel_does(formula, expected):
    assert evaluate(formula) == expected


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("=EDATE(46326,1)", 46356),  # 31 October + 1 month is 30 November
        ("=EDATE(46053,1)", 46081),  # 31 January 2026 + 1 month is 28 February
        ("=EDATE(46053,-12)", 45688),
        ("=EOMONTH(46339,0)", 46356),
        ("=EOMONTH(46339,-11)", 46022),
        ("=EOMONTH(46339,3)", 46446),  # 28 February 2027
        ("=DAYS(46387,46339)", 48),
        ("=DAYS(46339.9,46339.1)", 0),
        ("=WEEKDAY(46339)", 6),  # a Friday
        ("=WEEKDAY(46339,2)", 5),
        ("=WEEKDAY(46339,3)", 4),
        ("=WEEKDAY(46339,11)", 5),
        ("=WEEKDAY(1)", 1),  # Excel calls 1 January 1900 a Sunday
        ("=WEEKDAY(46339,4)", "#NUM!"),
        ('=DATEDIF(45658,46339,"Y")', 1),
        ('=DATEDIF(45658,46339,"M")', 22),
        ('=DATEDIF(45658,46339,"D")', 681),
        ('=DATEDIF(45658,46339,"MD")', 12),
        ('=DATEDIF(45658,46339,"YM")', 10),
        ('=DATEDIF(45658,46339,"YD")', 316),
        ('=DATEDIF(45688,45716,"MD")', 28),
        ('=DATEDIF(46339,45658,"Y")', "#NUM!"),
        ('=DATEDIF(45658,46339,"W")', "#NUM!"),
    ],
)
def test_months_and_differences_follow_the_calendar(formula, expected):
    assert evaluate(formula) == expected


def close(value, expected, digits=6):
    return round(value, digits) == round(expected, digits)


def test_payments_values_and_rates_give_excels_results():
    assert close(evaluate("=PMT(0.08/12,10,10000)"), -1037.032089)  # Excel's own PMT example
    assert close(evaluate("=PMT(0.08/12,10,10000,0,1)"), -1030.164327)
    assert close(evaluate("=PMT(0.06/12,18*12,0,50000)"), -129.081161)
    assert evaluate("=PMT(0,12,1200)") == -100
    assert evaluate("=PMT(0.05,0,100)") == "#NUM!"
    assert close(evaluate("=FV(0.06/12,10,-200,-500,1)"), 2581.403374)  # Excel's own FV example
    assert close(evaluate("=FV(0,10,-100)"), 1000)
    assert close(evaluate("=PV(0.08/12,12*20,500,0,0)"), -59777.145851)  # Excel's own PV example
    assert close(evaluate("=PV(0,10,-100)"), 1000)


def test_npv_and_irr_read_the_cash_flows_in_their_order():
    flows = {(0, 0): -70000, (1, 0): 12000, (2, 0): 15000, (3, 0): 18000, (4, 0): 21000, (5, 0): 26000}
    assert close(evaluate("=IRR(A1:A5)", flows), -0.021245, 6)  # Excel's own IRR example
    assert close(evaluate("=IRR(A1:A6)", flows), 0.086631, 6)
    assert close(evaluate("=IRR(A1:A3,-0.1)", flows), -0.443507, 6)
    npv_cells = {(0, 0): 10000, (1, 0): 3000, (2, 0): 4200, (3, 0): 6800}
    assert close(evaluate("=NPV(0.1,-10000,A2:A4)", npv_cells), 1188.443412)  # Excel's own NPV example


def test_irr_needs_money_in_and_out_and_skips_what_is_not_a_number():
    assert evaluate("=IRR(A1:A3)", {(0, 0): 1, (1, 0): 2, (2, 0): 3}) == "#NUM!"
    assert close(evaluate("=IRR(A1:A4)", {(0, 0): -100, (1, 0): "note", (2, 0): 60, (3, 0): 60}), 0.130662, 6)
    assert evaluate("=NPV(-1,A1)", {(0, 0): 5}) == "#DIV/0!"


def test_irr_finds_a_rate_newton_would_miss():
    flows = {(0, 0): -1000, (1, 0): 0, (2, 0): 0, (3, 0): 0, (4, 0): 0, (5, 0): 20000}
    assert close(evaluate("=IRR(A1:A6,5)", flows), 0.820564, 6)


def test_a_reference_only_asked_where_it_is_is_no_circle():
    # The pattern of the real planning workbook: a running column count that includes the formula's own cell.
    model = WorkbookModel()
    sheet = Sheet(SheetId("s1"), "S")
    model.sheets[sheet.id] = sheet
    sheet.cells[(2, 1)] = {"t": "formula", "v": "=COLUMNS($B$3:B3)+2025"}
    sheet.cells[(2, 2)] = {"t": "formula", "v": "=COLUMNS($B$3:C3)+2025"}
    sheet.cells[(3, 1)] = {"t": "formula", "v": "=ROW(B4)+ROWS((B1:B4))"}
    sheet.cells[(4, 1)] = {"t": "formula", "v": "=ROWS(B1:B5)+SUM(B1:B5)"}  # read as well: still a circle
    model.open_container("s1")
    model._calculate_loaded()  # noqa: SLF001
    assert sheet.grid.get((2, 1)) == 2026
    assert sheet.grid.get((2, 2)) == 2027
    assert sheet.grid.get((3, 1)) == 8
    assert sheet.grid.get((4, 1)).code == "#CIRC!"
