"""OpenDocument number styles and Excel format codes, both ways (E6.14, D378).

The workbook keeps a number format as an Excel code (``#,##0.00 "€"``), because that is the one way of writing a
format every spreadsheet reads. An ods file writes the same thing as a *number style*: a ``number:number-style``
(or a percentage, currency, date or time style) whose children are the parts in order -- a number with so many
decimals, a piece of text, a day, a month. :func:`code_of` reads such a style as a code, :func:`number_style` writes
a code as one. What a code can say and a number style cannot (a fill character, a space as wide as a character) is
left out on the way to ods, and what a number style can say and a code cannot (an era, a calendar) on the way back.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from lxml import etree

from claudia_computes.numformats import Section, Token, parse
from claudia_odf_io import NS, local_name

#: The kinds of number style an ods file has, as their element names.
NUMBER_STYLES = ("number-style", "currency-style", "percentage-style", "date-style", "time-style", "text-style",
                 "boolean-style")  # fmt: skip
_N = NS["number"]
_DECLARED = {prefix: uri for prefix, uri in NS.items() if prefix != "xml"}
_RED = "#ff0000"


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def _get(element: etree._Element, prefix: str, local: str, default: str = "") -> str:
    return element.get(_q(prefix, local), default)


# ------------------------------------------------------------------------------------------------ ods -> code
def code_of(style: etree._Element, by_name: Mapping[str, etree._Element]) -> str:
    """The Excel code of a number style. Its ``style:map`` children become the code's other sections, the way an
    ods file writes them: a style for numbers from zero up (or above zero) first, one for numbers below zero second,
    the style itself for the rest."""
    own = _section(style)
    maps: dict[str, str] = {}
    for mapping in style.iterfind("style:map", NS):
        other = by_name.get(_get(mapping, "style", "apply-style-name"))
        condition = _get(mapping, "style", "condition").replace(" ", "")
        if other is not None and other is not style and condition.startswith("value()"):
            maps[condition[len("value()") :]] = _section(other)
    everything = next((c for c in maps if c.startswith("<=") and _huge(c[2:])), None)
    positive = maps.pop(">=0", None) or maps.pop(">0", None) or (maps.pop(everything) if everything else None)
    negative = maps.pop("<0", None)
    if positive is not None and negative is not None:
        return f"{positive};{negative};{own}"
    if positive is not None:
        return f"{positive};{own}"
    if negative is not None:
        return f"{own};{negative}"
    if maps:
        return ";".join([*(f"[{condition}]{section}" for condition, section in maps.items()), own])
    return own


def _huge(number: str) -> bool:
    """LibreOffice maps "every number" to a section with ``value()<=1.7976931348623157E+308``."""
    try:
        return float(number) > 1e300  # noqa: PLR2004
    except ValueError:
        return False


def _section(style: etree._Element) -> str:
    kind = local_name(style.tag)
    out: list[str] = []
    colour = style.find("style:text-properties", NS)
    if colour is not None and _get(colour, "fo", "color").lower() == _RED:
        out.append("[Red]")
    truncate = _get(style, "number", "truncate-on-overflow", "true") == "false"
    for part in style:
        if not isinstance(part.tag, str) or etree.QName(part).namespace != _N:
            continue
        out.append(_PARTS.get(etree.QName(part).localname, _nothing)(part, kind, truncate))
    return "".join(out) or ("@" if kind == "text-style" else "General")


def _nothing(_part: etree._Element, _kind: str, _truncate: bool) -> str:
    return ""


def _number(part: etree._Element, _kind: str, _truncate: bool) -> str:
    places = int(_get(part, "number", "decimal-places", "0") or 0)
    least = int(_get(part, "number", "min-decimal-places", str(places)) or 0)
    digits = int(_get(part, "number", "min-integer-digits", "1") or 0)
    integer = "0" * digits or "#"
    if _get(part, "number", "grouping") == "true":
        padded = "#" * max(0, 4 - digits) + "0" * digits
        integer = padded[:-3] + "," + padded[-3:]
    decimals = "0" * min(least, places) + "#" * max(places - least, 0)
    return integer + ("." + decimals if decimals else "")


def _scientific(part: etree._Element, _kind: str, _truncate: bool) -> str:
    places = int(_get(part, "number", "decimal-places", "0") or 0)
    exponent = int(_get(part, "number", "min-exponent-digits", "2") or 2)
    return "0" + ("." + "0" * places if places else "") + "E+" + "0" * exponent


def _fraction(part: etree._Element, _kind: str, _truncate: bool) -> str:
    numerator = int(_get(part, "number", "min-numerator-digits", "1") or 1)
    denominator = _get(part, "number", "denominator-value") or "?" * int(
        _get(part, "number", "min-denominator-digits", "1") or 1
    )
    whole = "# " if _get(part, "number", "min-integer-digits") else ""
    return whole + "?" * numerator + "/" + denominator


def _text(part: etree._Element, kind: str, _truncate: bool) -> str:
    words = _words_of(part)
    if kind == "percentage-style" and "%" in words:
        before, _, after = words.partition("%")
        return _quoted(before) + "%" + _quoted(after)
    return _quoted(words, dated=kind in ("date-style", "time-style"))


def _words_of(part: etree._Element) -> str:
    return "".join(str(piece) for piece in part.itertext())


def _quoted(words: str, *, dated: bool = False) -> str:
    """Text of a number style as a code writes it: bare where it cannot be read as anything else (a space, a
    bracket; in a date also a dot, a comma, a slash or a colon), else in quotes."""
    if not words:
        return ""
    if set(words) <= set(" .,-/:" if dated else " -()"):
        return words
    return '"' + words.replace('"', '\\"') + '"'


def _currency(part: etree._Element, _kind: str, _truncate: bool) -> str:
    return _quoted(_words_of(part))


def _long(part: etree._Element) -> bool:
    return _get(part, "number", "style") == "long"


def _date_part(short: str, long: str) -> Callable[[etree._Element, str, bool], str]:
    def made(part: etree._Element, _kind: str, _truncate: bool) -> str:
        return long if _long(part) else short

    return made


def _month(part: etree._Element, _kind: str, _truncate: bool) -> str:
    if _get(part, "number", "textual") == "true":
        return "mmmm" if _long(part) else "mmm"
    return "mm" if _long(part) else "m"


def _hours(part: etree._Element, _kind: str, truncate: bool) -> str:
    hours = "hh" if _long(part) else "h"
    return f"[{hours}]" if truncate else hours


def _seconds(part: etree._Element, _kind: str, _truncate: bool) -> str:
    places = int(_get(part, "number", "decimal-places", "0") or 0)
    return ("ss" if _long(part) else "s") + ("." + "0" * places if places else "")


_PARTS: dict[str, Callable[[etree._Element, str, bool], str]] = {
    "number": _number,
    "scientific-number": _scientific,
    "fraction": _fraction,
    "text": _text,
    "currency-symbol": _currency,
    "text-content": lambda _part, _kind, _truncate: "@",
    "day": _date_part("d", "dd"),
    "month": _month,
    "year": _date_part("yy", "yyyy"),
    "day-of-week": _date_part("ddd", "dddd"),
    "hours": _hours,
    "minutes": _date_part("m", "mm"),
    "seconds": _seconds,
    "am-pm": lambda _part, _kind, _truncate: "AM/PM",
}


# ------------------------------------------------------------------------------------------------ code -> ods
def number_style(code: str, name: str) -> list[etree._Element]:
    """A code as the number styles an ods file needs for it, named ``name`` (and ``name`` + ``P0``, ``P1``... for
    its other sections, which the last of the list maps to). The last element is the one a cell style names."""
    sections = parse(code)[:3]  # a fourth section, for text, has no number style to go to
    if len(sections) == 1:
        return [_style_of(sections[0], name)]
    made = [_style_of(section, f"{name}P{i}") for i, section in enumerate(sections[:-1])]
    last = _style_of(sections[-1], name)
    for i, condition in enumerate(_conditions(sections)):
        etree.SubElement(
            last,
            _q("style", "map"),
            {_q("style", "condition"): condition, _q("style", "apply-style-name"): f"{name}P{i}"},
        )
    return [*made, last]


def _conditions(sections: list[Section]) -> list[str]:
    explicit = [section.condition for section in sections[:-1]]
    if all(explicit):
        return [f"value(){op}{value:g}" for op, value in explicit if op]  # type: ignore[misc]
    return ["value()>0", "value()<0"] if len(sections) > 2 else ["value()>=0"]  # noqa: PLR2004


def _kind(section: Section) -> str:
    if section.is_date:
        return "date-style"
    if section.has_text and not any(t.kind == "digit" for t in section.tokens):
        return "text-style"
    if any(t.kind == "percent" for t in section.tokens):
        return "percentage-style"
    return "number-style"


def _style_of(section: Section, name: str) -> etree._Element:
    kind = _kind(section)
    style = etree.Element(_q("number", kind), {_q("style", "name"): name}, nsmap=_DECLARED)
    if section.colour == "red":
        etree.SubElement(style, _q("style", "text-properties"), {_q("fo", "color"): _RED})
    if section.is_date:
        _date_parts(style, section)
    else:
        _number_parts(style, section)
    return style


def _add_text(style: etree._Element, words: str) -> None:
    if not words:
        return
    last = style[-1] if len(style) and etree.QName(style[-1]).localname == "text" else None
    if last is not None:
        last.text = (last.text or "") + words
    else:
        etree.SubElement(style, _q("number", "text")).text = words


@dataclass
class _Digits:
    """The digits of a section as a number style counts them."""

    integer: int = 0
    decimals: int = 0
    least: int = 0
    grouping: bool = False
    exponent: int = 0
    numerator: int = 0
    denominator: str = ""


def _count(tokens: tuple[Token, ...]) -> tuple[str, _Digits]:
    digits, part = _Digits(), "integer"
    for token in tokens:
        if token.kind == "point" and part == "integer":
            part = "decimals"
        elif token.kind == "exp":
            part = "exponent"
        elif token.kind == "slash":
            digits.numerator, digits.integer, part = digits.integer or 1, 0, "denominator"
        elif token.kind == "group" and part == "integer":
            digits.grouping = True
        elif token.kind == "digit" or (part == "denominator" and token.text.isdigit()):
            _one_digit(digits, part, token.text)  # (a fixed denominator, "# ?/4", is digits Excel reads as text)
    shape = "scientific" if digits.exponent else "fraction" if digits.denominator else "number"
    return shape, digits


def _one_digit(digits: _Digits, part: str, text: str) -> None:
    if part == "integer":
        digits.integer += text == "0"
    elif part == "decimals":
        digits.decimals += 1
        digits.least += text == "0"
    elif part == "exponent":
        digits.exponent += 1
    else:
        digits.denominator += "?" if text in "#?" else text


def _number_parts(style: etree._Element, section: Section) -> None:
    shape, digits = _count(section.tokens)
    numeric = ("digit", "point", "group", "exp", "slash")
    slash = next((i for i, token in enumerate(section.tokens) if token.kind == "slash"), len(section.tokens))
    places = [
        i
        for i, token in enumerate(section.tokens)
        if token.kind in numeric or (shape == "fraction" and i > slash and token.text.isdigit())
    ]
    placed = False
    for i, token in enumerate(section.tokens):
        if shape == "fraction" and places and places[0] < i <= places[-1]:
            continue  # the space before the fraction and a fixed denominator are the fraction element's own
        if token.kind in numeric:
            if not placed:
                _place_number(style, shape, digits)
                placed = True
        elif token.kind == "text":
            etree.SubElement(style, _q("number", "text-content"))
        elif token.kind in ("literal", "percent"):
            _add_text(style, token.text)


def _place_number(style: etree._Element, shape: str, digits: _Digits) -> None:
    attributes = {_q("number", "min-integer-digits"): str(digits.integer)}
    if shape == "fraction":
        attributes[_q("number", "min-numerator-digits")] = str(digits.numerator)
        if digits.denominator.isdigit():
            attributes[_q("number", "denominator-value")] = digits.denominator
        else:
            attributes[_q("number", "min-denominator-digits")] = str(len(digits.denominator))
        etree.SubElement(style, _q("number", "fraction"), attributes)
        return
    attributes[_q("number", "decimal-places")] = str(digits.decimals)
    if digits.grouping:
        attributes[_q("number", "grouping")] = "true"
    if shape == "scientific":
        attributes[_q("number", "min-exponent-digits")] = str(digits.exponent)
        etree.SubElement(style, _q("number", "scientific-number"), attributes)
        return
    attributes[_q("number", "min-decimal-places")] = str(digits.least)
    etree.SubElement(style, _q("number", "number"), attributes)


_DATE_TOKENS: dict[str, tuple[str, dict[str, str]]] = {
    "d": ("day", {}),
    "dd": ("day", {"style": "long"}),
    "ddd": ("day-of-week", {}),
    "dddd": ("day-of-week", {"style": "long"}),
    "m": ("month", {}),
    "mm": ("month", {"style": "long"}),
    "mmm": ("month", {"textual": "true"}),
    "mmmm": ("month", {"textual": "true", "style": "long"}),
    "mmmmm": ("month", {"textual": "true"}),
    "y": ("year", {}),
    "yy": ("year", {}),
    "yyyy": ("year", {"style": "long"}),
    "h": ("hours", {}),
    "hh": ("hours", {"style": "long"}),
    "mi": ("minutes", {}),
    "mmi": ("minutes", {"style": "long"}),
    "s": ("seconds", {}),
    "ss": ("seconds", {"style": "long"}),
}


def _date_parts(style: etree._Element, section: Section) -> None:
    last_seconds: etree._Element | None = None
    after_point = False
    for token in section.tokens:
        word = token.text.lower()
        if token.kind == "date":
            if word.startswith("["):
                style.set(_q("number", "truncate-on-overflow"), "false")
                word = word.strip("[]")
                word = {"m": "mi", "mm": "mmi"}.get(word, word)
            local, extra = _DATE_TOKENS.get(word, ("", {}))
            if not local:
                continue
            element = etree.SubElement(style, _q("number", local), {_q("number", k): v for k, v in extra.items()})
            last_seconds = element if local == "seconds" else None
        elif token.kind == "ampm":
            etree.SubElement(style, _q("number", "am-pm"))
        elif token.kind == "point" and last_seconds is not None:
            after_point = True
        elif token.kind == "digit" and after_point and last_seconds is not None:
            places = int(last_seconds.get(_q("number", "decimal-places"), "0")) + 1
            last_seconds.set(_q("number", "decimal-places"), str(places))
        else:
            after_point = False
            _add_text(style, token.text)
