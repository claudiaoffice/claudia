"""The fonts of a pptx (E3.13, bug 2), the way PowerPoint finds them: a run's own Latin font (``a:latin``), else, for
a title placeholder, the theme's heading font, else the theme's body font -- what a text box and a body placeholder
inherit from the presentation's default text style and the master. A reference to a theme font (``+mj-lt``) is the
font the theme names."""

from __future__ import annotations

from typing import Any

from lxml import etree
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.opc.constants import RELATIONSHIP_TYPE

from claudia_opc_io import ThemeFonts

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_TITLES = (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE)


def deck_theme(prs: Any) -> ThemeFonts:  # noqa: ANN401
    """The fonts of the theme of the deck's first master; none for a deck without one."""
    try:
        return ThemeFonts.read(prs.slide_masters[0].part.part_related_by(RELATIONSHIP_TYPE.THEME).blob)
    except (IndexError, KeyError):
        return ThemeFonts(None, None)


def _run_fonts(shape: Any) -> list[str | None]:  # noqa: ANN401
    """The Latin font each run with words names of its own (``None`` for one that inherits), in order."""
    if not shape.has_text_frame:
        return []
    fonts = []
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            if run.text:
                latin = run._r.find(f"{_A}rPr/{_A}latin")  # noqa: SLF001 - python-pptx has no reader for it
                fonts.append(latin.get("typeface") if latin is not None else None)
    return fonts


def _inherited(shape: Any, theme: ThemeFonts) -> str | None:  # noqa: ANN401
    is_title = shape.is_placeholder and shape.placeholder_format.type in _TITLES
    return theme.major if is_title else theme.minor


def _shown(font: str | None, shape: Any, theme: ThemeFonts) -> str | None:  # noqa: ANN401
    """The font a run naming ``font`` (``None``: naming none) is shown in."""
    return (theme.named(font) if font else None) or _inherited(shape, theme)


def shape_font(shape: Any, theme: ThemeFonts) -> str | None:  # noqa: ANN401
    """The font the words of ``shape`` are in: its first run's, as PowerPoint shows it."""
    fonts = _run_fonts(shape)
    return _shown(fonts[0] if fonts else None, shape, theme)


def mixes_fonts(shape: Any, theme: ThemeFonts) -> bool:  # noqa: ANN401
    """Are the words of ``shape`` in more than one font? Only one can be its style's."""
    return len({_shown(font, shape, theme) for font in _run_fonts(shape)}) > 1


def write_body_font(prs: Any, family: str | None) -> None:  # noqa: ANN401
    """Make ``family`` the theme's body font of every master of ``prs`` (a deck written from nothing), so PowerPoint
    and an import both see the deck's body font where a body font is looked for (E3.13)."""
    if not family:
        return
    for master in prs.slide_masters:
        try:
            part = master.part.part_related_by(RELATIONSHIP_TYPE.THEME)
        except KeyError:
            continue
        root = etree.fromstring(part.blob)
        for latin in root.iterfind(f".//{_A}fontScheme/{_A}minorFont/{_A}latin"):
            latin.set("typeface", family)
        part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)  # noqa: SLF001
