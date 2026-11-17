"""What a style looks like, resolved into values a file format can hold (shared by the pptx and the odp converter).

A style says ``fill: @accent/14`` and a palette role is not a colour a file can hold, so every converter *resolves*
first (D73, D200): its parents taken in, its palette roles turned into colours, a translucent colour flattened over
the slide's own colour (a solid fill has no alpha to put the opacity in; keeping the colour and dropping the opacity
would turn a 14% wash into full-strength iris)."""

from __future__ import annotations

from claudia_core import StyleDef
from claudia_core.looks import colour_of, parse_colour, points_of
from claudia_core.stand_ins import css_family
from claudia_creates import SlideModel

__all__ = [
    "colour_of",
    "is_bold",
    "look",
    "page_colour",
    "parse_colour",
    "points_of",
    "style_for_font",
    "take_body_font",
]


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


def is_bold(css: dict[str, str]) -> bool:
    """Do the words of a style say bold (``bold`` or a weight from 700)?"""
    return css.get("font-weight") in ("bold", "bolder", "700", "800", "900")


#: Why a style made on import for a font exists, until somebody names it for what it is for.
_PURPOSE_FONT = "words the file gave a font of their own: name it for what they are for"


def take_body_font(model: SlideModel, family: str | None, base: str = "body-text") -> None:
    """Give ``base`` (Body text) the deck's body font ``family``, if the file names one (E3.13)."""
    if family and base in model.styles:
        model.styles.set_css(base, {**model.styles.get(base).css, "font-family": css_family(family)})


def style_for_font(model: SlideModel, base: str, family: str | None) -> str:
    """The style for words based on ``base`` that a file sets in ``family`` (E3.13): ``base`` itself when it already
    shows that font (or the file names none), else a style of its own based on ``base``, made once per font and named
    by it ("Body text · Georgia") until somebody names it for its purpose, as an import names a look it cannot place
    (``to_name``)."""
    if not family or base not in model.styles:
        return base
    wanted = css_family(family)
    if model.styles.computed(base).get("font-family") == wanted:
        return base
    for style in model.styles:
        if style.based_on == base and style.to_name and style.css == {"font-family": wanted}:
            return style.id
    name = f"{model.styles.get(base).name} · {family.strip()}"
    candidate, number = name, 1
    while model.styles.name_taken(candidate):
        number += 1
        candidate = f"{name} ({number})"
    style_id = model.styles.unique_id(candidate)
    model.styles.add(StyleDef(style_id, candidate, _PURPOSE_FONT, base, {"font-family": wanted}, to_name=True))
    return style_id
