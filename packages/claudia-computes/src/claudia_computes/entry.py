"""What a person typed into a cell, read as a value (the formulas come later and will use the same door)."""

from __future__ import annotations

import math
import re

from .model import Content, content_of

_INT = re.compile(r"[+-]?[0-9]+")
_FLOAT = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_INT_LIMIT = 2**53  # beyond this a float stores the number as exactly as the person can use it


def parse_input(text: str) -> Content:
    """The content that typing ``text`` makes.

    Nothing (or only blanks) empties the cell; a leading apostrophe keeps the rest as text (``'007``); TRUE and FALSE
    in any case are booleans; whole numbers are integers and decimals with a point or an exponent are floats; anything
    else, including a number the computer cannot hold, stays text."""
    if text.startswith("'"):
        return content_of(text[1:]) if len(text) > 1 else None
    word = text.strip()
    if not word:
        return None
    if word.upper() in ("TRUE", "FALSE"):
        return content_of(word.upper() == "TRUE")
    if _INT.fullmatch(word):
        whole = int(word)
        return content_of(whole if abs(whole) <= _INT_LIMIT else float(whole))
    if _FLOAT.fullmatch(word):
        number = float(word)
        if math.isfinite(number):
            return content_of(number)
    return content_of(text)
