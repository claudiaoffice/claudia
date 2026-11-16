"""The fonts of an OpenDocument file (E3.13): a style's text properties name a font either by a font face of the file
(``style:font-name``, declared in ``office:font-face-decls`` with its family in ``svg:font-family``) or by a CSS-like
family list (``fo:font-family``). Only the Latin font is read: ``style:font-name-asian`` and ``-complex`` are not
modelled.
"""

from __future__ import annotations

from lxml import etree

from .names import qname


def _first(families: str) -> str | None:
    for part in families.split(","):
        name = part.strip().strip("'\"").strip()
        if name:
            return name
    return None


def font_faces(*roots: etree._Element | None) -> dict[str, str]:
    """Every font face declared in ``roots`` (``content.xml``, ``styles.xml``), its name to its family, unquoted. The
    first declaration of a name wins."""
    faces: dict[str, str] = {}
    for root in roots:
        if root is None:
            continue
        for face in root.iter(qname("style:font-face")):
            name = face.get(qname("style:name"))
            family = _first(face.get(qname("svg:font-family")) or "") or name
            if name and family:
                faces.setdefault(name, family)
    return faces


def font_of(properties: etree._Element | None, faces: dict[str, str]) -> str | None:
    """The font a ``style:text-properties`` element names, or ``None`` if it names none: its font face's family (the
    face's name itself if the file does not declare it), else the first family of ``fo:font-family``."""
    if properties is None:
        return None
    face = properties.get(qname("style:font-name"))
    if face:
        return faces.get(face, face)
    return _first(properties.get(qname("fo:font-family")) or "")
