"""Weeks, working days, times of day, dates read from text, and fractions of years.

Day numbers: 46339 is Friday 13 November 2026. Reference values for working days come from a plain calendar count in
Python; WEEKNUM, ISOWEEKNUM, YEARFRAC and DAYS360 examples are from Microsoft's documentation where noted."""

from __future__ import annotations

from datetime import datetime

from excel_helpers import NOW, cases, check, code, column, value

FRIDAY = 46339

WEEKS = (
    ("=WEEKNUM(40977)", 10),  # 9 March 2012 (Microsoft's example)
    ("=WEEKNUM(40977,2)", 11),  # (1 Jan 2012 is a Sunday: a Monday-starting week 2 begins on the 2nd)
    ("=WEEKNUM(46339)", 46),
    ("=WEEKNUM(46023)", 1),  # 1 Jan 2026, a Thursday
    ("=WEEKNUM(46026)", 2),  # Sunday 4 Jan: a new week when weeks start on Sunday ...
    ("=WEEKNUM(46026,2)", 1),  # ... and not when they start on Monday
    ("=WEEKNUM(46026,17)", 2),  # Sunday-starting again, by its other number
    ("=WEEKNUM(46387,21)", 53),
    ("=WEEKNUM(46391,21)", 1),
    ("=WEEKNUM(46339,3)", "#NUM!"),
    ("=WEEKNUM(-1)", "#NUM!"),
    ("=ISOWEEKNUM(40977)", 10),
    ("=ISOWEEKNUM(46387)", 53),  # 31 Dec 2026, a Thursday: 2026 has 53 ISO weeks
    ("=ISOWEEKNUM(46388)", 53),  # 1 Jan 2027 still belongs to week 53
    ("=ISOWEEKNUM(46391)", 1),
    ("=ISOWEEKNUM(46023)", 1),
)


@cases(*WEEKS)
def test_week_numbers(formula, expected, cells):
    check(formula, expected, cells)


HOLIDAYS = column("A1", [41235, 41247, 41295])  # 22 Nov 2012, 4 Dec 2012, 21 Jan 2013
WORKING = (
    ("=NETWORKDAYS(41183,41334)", 110),  # 1 Oct 2012 to 1 Mar 2013, a plain count
    ("=NETWORKDAYS(41183,41334,A1)", 109),
    ("=NETWORKDAYS(41183,41334,A1:A3)", 107),
    ("=NETWORKDAYS(41334,41183)", -110),
    ("=NETWORKDAYS(46339,46339)", 1),  # a Friday
    ("=NETWORKDAYS(46340,46340)", 0),  # a Saturday
    ("=NETWORKDAYS(46332,46339)", 6),
    ("=NETWORKDAYS.INTL(46332,46339)", 6),
    ("=NETWORKDAYS.INTL(46332,46339,1)", 6),
    ("=NETWORKDAYS.INTL(46332,46339,11)", 7),  # only Sunday off
    ("=NETWORKDAYS.INTL(46332,46339,2)", 6),  # Sunday and Monday off
    ("=NETWORKDAYS.INTL(46332,46339,7)", 5),  # Friday and Saturday off
    ('=NETWORKDAYS.INTL(46332,46339,"0000011")', 6),
    ('=NETWORKDAYS.INTL(46332,46339,"1000000")', 7),  # only Monday off
    ('=NETWORKDAYS.INTL(46332,46339,"1111111")', "#VALUE!"),
    ('=NETWORKDAYS.INTL(46332,46339,"00000")', "#VALUE!"),
    ("=NETWORKDAYS.INTL(46332,46339,8)", "#NUM!"),
    ("=WORKDAY(39722,151)", 39933),  # 1 Oct 2008 + 151 working days = 30 Apr 2009
    ("=WORKDAY(46339,1)", 46342),  # Friday -> Monday
    ("=WORKDAY(46339,0)", 46339),
    ("=WORKDAY(46339,-5)", 46332),
    ("=WORKDAY(46340,1)", 46342),  # from a Saturday
    ("=WORKDAY.INTL(46339,1,11)", 46340),  # only Sunday off: the Saturday is a workday
    ("=WORKDAY.INTL(46339,3,11)", 46343),  # Sat, Mon, Tue
    ('=WORKDAY.INTL(46339,1,"1111111")', "#VALUE!"),
    ("=WORKDAY(46339,1,A1)", 46342),  # (a holiday that is not on the way changes nothing)
)


@cases(*[(f, e, HOLIDAYS) for f, e in WORKING])
def test_working_days(formula, expected, cells):
    check(formula, expected, cells)


def test_workday_skips_holidays():
    holidays = column("A1", [39778, 39786, 39834])  # 26 Nov 2008, 4 Dec 2008, 21 Jan 2009
    check("=WORKDAY(39722,151,A1:A3)", 39938, holidays)  # 5 May 2009: three working days later than without
    check("=WORKDAY.INTL(39722,151,1,A1:A3)", 39938, holidays)


def test_workdays_run_the_other_way_and_agree_with_networkdays():
    for days in (1, 7, 20, 100):
        for start in (46335, 46339, 46340, 46341):
            end = value(f"=WORKDAY({start},{days})")
            assert value(f"=NETWORKDAYS({start},{end})") == days + (1 if value(f"=NETWORKDAYS({start},{start})") else 0)


TIMES = (
    ("=HOUR(0.75)", 18),
    ("=MINUTE(0.75)", 0),
    ("=HOUR(TIME(14,30,15))", 14),
    ("=MINUTE(TIME(14,30,15))", 30),
    ("=SECOND(TIME(14,30,15))", 15),
    ("=HOUR(46339.6042)", 14),  # a date with a time: only the time counts
    ("=HOUR(0.999999999)", 0),  # (rounded to the second: midnight)
    ("=SECOND(0.0007523148)", 5),
    ("=HOUR(-1)", "#NUM!"),
    ("=TIME(12,0,0)", 0.5),
    ("=TIME(16,48,10)", 0.7001157407407407),  # Microsoft: 0.700115741
    ("=TIME(27,0,0)", 0.125),  # more than a day wraps (Microsoft)
    ("=TIME(0,750,0)", 0.5208333333333334),
    ("=TIME(0,0,3600)", 1 / 24),
    ("=TIME(0,0,40000)", "#NUM!"),
    ("=TIME(0,0,-1)", "#NUM!"),
    ("=TIME(40000,0,0)", "#NUM!"),
)


@cases(*TIMES)
def test_times_of_day(formula, expected, cells):
    check(formula, expected, cells)


TEXTS = (
    ('=DATEVALUE("2026-11-13")', 46339),
    ('=DATEVALUE("2026/11/13")', 46339),
    ('=DATEVALUE("2026-11-13 14:30:00")', 46339),
    ('=DATEVALUE("2026-11-13T14:30:00")', 46339),
    ('=DATEVALUE("13 Nov 2026")', 46339),
    ('=DATEVALUE("13-Nov-2026")', 46339),
    ('=DATEVALUE("13 November 2026")', 46339),
    ('=DATEVALUE("Nov 13, 2026")', 46339),
    ('=DATEVALUE("November 13, 2026")', 46339),
    ('=DATEVALUE("2026-02-29")', "#VALUE!"),
    ('=DATEVALUE("13 Foo 2026")', "#VALUE!"),
    ('=DATEVALUE("hello")', "#VALUE!"),
    ('=DATEVALUE("")', "#VALUE!"),
    ('=TIMEVALUE("12:00")', 0.5),
    ('=TIMEVALUE("6:00 PM")', 0.75),
    ('=TIMEVALUE("12:00 AM")', 0),
    ('=TIMEVALUE("12:30 PM")', 0.5208333333333334),
    ('=TIMEVALUE("14:30:15")', 0.6043402777777778),
    ('=TIMEVALUE("2026-11-13 14:30:15")', 0.6043402777777778),
    ('=TIMEVALUE("25:00")', "#VALUE!"),
    ('=TIMEVALUE("13:00 PM")', "#VALUE!"),
    ('=TIMEVALUE("noon")', "#VALUE!"),
)


@cases(*TEXTS)
def test_dates_and_times_read_from_text(formula, expected, cells):
    check(formula, expected, cells)


FRACTIONS = (
    ("=YEARFRAC(40909,41120)", 209 / 360),  # 1 Jan to 30 Jul 2012, 30/360 (Microsoft: 0.58055556)
    ("=YEARFRAC(40909,41120,0)", 209 / 360),
    ("=YEARFRAC(40909,41120,1)", 211 / 366),  # (Microsoft: 0.57650273)
    ("=YEARFRAC(40909,41120,2)", 211 / 360),
    ("=YEARFRAC(40909,41120,3)", 211 / 365),
    ("=YEARFRAC(40909,41120,4)", 209 / 360),
    ("=YEARFRAC(41120,40909)", 209 / 360),  # (the order does not matter)
    ("=YEARFRAC(43831,44927,1)", 1096 / 365.25),  # 1 Jan 2020 to 1 Jan 2023: the average of the years 2020-2023
    ("=YEARFRAC(46339,46339)", 0),
    ("=YEARFRAC(40909,41120,5)", "#NUM!"),
    ("=DAYS360(39477,39479)", 1),  # 30 Jan to 1 Feb 2008 (Microsoft)
    ("=DAYS360(39448,39813)", 360),  # 1 Jan to 31 Dec 2008 (Microsoft)
    ("=DAYS360(39812,39844)", 30),  # 30 Dec 2008 to 31 Jan 2009: the 31st counts as the 30th
    ("=DAYS360(45688,45716)", 28),  # 31 Jan to 28 Feb 2025
    ("=DAYS360(45688,45716,TRUE)", 28),
    ("=DAYS360(39477,39478)", 0),  # 30 Jan to 31 Jan: both are the 30th
    ("=DAYS360(39813,39448)", -359),  # (not the opposite of 360: Dec 31 is the 30th only at the start)
)


@cases(*FRACTIONS)
def test_year_fractions_and_thirty_day_months(formula, expected, cells):
    check(formula, expected, cells)


def test_us_and_european_thirty_day_months_differ_at_the_end_of_a_month():
    # 30 Jan 2008 -> 31 Mar 2008: the US way makes the 31st a 30th only when the start is on the 30th or 31st
    check("=DAYS360(39477,39538)", 60)
    check("=DAYS360(39477,39538,TRUE)", 60)
    # 15 Jan -> 31 Jan 2008: US keeps the 31, European makes it the 30th
    check("=DAYS360(39462,39477+1)", 16)
    check("=DAYS360(39462,39478,TRUE)", 15)


def test_today_and_now_read_the_clock():
    check("=TODAY()", 46339)
    check("=NOW()", 46339 + (14 * 3600 + 30 * 60 + 15) / 86400)
    check("=TODAY()", 46339 + 1, now=datetime(2026, 11, 14, 0, 0, 1))
    check("=NOW()-TODAY()", 0.5, now=datetime(2026, 11, 14, 12, 0, 0))
    check("=HOUR(NOW())", 14)
    check("=MINUTE(NOW())", 30)
    check("=SECOND(NOW())", 15)
    check("=WEEKDAY(TODAY())", 6)  # a Friday
    assert code("=TODAY(1)") == "#VALUE!"
    assert code("=NOW(1)") == "#VALUE!"
    assert NOW.year == 2026
