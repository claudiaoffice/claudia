"""Functions of text. Positions count from 1, as in a spreadsheet."""

from __future__ import annotations

import math

from ...numformats import check_code, render
from ...values import VALUE, ErrorValue, format_value
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .catalog import builtin

MAX_TEXT = 32_767  # as long as a cell may be: REPT cannot be used to fill the server's memory


def _count(n: int) -> int:
    if n < 0:
        raise FunctionError(VALUE, "this needs a number of 0 or more")
    return n


def _pieces(ranges: tuple[Range, ...]) -> list[str]:
    pieces = []
    for area in ranges:
        for _, _, value in area.cells():
            if value.__class__ is ErrorValue:
                raise value.raised()
            pieces.append(format_value(value))
    return pieces


@builtin
class LEN(UserFunction):
    description = "The number of characters of the text."
    examples = (Example('=LEN("hello")', 5),)

    def call(self, text: str):
        return len(text)


@builtin
class LEFT(UserFunction):
    description = "The first characters of the text (one unless a number is given)."
    examples = (Example('=LEFT("hello", 2)', "he"),)

    def call(self, text: str, count: int = 1):
        return text[: _count(count)]


@builtin
class RIGHT(UserFunction):
    description = "The last characters of the text (one unless a number is given)."
    examples = (Example('=RIGHT("hello", 3)', "llo"),)

    def call(self, text: str, count: int = 1):
        count = _count(count)
        return text[-count:] if count else ""


@builtin
class MID(UserFunction):
    description = "Characters from the middle of the text: where to start (from 1) and how many."
    examples = (Example('=MID("hello", 2, 3)', "ell"),)

    def call(self, text: str, start: int, count: int):
        if start < 1:
            raise FunctionError(VALUE, "the start counts from 1")
        return text[start - 1 : start - 1 + _count(count)]


@builtin
class UPPER(UserFunction):
    description = "The text in capital letters."
    examples = (Example('=UPPER("abc")', "ABC"),)

    def call(self, text: str):
        return text.upper()


@builtin
class LOWER(UserFunction):
    description = "The text in small letters."
    examples = (Example('=LOWER("ABC")', "abc"),)

    def call(self, text: str):
        return text.lower()


@builtin
class PROPER(UserFunction):
    description = "The first letter of every word in a capital, the others small."
    examples = (Example('=PROPER("hello wORLD")', "Hello World"),)

    def call(self, text: str):
        return text.title()


@builtin
class TRIM(UserFunction):
    description = "Removes spaces at both ends and reduces the ones between words to one."
    examples = (Example('=TRIM("  a   b ")', "a b"),)

    def call(self, text: str):
        return " ".join(part for part in text.split(" ") if part)


@builtin
class CONCAT(UserFunction):
    description = "Joins the text of all values and ranges (ranges row by row, empty cells skipped)."
    examples = (Example("=CONCAT(A1:A3)", "ab1", {"A1": "a", "A2": "b", "A3": 1}),)

    def call(self, *values: Range):
        joined = "".join(_pieces(values))
        if len(joined) > MAX_TEXT:
            raise FunctionError(VALUE, "the text would be too long")
        return joined


@builtin
class TEXTJOIN(UserFunction):
    description = (
        "Joins values and ranges with a delimiter between them; empty ones are left out if the second argument is TRUE."
    )
    examples = (Example('=TEXTJOIN(", ", TRUE, A1:A3)', "a, b", {"A1": "a", "A3": "b"}),)

    def call(self, delimiter: str, ignore_empty: bool, *values: Range):
        if ignore_empty:
            pieces = [p for p in _pieces(values) if p != ""]
        else:
            pieces = []
            for area in values:
                pieces.extend(format_value(v) for row in area.dense() for v in row)
        joined = delimiter.join(pieces)
        if len(joined) > MAX_TEXT:
            raise FunctionError(VALUE, "the text would be too long")
        return joined


@builtin
class REPT(UserFunction):
    description = "The text repeated a number of times."
    examples = (Example('=REPT("ab", 3)', "ababab"),)

    def call(self, text: str, times: int):
        if len(text) * _count(times) > MAX_TEXT:
            raise FunctionError(VALUE, "the text would be too long")
        return text * times


@builtin
class SUBSTITUTE(UserFunction):
    description = "Replaces old text by new text (all of it, or only the n-th occurrence)."
    examples = (
        Example('=SUBSTITUTE("a-b-c", "-", "+")', "a+b+c"),
        Example('=SUBSTITUTE("a-b-c", "-", "+", 2)', "a-b+c"),
    )

    def call(self, text: str, old: str, new: str, which: int | None = None):
        if old == "":
            return text
        if which is None:
            return text.replace(old, new)
        if which < 1:
            raise FunctionError(VALUE, "the occurrence counts from 1")
        at = -1
        for _ in range(which):
            at = text.find(old, at + 1)
            if at < 0:
                return text
        return text[:at] + new + text[at + len(old) :]


@builtin
class FIND(UserFunction):
    description = "Where the text is found in another text (from 1; capitals matter). #VALUE! if it is not."
    examples = (Example('=FIND("l", "hello")', 3),)

    def call(self, find: str, within: str, start: int = 1):
        if start < 1 or start > len(within) + 1:
            raise FunctionError(VALUE, "the start is outside the text")
        at = within.find(find, start - 1)
        if at < 0:
            raise FunctionError(VALUE, "the text was not found")
        return at + 1


@builtin
class SEARCH(UserFunction):
    description = "Where the text is found in another text (from 1; capitals do not matter). #VALUE! if it is not."
    examples = (Example('=SEARCH("L", "hello")', 3),)

    def call(self, find: str, within: str, start: int = 1):
        if start < 1 or start > len(within) + 1:
            raise FunctionError(VALUE, "the start is outside the text")
        at = within.casefold().find(find.casefold(), start - 1)
        if at < 0:
            raise FunctionError(VALUE, "the text was not found")
        return at + 1


@builtin
class EXACT(UserFunction):
    description = "TRUE if two texts are the same, capitals included."
    examples = (Example('=EXACT("a", "A")', False),)

    def call(self, first: str, second: str):
        return first == second


@builtin
class VALUE_OF(UserFunction):
    name = "VALUE"
    description = 'Reads text as a number ("12.5" gives 12.5); #VALUE! if it is not one.'
    examples = (Example('=VALUE("12.5")', 12.5),)

    def call(self, text: str):
        try:
            return int(text)
        except ValueError:
            pass
        try:
            number = float(text)
        except ValueError:
            number = math.nan
        if not math.isfinite(number):
            raise FunctionError(VALUE, f"{text!r} is not a number")
        return number


@builtin
class TEXT(UserFunction):
    description = 'A number as text, shown through a number format code ("#,##0.00", "dd.mm.yyyy", "0%").'
    examples = (
        Example('=TEXT(1234.5,"#,##0.00")', "1,234.50"),
        Example('=TEXT(46339,"dd.mm.yyyy")', "13.11.2026"),
        Example('=TEXT(0.256,"0.0%")', "25.6%"),
    )

    def call(self, value, code: str):  # noqa: ANN001 (any value: a number, a text, TRUE/FALSE)
        if isinstance(value, Range):
            value = value.at(0, 0)
        if isinstance(value, ErrorValue):
            raise value.raised()
        try:
            check_code(code)
            return render(value, code)
        except ValueError as why:
            raise FunctionError(VALUE, str(why)) from None
