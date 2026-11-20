"""The size a new picture or container is shown at, the same in all three apps (D1229, D1332, D1333).

A picture coming in from a file and the first picture of a rendered container (a formula, a diagram) have a size of
their own. They are shown at that size, but

1. no larger than *the most* a new object takes (420 × 240, D1229), so that an import does not fill the page;
2. no smaller than *the least*: as tall as the letters of the document's body text (D1332), so that a short formula is
   not lost next to the words. The least wins over the most;
3. no wider than *the room* it has, if the app knows one (the text column, the rest of the slide);
4. and no side below *the smallest* any object may be (``MIN_OBJECT_SIZE``), which the model checks on every object.

Every step keeps the picture's proportions: the height is decided, and the width is made from it, so that a picture
passes the model's check that its width is its height times its aspect within one unit.
"""

from __future__ import annotations

import math
import re

from .objects import MIN_OBJECT_SIZE

#: A browser's default font size, which ``em``, ``rem`` and ``%`` are taken against when nothing else is known.
BASE_FONT_PX = 16.0

_SIZE = re.compile(r"\s*([-+]?(?:\d+\.?\d*|\.\d+))(px|pt|em|rem|%)\s*")
_PX_PER = {"px": 1.0, "pt": 4.0 / 3.0}


def font_size_px(value: str | None, base: float = BASE_FONT_PX) -> float | None:
    """A CSS ``font-size`` (``12pt``, ``13px``, ``1.5em``, ``125%``) in pixels, which are the units objects are
    measured in, in every app; ``None`` for a value that is no length with a unit (a keyword, a bare number)."""
    found = _SIZE.fullmatch(value or "")
    if not found:
        return None
    number, unit = float(found.group(1)), found.group(2)
    if unit in _PX_PER:
        return number * _PX_PER[unit]
    return number * base / 100 if unit == "%" else number * base


def new_object_size(
    most_w: float,
    most_h: float,
    picture_w: float,
    picture_h: float,
    *,
    least: float,
    room: float | None = None,
    smallest: int = MIN_OBJECT_SIZE,
) -> tuple[int, int]:
    """The width and height to show a picture of ``picture_w`` × ``picture_h`` at, as a new object: within the most
    (``most_w`` × ``most_h``), at least ``least`` high, no wider than ``room`` (if given), no side below ``smallest``,
    in that order of precedence, and always with the picture's proportions (see the module)."""
    if picture_w <= 0 or picture_h <= 0:
        raise ValueError("a picture has a positive width and height")
    aspect = picture_w / picture_h
    height = picture_h * min(1.0, most_w / picture_w, most_h / picture_h)
    height = max(height, least)
    if room is not None:
        height = min(height, room / aspect)
    height = max(height, smallest, smallest / aspect)
    h = max(round(height), math.ceil(smallest / aspect - 1e-9), smallest)
    while room is not None and round(h * aspect) > room and h > smallest and round((h - 1) * aspect) >= smallest:
        h -= 1  # rounding up must not push it out of its room
    return round(h * aspect), h
