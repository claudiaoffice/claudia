"""The fonts of an Office theme (E3.13), which docx and pptx files share: a theme (``word/theme/theme1.xml``,
``ppt/theme/theme1.xml``) names a heading font (``a:majorFont``) and a body font (``a:minorFont``), and a style or a
run that does not name a font of its own refers to one of them -- Word as ``majorHAnsi`` or ``minorAscii``, PowerPoint
as ``+mj-lt`` or ``+mn-lt``. Only the Latin fonts are read: the fonts of other scripts are not modelled.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
#: How each notation refers to a Latin theme font: ``True`` for the heading font, ``False`` for the body font.
_REFERENCES = {
    "+mj-lt": True,
    "+mn-lt": False,
    "majorHAnsi": True,
    "majorAscii": True,
    "minorHAnsi": False,
    "minorAscii": False,
}


@dataclass(frozen=True)
class ThemeFonts:
    """The heading font (``major``) and body font (``minor``) of a theme, ``None`` where it names none."""

    major: str | None
    minor: str | None

    @classmethod
    def read(cls, theme_xml: bytes | None) -> ThemeFonts:
        """The fonts of a theme part; a missing or empty theme names none."""
        if not theme_xml:
            return cls(None, None)
        root = ElementTree.fromstring(theme_xml)  # noqa: S314 - expat refuses external entities and entity bombs

        def latin(kind: str) -> str | None:
            found = root.find(f".//{_A}fontScheme/{_A}{kind}/{_A}latin")
            name = (found.get("typeface") or "").strip() if found is not None else ""
            return name or None

        return cls(latin("majorFont"), latin("minorFont"))

    def named(self, reference: str | None) -> str | None:
        """The font ``reference`` names: a theme font by either notation, or ``reference`` itself if it is a font's
        name. ``None`` for nothing, or for a theme font of another script (``+mn-ea``) or one the theme lacks."""
        if not reference:
            return None
        if reference in _REFERENCES:
            return self.major if _REFERENCES[reference] else self.minor
        if reference.startswith("+") or reference.endswith(("Bidi", "EastAsia")):
            return None
        return reference
