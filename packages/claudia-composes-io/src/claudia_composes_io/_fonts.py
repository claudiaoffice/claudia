"""The fonts of a file's styles, taken into a text's styles (E3.13, bug 1).

Each reader (:mod:`._docx_fonts`, :mod:`._odt_fonts`) finds the font the file gives the styles that map to the text's
own (body text, title, headings, quotation), from wherever the file says it; :func:`take_fonts` writes each into its
style as the font and its generic family. The stand-in a server shows for a font it lacks is not written: it is
chosen where the text is shown, so the text keeps asking for the font its file asked for, and an export names it.
"""

from __future__ import annotations

from collections.abc import Mapping

from claudia_composes import TextModel
from claudia_core.stand_ins import css_family


def take_fonts(model: TextModel, fonts: Mapping[str, str]) -> None:
    """Give each style of ``model`` named in ``fonts`` (style id to the font its file gives it) that font."""
    for style_id, family in fonts.items():
        if style_id in model.styles:
            css = model.styles.get(style_id).css
            model.styles.set_css(style_id, {**css, "font-family": css_family(family)})
