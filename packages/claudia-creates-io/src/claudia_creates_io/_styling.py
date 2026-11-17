"""What a style looks like, resolved into values a file format can hold (shared by the pptx and the odp converter).

A style says ``fill: @accent/14`` and a palette role is not a colour a file can hold, so every converter *resolves*
first (D73, D200): its parents taken in, its palette roles turned into colours, a translucent colour flattened over
the slide's own colour (a solid fill has no alpha to put the opacity in; keeping the colour and dropping the opacity
would turn a 14% wash into full-strength iris)."""

from __future__ import annotations

from claudia_core.looks import colour_of, parse_colour, points_of
from claudia_creates import BUILTIN_STYLES, SlideModel

__all__ = ["colour_of", "is_bold", "look", "page_colour", "parse_colour", "points_of", "written_family"]


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


_BUILTIN_FAMILY = BUILTIN_STYLES[0].css["font-family"]


def is_bold(css: dict[str, str]) -> bool:
    """Do the words of a style say bold (``bold`` or a weight from 700)?"""
    return css.get("font-weight") in ("bold", "bolder", "700", "800", "900")


def written_family(css: dict[str, str]) -> str | None:
    """The first font a style names, as a file says it (a name, quoted when it holds a space), or ``None`` when it
    names the stack every built-in style has: that is no choice anybody made, and a file does not need to say it."""
    families = css.get("font-family", "")
    if not families or families == _BUILTIN_FAMILY:
        return None
    first = families.split(",")[0].strip().strip("'\"")
    return f"'{first}'" if " " in first else first
