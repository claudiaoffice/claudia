"""The styles a presentation starts with (D62, D73, D75, E10.16).

A style is a :class:`~claudia_core.StyleDef` in the document's own :class:`~claudia_core.StyleBook`, exactly as in
composes: a name, a sentence about its purpose, a parent it is *based on*, and the few CSS properties in which it
differs from that parent. They are made by the model, not by commands, so they are in every log's past, and from
then on the core style commands (``CreateStyle``, ``ChangeStyle``, ``RenameStyle``) change them like any other
document state — a change is in the log, can be undone, and everybody sees it.

Nothing in a style can reach outside the page: the allow-list is ``claudia_core``'s ``ALLOWED_CSS``, with no
``url()``, no ``@import`` and no script.

How a shape says what it looks like
-----------------------------------
A shape is an outline in a 100 by 100 box (``claudia_core.shapes``) — a path, not a rectangle — so its
background is ``fill`` and its border is ``stroke`` plus ``stroke-width``, not ``background-color`` and
``border-*``. That is the one vocabulary for shapes in all three apps (D178): a triangle or a circle can carry a
border this way and cannot the other. A client's property dialog may of course call them "background" and
"border" in plain words.
"""

from __future__ import annotations

from claudia_core import ALLOWED_CSS, StyleBook, StyleDef  # noqa: F401  (ALLOWED_CSS re-exported, as always)

#: The id of the style everything else is based on.
DEFAULT_STYLE = "body-text"

# The same stack composes uses. ``-apple-system`` is deliberately not in it: ``ALLOWED_CSS`` refuses a font name
# starting with a hyphen, and creates' own built-in styles never went through ``validate_css`` before E10.16, so
# nothing caught it.
_FONT = "Inter, system-ui, 'Segoe UI', sans-serif"
_INK = "#1F1A33"
_IRIS = "#5B4BC4"
_MIST = "#E7E1F4"


def _style(style_id: str, name: str, purpose: str, **css: str) -> StyleDef:
    return StyleDef(style_id, name, purpose, None if style_id == DEFAULT_STYLE else DEFAULT_STYLE, css)


#: The styles every presentation starts with, all based on Body text: a change to Body text reaches the others
#: where they have not set the property themselves (D73). Sizes are in slide units (1 unit = 1 CSS pixel of the
#: 1600 by 900 stage).
BUILTIN_STYLES: tuple[StyleDef, ...] = (
    _style(
        DEFAULT_STYLE,
        "Body text",
        "running text on a slide: sentences, short lists, captions",
        **{
            "color": _INK,
            "font-family": _FONT,
            "font-size": "40px",
            "line-height": "1.3",
            "text-align": "left",
        },
    ),
    _style(
        "plain-shape",
        "Plain shape",
        "a shape that carries a thought or marks a part of the slide, without drawing attention to itself",
        **{
            "fill": _MIST,
            "stroke": _IRIS,
            "stroke-width": "4px",
            "font-size": "36px",
            "line-height": "1.25",
            "text-align": "center",
        },
    ),
    _style(
        "plain-image",
        "Plain image",
        "a picture placed on the slide; it carries its own colours, so no style properties apply to it",
    ),
)


def builtin_styles() -> StyleBook:
    """A new style book with the styles a presentation starts with."""
    return StyleBook(BUILTIN_STYLES)
