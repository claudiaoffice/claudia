"""The fonts of an odp (E3.13, bug 2), the way LibreOffice finds them. The deck's body font is the font of the default
style of drawn things (``style:default-style`` of family ``graphic``, else ``presentation``). The words of a text box
are in the font of the first text style of their spans, else of their paragraph's style, else of the box's own style
(its ``presentation:style-name``, else its ``draw:style-name``), each with what it is based on, else the body font.

A font named by a text style is not a loss: it is what the words' style shows. Only words in two fonts in one box are
(``formatting``), as only one font per box is modelled.
"""

from __future__ import annotations

from lxml import etree

from claudia_odf_io import NS, font_faces, font_of, read_text

#: What a text style may say and still be no more than a font: the font, in the ways a file can name it.
_FONT_ONLY = {
    f"{{{NS['style']}}}font-name",
    f"{{{NS['fo']}}}font-family",
    f"{{{NS['style']}}}font-family-generic",
    f"{{{NS['style']}}}font-pitch",
}


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


class DeckFonts:
    """The fonts the styles of a deck name, read once from both parts (``content.xml`` and ``styles.xml``)."""

    def __init__(self, content: etree._Element, styles: etree._Element | None) -> None:
        self._faces = font_faces(content, styles)
        self._styles: dict[tuple[str, str], etree._Element] = {}
        self._defaults: dict[str, etree._Element] = {}
        for root in (content, styles):
            if root is None:
                continue
            for style in root.iter(_q("style", "style")):
                key = (style.get(_q("style", "family")) or "", style.get(_q("style", "name")) or "")
                self._styles.setdefault(key, style)
            for default in root.iter(_q("style", "default-style")):
                self._defaults.setdefault(default.get(_q("style", "family")) or "", default)

    def _own(self, style: etree._Element | None) -> str | None:
        if style is None:
            return None
        return font_of(style.find("style:text-properties", NS), self._faces)

    def of_style(self, family: str, name: str | None) -> str | None:
        """The font a style of ``family`` names, itself or through what it is based on; ``None`` if none does."""
        seen: set[str] = set()
        while name and name not in seen and (family, name) in self._styles:
            seen.add(name)
            style = self._styles[family, name]
            found = self._own(style)
            if found:
                return found
            name = style.get(_q("style", "parent-style-name"))
        return None

    @property
    def body(self) -> str | None:
        """The deck's body font: what its default style of drawn things names."""
        return self._own(self._defaults.get("graphic")) or self._own(self._defaults.get("presentation"))

    def _spans(self, paragraphs: list[etree._Element]) -> list[str | None]:
        """The font each piece of words with text names of its own, through its span's text style, in order."""
        fonts: list[str | None] = []
        for paragraph in paragraphs:
            own = self.of_style("paragraph", paragraph.get(_q("text", "style-name")))
            if (paragraph.text or "").strip():
                fonts.append(own)
            fonts.extend(
                self.of_style("text", span.get(_q("text", "style-name"))) or own
                for span in paragraph.iter(_q("text", "span"))
                if read_text(span).strip()
            )
        return fonts

    def _box(self, element: etree._Element) -> str | None:
        return (
            self.of_style("presentation", element.get(_q("presentation", "style-name")))
            or self.of_style("graphic", element.get(_q("draw", "style-name")))
            or self.body
        )

    def of_object(self, element: etree._Element, paragraphs: list[etree._Element]) -> str | None:
        """The font the words of a drawn thing are shown in: the first of their own, else the box's."""
        return next((font for font in self._spans(paragraphs) if font), None) or self._box(element)

    def mixes(self, element: etree._Element, paragraphs: list[etree._Element]) -> bool:
        """Whether the words of a drawn thing are in more than one font."""
        box = self._box(element)
        return len({font or box for font in self._spans(paragraphs)}) > 1

    def only_a_font(self, name: str | None) -> bool:
        """Whether a text style says nothing but a font (itself and what it is based on)."""
        seen: set[str] = set()
        said = False
        while name and name not in seen and ("text", name) in self._styles:
            seen.add(name)
            style = self._styles["text", name]
            for props in style.findall("style:text-properties", NS):
                if set(props.attrib) - _FONT_ONLY:
                    return False
                said = said or bool(props.attrib)
            name = style.get(_q("style", "parent-style-name"))
        return said
