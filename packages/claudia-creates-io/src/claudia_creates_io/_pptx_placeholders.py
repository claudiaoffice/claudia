"""The placeholders of a pptx slide that hold the slide's own words (CODE-45): its title, its subtitle and its body,
as PowerPoint makes nearly every slide from a layout. They come in as text boxes in the place and size their layout
gives them. A footer, a date or a slide number is the master's, not the slide's, and stays in the file, and so does a
placeholder that holds a picture, a table or a chart. A placeholder with no words shows nothing in a show."""

from __future__ import annotations

from typing import Any

from lxml import etree
from pptx.enum.shapes import PP_PLACEHOLDER

TITLES = (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE)
_FOR_WORDS = (*TITLES, PP_PLACEHOLDER.SUBTITLE, PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT)
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def for_words(shape: Any) -> bool:  # noqa: ANN401 (python-pptx's own shape classes are not one type)
    """Is ``shape`` a placeholder for the slide's own words (with words in it or not)?"""
    return shape.is_placeholder and shape.has_text_frame and shape.placeholder_format.type in _FOR_WORDS


def list_styles(shape: Any) -> tuple[etree._Element, ...]:  # noqa: ANN401
    """The list styles the paragraphs of ``shape`` take their look from, nearest first: for a placeholder, the
    ``a:lstStyle`` of its layout's and its master's placeholder and the master's title or body style. A text box
    takes its look from the deck's default style, which has no bullet: none."""
    if not shape.is_placeholder:
        return ()
    found = []
    base = shape
    while (base := getattr(base, "_base_placeholder", None)) is not None:
        style = base._element.find(f"{_P}txBody/{_A}lstStyle")  # noqa: SLF001
        if style is not None:
            found.append(style)
    master = shape.part.slide.slide_layout.slide_master._element  # noqa: SLF001
    kind = "titleStyle" if shape.placeholder_format.type in TITLES else "bodyStyle"
    style = master.find(f"{_P}txStyles/{_P}{kind}")
    return (*found, style) if style is not None else tuple(found)
