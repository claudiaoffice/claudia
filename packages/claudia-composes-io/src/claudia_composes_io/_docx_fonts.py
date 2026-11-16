"""The fonts a docx gives its styles (E3.13, bug 1), the way Word finds them: a style's own ``w:rFonts``, else the
style it is based on, else the document defaults (``w:docDefaults``). Where ``w:rFonts`` refers to the theme
(``w:asciiTheme="minorHAnsi"``), the theme's font is meant, and it wins over a font named in the same element, as in
Word. Only the Latin font is read (``w:ascii``, ``w:hAnsi``)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml.ns import qn

from claudia_opc_io import ThemeFonts

_THEME_ATTRIBUTES = ("w:asciiTheme", "w:hAnsiTheme")
_FONT_ATTRIBUTES = ("w:ascii", "w:hAnsi")


def _theme(document: Any) -> ThemeFonts:  # noqa: ANN401
    try:
        return ThemeFonts.read(document.part.part_related_by(RELATIONSHIP_TYPE.THEME).blob)
    except KeyError:
        return ThemeFonts(None, None)


def _named(element: Any, theme: ThemeFonts) -> str | None:  # noqa: ANN401
    """The Latin font a ``w:rPr`` (or ``None``) names, if it names one."""
    fonts = element.find(qn("w:rFonts")) if element is not None else None
    if fonts is None:
        return None
    for attribute in _THEME_ATTRIBUTES:
        if (reference := fonts.get(qn(attribute))) and (found := theme.named(reference)):
            return found
    for attribute in _FONT_ATTRIBUTES:
        if name := (fonts.get(qn(attribute)) or "").strip():
            return name
    return None


def style_fonts(document: Any, word_names: Mapping[str, str]) -> dict[str, str]:  # noqa: ANN401
    """The font the file gives each style of ``word_names`` (a style id of the text to the name of its Word style),
    for those the file has; a style whose chain names no font and with no default font is left out."""
    theme = _theme(document)
    root = document.styles.element
    by_id = {s.get(qn("w:styleId")): s for s in root.findall(qn("w:style"))}
    defaults = root.find(f"{qn('w:docDefaults')}/{qn('w:rPrDefault')}/{qn('w:rPr')}")
    default = _named(defaults, theme)
    fonts: dict[str, str] = {}
    for style_id, word_name in word_names.items():
        try:
            style = document.styles[word_name].element
        except KeyError:
            continue
        found, seen = None, set()
        while style is not None and found is None and id(style) not in seen:
            seen.add(id(style))
            found = _named(style.find(qn("w:rPr")), theme)
            based = style.find(qn("w:basedOn"))
            style = by_id.get(based.get(qn("w:val"))) if based is not None else None
        if found := found or default:
            fonts[style_id] = found
    return fonts
