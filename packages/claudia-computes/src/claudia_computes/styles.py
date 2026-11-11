"""The styles a workbook starts with (D62, D73, D75, E10.16).

A workbook's style book is the same :class:`~claudia_core.StyleBook` composes and creates hold, and is changed by
the same core commands (``CreateStyle``, ``ChangeStyle``, ``RenameStyle``). Today only the floating objects of a
sheet use it — an image, and the shapes and text boxes the shared object layer brings in; cell styling (E6.13) is
a separate story and will take its styles from this same book when it arrives.

Sizes are in pixels, matching the grid's own units. A shape says what it looks like with ``fill``, ``stroke`` and
``stroke-width``, not ``background-color`` and ``border-*`` (D178): a shape is an outline in a 100 by 100 box,
not a rectangle, so only the SVG vocabulary can give a circle or a triangle a border. Its outline and its words are
two slots with a style each, ``plain-shape`` (an ``outline`` style) and ``shape-label`` (D304, D310).
"""

from __future__ import annotations

from claudia_core import StyleBook, StyleDef

#: The id of the style everything else is based on.
DEFAULT_STYLE = "body-text"

_FONT = "Inter, system-ui, 'Segoe UI', sans-serif"

# Colours are roles of the document's palette, never literals (D200). A workbook's plain shape used to be teal
# where a slide's and a text's were iris; there is one object layer and one palette now, so all three say
# ``@accent`` and a shape carried between the apps keeps looking like itself.
_INK = "@text"
_ACCENT = "@accent"
_MIST = "@accent/14"


def _style(style_id: str, name: str, purpose: str, *, kind: str = "paragraph", **css: str) -> StyleDef:
    # A paragraph style is based on Body text, so a change to Body text reaches it (D73); a box or outline style is
    # a root of its own, because a style and its parent are always of the same kind (D305).
    parent = DEFAULT_STYLE if kind == "paragraph" and style_id != DEFAULT_STYLE else None
    return StyleDef(style_id, name, purpose, parent, css, kind=kind)


#: The styles every workbook starts with. The paragraph styles are based on Body text: a change to Body text
#: reaches the others where they have not set the property themselves (D73); the outline and the picture's box are
#: styles of their own kinds (D305). The same three ids as in creates and composes, so an object
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
        "shape-label",
        "Shape label",
        "the words inside a shape on a sheet",
        **{"text-align": "center"},
    ),
    _style(
        "plain-shape",
        "Plain shape",
        "a shape that marks or annotates a part of the sheet, without drawing attention to itself",
        kind="outline",
        **{
            "fill": _MIST,
            "stroke": _ACCENT,
            "stroke-width": "2px",
        },
    ),
    _style(
        "plain-box",
        "Plain box",
        "the box of a text box on a sheet: no background and no border, so only its words show",
        kind="box",
    ),
    # The cell styles (D313): named by what a cell is *for*, written in palette roles, all based on Body text, which
    # is also what a cell has when no style range says otherwise. Each is a bundle (D309): applying one fills both
    # slots of a cell, its box reading the background and borders, its words the rest (D311, D316).
    _style(
        "header",
        "Header",
        "the labels at the top of a table or the start of a row",
        **{
            "font-weight": "600",
            "background-color": "@accent/14",
            "border-bottom": "1px solid @accent",
        },
    ),
    _style(
        "input",
        "Input",
        "a number someone is meant to change: an assumption of the model",
        **{
            "color": "@accent",
            "background-color": "@highlight/14",
        },
    ),
    _style(
        "result",
        "Result",
        "a number the model works out and someone reads",
        **{
            "font-weight": "600",
            "border-top": "1px solid @structure",
        },
    ),
    _style(
        "note",
        "Note",
        "a remark beside the numbers",
        **{
            "font-style": "italic",
            "color": "@muted",
        },
    ),
    _style(
        "plain-image",
        "Plain image",
        "a picture placed on the sheet; it carries its own colours, so no style properties apply to it",
        kind="box",
    ),
)


def builtin_styles() -> StyleBook:
    """A new style book with the styles a workbook starts with."""
    return StyleBook(BUILTIN_STYLES)
