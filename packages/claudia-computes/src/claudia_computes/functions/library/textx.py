"""More text functions: CONCATENATE, character codes, CLEAN, NUMBERVALUE, DOLLAR and FIXED, REPLACE, TEXTBEFORE,
TEXTAFTER and TEXTSPLIT.

``CHAR`` and ``CODE`` use the Windows-1252 character set Excel uses (``CHAR(128)`` is the euro sign); ``UNICHAR`` and
``UNICODE`` use code points. ``DOLLAR`` writes a dollar sign and the separators of English: it does not follow the
language of the person (number formats do: ``TEXT``).
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from ...values import NA, VALUE, ErrorValue, format_value
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .arrays import matrix
from .catalog import builtin

_WINDOWS_1252_HOLES = {129, 141, 143, 144, 157}  # (bytes cp1252 leaves undefined: they are the Latin-1 characters)


def _joined(texts: tuple[str, ...]) -> str:
    return "".join(texts)


@builtin
class CONCATENATE(UserFunction):
    description = "Joins texts, numbers and TRUE/FALSE into one text (one value each: CONCAT takes ranges)."
    examples = (Example('=CONCATENATE("a", "b", 1)', "ab1"),)

    def call(self, *texts: str):
        return _joined(texts)


@builtin
class CHAR(UserFunction):
    description = "The character with a code from 1 to 255 (the Windows-1252 set: 65 is A, 128 the euro sign)."
    examples = (Example("=CHAR(65)", "A"),)

    def call(self, code: int):
        if not 1 <= code <= 255:
            raise FunctionError(VALUE, "a character code is from 1 to 255")
        if code in _WINDOWS_1252_HOLES:
            return chr(code)
        return bytes([code]).decode("cp1252")


@builtin
class CODE(UserFunction):
    description = "The code of the first character of a text (the Windows-1252 set; 63 for one it does not have)."
    examples = (Example('=CODE("A")', 65),)

    def call(self, text: str):
        if not text:
            raise FunctionError(VALUE, "there is no character")
        try:
            return text[0].encode("cp1252")[0]
        except UnicodeEncodeError:
            return 63 if ord(text[0]) > 255 else ord(text[0])


@builtin
class UNICHAR(UserFunction):
    description = "The character with a Unicode code point."
    examples = (Example("=UNICHAR(8364)", "€"),)

    def call(self, number: int):
        if number < 1 or number > 0x10FFFF or 0xD800 <= number <= 0xDFFF:
            raise FunctionError(VALUE, "this is not the code of a character")
        return chr(number)


@builtin
class UNICODE(UserFunction):
    description = "The Unicode code point of the first character of a text."
    examples = (Example('=UNICODE("€")', 8364),)

    def call(self, text: str):
        if not text:
            raise FunctionError(VALUE, "there is no character")
        return ord(text[0])


@builtin
class CLEAN(UserFunction):
    description = "Removes the characters that cannot be printed (codes 0 to 31) from a text."
    examples = (Example('=CLEAN("a" & CHAR(7) & "b")', "ab"),)

    def call(self, text: str):
        return "".join(char for char in text if ord(char) >= 32)


@builtin
class NUMBERVALUE(UserFunction):
    description = (
        "A text as a number with the decimal and group separators you name (. and , unless given); spaces are "
        "ignored and each % divides by 100."
    )
    examples = (Example('=NUMBERVALUE("2.500,27", ",", ".")', 2500.27), Example('=NUMBERVALUE("3.5%")', 0.035))

    def call(self, text: str, decimal_separator: str | None = None, group_separator: str | None = None):
        decimal = (decimal_separator or ".")[:1]
        group = (group_separator or ",")[:1]
        if decimal == group:
            raise FunctionError(VALUE, "the decimal and the group separator must differ")
        cleaned = re.sub(r"\s", "", text)
        percents = len(cleaned) - len(cleaned.rstrip("%"))
        cleaned = cleaned.rstrip("%")
        if not cleaned:
            return 0
        whole, point, fraction = cleaned.partition(decimal)
        if group in fraction or decimal in fraction:
            raise FunctionError(VALUE, "the group separator comes after the decimal separator")
        whole = whole.replace(group, "")
        number = whole + ("." + fraction if point else "")
        if not re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", number):
            raise FunctionError(VALUE, f"{text!r} is not a number")
        result = Decimal(number)
        for _ in range(percents):
            result /= 100
        value = float(result)
        return int(value) if value.is_integer() and abs(value) < 2**53 and "." not in number and not percents else value


def _fixed(number: float, decimals: int, commas: bool) -> str:
    quantum = Decimal(1).scaleb(-decimals)
    rounded = Decimal(repr(number)).quantize(quantum, rounding=ROUND_HALF_UP) if abs(decimals) <= 100 else None
    if rounded is None:
        raise FunctionError(VALUE, "too many decimals")
    places = max(decimals, 0)
    text = f"{abs(rounded):,.{places}f}" if commas else f"{abs(rounded):.{places}f}"
    return ("-" if rounded < 0 else "") + text


@builtin
class FIXED(UserFunction):
    description = (
        "A number as text rounded to a number of decimals (2 unless given), with thousands separators unless no_commas "
        "is TRUE."
    )
    examples = (Example("=FIXED(1234.567, 1)", "1,234.6"),)

    def call(self, number: float, decimals: int = 2, no_commas: bool = False):
        return _fixed(number, decimals, not no_commas)


@builtin
class DOLLAR(UserFunction):
    description = "A number as text with a dollar sign, rounded to a number of decimals (2 unless given)."
    examples = (Example("=DOLLAR(1234.567)", "$1,234.57"),)

    def call(self, number: float, decimals: int = 2):
        text = _fixed(number, decimals, True)
        return "-$" + text[1:] if text.startswith("-") else "$" + text


@builtin
class REPLACE(UserFunction):
    description = "Replaces a number of characters of a text, from a position, with other text."
    examples = (Example('=REPLACE("abcdefghijk", 6, 5, "*")', "abcde*k"),)

    def call(self, old_text: str, start: int, count: int, new_text: str):
        if start < 1 or count < 0:
            raise FunctionError(VALUE, "the start is 1 or more and the count 0 or more")
        return old_text[: start - 1] + new_text + old_text[start - 1 + count :]


# -- before and after a delimiter ------------------------------------------------------------------------------------
def _occurrences(text: str, delimiter: str, ignore_case: bool) -> list[tuple[int, int]]:
    """Where ``delimiter`` occurs in ``text`` without overlapping: (start, end) pairs, from the left."""
    haystack, needle = (text.casefold(), delimiter.casefold()) if ignore_case else (text, delimiter)
    if len(haystack) != len(text):  # (case folding changed the length, as ß does: compare without it)
        haystack, needle = text.lower(), delimiter.lower()
    found, at = [], 0
    while (index := haystack.find(needle, at)) >= 0:
        found.append((index, index + len(needle)))
        at = index + len(needle)
    return found


def _cut(text, delimiter, instance, ignore_case, match_end, if_not_found, *, before: bool):
    if instance == 0 or abs(instance) > max(len(text), 1):
        raise FunctionError(VALUE, "the instance is a number from 1 (or -1 from the end) up to the length of the text")
    if delimiter == "":
        return "" if before else text
    spans = _occurrences(text, delimiter, bool(ignore_case))
    if match_end:  # (the end of the text counts as one more delimiter: the last one, so the first met from the end)
        spans = [*spans, (len(text), len(text))]
    count = len(spans)
    if abs(instance) > count:
        if if_not_found is None:
            raise FunctionError(NA, "the delimiter is not in the text")
        return if_not_found
    start, end = spans[instance - 1] if instance > 0 else spans[count + instance]
    return text[:start] if before else text[end:]


@builtin
class TEXTBEFORE(UserFunction):
    description = (
        "The text before a delimiter: before its nth occurrence (negative: counted from the end); match_mode 1 ignores "
        "case, match_end 1 counts the end of the text as a delimiter; if_not_found is given when it is not there "
        "(else #N/A)."
    )
    examples = (Example('=TEXTBEFORE("a-b-c", "-", -1)', "a-b"),)

    def call(
        self,
        text: str,
        delimiter: str,
        instance: int | None = None,
        match_mode: int = 0,
        match_end: int = 0,
        if_not_found=None,
    ):
        return _cut(
            text, delimiter, 1 if instance is None else instance, match_mode, match_end, if_not_found, before=True
        )


@builtin
class TEXTAFTER(UserFunction):
    description = (
        "The text after a delimiter: after its nth occurrence (negative: counted from the end); match_mode 1 ignores "
        "case, match_end 1 counts the end of the text as a delimiter; if_not_found is given when it is not there "
        "(else #N/A)."
    )
    examples = (Example('=TEXTAFTER("a-b-c", "-", -1)', "c"),)

    def call(
        self,
        text: str,
        delimiter: str,
        instance: int | None = None,
        match_mode: int = 0,
        match_end: int = 0,
        if_not_found=None,
    ):
        return _cut(
            text, delimiter, 1 if instance is None else instance, match_mode, match_end, if_not_found, before=False
        )


# -- splitting ------------------------------------------------------------------------------------------------------
def _delimiters(area: Range | None) -> list[str]:
    if area is None:
        return []
    found = [format_value(v) for v in area.present()]
    if any(d == "" for d in found):
        raise FunctionError(VALUE, "a delimiter cannot be empty")
    return found


def _splitter(delimiters: list[str], ignore_case: bool) -> re.Pattern[str]:
    longest_first = sorted(delimiters, key=len, reverse=True)
    return re.compile("|".join(re.escape(d) for d in longest_first), re.IGNORECASE if ignore_case else 0)


@builtin
class TEXTSPLIT(UserFunction):
    description = (
        "Splits a text into columns at the column delimiters and into rows at the row delimiters (each may be several "
        "in a range). ignore_empty TRUE drops empty pieces, match_mode 1 ignores case; shorter rows are filled with "
        "pad_with (#N/A)."
    )
    examples = (Example('=INDEX(TEXTSPLIT("a,b;c,d", ",", ";"), 2, 2)', "d"),)

    def call(
        self,
        text: str,
        col_delimiter: Range | None = None,
        row_delimiter: Range | None = None,
        ignore_empty: bool = False,
        match_mode: int = 0,
        pad_with=None,
    ):
        cols, rows = _delimiters(col_delimiter), _delimiters(row_delimiter)
        if not cols and not rows:
            raise FunctionError(VALUE, "give a delimiter for the columns or for the rows")
        ignore_case = bool(match_mode)
        lines = _splitter(rows, ignore_case).split(text) if rows else [text]
        table = [(_splitter(cols, ignore_case).split(line) if cols else [line]) for line in lines]
        if ignore_empty:
            table = [[piece for piece in line if piece != ""] for line in table]
            table = [line for line in table if line]
            if not table:
                raise FunctionError(NA, "nothing is left of the text")
        width = max(len(line) for line in table)
        pad = ErrorValue(NA) if pad_with is None else pad_with
        return matrix([line + [pad] * (width - len(line)) for line in table])
