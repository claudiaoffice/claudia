"""The styles a workbook starts with (D62, D73, D75, E10.16).

A workbook's style book is the same :class:`~claudia_core.StyleBook` composes and creates hold, and is changed by
the same core commands (``CreateStyle``, ``ChangeStyle``, ``RenameStyle``). Today only the floating objects of a
sheet use it — an image, and the shapes and text boxes the shared object layer brings in; cell styling (E6.13) is
a separate story and will take its styles from this same book when it arrives.

Sizes are in pixels, matching the grid's own units. A shape says what it looks like with ``fill``, ``stroke`` and
``stroke-width``, not ``background-color`` and ``border-*`` (D178): a shape is an outline in a 100 by 100 box,
not a rectangle, so only the SVG vocabulary can give a circle or a triangle a border.
"""

from __future__ import annotations

from claudia_core import StyleBook, StyleDef

#: The id of the style everything else is based on.
DEFAULT_STYLE = "body-text"

_FONT = "Inter, system-ui, 'Segoe UI', sans-serif"
_INK = "#1F1A33"
_TEAL = "#2E7D74"
_MIST = "#E3EFED"


def _style(style_id: str, name: str, purpose: str, **css: str) -> StyleDef:
    return StyleDef(style_id, name, purpose, None if style_id == DEFAULT_STYLE else DEFAULT_STYLE, css)


#: The styles every workbook starts with, all based on Body text: a change to Body text reaches the others where
#: they have not set the property themselves (D73). The same three ids as in creates and composes, so an object
#: carried from one app to another keeps a style that exists there.
BUILTIN_STYLES: tuple[StyleDef, ...] = (
    _style(
        DEFAULT_STYLE,
        "Body text",
        "words in a floating text box or shape on a sheet",
        **{
            "color": _INK,
            "font-family": _FONT,
            "font-size": "13px",
            "line-height": "1.4",
            "text-align": "left",
        },
    ),
    _style(
        "plain-shape",
        "Plain shape",
        "a shape that marks or annotates a part of the sheet, without drawing attention to itself",
        **{
            "fill": _MIST,
            "stroke": _TEAL,
            "stroke-width": "2px",
            "text-align": "center",
        },
    ),
    _style(
        "plain-image",
        "Plain image",
        "a picture placed on the sheet; it carries its own colours, so no style properties apply to it",
    ),
)


def builtin_styles() -> StyleBook:
    """A new style book with the styles a workbook starts with."""
    return StyleBook(BUILTIN_STYLES)
