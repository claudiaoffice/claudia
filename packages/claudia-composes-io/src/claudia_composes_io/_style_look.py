"""What a style looks like, in the units and words that office files use (D455).

A style of the model holds CSS (D62): lengths in ``pt``, ``px`` or ``em``, colours that may be translucent, a list of
font families. A file holds absolute lengths, one font, and colours without opacity. :func:`look_of` turns the CSS a
style sets (its palette roles already replaced by colours, :meth:`claudia_core.StyleBook.resolved`) into a
:class:`Look` that the writers of both formats read; what a file cannot say is named in ``Look.unsaid`` and becomes a
loss."""

from __future__ import annotations

import colorsys
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from claudia_core import StyleBook
from claudia_core.css import resolve_css

_NUMBER = r"-?(?:\d+\.?\d*|\.\d+)"
_LENGTH = re.compile(rf"({_NUMBER})(pt|px|em|rem|cm|mm|in|%)?")
_FUNCTION = re.compile(r"(rgba?|hsla?)\(\s*([^)]*)\)", re.IGNORECASE)
_PX = 0.75  # points in a CSS pixel
_REM = 12.0  # points in a rem: the size of body text
_SIDES = ("top", "right", "bottom", "left")
_GENERIC = {"serif": "Liberation Serif", "sans-serif": "Liberation Sans", "monospace": "Liberation Mono"}
_NAMED = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "transparent": None,
}
_WEIGHTS = {"normal": 400, "bold": 700}
_ROOT_SIZE = 12.0  # points: what a text is set in when no style says
_NOT_FOR_TEXT = ("word-spacing", "vertical-align", "white-space")


def points(value: str, *, font_size: float, percent_of: float | None = None) -> float | None:
    """``value`` (``"12pt"``, ``"0.9em"``, ``"0"``, ``"110%"``) in points, or ``None`` when it is none we can say: an
    ``em`` is that many times ``font_size``, a percentage that share of ``percent_of`` (``None``: not a length)."""
    found = _LENGTH.fullmatch(value.strip())
    if not found:
        return None
    number, unit = float(found.group(1)), found.group(2)
    if unit is None or unit == "pt":
        return number
    if unit == "%":
        return None if percent_of is None else number * percent_of / 100
    factors = {"px": _PX, "em": font_size, "rem": _REM, "cm": 72 / 2.54, "mm": 72 / 25.4, "in": 72.0}
    return number * factors[unit]


def colour_of(value: str) -> tuple[str, float] | None:
    """The colour ``value`` is as ``#rrggbb`` and how opaque it is (1 for an ordinary colour), or ``None`` for a colour
    that is none we know (a named colour that is not one of the plain ones) or that is nothing (``transparent``)."""
    text = value.strip().lower()
    if text.startswith("#"):
        digits = text[1:]
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits)
        if len(digits) not in (6, 8) or any(c not in "0123456789abcdef" for c in digits):
            return None
        alpha = int(digits[6:], 16) / 255 if len(digits) == 8 else 1.0
        return f"#{digits[:6].upper()}", alpha
    if (found := _FUNCTION.fullmatch(text)) is not None:
        return _from_function(found.group(1), re.split(r"[\s,/]+", found.group(2).strip()))
    named = _NAMED.get(text)
    return None if named is None else (_hex(*named), 1.0)


def _from_function(kind: str, parts: list[str]) -> tuple[str, float] | None:
    try:
        numbers = [float(p.rstrip("%deg")) if p.rstrip("%deg") else 0.0 for p in parts]
    except ValueError:
        return None
    if len(numbers) < 3:
        return None
    alpha = numbers[3] / (100 if parts[3].endswith("%") else 1) if len(numbers) > 3 else 1.0
    if kind.startswith("rgb"):
        red, green, blue = (
            round(n * 255 / 100) if p.endswith("%") else round(n) for n, p in zip(numbers[:3], parts, strict=False)
        )
    else:
        red, green, blue = (
            round(c * 255) for c in colorsys.hls_to_rgb((numbers[0] % 360) / 360, numbers[2] / 100, numbers[1] / 100)
        )
    if any(not 0 <= c <= 255 for c in (red, green, blue)):
        return None
    return f"#{red:02X}{green:02X}{blue:02X}", max(0.0, min(alpha, 1.0))


def _hex(red: int, green: int, blue: int) -> str:
    return f"#{red:02X}{green:02X}{blue:02X}"


def over_white(value: str) -> str | None:
    """``value`` as the opaque colour it shows as on a white page (a file has no opacity for text and paper)."""
    found = colour_of(value)
    if found is None:
        return None
    colour, alpha = found
    mixed = [round(255 - (255 - int(colour[i : i + 2], 16)) * alpha) for i in (1, 3, 5)]
    return _hex(*mixed)


@dataclass(frozen=True)
class Border:
    """One side of a box: its width in points, the line (``solid``, ``dashed``, ``dotted``, ``double``) and colour."""

    width: float
    line: str
    colour: str


@dataclass
class Look:
    """The properties of a style in the words of a file: every length in points, colours as ``#RRGGBB``. A property
    the style does not set is ``None`` (or absent), so that it is inherited in the file as it is in the model."""

    family: str | None = None
    size: float | None = None
    weight: int | None = None
    italic: bool | None = None
    underline: bool | None = None
    strike: bool | None = None
    colour: str | None = None
    spacing: float | None = None
    align: str | None = None
    #: A multiple of the font size, or a height in points when ``line_fixed``.
    line: float | None = None
    line_fixed: bool = False
    margins: dict[str, float] = field(default_factory=dict)
    padding: dict[str, float] = field(default_factory=dict)
    borders: dict[str, Border | None] = field(default_factory=dict)
    background: str | None = None
    hyphenate: bool | None = None
    #: Properties the style sets that the file cannot say.
    unsaid: list[str] = field(default_factory=list)


def _family(value: str) -> str | None:
    for part in (p.strip() for p in value.split(",")):
        name = part.strip("'\"")
        if not name:
            continue
        low = name.lower()
        if low in _GENERIC:
            return _GENERIC[low]
        if low not in {"system-ui", "ui-serif", "cursive", "fantasy"}:
            return name
    return None


def _weight(value: str) -> int | None:
    low = value.lower()
    if low in _WEIGHTS:
        return _WEIGHTS[low]
    return int(low) if low.isdigit() else None


def look_of(css: Mapping[str, str], *, font_size: float, parent_size: float) -> Look:
    """The look of the CSS ``css`` (what one style sets, palette roles replaced), when its own font size is
    ``font_size`` points (the size of the style as it is, with its parents' words) and its parent's is ``parent_size``.
    Lengths in ``em`` follow ``font_size``, but the size itself follows the parent's."""
    look = Look()
    for prop, value in css.items():
        if prop in _NOT_FOR_TEXT or not _apply(look, prop, value, font_size, parent_size):
            look.unsaid.append(prop)
    return look


def _apply(look: Look, prop: str, value: str, font_size: float, parent_size: float) -> bool:  # noqa: PLR0911, PLR0912
    """Put one property into ``look``; ``False`` when the file cannot say it."""
    if prop == "font-family":
        look.family = _family(value)
        return look.family is not None
    if prop == "font-size":
        look.size = points(value, font_size=parent_size, percent_of=parent_size)
        return look.size is not None
    if prop == "font-weight":
        look.weight = _weight(value)
        return look.weight is not None
    if prop == "font-style":
        look.italic = value != "normal"
        return True
    if prop == "text-decoration":
        look.underline, look.strike = "underline" in value, "line-through" in value
        return "overline" not in value
    if prop == "color":
        look.colour = over_white(value)
        return look.colour is not None
    if prop == "background-color":
        look.background = over_white(value)
        return look.background is not None
    if prop == "letter-spacing":
        look.spacing = 0.0 if value == "normal" else points(value, font_size=font_size)
        return look.spacing is not None
    if prop == "text-align":
        look.align = {"start": "left", "end": "right"}.get(value, value)
        return True
    if prop == "line-height":
        return _line(look, value, font_size)
    if prop == "hyphens":
        look.hyphenate = value == "auto"
        return True
    side = prop.rsplit("-", 1)[-1]
    if prop.startswith(("margin-", "padding-")) and side in _SIDES:
        found = points(value, font_size=font_size)
        if found is not None:
            (look.margins if prop.startswith("margin") else look.padding)[side] = found
        return found is not None
    if prop.startswith("border-") and side in _SIDES:
        return _border(look, side, value, font_size)
    return False


def _line(look: Look, value: str, font_size: float) -> bool:
    if value == "normal":
        look.line, look.line_fixed = 1.0, False
        return True
    if re.fullmatch(_NUMBER, value):
        look.line, look.line_fixed = float(value), False
        return True
    if value.endswith("%"):
        look.line, look.line_fixed = float(value[:-1]) / 100, False
        return True
    if value.endswith("em") or value.endswith("rem"):
        found = points(value, font_size=font_size)
        look.line, look.line_fixed = (found / font_size if found is not None else None), False
        return found is not None
    found = points(value, font_size=font_size)
    look.line, look.line_fixed = found, True
    return found is not None


def _border(look: Look, side: str, value: str, font_size: float) -> bool:
    if value == "none":
        look.borders[side] = None
        return True
    width, line, colour = value.split(None, 2)
    size, paint = points(width, font_size=font_size), over_white(colour)
    if size is None or paint is None:
        return False
    look.borders[side] = Border(size, line, paint)
    return True


def size_of(book: StyleBook, style_id: str, colours: dict[str, str]) -> float:
    """The font size, in points, that a style is set in once its parents have been taken in."""
    size = _ROOT_SIZE
    for style in book.chain(style_id):
        value = resolve_css(style.css, colours).get("font-size")
        if value is not None:
            size = points(value, font_size=size, percent_of=size) or size
    return size


def look_for(book: StyleBook, style_id: str, colours: dict[str, str]) -> Look:
    """The look the style sets by itself: what differs from its parent, as a file says it."""
    style = book.get(style_id)
    parent = size_of(book, style.based_on, colours) if style.based_on else _ROOT_SIZE
    return look_of(resolve_css(style.css, colours), font_size=size_of(book, style_id, colours), parent_size=parent)
