"""Weeks, working days, times of day and the fractions of years between dates (see ``dates`` for how dates count).

``DATEVALUE`` and ``TIMEVALUE`` are the only functions that read a date from text, and they read only the forms
named in their description (E6.4 keeps text from being taken for a date anywhere else)."""

from __future__ import annotations

import calendar
import datetime as dt
import math
import re

from ...values import NUM, VALUE
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .catalog import builtin
from .dates import date_of, parts_of, serial_of

_SECONDS = 86400
_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name}
_MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_name) if name})


def _monday_based(serial: int) -> int:
    """The weekday of a day number, Monday 0 (day 1, 1 January 1900, is a Sunday in Excel's count)."""
    return (serial + 5) % 7


# -- weeks --------------------------------------------------------------------------------------------------------------
_WEEK_STARTS = {1: 6, 2: 0, 11: 0, 12: 1, 13: 2, 14: 3, 15: 4, 16: 5, 17: 6}


@builtin
class WEEKNUM(UserFunction):
    description = "The number of the week of the year a date is in; the week with 1 January is week 1. The second argument says which day a week starts on (1 Sunday, 2 Monday, 11 to 17 Monday to Sunday, 21 ISO weeks)."
    examples = (Example("=WEEKNUM(46339)", 46), Example("=WEEKNUM(46339,2)", 46), Example("=WEEKNUM(46391,21)", 1, note="4 Jan 2027, a Monday"))

    def call(self, date: float, starting: int = 1):
        if starting == 21:
            return date_of(date).isocalendar()[1]
        first = _WEEK_STARTS.get(starting)
        if first is None:
            raise FunctionError(NUM, "the week starts on 1, 2, 11 to 17, or 21 counts ISO weeks")
        day = math.floor(date)
        year = parts_of(day)[0]
        january = serial_of(dt.date(year, 1, 1))
        offset = (_monday_based(january) - first) % 7
        return (day - january + offset) // 7 + 1


@builtin
class ISOWEEKNUM(UserFunction):
    description = "The ISO week number of a date: weeks start on Monday and week 1 is the one with the first Thursday."
    examples = (Example("=ISOWEEKNUM(46339)", 46), Example("=ISOWEEKNUM(46387)", 53, note="31 Dec 2026: 2026 has 53 ISO weeks"))

    def call(self, date: float):
        return date_of(date).isocalendar()[1]


# -- working days --------------------------------------------------------------------------------------------------------
_WEEKEND_CODES = {1: (5, 6), 2: (6, 0), 3: (0, 1), 4: (1, 2), 5: (2, 3), 6: (3, 4), 7: (4, 5)}


def _weekend(spec: Range | None) -> frozenset[int]:
    """The days (Monday 0) that are not working days, from a weekend code (1 to 7, 11 to 17) or a text of seven 0 and 1,
    Monday first, a 1 for a day off."""
    value = None if spec is None else spec.at(0, 0)
    if value is None:
        return frozenset({5, 6})
    if isinstance(value, str):
        if not re.fullmatch(r"[01]{7}", value) or value == "1" * 7:
            raise FunctionError(VALUE, "the weekend is a code or seven 0 and 1 that are not all 1")
        return frozenset(i for i, c in enumerate(value) if c == "1")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        code = int(value)
        if code in _WEEKEND_CODES:
            return frozenset(_WEEKEND_CODES[code])
        if 11 <= code <= 17:
            return frozenset({(code - 5) % 7})
    raise FunctionError(NUM, "the weekend is 1 to 7, 11 to 17, or text of seven 0 and 1")


def _holidays(holidays: Range | None) -> frozenset[int]:
    return frozenset() if holidays is None else frozenset(math.floor(n) for n in holidays.numbers())


def _working(day: int, off: frozenset[int], holidays: frozenset[int]) -> bool:
    return _monday_based(day) not in off and day not in holidays


def _networkdays(start: float, end: float, off: frozenset[int], holidays: frozenset[int]) -> int:
    parts_of(start), parts_of(end)
    first, last = math.floor(start), math.floor(end)
    sign = 1
    if first > last:
        first, last, sign = last, first, -1
    count = sum(1 for day in range(first, last + 1) if _working(day, off, holidays))
    return sign * count


def _workday(start: float, days: float, off: frozenset[int], holidays: frozenset[int]) -> int:
    parts_of(start)
    if len(off) == 7:
        raise FunctionError(VALUE, "every day is a day off")
    step = 1 if days >= 0 else -1
    remaining = abs(int(days))
    day = math.floor(start)
    if remaining > 1_000_000:
        raise FunctionError(NUM, "that is too many days")
    while remaining:
        day += step
        if day < 0 or day > 2_958_465:
            raise FunctionError(NUM, "the date falls outside 1900 to 9999")
        if _working(day, off, holidays):
            remaining -= 1
    return day


@builtin
class NETWORKDAYS(UserFunction):
    description = "The number of working days (not Saturday or Sunday, not a holiday) from the start date to the end date, both included."
    examples = (Example("=NETWORKDAYS(46332,46339)", 6, note="6 Nov to 13 Nov 2026"), Example("=NETWORKDAYS(46339,46332)", -6))

    def call(self, start_date: float, end_date: float, holidays: Range | None = None):
        return _networkdays(start_date, end_date, frozenset({5, 6}), _holidays(holidays))


@builtin
class NETWORKDAYS_INTL(UserFunction):
    name = "NETWORKDAYS.INTL"
    description = "The number of working days between two dates, both included, with a choice of weekend: a code (1 Saturday and Sunday, 2 Sunday and Monday ... 7 Friday and Saturday, 11 to 17 one day) or seven 0 and 1 for Monday to Sunday."
    examples = (Example("=NETWORKDAYS.INTL(46332,46339,11)", 7, note="only Sunday is off"), Example('=NETWORKDAYS.INTL(46332,46339,"0000011")', 6))

    def call(self, start_date: float, end_date: float, weekend: Range | None = None, holidays: Range | None = None):
        return _networkdays(start_date, end_date, _weekend(weekend), _holidays(holidays))


@builtin
class WORKDAY(UserFunction):
    description = "The date a number of working days (not Saturday or Sunday, not a holiday) after, or before if negative, a date."
    examples = (Example("=WORKDAY(46339,1)", 46342, note="Friday 13 Nov 2026 + 1 = Monday 16 Nov"), Example("=WORKDAY(46339,-5)", 46332))

    def call(self, start_date: float, days: float, holidays: Range | None = None):
        return _workday(start_date, days, frozenset({5, 6}), _holidays(holidays))


@builtin
class WORKDAY_INTL(UserFunction):
    name = "WORKDAY.INTL"
    description = "The date a number of working days after, or before if negative, a date, with a choice of weekend (see NETWORKDAYS.INTL)."
    examples = (Example("=WORKDAY.INTL(46339,1,11)", 46340, note="only Sunday is off: Saturday is a workday"),)

    def call(self, start_date: float, days: float, weekend: Range | None = None, holidays: Range | None = None):
        return _workday(start_date, days, _weekend(weekend), _holidays(holidays))


# -- times of day ---------------------------------------------------------------------------------------------------------
def _seconds_of(serial: float) -> int:
    if serial < 0:
        raise FunctionError(NUM, "a time cannot be negative")
    return round((serial - math.floor(serial)) * _SECONDS) % _SECONDS


@builtin
class HOUR(UserFunction):
    description = "The hour, 0 to 23, of a time (or of a date with a time)."
    examples = (Example("=HOUR(0.75)", 18), Example("=HOUR(46339.5208333333)", 12))

    def call(self, serial_number: float):
        return _seconds_of(serial_number) // 3600


@builtin
class MINUTE(UserFunction):
    description = "The minute, 0 to 59, of a time."
    examples = (Example("=MINUTE(0.7604166667)", 15),)

    def call(self, serial_number: float):
        return _seconds_of(serial_number) // 60 % 60


@builtin
class SECOND(UserFunction):
    description = "The second, 0 to 59, of a time."
    examples = (Example("=SECOND(0.0007523148)", 5),)

    def call(self, serial_number: float):
        return _seconds_of(serial_number) % 60


@builtin
class TIME(UserFunction):
    description = "The time of day (a fraction of a day) of an hour, minute and second. More than 24 hours wrap around to the next day."
    examples = (Example("=TIME(12,0,0)", 0.5), Example("=TIME(18,0,0)", 0.75), Example("=TIME(25,0,0)", 1 / 24))

    def call(self, hour: int, minute: int, second: int):
        if not 0 <= hour <= 32767 or not 0 <= minute <= 32767 or not 0 <= second <= 32767:
            raise FunctionError(NUM, "hour, minute and second are from 0 to 32767")
        return ((hour * 3600 + minute * 60 + second) % _SECONDS) / _SECONDS


# -- reading dates and times from text ---------------------------------------------------------------------------------------
_ISO = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")
_DAY_MONTH = re.compile(r"(\d{1,2})[ \-]([A-Za-z]+)\.?,?[ \-](\d{4})")
_MONTH_DAY = re.compile(r"([A-Za-z]+)\.? (\d{1,2}),? (\d{4})")


def _read_date(text: str) -> dt.date:
    text = text.strip()
    try:
        if m := _ISO.fullmatch(text):
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        if m := _DAY_MONTH.fullmatch(text):
            return dt.date(int(m[3]), _MONTHS[m[2].lower()], int(m[1]))
        if m := _MONTH_DAY.fullmatch(text):
            return dt.date(int(m[3]), _MONTHS[m[1].lower()], int(m[2]))
    except (KeyError, ValueError):
        pass
    raise FunctionError(VALUE, "this is not a date claudia can read: use 2026-11-13, 13 Nov 2026 or Nov 13, 2026")


@builtin
class DATEVALUE(UserFunction):
    description = "The date a text names, as a day number. Read: 2026-11-13, 2026/11/13, 13 Nov 2026, 13-Nov-2026 and Nov 13, 2026 (a time after the date is ignored)."
    examples = (Example('=DATEVALUE("2026-11-13")', 46339), Example('=DATEVALUE("13 Nov 2026")', 46339), Example('=DATEVALUE("November 13, 2026")', 46339))

    def call(self, date_text: str):
        text = date_text.strip()
        if re.match(r"\d{4}[-/]", text):
            text = re.split(r"[T ]", text, maxsplit=1)[0]  # (a time after an ISO date is left out)
        return serial_of(_read_date(text))


_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?\s*([AaPp][Mm])?")


@builtin
class TIMEVALUE(UserFunction):
    description = "The time of day a text names, as a fraction of a day. Read: 14:30, 14:30:15, 2:30 PM; a date before the time is ignored."
    examples = (Example('=TIMEVALUE("12:00")', 0.5), Example('=TIMEVALUE("6:00 PM")', 0.75))

    def call(self, time_text: str):
        m = _TIME.search(time_text.strip())
        if not m:
            raise FunctionError(VALUE, "this is not a time claudia can read: use 14:30, 14:30:15 or 2:30 PM")
        hour, minute, second, meridiem = int(m[1]), int(m[2]), int(m[3] or 0), (m[4] or "").lower()
        if meridiem:
            if not 1 <= hour <= 12:
                raise FunctionError(VALUE, "with AM or PM the hour is 1 to 12")
            hour = hour % 12 + (12 if meridiem == "pm" else 0)
        if hour > 23 or minute > 59 or second > 59:
            raise FunctionError(VALUE, "this is not a time")
        return (hour * 3600 + minute * 60 + second) / _SECONDS


# -- year fractions ---------------------------------------------------------------------------------------------------------------
def _is_last_of_february(day: dt.date) -> bool:
    return day.month == 2 and day.day == calendar.monthrange(day.year, 2)[1]


def _days360(first: dt.date, last: dt.date, *, european: bool) -> int:
    d1, d2 = first.day, last.day
    if european:
        d1, d2 = min(d1, 30), min(d2, 30)
    else:
        if _is_last_of_february(first) or d1 == 31:
            d1 = 30
        if d2 == 31 and d1 == 30:
            d2 = 30
    return 360 * (last.year - first.year) + 30 * (last.month - first.month) + (d2 - d1)


def _nasd(first: dt.date, last: dt.date) -> int:
    """30/360 as ``YEARFRAC`` basis 0 counts it (the end of February counts as 30 on both ends)."""
    d1, d2 = first.day, last.day
    if _is_last_of_february(first) and _is_last_of_february(last):
        d2 = 30
    if _is_last_of_february(first):
        d1 = 30
    if d2 == 31 and d1 >= 30:
        d2 = 30
    if d1 == 31:
        d1 = 30
    return 360 * (last.year - first.year) + 30 * (last.month - first.month) + (d2 - d1)


def _leap_day_between(first: dt.date, last: dt.date) -> bool:
    return any(
        calendar.isleap(year) and first <= dt.date(year, 2, 29) <= last for year in range(first.year, last.year + 1)
    )


def _actual_year_length(first: dt.date, last: dt.date) -> float:
    if first.year == last.year:
        return 366 if calendar.isleap(first.year) else 365
    within_a_year = last.year == first.year + 1 and (last.month, last.day) <= (first.month, first.day)
    if within_a_year:
        return 366 if _leap_day_between(first, last) else 365
    years = range(first.year, last.year + 1)
    return sum(366 if calendar.isleap(y) else 365 for y in years) / len(years)


@builtin
class YEARFRAC(UserFunction):
    description = "The part of a year between two dates. Basis: 0 (default) US 30/360, 1 actual days over actual year, 2 actual/360, 3 actual/365, 4 European 30/360."
    examples = (Example("=ROUND(YEARFRAC(40909,41120),4)", 0.5806, note="1 Jan to 30 Jul 2012, 30/360"), Example("=ROUND(YEARFRAC(40909,41120,1),4)", 0.5765))

    def call(self, start_date: float, end_date: float, basis: int = 0):
        first, last = sorted((math.floor(start_date), math.floor(end_date)))
        a, b = date_of(first), date_of(last)
        if basis == 0:
            return _nasd(a, b) / 360
        if basis == 1:
            return (last - first) / _actual_year_length(a, b)
        if basis == 2:
            return (last - first) / 360
        if basis == 3:
            return (last - first) / 365
        if basis == 4:
            return _days360(a, b, european=True) / 360
        raise FunctionError(NUM, "the basis is 0 to 4")


@builtin
class DAYS360(UserFunction):
    description = "The number of days between two dates in a year of twelve 30-day months; the third argument TRUE counts European style."
    examples = (Example("=DAYS360(39812,39844)", 30, note="30 Dec 2008 to 31 Jan 2009"), Example("=DAYS360(45688,45716)", 28, note="31 Jan to 28 Feb 2025"))

    def call(self, start_date: float, end_date: float, method: bool = False):
        parts_of(start_date), parts_of(end_date)
        return _days360(date_of(start_date), date_of(end_date), european=method)
