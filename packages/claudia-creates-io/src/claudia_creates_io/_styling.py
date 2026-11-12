"""What a style looks like, resolved into values a file format can hold (shared by the pptx and the odp converter).

A style says ``fill: @accent/14`` and a palette role is not a colour a file can hold, so every converter *resolves*
first (D73, D200): its parents taken in, its palette roles turned into colours, a translucent colour flattened over
the slide's own colour (a solid fill has no alpha to put the opacity in; keeping the colour and dropping the opacity
would turn a 14% wash into full-strength iris)."""

from __future__ import annotations

import re

from claudia_creates import SlideModel

_HEX = re.compile(r"#([0-9a-fA-F]{6})\b")
_SHORT_HEX = re.compile(r"#([0-9a-fA-F]{3})\b")
_RGB_FUNCTION = re.compile(r"rgba?\(([^)]*)\)")
_NUMBER = re.compile(r"[\d.]+")


def points_of(css: dict[str, str], prop: str, pt_per_unit: float) -> float | None:
    """``css[prop]`` (CSS pixels, a unit of the slide's own 1600x900 space) as points, or ``None``."""
    value = css.get(prop)
    match = _NUMBER.search(value) if value else None
    return float(match.group()) * pt_per_unit if match else None


def colour_of(css: dict[str, str], prop: str, over: str | None = None) -> tuple[int, int, int] | None:
    """``css[prop]`` as red, green and blue, or ``None`` if it holds no colour this can read. Hexadecimal **and**
    ``rgb()``/``rgba()``, because a palette role at an opacity resolves to the latter; a translucent colour is
    composited over ``over`` (the slide's own colour)."""
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


def page_colour(model: SlideModel) -> str | None:
    """The slide's own colour, which a translucent fill is flattened over on the way into a file (see ``_rgb``)."""
    return model.palette.colours().get("page")


def look(model: SlideModel, style_id: str) -> dict[str, str]:
    """What a style really looks like, ready to write into a file: its parents taken in and its palette roles
    turned into colours (D73, D200).

    *Resolved*, not computed. A built-in style says ``fill: @accent/14``, and a role is not a colour a file format
    can hold: ``_rgb`` would find no hex in it and the fill would go missing without a word of complaint. The
    document's palette is what turns it into one.
    """
    if style_id not in model.styles:
        return {}
    return model.styles.resolved(style_id, model.palette.colours())
