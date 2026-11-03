"""Styles: how objects look, named by what they are for (D62, D73).

A style is a name, a sentence about its purpose and a few CSS properties from a short allow-list. Nothing in a style
can reach outside the page: no ``url()``, no ``@import``, no script. The first draft ships two built-in styles and has
no style editor; every object refers to one of them by id, so that "how does this look" always has a name.
The styles live in the program, not in the document, until templates arrive (E10.4); a later release that changes
them restyles old documents.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The CSS properties a style may set. Widened on purpose, one property at a time, as the apps need them (D73).
ALLOWED_CSS = frozenset(
    {
        "color",
        "fill",
        "font-family",
        "font-size",
        "font-style",
        "font-weight",
        "letter-spacing",
        "line-height",
        "stroke",
        "stroke-width",
        "text-align",
    }
)

_FONT = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"


@dataclass(frozen=True)
class Style:
    """A named look: ``css`` holds allow-listed properties; sizes are in slide units (1 CSS pixel of the stage)."""

    id: str
    name: str
    purpose: str
    css: dict[str, str]

    def to_data(self) -> dict:
        """The plain-data form that is sent to clients."""
        return {"id": self.id, "name": self.name, "purpose": self.purpose, "css": dict(self.css)}


#: The styles every document can use, by id: ``body-text`` and ``plain-shape``.
BUILTIN_STYLES: dict[str, Style] = {
    "body-text": Style(
        id="body-text",
        name="Body text",
        purpose="Running text on a slide: sentences, short lists, captions.",
        css={
            "color": "#1F1A33",
            "font-family": _FONT,
            "font-size": "40px",
            "line-height": "1.3",
            "text-align": "left",
        },
    ),
    "plain-shape": Style(
        id="plain-shape",
        name="Plain shape",
        purpose="A shape that carries a thought or marks a part of the slide, without drawing attention to itself.",
        css={
            "fill": "#E7E1F4",
            "stroke": "#5B4BC4",
            "stroke-width": "4px",
            "color": "#1F1A33",
            "font-family": _FONT,
            "font-size": "36px",
            "line-height": "1.25",
            "text-align": "center",
        },
    ),
}
