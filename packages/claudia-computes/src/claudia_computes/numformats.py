"""Named number formats: how a number in a cell is shown, never what it is (E6.14, D75, D348).

A **number format** is a name, Excel's format code (``#,##0.00 "MWh"``, ``dd.mm.yyyy``, ``0.0%``) and, like a style
made by deviating, a flag that it still has the provisional name the import gave it (``to_name``). A workbook keeps
its formats in a :class:`NumberFormatBook`; a cell style names one (``StyleDef.number_format``), and a cell shows its
number through the format of its words' style.

The code is Excel's on purpose: it is what xlsx files hold, what ods number styles translate to and from, and what
people who know spreadsheets can read. The *look* follows the reader's locale -- the decimal comma, the thousands
separator, the names of months -- while the stored value never changes. Rendering for the grid is done by the client
(``web/app/lib/number-format.ts``); :func:`render` is the same algorithm here, for ``TEXT()`` and for tests, and both
are checked against one list of cases (``packages/claudia-computes/tests/number_format_cases.json``).

What a code may hold, as Excel writes it:

* up to four sections ``positive;negative;zero;text``, each with an optional colour (``[Red]``) and condition
  (``[<0]``); a locale (``[$-407]``) or a currency (``[$€-407]``);
* digits ``0`` (always), ``#`` (if needed), ``?`` (a space if not needed), a decimal point ``.``, a thousands
  separator ``,`` between digits, and ``,`` after the digits to divide by a thousand; ``%``; ``E+00``; ``# ?/?``;
* dates and times: ``d dd ddd dddd``, ``m mm mmm mmmm mmmmm``, ``yy yyyy``, ``h hh``, ``m mm`` after an hour or before
  a second for minutes, ``s ss``, ``[h]`` ``[m]`` ``[s]`` for elapsed time, ``AM/PM``, ``A/P``, ``.0`` for fractions
  of a second;
* text in quotes, ``\\x`` for one character, ``_x`` for the width of a character (a space here), ``*x`` to fill (left
  out here), ``@`` for the cell's text.

``General``, and Excel's built-in short date (``m/d/yyyy``, its format 14), are shown the reader's way.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

#: Excel's built-in formats by their number in an xlsx file (ECMA-376 part 1, 18.8.30). 14 is "the reader's short
#: date": its code here is ``m/d/yyyy``, which :func:`render` shows the reader's way.
BUILTIN: dict[int, str] = {
    0: "General",
    1: "0",
    2: "0.00",
    3: "#,##0",
    4: "#,##0.00",
    9: "0%",
    10: "0.00%",
    11: "0.00E+00",
    12: "# ?/?",
    13: "# ??/??",
    14: "m/d/yyyy",
    15: "d-mmm-yy",
    16: "d-mmm",
    17: "mmm-yy",
    18: "h:mm AM/PM",
    19: "h:mm:ss AM/PM",
    20: "h:mm",
    21: "h:mm:ss",
    22: "m/d/yyyy h:mm",
    37: "#,##0 ;(#,##0)",
    38: "#,##0 ;[Red](#,##0)",
    39: "#,##0.00;(#,##0.00)",
    40: "#,##0.00;[Red](#,##0.00)",
    45: "mm:ss",
    46: "[h]:mm:ss",
    47: "mmss.0",
    48: "##0.0E+0",
    49: "@",
}
SHORT_DATE = "m/d/yyyy"
MAX_CODE = 255

_COLOURS = {"black", "blue", "cyan", "green", "magenta", "red", "white", "yellow"}


# ------------------------------------------------------------------------------------------------ the model
@dataclass(frozen=True)
class NumberFormat:
    """A named format code. ``to_name`` marks one that still has the provisional name an import gave it."""

    id: str
    name: str
    code: str
    to_name: bool = False

    def to_data(self) -> dict:
        """The plain-data form for snapshots and clients."""
        return {"id": self.id, "name": self.name, "code": self.code, "to_name": self.to_name}

    @classmethod
    def from_data(cls, data: dict) -> NumberFormat:
        """Inverse of :meth:`to_data`."""
        return cls(data["id"], data["name"], data["code"], data["to_name"])


@dataclass
class NumberFormatBook:
    """The number formats of a workbook, in the order they were made."""

    formats: dict[str, NumberFormat] = field(default_factory=dict)

    def __iter__(self):
        return iter(list(self.formats.values()))

    def __len__(self) -> int:
        return len(self.formats)

    def __contains__(self, format_id: object) -> bool:
        return format_id in self.formats

    def get(self, format_id: str) -> NumberFormat:
        """The format with this id; ``KeyError`` if there is none."""
        return self.formats[format_id]

    def add(self, number_format: NumberFormat) -> None:
        """Add a format; ``ValueError`` for an id or a name another format has, or a code that is not one."""
        if number_format.id in self.formats:
            raise ValueError(f"there is already a number format {number_format.id!r}")
        if any(f.name.casefold() == number_format.name.casefold() for f in self.formats.values()):
            raise ValueError(f"there is already a number format called {number_format.name!r}")
        check_code(number_format.code)
        self.formats[number_format.id] = number_format

    def by_code(self, code: str) -> NumberFormat | None:
        """The format with exactly this code, if the book has one."""
        return next((f for f in self.formats.values() if f.code == code), None)

    def free_name(self, wanted: str) -> str:
        """``wanted``, or ``wanted 2``, ``wanted 3``... whichever no format has yet."""
        taken = {f.name.casefold() for f in self.formats.values()}
        name, number = wanted, 1
        while name.casefold() in taken:
            number += 1
            name = f"{wanted} {number}"
        return name

    def to_data(self) -> list[dict]:
        """The book as plain data; :meth:`from_data` is the inverse."""
        return [f.to_data() for f in self.formats.values()]

    @classmethod
    def from_data(cls, items: list[dict]) -> NumberFormatBook:
        """Inverse of :meth:`to_data`."""
        book = cls()
        for item in items:
            book.formats[item["id"]] = NumberFormat.from_data(item)
        return book


def check_code(code: str) -> None:
    """``ValueError`` unless ``code`` is a format code this module reads (and no longer than Excel allows)."""
    if not code or len(code) > MAX_CODE:
        raise ValueError(f"a number format code has 1 to {MAX_CODE} characters")
    if len(split_sections(code)) > 4:
        raise ValueError("a number format code has at most four sections")


# ------------------------------------------------------------------------------------------------ reading a code
@dataclass(frozen=True)
class Token:
    """One piece of a section: a ``kind`` (``digit``, ``point``, ``group``, ``percent``, ``exp``, ``slash``,
    ``literal``, ``text``, ``date``, ``ampm``, ``general``) and its text."""

    kind: str
    text: str


@dataclass(frozen=True)
class Section:
    """One section of a code: its tokens, its colour and condition (if any), and the locale it asks for."""

    tokens: tuple[Token, ...]
    colour: str | None = None
    condition: tuple[str, float] | None = None
    locale: str | None = None

    @property
    def is_date(self) -> bool:
        return any(t.kind in ("date", "ampm") for t in self.tokens)

    @property
    def has_text(self) -> bool:
        return any(t.kind == "text" for t in self.tokens)


def split_sections(code: str) -> list[str]:
    """The sections of a code, split at the semicolons that are not quoted, escaped or in brackets."""
    sections, current, i = [], [], 0
    quoted = bracket = False
    while i < len(code):
        ch = code[i]
        if ch == "\\" and not quoted and i + 1 < len(code):
            current.append(code[i : i + 2])
            i += 2
            continue
        if ch == '"' and not bracket:
            quoted = not quoted
        elif ch == "[" and not quoted:
            bracket = True
        elif ch == "]" and not quoted:
            bracket = False
        if ch == ";" and not quoted and not bracket:
            sections.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    sections.append("".join(current))
    return sections


_CONDITION = re.compile(r"^(<=|>=|<>|<|>|=)\s*(-?\d+(?:\.\d+)?)$")
_DAY_WORDS = frozenset({"d", "dd", "ddd", "dddd", "m", "mm", "mmm", "mmmm", "mmmmm", "y", "yy", "yyyy", "e"})
_DATE_RUN = re.compile(r"(yyyy|yy|y|mmmmm|mmmm|mmm|mm|m|dddd|ddd|dd|d|hh|h|ss|s|e|g{1,3}|b{2,4})", re.IGNORECASE)


@dataclass
class _Reading:
    """A section being read: its tokens so far, and what its brackets said."""

    tokens: list[Token] = field(default_factory=list)
    colour: str | None = None
    condition: tuple[str, float] | None = None
    locale: str | None = None

    def bracket(self, inside: str) -> None:
        """What ``[...]`` says: a colour, a condition, a currency or locale, or an elapsed time."""
        low = inside.lower()
        condition = _CONDITION.match(inside.replace(" ", ""))
        if low in _COLOURS or re.fullmatch(r"color\d{1,2}", low):
            self.colour = low
        elif condition is not None:
            self.condition = (condition.group(1), float(condition.group(2)))
        elif inside.startswith("$"):
            symbol, _, lcid = inside[1:].partition("-")
            if symbol:
                self.tokens.append(Token("literal", symbol))
            self.locale = lcid.upper() or None
        elif re.fullmatch(r"[hms]+", low):
            self.tokens.append(Token("date", f"[{low}]"))


#: Characters that are a token of their own, by kind.
_SINGLE = {
    "0": "digit",
    "#": "digit",
    "?": "digit",
    ".": "point",
    ",": "group",
    "%": "percent",
    "/": "slash",
    "@": "text",
}
#: Words read case-blind before anything else at their place, by kind.
_WORDS = (("general", "general"), ("am/pm", "ampm"), ("a/p", "ampm"))


def _skip_or_quote(text: str, i: int, reading: _Reading) -> int | None:
    """Read a quoted text, an escaped character, a space width (``_x``) or a fill (``*x``) at ``i``; the place after
    it, or ``None`` when there is none at ``i``."""
    ch = text[i]
    if ch == '"':
        end = text.find('"', i + 1)
        end = len(text) if end < 0 else end
        reading.tokens.append(Token("literal", text[i + 1 : end]))
        return end + 1
    if ch in "\\_*" and i + 1 < len(text):
        if ch != "*":
            reading.tokens.append(Token("literal", " " if ch == "_" else text[i + 1]))
        return i + 2
    return None


def _word_or_token(text: str, i: int, reading: _Reading) -> int:
    """Read a word (``General``, ``AM/PM``), a run of date letters, an exponent or a single character at ``i``."""
    for word, kind in _WORDS:
        if text[i : i + len(word)].lower() == word:
            reading.tokens.append(Token(kind, text[i : i + len(word)]))
            return i + len(word)
    ch = text[i]
    if ch in "Ee" and i + 1 < len(text) and text[i + 1] in "+-":
        reading.tokens.append(Token("exp", text[i : i + 2]))
        return i + 2
    if ch.lower() in "ymdhsegb":
        run = _DATE_RUN.match(text, i)
        if run is not None:
            reading.tokens.append(Token("date", run.group(0)))
            return run.end()
    reading.tokens.append(Token(_SINGLE.get(ch, "literal"), ch))
    return i + 1


def parse_section(text: str) -> Section:
    """One section read into tokens."""
    reading = _Reading()
    i = 0
    while i < len(text):
        if text[i] == "[":
            end = text.find("]", i)
            if end < 0:
                reading.tokens.append(Token("literal", text[i:]))
                break
            reading.bracket(text[i + 1 : end])
            i = end + 1
            continue
        after = _skip_or_quote(text, i, reading)
        i = after if after is not None else _word_or_token(text, i, reading)
    tokens = _minutes(_date_slashes(reading.tokens))
    return Section(tuple(tokens), reading.colour, reading.condition, reading.locale)


def _date_slashes(tokens: list[Token]) -> list[Token]:
    """In a date, ``/`` is a literal (``dd/mm/yyyy``), not a fraction."""
    if not any(t.kind == "date" for t in tokens):
        return tokens
    return [Token("literal", "/") if t.kind == "slash" else t for t in tokens]


def _minutes(tokens: list[Token]) -> list[Token]:
    """``m``/``mm`` right after an hour or right before a second is minutes (``mi``), as Excel reads it."""
    dated = [i for i, t in enumerate(tokens) if t.kind == "date"]
    out = list(tokens)
    for place, index in enumerate(dated):
        word = tokens[index].text.lower()
        if word not in ("m", "mm"):
            continue
        before = tokens[dated[place - 1]].text.lower() if place > 0 else ""
        after = tokens[dated[place + 1]].text.lower() if place + 1 < len(dated) else ""
        if before.startswith(("h", "[h")) or after.startswith(("s", "[s")):
            out[index] = Token("date", "mi" if word == "m" else "mmi")
    return out


def parse(code: str) -> list[Section]:
    """Every section of a code."""
    return [parse_section(s) for s in split_sections(code)]


def kind_of(code: str) -> str:
    """What a code shows: ``general``, ``date``, ``time``, ``percent``, ``scientific``, ``fraction``, ``text`` or
    ``number``."""
    first = parse(code)[0]
    kinds = {t.kind for t in first.tokens}
    if code.strip().lower() == "general" or kinds == {"general"}:
        return "general"
    if first.is_date:
        dated = {t.text.lower().strip("[]") for t in first.tokens if t.kind == "date"}
        return "date" if dated & _DAY_WORDS else "time"
    if "percent" in kinds:
        return "percent"
    if "exp" in kinds:
        return "scientific"
    if "slash" in kinds:
        return "fraction"
    if kinds == {"text"} or kinds <= {"text", "literal"}:
        return "text"
    return "number"


# ------------------------------------------------------------------------------------------------ the locale
@dataclass(frozen=True)
class Symbols:
    """How a reader writes numbers and dates: separators, names of months and days, and the short date."""

    decimal: str = "."
    group: str = ","
    months: tuple[str, ...] = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    months_short: tuple[str, ...] = (
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    )
    days: tuple[str, ...] = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
    days_short: tuple[str, ...] = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
    short_date: str = "m/d/yyyy"


ENGLISH = Symbols()
GERMAN = Symbols(
    ",",
    ".",
    (
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ),
    ("Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"),
    ("Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"),
    ("So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"),
    "dd.mm.yyyy",
)
#: The Windows locale ids of the languages a code can ask for (``[$-407]``), for the names of months and days.
_LCID = {"407": GERMAN, "807": GERMAN, "C07": GERMAN, "409": ENGLISH, "809": ENGLISH}


# ------------------------------------------------------------------------------------------------ rendering
def render(value: object, code: str, symbols: Symbols = ENGLISH) -> str:
    """``value`` (a number, a text, TRUE/FALSE or nothing) shown through ``code`` the way ``symbols`` writes it."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    sections = parse(code)
    if isinstance(value, str):
        return _render_text(value, sections)
    number = value if isinstance(value, int | float) else float(str(value))
    section, negate = _pick(number, sections)
    if any(t.kind == "general" for t in section.tokens) and len(section.tokens) == 1:
        return general(-number if negate else number, symbols)
    if code == SHORT_DATE:
        section = parse_section(symbols.short_date)
    if section.is_date:
        names = _LCID.get(section.locale or "", symbols)
        return _render_date(abs(number) if negate else number, section, replace(symbols, **_names_of(names)))
    return _render_number(abs(number) if negate else number, section, symbols, keep_sign=not negate)


def _names_of(symbols: Symbols) -> dict:
    return {
        "months": symbols.months,
        "months_short": symbols.months_short,
        "days": symbols.days,
        "days_short": symbols.days_short,
    }


def general(number: float, symbols: Symbols = ENGLISH) -> str:
    """A number the General way: up to 10 decimals, no thousands separator, the reader's decimal sign."""
    if isinstance(number, float) and number.is_integer() and abs(number) < 1e15:
        number = int(number)
    if isinstance(number, int):
        text = str(number)
    elif abs(number) >= 1e15 or (number != 0 and abs(number) < 1e-9):
        text = f"{number:.5E}".replace("E+0", "E+").replace("E-0", "E-")
    else:
        text = f"{number:.10f}".rstrip("0").rstrip(".")
    return text.replace(".", symbols.decimal)


def _matches(condition: tuple[str, float], number: float) -> bool:
    op, limit = condition
    return {
        "<": number < limit,
        "<=": number <= limit,
        ">": number > limit,
        ">=": number >= limit,
        "=": number == limit,
        "<>": number != limit,
    }[op]


def _pick(number: float, sections: list[Section]) -> tuple[Section, bool]:
    """The section a number is shown with, and whether the section shows it without its sign."""
    numeric = sections[:3]
    if any(s.condition for s in numeric):
        for index, s in enumerate(numeric):
            if s.condition is None or _matches(s.condition, number):
                return s, index > 0 and number < 0
        return numeric[-1], number < 0
    if len(numeric) >= 3 and number == 0:
        return numeric[2], False
    if len(numeric) >= 2 and number < 0:
        return numeric[1], True
    return numeric[0], False


def _render_text(text: str, sections: list[Section]) -> str:
    section = sections[3] if len(sections) >= 4 else next((s for s in sections if s.has_text), None)
    if section is None:
        return text
    return "".join(text if t.kind == "text" else t.text for t in section.tokens if t.kind in ("text", "literal"))


def _render_number(number: float, section: Section, symbols: Symbols, *, keep_sign: bool) -> str:
    tokens = list(section.tokens)
    kinds = [t.kind for t in tokens]
    if "exp" in kinds:
        return _render_scientific(number, tokens, symbols, keep_sign)
    if "slash" in kinds:
        return _render_fraction(number, tokens, keep_sign)
    point = kinds.index("point") if "point" in kinds else None
    digits_at = [i for i, k in enumerate(kinds) if k == "digit"]
    int_places = [i for i in digits_at if point is None or i < point]
    frac_places = [i for i in digits_at if point is not None and i > point]
    last_digit = digits_at[-1] if digits_at else -1
    scale = sum(1 for i, k in enumerate(kinds) if k == "group" and i > last_digit and (point is None or i > point))
    grouped = any(
        k == "group" and int_places and int_places[0] < i < (point if point is not None else last_digit + 1)
        for i, k in enumerate(kinds)
    )
    value = number * 100 ** kinds.count("percent") / 1000**scale
    decimals = len(frac_places)
    rounded = _round(abs(value), decimals)
    whole, _, fraction = rounded.partition(".")
    negative = value < 0 and keep_sign and bool(digits_at) and any(c not in "0." for c in rounded)
    places = [tokens[i].text for i in int_places]
    int_parts = (
        [_fill_integer(whole, places, symbols.group)] + [""] * (len(places) - 1)
        if grouped
        else _spread_integer(whole, places)
    )
    frac_text = _fill_fraction(fraction, [tokens[i].text for i in frac_places])
    out: list[str] = []
    int_index = frac_index = 0
    for i, token in enumerate(tokens):
        if i in int_places:
            out.append(int_parts[int_index])
            int_index += 1
        elif i in frac_places:
            out.append(frac_text[frac_index])
            frac_index += 1
        elif token.kind == "point":
            out.append(symbols.decimal)
        elif token.kind in ("literal", "percent"):
            out.append(token.text)
    text = "".join(out)
    return ("-" + text) if negative else text


def _round(value: float, decimals: int) -> str:
    """``value`` with exactly ``decimals`` decimals, halves away from zero (as Excel shows them)."""
    exact = Decimal(repr(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    return f"{exact:f}"


_PAD = {"0": "0", "?": " ", "#": ""}  # what a placeholder shows when there is no digit for it


def _fill_integer(whole: str, places: list[str], group: str) -> str:
    """The integer digits put into their placeholders: extra digits go before the first; ``0`` pads with zeros,
    ``?`` with spaces, ``#`` with nothing; a thousands separator every three digits."""
    if not places:
        return ""
    digits = "" if whole == "0" else whole
    needed = len(places)
    if len(digits) < needed:
        digits = "".join(_PAD[kind] for kind in places[: needed - len(digits)]) + digits
    if not group:
        return digits
    lead = len(digits) - len(digits.lstrip(" "))
    body = digits[lead:]
    parts: list[str] = []
    while len(body) > 3:
        parts.insert(0, body[-3:])
        body = body[:-3]
    if body:
        parts.insert(0, body)
    return " " * lead + group.join(parts)


def _spread_integer(whole: str, places: list[str]) -> list[str]:
    """The integer digits put into placeholders that literals stand between (``000-000``): right-aligned, the extra
    digits before the first placeholder."""
    if not places:
        return []
    digits = "" if whole == "0" else whole
    out = []
    for back, kind in enumerate(reversed(places), start=1):
        if back <= len(digits):
            out.append(digits[-back])
        else:
            out.append("0" if kind == "0" else " " if kind == "?" else "")
    out.reverse()
    if len(digits) > len(places):
        out[0] = digits[: len(digits) - len(places) + 1]
    return out


def _fill_fraction(fraction: str, places: list[str]) -> list[str]:
    """The decimals put into their placeholders: trailing zeros of ``#`` places are left out, of ``?`` spaces."""
    chars = list(fraction.ljust(len(places), "0"))[: len(places)]
    for index in range(len(places) - 1, -1, -1):
        if chars[index] != "0" or places[index] == "0":
            break
        chars[index] = "" if places[index] == "#" else " "
    return chars


def _render_scientific(number: float, tokens: list[Token], symbols: Symbols, keep_sign: bool) -> str:
    kinds = [t.kind for t in tokens]
    exp_at = kinds.index("exp")
    point = kinds.index("point") if "point" in kinds[:exp_at] else exp_at
    int_digits = max(1, kinds[:point].count("digit"))
    decimals = kinds[point:exp_at].count("digit")
    exp_digits = kinds[exp_at + 1 :].count("digit")
    exponent = 0 if number == 0 else math.floor(math.log10(abs(number)))
    if int_digits > 1:  # engineering style (``##0.0E+0``): exponents in steps of the integer digits
        exponent -= exponent % int_digits
    text = _round(abs(number) / 10**exponent if number else 0.0, decimals)
    if float(text) >= 10 ** (int_digits if int_digits > 1 else 1):  # rounding carried over into the next power
        exponent += int_digits
        text = _round(abs(number) / 10**exponent, decimals)
    mark = tokens[exp_at].text
    sign = "-" if exponent < 0 else ("+" if mark.endswith("+") else "")
    shown = text.replace(".", symbols.decimal) + mark[0] + sign + str(abs(exponent)).zfill(exp_digits)
    return ("-" + shown) if number < 0 and keep_sign else shown


def _render_fraction(number: float, tokens: list[Token], keep_sign: bool) -> str:
    kinds = [t.kind for t in tokens]
    slash = kinds.index("slash")
    denominator_places = sum(1 for t in tokens[slash + 1 :] if t.kind == "digit")
    fixed = "".join(t.text for t in tokens[slash + 1 :] if t.kind == "digit")
    whole_part = any(k == "literal" and tokens[i].text == " " for i, k in enumerate(kinds[:slash]))
    value = abs(number)
    whole = math.floor(value) if whole_part else 0
    rest = value - whole
    if fixed.isdigit():
        denominator = int(fixed)
        numerator = round(rest * denominator)
    else:
        fraction = Fraction(rest).limit_denominator(10**denominator_places - 1)
        numerator, denominator = fraction.numerator, fraction.denominator
    if numerator == denominator and denominator:
        whole, numerator = whole + 1, 0
    width = denominator_places
    if numerator == 0:
        text = str(whole) if whole_part else "0"
        text += " " * (2 * width + 2) if whole_part else ""
    else:
        text = (f"{whole} " if whole_part and whole else "") + f"{numerator}/{denominator}"
    text = text.rstrip()
    return "-" + text if number < 0 and keep_sign else text


def _second_decimals(tokens: list[Token]) -> int:
    """How many decimals of a second a date section shows (``ss.00``: 2)."""
    for i, token in enumerate(tokens):
        if (
            token.kind == "point"
            and i > 0
            and tokens[i - 1].kind == "date"
            and tokens[i - 1].text.lower() in ("s", "ss")
        ):
            return sum(1 for t in tokens[i + 1 :] if t.kind == "digit")
    return 0


@dataclass(frozen=True)
class _Moment:
    """A day number taken apart for a date section."""

    number: float
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    fraction: float


def _moment(number: float, decimals: int) -> _Moment:
    from .functions.library.dates import parts_of  # noqa: PLC0415 (the day count lives with the date functions)

    day_number = math.floor(number)
    seconds = round((number - day_number) * 86400 * 1000) / 1000
    if not decimals:
        seconds = round(seconds)
    if seconds >= 86400:
        day_number, seconds = day_number + 1, seconds - 86400
    year, month, day = parts_of(day_number) if day_number >= 0 else (1900, 1, 0)
    hour, rest = divmod(int(seconds), 3600)
    minute, second = divmod(rest, 60)
    return _Moment(number, year, month, day, hour, minute, second, seconds - int(seconds))


def _render_date(number: float, section: Section, symbols: Symbols) -> str:
    tokens = list(section.tokens)
    decimals = _second_decimals(tokens)
    moment = _moment(number, decimals)
    twelve = any(t.kind == "ampm" for t in tokens)
    out: list[str] = []
    after_point = False
    for token in tokens:
        if token.kind == "date":
            out.append(_date_part(token.text, moment, twelve, symbols))
        elif token.kind == "ampm":
            out.append(_am_pm(token.text, moment.hour))
        elif token.kind == "point" and decimals:
            out.append(symbols.decimal + str(round(moment.fraction * 10**decimals)).zfill(decimals))
            after_point = True
        elif token.kind != "digit" or not after_point:
            out.append(token.text if token.kind != "digit" else "")
    return "".join(out)


def _am_pm(word: str, hour: int) -> str:
    am = hour < 12
    shown = ("AM" if am else "PM") if word.upper() == "AM/PM" else ("A" if am else "P")
    return shown.lower() if word[0].islower() else shown


def _date_part(word: str, moment: _Moment, twelve: bool, symbols: Symbols) -> str:
    """What one word of a date section (``dd``, ``mmmm``, ``hh``, ``[h]``...) shows for ``moment``."""
    low = word.lower()
    if low.startswith("["):
        total = round(moment.number * 86400)
        return str({"h": total // 3600, "m": total // 60, "s": total}[low[1]]).zfill(len(low) - 2)
    weekday = (math.floor(moment.number) + 6) % 7  # (day 1, a Sunday in Excel's count, is weekday 0 here)
    hour = (moment.hour % 12 or 12) if twelve else moment.hour
    parts: dict[str, str] = {
        "yyyy": str(moment.year),
        "yyy": str(moment.year),
        "e": str(moment.year),
        "yy": str(moment.year % 100).zfill(2),
        "y": str(moment.year % 100).zfill(2),
        "mmmmm": symbols.months[moment.month - 1][0],
        "mmmm": symbols.months[moment.month - 1],
        "mmm": symbols.months_short[moment.month - 1],
        "mm": str(moment.month).zfill(2),
        "m": str(moment.month),
        "dddd": symbols.days[weekday],
        "ddd": symbols.days_short[weekday],
        "dd": str(moment.day).zfill(2),
        "d": str(moment.day),
        "hh": str(hour).zfill(2),
        "h": str(hour),
        "mmi": str(moment.minute).zfill(2),
        "mi": str(moment.minute),
        "ss": str(moment.second).zfill(2),
        "s": str(moment.second),
    }
    return parts.get(low, word)


# ------------------------------------------------------------------------------------------------ naming
def describe(code: str) -> str:
    """A short name for what a code shows, for the provisional name of an imported format: ``MWh``, ``€``,
    ``percent, 1 decimal``, ``date``, ``3 decimals``."""
    if code == SHORT_DATE:
        return "short date"
    first = parse(code)[0]
    kind = kind_of(code)
    if kind in ("date", "time", "general", "text", "scientific", "fraction"):
        unit = _unit(first)
        return f"{kind} {unit}".strip() if kind in ("date", "time") and unit else kind
    decimals = 0
    seen_point = False
    for token in first.tokens:
        if token.kind == "point":
            seen_point = True
        elif token.kind == "digit" and seen_point:
            decimals += 1
    unit = _unit(first)
    parts = []
    if kind == "percent":
        parts.append("percent")
    if unit:
        parts.append(unit)
    if decimals:
        parts.append(f"{decimals} decimal{'s' if decimals > 1 else ''}")
    elif not parts:
        parts.append("whole number")
    if parts == ["whole number"] and any(t.kind == "group" for t in first.tokens):
        parts.append("thousands")
    return ", ".join(parts)


def _unit(section: Section) -> str:
    """The literal text of a section that names a unit or a currency (``MWh``, ``€``), without stray punctuation."""
    text = "".join(t.text for t in section.tokens if t.kind == "literal").strip()
    text = text.strip(" ()-+:/")
    if len(text) > _LONG_UNIT:  # a label, not a unit: its start is enough to know it again
        text = text[: _LONG_UNIT - 1].rstrip() + "…"
    return text if any(ch.isalpha() or ch in "€$£¥°" for ch in text) else ""


_LONG_UNIT = 16
