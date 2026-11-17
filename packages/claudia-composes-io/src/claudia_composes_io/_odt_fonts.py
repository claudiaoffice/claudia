"""The fonts an odt gives its styles (E3.13, bug 1), the way LibreOffice finds them: a paragraph style's own text
properties (a font face by ``style:font-name``, or ``fo:font-family``), else the style it is based on, else the
default style of paragraphs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from lxml import etree

from claudia_odf_io import NS, font_faces, font_of, qname

_FAMILY, _NAME, _PARENT = qname("style:family"), qname("style:name"), qname("style:parent-style-name")


def style_fonts(roots: Iterable[etree._Element | None], odf_names: Mapping[str, Iterable[str]]) -> dict[str, str]:
    """The font the file gives each style of ``odf_names`` (a style id of the text to the names of the file's styles
    that are it, the first one the file has counting), for those the file has; ``roots`` are ``content.xml`` and
    ``styles.xml``."""
    present = [root for root in roots if root is not None]
    faces = font_faces(*present)
    styles: dict[str, etree._Element] = {}
    default = None
    for root in present:
        for style in root.iter(qname("style:style")):
            if style.get(_FAMILY) == "paragraph" and (name := style.get(_NAME)):
                styles.setdefault(name, style)
        for style in root.iter(qname("style:default-style")):
            if style.get(_FAMILY) == "paragraph" and default is None:
                default = font_of(style.find("style:text-properties", NS), faces)
    fonts: dict[str, str] = {}
    for style_id, names in odf_names.items():
        name = next((n for n in names if n in styles), None)
        if name is None:
            continue
        found, seen = None, set()
        while name and name in styles and name not in seen and found is None:
            seen.add(name)
            found = font_of(styles[name].find("style:text-properties", NS), faces)
            name = styles[name].get(_PARENT)
        if found := found or default:
            fonts[style_id] = found
    return fonts
