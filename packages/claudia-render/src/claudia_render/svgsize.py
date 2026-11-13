"""How big a picture is and what to say about it, read from the SVG itself (D344).

A document needs a picture's size to give an object its first shape, and a person who cannot see it needs a sentence.
Both come from the SVG, which every plugin delivers (the narrow waist of D341), so no plugin has to report them."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # noqa: S405 - the picture was checked (no DOCTYPE) before it got here

#: Larger than any page a document holds; a picture beyond this is a mistake or an attack.
MAX_SIDE_PX = 20_000.0
MAX_ALT_CHARS = 200

_LENGTH = re.compile(r"\s*([0-9]*\.?[0-9]+)\s*(px|pt|mm|cm|in|pc)?\s*")
_PX_PER = {None: 1.0, "px": 1.0, "pt": 96 / 72, "pc": 16.0, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96.0}


def _length(value: str | None) -> float | None:
    found = _LENGTH.fullmatch(value) if value else None
    return float(found[1]) * _PX_PER[found[2]] if found else None


def _view_box(value: str | None) -> tuple[float, float] | None:
    parts = re.split(r"[\s,]+", value.strip()) if value else []
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        return None
    return (numbers[2], numbers[3]) if len(numbers) == 4 else None


def svg_size(svg: str) -> tuple[float, float]:
    """The width and height of ``svg`` in pixels (96 per inch): its own lengths, else its view box.

    ``ValueError`` (naming the size) if neither says a usable size."""
    try:
        root = ET.fromstring(svg)  # noqa: S314 - see the import
    except ET.ParseError as error:
        raise ValueError(f"the picture has no size: it is not valid XML ({error})") from error
    width, height = _length(root.get("width")), _length(root.get("height"))
    if width is None or height is None:
        box = _view_box(root.get("viewBox"))
        width, height = box if box else (None, None)
    if width is None or height is None or not 0 < width <= MAX_SIDE_PX or not 0 < height <= MAX_SIDE_PX:
        raise ValueError("the picture has no usable size (at most 20000 pixels a side)")
    return round(width, 3), round(height, 3)


def default_alt(kind: str, source: str, svg: str) -> str:
    """The sentence for somebody who cannot see the picture: its own title, else the kind and its first words."""
    try:
        for element in ET.fromstring(svg).iter("{http://www.w3.org/2000/svg}title"):  # noqa: S314
            if element.text and element.text.strip():
                return " ".join(element.text.split())[:MAX_ALT_CHARS]
    except ET.ParseError:
        pass
    return f"{kind}: {' '.join(source.split())}"[:MAX_ALT_CHARS]
