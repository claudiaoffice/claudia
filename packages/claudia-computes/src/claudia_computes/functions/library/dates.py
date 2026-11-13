"""Dates as Excel counts them: a date is a whole number of days, a time of day the fraction of one (D347).

Day 1 is 1 January 1900. Excel counts a 29 February 1900 that never was (day 60), a mistake Lotus 1-2-3 made and
Excel kept so that old files keep their dates; claudia counts it too, so that a date in a file means the same day
here. From 1 March 1900 (day 61) on, the count is the calendar's. The largest date is 31 December 9999 (2,958,465).

A date in a cell is that number; how it is *shown* (``13.11.2026``, ``Nov 2026``) is the cell's number format, not
the value. Text is never read as a date (E6.4): ``YEAR("2026-11-13")`` is ``#VALUE!``.
"""

from __future__ import annotations

import calendar
import datetime as dt
import math

from ...values import NUM
from ..base import Example, FunctionError, UserFunction
from .catalog import builtin

_DAY_ZERO = dt.date(1899, 12, 31)
#: The first day after the 29 February 1900 Excel counts and the calendar does not.
_MARCH_1900 = 61
#: 31 December 9999, the last day Excel shows.
LAST_DAY = 2_958_465


def serial_of(day: dt.date) -> int:
    """The day number of a calendar date (1 January 1900 is 1; from 1 March 1900 on, one more for Excel's 29
    February)."""
    number = (day - _DAY_ZERO).days
    return number + 1 if number >= _MARCH_1900 - 1 else number


def parts_of(serial: float) -> tuple[int, int, int]:
    """Year, month and day of a day number, as Excel shows them: day 0 is 0 January 1900 and day 60 is the 29
    February 1900 Excel counts. ``#NUM!`` for a negative day or one after 31 December 9999."""
    day = math.floor(serial)
    if day < 0 or day > LAST_DAY:
        raise FunctionError(NUM, "a date is a day from 0 to 2,958,465 (31 December 9999)")
    if day == 0:
        return 1900, 1, 0
    if day == _MARCH_1900 - 1:
        return 1900, 2, 29
    date = _DAY_ZERO + dt.timedelta(days=day if day < _MARCH_1900 else day - 1)
    return date.year, date.month, date.day


def date_of(serial: float) -> dt.date:
    """A day number as a calendar date. Day 0 and Excel's 29 February 1900 have none: they are read as the day after
    them, which is what adding months or years to them gives in Excel too."""
    year, month, day = parts_of(serial)
    if day == 0:
        return dt.date(1900, 1, 1)
    if (month, day) == (2, 29) and year == 1900:
        return dt.date(1900, 3, 1)
    return dt.date(year, month, day)


def _checked(serial: int) -> int:
    if serial < 0 or serial > LAST_DAY:
        raise FunctionError(NUM, "the date falls outside 1900 to 9999")
    return serial


def add_months(day: dt.date, months: int) -> dt.date:
    """``day`` moved by whole months; the day of the month is the last one the new month has when it is shorter."""
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    if not 1900 <= year <= 9999:
        raise FunctionError(NUM, "the date falls outside 1900 to 9999")
    return dt.date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


@builtin
class DATE(UserFunction):
    description = "The date of a year, month and day. Months and days beyond their end carry over."
    examples = (Example("=DATE(2026,11,13)", 46339), Example("=DATE(2026,14,1)", 46419), Example("=DATE(26,1,1)", 9498))

    def call(self, year: int, month: int, day: int):
        if 0 <= year < 1900:
            year += 1900
        if not 1900 <= year <= 9999:
            raise FunctionError(NUM, "the year is from 1900 to 9999 (0 to 1899 are counted from 1900)")
        first_year, first_month = divmod(year * 12 + month - 1, 12)
        return _checked(serial_of(dt.date(first_year, first_month + 1, 1)) + day - 1)


@builtin
class YEAR(UserFunction):
    description = "The year of a date."
    examples = (Example("=YEAR(46339)", 2026),)

    def call(self, date: float):
        return parts_of(date)[0]


@builtin
class MONTH(UserFunction):
    description = "The month of a date, 1 to 12."
    examples = (Example("=MONTH(46339)", 11),)

    def call(self, date: float):
        return parts_of(date)[1]


@builtin
class DAY(UserFunction):
    description = "The day of the month of a date, 1 to 31."
    examples = (Example("=DAY(46339)", 13),)

    def call(self, date: float):
        return parts_of(date)[2]


@builtin
class EDATE(UserFunction):
    description = "The date a number of months before or after a date, on the same day of the month where it has one."
    examples = (Example("=EDATE(46326,1)", 46356, note="31 Oct 2026 + 1 month = 30 Nov 2026"),)

    def call(self, start: float, months: int):
        return _checked(serial_of(add_months(date_of(start), months)))


@builtin
class EOMONTH(UserFunction):
    description = "The last day of the month a number of months before or after a date."
    examples = (Example("=EOMONTH(46339,0)", 46356), Example("=EOMONTH(46339,-1)", 46326))

    def call(self, start: float, months: int):
        moved = add_months(date_of(start).replace(day=1), months)
        return _checked(serial_of(moved.replace(day=calendar.monthrange(moved.year, moved.month)[1])))


@builtin
class DAYS(UserFunction):
    description = "The number of days from the start date to the end date."
    examples = (Example("=DAYS(46387,46339)", 48),)

    def call(self, end: float, start: float):
        parts_of(end), parts_of(start)
        return math.floor(end) - math.floor(start)


@builtin
class WEEKDAY(UserFunction):
    description = "The day of the week of a date: 1 (Sunday) to 7, or as the second argument counts (2: Monday is 1)."
    examples = (Example("=WEEKDAY(46339)", 6, note="13 Nov 2026 is a Friday"), Example("=WEEKDAY(46339,2)", 5))

    _FIRST = {1: 6, 2: 0, 3: 0, 11: 0, 12: 1, 13: 2, 14: 3, 15: 4, 16: 5, 17: 6}  # the weekday (Monday 0) counted as 1

    def call(self, date: float, counting: int = 1):
        first = self._FIRST.get(counting)
        if first is None:
            raise FunctionError(NUM, "the counting is 1, 2, 3 or 11 to 17")
        weekday = date_of(date).weekday() if math.floor(date) >= _MARCH_1900 else (math.floor(date) + 5) % 7
        number = (weekday - first) % 7
        return number if counting == 3 else number + 1


@builtin
class DATEDIF(UserFunction):
    description = (
        'The time between two dates in whole years ("Y"), months ("M") or days ("D"), '
        'or what is left over ("MD", "YM", "YD").'
    )
    examples = (
        Example('=DATEDIF(45658,46339,"Y")', 1, note="1 Jan 2025 to 13 Nov 2026"),
        Example('=DATEDIF(45658,46339,"M")', 22),
        Example('=DATEDIF(45658,46339,"YD")', 316),
    )

    def call(self, start: float, end: float, unit: str):
        if math.floor(start) > math.floor(end):
            raise FunctionError(NUM, "the start date comes after the end date")
        first, last = date_of(start), date_of(end)
        months = (last.year - first.year) * 12 + last.month - first.month - (last.day < first.day)
        unit = unit.strip().upper()
        if unit == "Y":
            return months // 12
        if unit == "M":
            return months
        if unit == "D":
            return math.floor(end) - math.floor(start)
        if unit == "YM":
            return months % 12
        if unit == "MD":
            back = add_months(first, months) if months else first
            return (last - back).days
        if unit == "YD":
            years = months // 12
            back = add_months(first, years * 12)
            return (last - back).days
        raise FunctionError(NUM, 'the unit is "Y", "M", "D", "MD", "YM" or "YD"')
