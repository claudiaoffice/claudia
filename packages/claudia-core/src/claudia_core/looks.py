"""What a style looks like in values a file format can hold: colours as red, green and blue and lengths as points
(D465). Shared by every converter that writes a style's fill, line or text into a file: the slides' (pptx, odp) and the
text's (docx, odt) floating boxes and shapes."""

from __future__ import annotations

import re

_HEX = re.compile(r"#([0-9a-fA-F]{6})\b")
_SHORT_HEX = re.compile(r"#([0-9a-fA-F]{3})\b")
_RGB_FUNCTION = re.compile(r"rgba?\(([^)]*)\)")
_NUMBER = re.compile(r"[\d.]+")


def points_of(css: dict[str, str], prop: str, pt_per_unit: float) -> float | None:
    """``css[prop]`` (CSS pixels, in the object's own space) as points at ``pt_per_unit`` a pixel, or ``None``."""
    value = css.get(prop)
    match = _NUMBER.search(value) if value else None
    return float(match.group()) * pt_per_unit if match else None


def colour_of(css: dict[str, str], prop: str, over: str | None = None) -> tuple[int, int, int] | None:
    """``css[prop]`` as red, green and blue, or ``None`` if it holds no colour this can read. Hexadecimal **and**
    ``rgb()``/``rgba()``, because a palette role at an opacity resolves to the latter; a translucent colour is
    composited over ``over`` (the colour of the page behind it)."""
    value = css.get(prop)
    if not value:
        return None
    parsed = parse_colour(value)
    if parsed is None:
        return None
    red, green, blue, alpha = parsed
    if alpha < 1:
        behind = parse_colour(over or "") or (255, 255, 255, 1.0)
        red, green, blue = (
            round(alpha * near + (1 - alpha) * far) for near, far in zip((red, green, blue), behind[:3], strict=True)
        )
    return red, green, blue


def parse_colour(value: str) -> tuple[int, int, int, float] | None:
    """``#rgb``, ``#rrggbb``, ``rgb(r, g, b)`` or ``rgba(r, g, b, a)`` as red, green, blue and opacity."""
    hex_match = _HEX.search(value)
    if hex_match:
        text = hex_match.group(1)
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), 1.0
    short = _SHORT_HEX.search(value)
    if short:
        text = short.group(1)
        return (*(int(char * 2, 16) for char in text), 1.0)  # type: ignore[return-value]
    func = _RGB_FUNCTION.search(value)
    if not func:
        return None
    parts = [part.strip() for part in func.group(1).split(",")]
    if len(parts) not in (3, 4):
        return None
    try:
        red, green, blue = (min(255, max(0, round(float(part)))) for part in parts[:3])
        alpha = min(1.0, max(0.0, float(parts[3]))) if len(parts) == 4 else 1.0
    except ValueError:
        return None
    return red, green, blue, alpha
