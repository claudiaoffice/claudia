"""The CSS a style may hold: a short, versioned allow-list of properties and value types (E1.10, D73, D75).

Styles are CSS in all three apps, in the file as well as on screen. A style is also something a stranger's document
brings along, so nothing in it may reach outside the page: no ``url()``, no ``@import``, no ``@font-face``, no
``var()`` or ``calc()``, no ``!important``, no scripts. Everything that is not on the list is refused with a sentence
that names the property, and the list is widened on purpose, one property at a time, as the apps need them.

``validate_css`` checks a dictionary, ``parse_css`` reads the text of a style (what the style menu shows in its CSS
view) and says what is wrong with every line, and ``format_css`` writes the text back in one fixed order.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

#: Bumped whenever the list or the meaning of a value changes; an old document is upcast, never broken (E1.3).
CSS_VERSION = 1

_MAX_LENGTH = 1000.0
_MAX_FAMILIES = 20
_MAX_TEXT = 4000

_NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)"
_LENGTH = re.compile(rf"({_NUMBER})(px|pt|em|rem|%)?")
_PLAIN_NUMBER = re.compile(_NUMBER)
_HEX = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")
_COLOR_FUNCTION = re.compile(
    rf"(?:rgb|rgba|hsl|hsla)\(\s*{_NUMBER}(?:deg|%)?(?:\s*[,\s]\s*{_NUMBER}%?){{2}}(?:\s*[,/]\s*{_NUMBER}%?)?\s*\)"
)
_FAMILY_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_ -]*")
_QUOTED_NAME = re.compile(r"""(?:'[^'\\;{}()<>@\n]+'|"[^"\\;{}()<>@\n]+")""")

# The 148 colour names of CSS Color 4, plus the two special values that are safe.
_COLOR_NAMES = frozenset(
    (
        "aliceblue",
        "antiquewhite",
        "aqua",
        "aquamarine",
        "azure",
        "beige",
        "bisque",
        "black",
        "blanchedalmond",
        "blue",
        "blueviolet",
        "brown",
        "burlywood",
        "cadetblue",
        "chartreuse",
        "chocolate",
        "coral",
        "cornflowerblue",
        "cornsilk",
        "crimson",
        "cyan",
        "darkblue",
        "darkcyan",
        "darkgoldenrod",
        "darkgray",
        "darkgreen",
        "darkgrey",
        "darkkhaki",
        "darkmagenta",
        "darkolivegreen",
        "darkorange",
        "darkorchid",
        "darkred",
        "darksalmon",
        "darkseagreen",
        "darkslateblue",
        "darkslategray",
        "darkslategrey",
        "darkturquoise",
        "darkviolet",
        "deeppink",
        "deepskyblue",
        "dimgray",
        "dimgrey",
        "dodgerblue",
        "firebrick",
        "floralwhite",
        "forestgreen",
        "fuchsia",
        "gainsboro",
        "ghostwhite",
        "gold",
        "goldenrod",
        "gray",
        "green",
        "greenyellow",
        "grey",
        "honeydew",
        "hotpink",
        "indianred",
        "indigo",
        "ivory",
        "khaki",
        "lavender",
        "lavenderblush",
        "lawngreen",
        "lemonchiffon",
        "lightblue",
        "lightcoral",
        "lightcyan",
        "lightgoldenrodyellow",
        "lightgray",
        "lightgreen",
        "lightgrey",
        "lightpink",
        "lightsalmon",
        "lightseagreen",
        "lightskyblue",
        "lightslategray",
        "lightslategrey",
        "lightsteelblue",
        "lightyellow",
        "lime",
        "limegreen",
        "linen",
        "magenta",
        "maroon",
        "mediumaquamarine",
        "mediumblue",
        "mediumorchid",
        "mediumpurple",
        "mediumseagreen",
        "mediumslateblue",
        "mediumspringgreen",
        "mediumturquoise",
        "mediumvioletred",
        "midnightblue",
        "mintcream",
        "mistyrose",
        "moccasin",
        "navajowhite",
        "navy",
        "oldlace",
        "olive",
        "olivedrab",
        "orange",
        "orangered",
        "orchid",
        "palegoldenrod",
        "palegreen",
        "paleturquoise",
        "palevioletred",
        "papayawhip",
        "peachpuff",
        "peru",
        "pink",
        "plum",
        "powderblue",
        "purple",
        "rebeccapurple",
        "red",
        "rosybrown",
        "royalblue",
        "saddlebrown",
        "salmon",
        "sandybrown",
        "seagreen",
        "seashell",
        "sienna",
        "silver",
        "skyblue",
        "slateblue",
        "slategray",
        "slategrey",
        "snow",
        "springgreen",
        "steelblue",
        "tan",
        "teal",
        "thistle",
        "tomato",
        "turquoise",
        "violet",
        "wheat",
        "white",
        "whitesmoke",
        "yellow",
        "yellowgreen",
        "transparent",
        "currentcolor",
    )
)
_GENERIC_FAMILIES = frozenset({"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-serif"})
_DECORATIONS = frozenset({"underline", "line-through", "overline"})


@dataclass(frozen=True)
class CssProblem:
    """One thing wrong with a piece of CSS: where (``line`` of a text, if there was one), which property, and what."""

    line: int | None
    property: str | None
    message: str

    def to_data(self) -> dict:
        """The plain-data form of the problem, as sent to clients."""
        return {"line": self.line, "property": self.property, "message": self.message}


class CssError(ValueError):
    """CSS that a style may not hold. ``problems`` lists everything that is wrong, each naming its property."""

    def __init__(self, problems: list[CssProblem]):
        super().__init__("; ".join(p.message for p in problems))
        self.problems = problems


class _Refused(Exception):
    """A value is not acceptable; the message says why (the property is added by the caller)."""


# --------------------------------------------------------------------------- value checks
def _color(value: str) -> str:
    if _HEX.fullmatch(value) or _COLOR_FUNCTION.fullmatch(value):
        return value
    if value.lower() in _COLOR_NAMES:
        return value.lower()
    raise _Refused("is not a colour (use #rrggbb, rgb(), hsl() or a colour name)")


def _length(value: str, *, lowest: float = 0.0, highest: float = _MAX_LENGTH, positive: bool = False) -> str:
    match = _LENGTH.fullmatch(value)
    if not match:
        raise _Refused("is not a length (like 12pt, 14px, 1.2em or 110%)")
    number = float(match.group(1))
    if match.group(2) is None and number != 0:
        raise _Refused("needs a unit (pt, px, em, rem or %)")
    if number < lowest or number > highest or (positive and number <= 0):
        low = "more than 0" if positive else f"{lowest:g}"
        raise _Refused(f"must be between {low} and {highest:g}")
    return value


def _size(value: str) -> str:
    return _length(value, positive=True)


def _spacing(value: str) -> str:
    return "normal" if value.lower() == "normal" else _length(value, lowest=-100, highest=100)


def _margin(value: str) -> str:
    return _length(value, lowest=-_MAX_LENGTH)


def _line_height(value: str) -> str:
    if value.lower() == "normal":
        return "normal"
    if _PLAIN_NUMBER.fullmatch(value):
        if not 0.5 <= float(value) <= 5:
            raise _Refused("must be between 0.5 and 5 when it has no unit")
        return value
    return _length(value, positive=True)


def _keywords(*allowed: str) -> Callable[[str], str]:
    def check(value: str) -> str:
        if value.lower() not in allowed:
            raise _Refused(f"must be one of {', '.join(allowed)}")
        return value.lower()

    return check


def _weight(value: str) -> str:
    low = value.lower()
    if low in {"normal", "bold", "bolder", "lighter"} or (
        low.isdigit() and low in {str(n) for n in range(100, 1000, 100)}
    ):
        return low
    raise _Refused("must be normal, bold, or 100 to 900 in steps of 100")


def _decoration(value: str) -> str:
    words = value.lower().split()
    if words == ["none"]:
        return "none"
    if not words or len(set(words)) != len(words) or not set(words) <= _DECORATIONS:
        raise _Refused("must be none, or some of underline, line-through, overline")
    return " ".join(words)


def _padding(value: str) -> str:
    return _length(value)


_BORDER = re.compile(rf"({_NUMBER}(?:px|pt|em|rem)?)\s+(solid|dashed|dotted|double)\s+(.+)", re.IGNORECASE)


def _border(value: str) -> str:
    """``none``, or ``<width> <style> <colour>`` like ``3px solid #D6477A``."""
    if value.lower() == "none":
        return "none"
    match = _BORDER.fullmatch(value)
    if not match:
        raise _Refused("must be none, or width, line and colour like 3px solid #D6477A")
    width = _length(match.group(1).lower(), highest=50)
    return f"{width} {match.group(2).lower()} {_color(match.group(3).strip())}"


def _paint(value: str) -> str:
    return "none" if value.lower() == "none" else _color(value)


def _stroke_width(value: str) -> str:
    return _length(value, highest=100)


def _family(value: str) -> str:
    parts = _split_families(value)
    if not parts or len(parts) > _MAX_FAMILIES:
        raise _Refused(f"needs one to {_MAX_FAMILIES} font names, separated by commas")
    for part in parts:
        low = part.lower()
        if not (_QUOTED_NAME.fullmatch(part) or _FAMILY_NAME.fullmatch(part) or low in _GENERIC_FAMILIES):
            raise _Refused(f"has a font name that is not allowed: {part[:30]!r} (names only, no urls or symbols)")
    return ", ".join(parts)


def _split_families(value: str) -> list[str]:
    """Split at commas outside quotes; an unclosed quote leaves a piece that no name rule accepts."""
    parts, current, quote = [], [], ""
    for char in value:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
            current.append(char)
        elif char == ",":
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append("".join(current).strip())
    return [p for p in parts if p] if all(parts) else [""]


#: Property -> the check that accepts a value and returns it in its clean form. The order of the entries is the
#: order in which ``format_css`` writes a style.
_CHECKS: dict[str, Callable[[str], str]] = {
    "font-family": _family,
    "font-size": _size,
    "font-weight": _weight,
    "font-style": _keywords("normal", "italic", "oblique"),
    "text-decoration": _decoration,
    "color": _color,
    "background-color": _color,
    "text-align": _keywords("left", "right", "center", "justify", "start", "end"),
    "line-height": _line_height,
    "letter-spacing": _spacing,
    "word-spacing": _spacing,
    "margin-top": _margin,
    "margin-right": _margin,
    "margin-bottom": _margin,
    "margin-left": _margin,
    "padding-top": _padding,
    "padding-right": _padding,
    "padding-bottom": _padding,
    "padding-left": _padding,
    "border-top": _border,
    "border-right": _border,
    "border-bottom": _border,
    "border-left": _border,
    "fill": _paint,
    "stroke": _paint,
    "stroke-width": _stroke_width,
}

#: The CSS properties a style may set (``CSS_VERSION``).
ALLOWED_CSS = frozenset(_CHECKS)
_ORDER = {name: place for place, name in enumerate(_CHECKS)}


# --------------------------------------------------------------------------- dictionaries
def _check_one(prop: str, value: object) -> str:
    check = _CHECKS.get(prop)
    if check is None:
        raise _Refused(f"“{prop}” is not a property a style can set")
    if not isinstance(value, str):
        raise _Refused("needs a text value")
    text = " ".join(value.split())
    if not text or len(text) > 200:
        raise _Refused("needs a value of up to 200 characters")
    if any(mark in text for mark in (";", "{", "}", "<", ">", "\\", "@", "!", "/*", "*/")):
        raise _Refused("has a character that is not allowed in a value")
    if re.search(r"url\s*\(|var\s*\(|calc\s*\(|expression\s*\(|image\s*\(|attr\s*\(|env\s*\(", text, re.IGNORECASE):
        raise _Refused("may not use url(), var(), calc() or other functions")
    return check(text)


def validate_css(css: Mapping[str, object]) -> dict[str, str]:
    """The same declarations in their clean form (keywords lower-cased, spaces collapsed); ``CssError`` lists every
    property that is not allowed or has a value that is not."""
    clean: dict[str, str] = {}
    problems: list[CssProblem] = []
    for prop, value in css.items():
        try:
            clean[prop] = _check_one(prop, value)
        except _Refused as why:
            text = str(why)
            message = text if text.startswith("“") else f"“{prop}” {text}"
            problems.append(CssProblem(None, prop, message))
    if problems:
        raise CssError(problems)
    return clean


# --------------------------------------------------------------------------- text
def _declarations(text: str) -> list[tuple[int, str]]:
    """The pieces of ``text`` between semicolons outside quotes, each with the line its first character is on."""
    pieces: list[tuple[int, str]] = []
    current: list[str] = []
    quote, line, start = "", 1, 0
    for char in text:
        if quote:
            current.append(char)
            quote = "" if char == quote else quote
        elif char == ";":
            pieces.append((start, "".join(current)))
            current, start = [], 0
        else:
            if char in "'\"":
                quote = char
            if not start and not char.isspace():
                start = line
            current.append(char)
        if char == "\n":
            line += 1
    pieces.append((start, "".join(current)))
    return [(number, piece.strip()) for number, piece in pieces if piece.strip()]


def parse_css(text: str) -> tuple[dict[str, str], list[CssProblem]]:
    """Read the text of a style. Returns what is valid and a problem for each line that is not: the dictionary can be
    used when there are no problems, and the problems say which line and which property to fix."""
    if len(text) > _MAX_TEXT:
        return {}, [CssProblem(None, None, f"A style can have at most {_MAX_TEXT} characters of CSS")]
    if "/*" in text or "*/" in text:
        return {}, [CssProblem(None, None, "Comments are not kept in a style, please remove them")]
    css: dict[str, str] = {}
    problems: list[CssProblem] = []
    for line, piece in _declarations(text):
        name, colon, value = piece.partition(":")
        prop = name.strip().lower()
        if not colon or not prop or not value.strip():
            problems.append(CssProblem(line, None, f"Line {line}: write it as “property: value”"))
            continue
        if prop in css:
            problems.append(CssProblem(line, prop, f"Line {line}: “{prop}” is set twice"))
            continue
        try:
            css[prop] = _check_one(prop, value)
        except _Refused as why:
            text_ = str(why)
            message = text_ if text_.startswith("“") else f"“{prop}” {text_}"
            problems.append(CssProblem(line, prop, f"Line {line}: {message}"))
    return css, problems


def format_css(css: Mapping[str, str]) -> str:
    """The text of a style: one ``property: value;`` per line, always in the same order."""
    ordered = sorted(css.items(), key=lambda item: (_ORDER.get(item[0], len(_ORDER)), item[0]))
    return "\n".join(f"{name}: {value};" for name, value in ordered)
