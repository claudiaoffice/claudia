"""What an odp says about how its objects and its slides look, as CSS of the model's styles (IEW-20, D467).

An object's look lives in the styles of the file: a graphic style for the shape (fill, outline), a paragraph style and
a text style for the words, a presentation style (that of the placeholder it is in) under both, each based on
another. :class:`StyleIndex` finds a style by family and name, takes what it is based on in, and answers what it
says; :func:`read_look` turns that into the properties a :class:`~claudia_creates_io._file_looks.LookBook` makes a
style of. What the model has no property for (a gradient, a shadow, a dashed line) is not read; it is said so."""

from __future__ import annotations

from lxml import etree

from claudia_creates import SLIDE_WIDTH
from claudia_odf_io import NS, inches

from ._file_looks import Look

_PREFIX = {uri: prefix for prefix, uri in NS.items()}
_POINTS_PER_INCH = 72
#: ``fo:text-align`` is a word of a language that is written either way; CSS says left and right.
_ALIGN = {"start": "left", "left": "left", "end": "right", "right": "right", "center": "center", "justify": "justify"}


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def _key(clark: str) -> str:
    """``{namespace}local`` as ``prefix:local``."""
    namespace, _, local = clark[1:].partition("}")
    return f"{_PREFIX.get(namespace, namespace)}:{local}"


class StyleIndex:
    """The named styles of the parts of a file (``content.xml`` and ``styles.xml``), found by family and name; the
    one that comes first in the parts wins, as it does for a program that reads them."""

    def __init__(self, *roots: etree._Element | None) -> None:
        self._styles: dict[tuple[str, str], etree._Element] = {}
        for root in roots:
            if root is None:
                continue
            for style in root.iter(_q("style", "style")):
                key = (style.get(_q("style", "family")) or "", style.get(_q("style", "name")) or "")
                self._styles.setdefault(key, style)

    def get(self, family: str, name: str | None) -> etree._Element | None:
        return self._styles.get((family, name or ""))

    def attributes(self, family: str, name: str | None, properties: str) -> dict[str, str]:
        """What the style ``name`` of ``family`` says in its ``properties`` element (``"style:text-properties"``...),
        as ``prefix:local`` to value, with what it is based on under it: the nearest style says it."""
        found: dict[str, str] = {}
        seen: set[str] = set()
        while name and name not in seen and (style := self.get(family, name)) is not None:
            seen.add(name)
            for element in style.findall(properties, NS):
                for clark, value in element.attrib.items():
                    found.setdefault(_key(str(clark)), str(value))
            name = style.get(_q("style", "parent-style-name"))
        return found


def read_look(
    element: etree._Element,
    paragraphs: list[etree._Element],
    index: StyleIndex,
    size_in: tuple[float, float],
    *,
    shape: bool,
) -> Look:
    """The look of the object ``element`` (a frame, or a shape) whose words are ``paragraphs``, on a slide of
    ``size_in`` inches (the model's slide is ``SLIDE_WIDTH`` units wide); ``shape`` says whether it has an outline of
    its own (a text box does not: a fill or a line it has is not read)."""
    per_inch = SLIDE_WIDTH / size_in[0]
    look = Look()
    graphic = index.attributes("graphic", element.get(_q("draw", "style-name")), "style:graphic-properties")
    presentation = index.attributes(
        "presentation", element.get(_q("presentation", "style-name")), "style:graphic-properties"
    )
    box = {**presentation, **graphic}
    _read_outline(look, box, per_inch, keep=shape)
    _read_words(look, element, paragraphs, index, per_inch / _POINTS_PER_INCH)
    return look


def _read_outline(look: Look, box: dict[str, str], per_inch: float, *, keep: bool) -> None:
    fill, stroke = box.get("draw:fill"), box.get("draw:stroke")
    if fill == "solid" and (colour := _colour(box.get("draw:fill-color"))):
        look.outline["fill"] = colour
    elif fill == "none":
        look.outline["fill"] = "none"
    elif fill not in (None, "solid"):
        look.unread = True  # a gradient, a hatch, a picture
    if stroke in ("solid", "dash") and (colour := _colour(box.get("svg:stroke-color"))):
        look.outline["stroke"] = colour
        width = inches(box.get("svg:stroke-width"))
        if width:
            look.outline["stroke-width"] = f"{max(width * per_inch, 0.5):.1f}px"
        look.unread |= stroke == "dash"
    elif stroke == "none":
        look.outline["stroke"] = "none"
    if box.get("draw:shadow") == "visible" or box.get("draw:opacity") not in (None, "100%"):
        look.unread = True
    if not keep:  # a text box has no outline in the model: what the file draws around it is not shown
        look.unread |= look.outline.get("fill", "none") != "none" or look.outline.get("stroke", "none") != "none"
        look.outline.clear()


def _read_words(
    look: Look, element: etree._Element, paragraphs: list[etree._Element], index: StyleIndex, per_point: float
) -> None:
    first = next((p for p in paragraphs if any(str(text).strip() for text in p.itertext())), None)
    if first is None:
        return
    span = first.find("text:span", NS) if not (first.text or "").strip() else None
    sources = (
        ("presentation", element.get(_q("presentation", "style-name"))),
        ("paragraph", first.get(_q("text", "style-name"))),
        ("text", span.get(_q("text", "style-name")) if span is not None else None),
    )
    said: dict[str, str] = {}
    for family, name in sources:  # the one that comes later is nearer the words
        for properties in ("style:text-properties", "style:paragraph-properties"):
            said.update(index.attributes(family, name, properties))
    if (size := _size(said.get("fo:font-size"), per_point)) is not None:
        look.words["font-size"] = size
    elif said.get("fo:font-size"):
        look.unread = True
    if colour := _colour(said.get("fo:color")):
        look.words["color"] = colour
    if said.get("fo:font-weight") in ("bold", "700", "800", "900"):
        look.words["font-weight"] = "bold"
    if said.get("fo:font-style") in ("italic", "oblique"):
        look.words["font-style"] = "italic"
    if said.get("fo:text-align") in _ALIGN:
        look.words["text-align"] = _ALIGN[said["fo:text-align"]]


def _colour(value: str | None) -> str | None:
    return value.lower() if value and len(value) == 7 and value.startswith("#") else None


def _size(value: str | None, per_point: float) -> str | None:
    """``18pt`` as slide pixels (the unit of the model's sizes), or ``None`` for a size in another unit."""
    if value and value.endswith("pt"):
        try:
            return f"{float(value[:-2]) * per_point:.1f}px"
        except ValueError:
            return None
    return None
