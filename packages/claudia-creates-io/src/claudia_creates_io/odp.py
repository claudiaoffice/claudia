"""Converting between a :class:`~claudia_creates.SlideModel` and OpenDocument presentation (odp) (D412).

The second of the three OpenDocument formats (D70: odt, odp, ods), with the promise of the first (D401, D403): **maximum
preservation from day one**.

* ``slides_to_odp`` writes a model as a new file, and ``odp_export_losses`` says what the file cannot hold.
* ``odp_to_slides`` reads a file as a model, and ``odp_import_losses`` says what the model does not show of it.
  Nothing is thrown away by reading.
* ``apply_edits_to_odp`` is the way back for an *edited* import: it patches what changed since the baseline onto the
  bytes of the original, so a picture, a table, a transition, the notes, a group -- everything the presentation app
  has no model for -- is still there, and every byte of ``content.xml`` outside what was edited is the original's. A
  moved object changes its start tag and nothing else.

What the model sees of an odp: every ``draw:page`` is a slide (``s1``, ``s2``... by its place) and every text box
(a ``draw:frame`` holding a ``draw:text-box``), ellipse, rectangle and triangle directly on it is an object (``o1``,
``o2``... by its place over the whole deck), in the order the file draws them. An object is *modeled* only if the app
can hold it as it is: it needs a place and a size in lengths, none of it rotated, all of it on the slide, and it must
pass the checks the model makes of every object (a size of at least a few units, a circle that is round...). The same
function decides that on the way in and on the way back, so an id means the same thing both times.

What an object looks like is not mapped (D407, as for odt): every text box comes in as "plain-box" with "body-text"
words and every shape as "plain-shape" with "shape-label" words (D310), and its look in the file is untouched until
somebody gives it another look.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from zipfile import BadZipFile

from lxml import etree

from claudia_core import ObjectBody, VisualObject, paragraph_for
from claudia_creates import SLIDE_HEIGHT, SLIDE_WIDTH, ShapeLibrary, SlideAnchor, SlideModel
from claudia_odf_io import (
    MIME,
    NS,
    DocumentInfo,
    Loss,
    LossLog,
    OdfError,
    XmlPart,
    hidden_content,
    local_name,
    new_meta,
    new_package,
    read_text,
    set_text,
    update_package_meta,
    xml_safe,
)
from claudia_opc_io import read_parts, write_parts

from ._raster import Rasterise
from ._styling import colour_of, look, page_colour, points_of
from .pptx import UnsupportedEdit

_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>\n'
_NS_DECLS = {prefix: uri for prefix, uri in NS.items() if prefix != "xml"}

#: The size of a new slide, 16:9 the way LibreOffice makes one: what a model's 1600 by 900 units are written as.
_SLIDE_CM = (28.0, 15.75)
_CM_PER_INCH = 2.54
_INCHES = {"cm": 1 / 2.54, "mm": 1 / 25.4, "in": 1.0, "pt": 1 / 72, "pc": 1 / 6, "px": 1 / 96}
_LENGTH = re.compile(r"\s*(-?(?:\d+\.?\d*|\.\d+))\s*(cm|mm|in|pt|pc|px)\s*")

_DEFAULT_TEXT_STYLE, _DEFAULT_SHAPE_STYLE, _DEFAULT_LABEL_STYLE = "body-text", "plain-shape", "shape-label"
#: A text box's own box (D310): its words are Body text, its box this style without properties.
_DEFAULT_BOX_STYLE = "plain-box"


def _default_styles(kind: str) -> tuple[str, str]:
    """The styles an object of ``kind`` comes in with, for its two slots (D304, D310): a text box's box and words,
    a shape's outline and label — as ``pptx_to_slides`` gives them."""
    if kind == "text":
        return _DEFAULT_BOX_STYLE, _DEFAULT_TEXT_STYLE
    return _DEFAULT_SHAPE_STYLE, _DEFAULT_LABEL_STYLE


#: What a ``draw:type`` of a custom shape is, as one of the three shapes the app has.
_CUSTOM = {
    "ellipse": "circle",
    "rectangle": "rectangle",
    "isosceles-triangle": "triangle",
    # LibreOffice names the preset geometries it takes from PowerPoint ``ooxml-*``.
    "ooxml-ellipse": "circle",
    "ooxml-rect": "rectangle",
    "ooxml-triangle": "triangle",
    "ooxml-isosceles-triangle": "triangle",
}
#: Things on a slide that are drawn (the others -- notes, animations, forms -- are not objects).
_DRAWN = {
    "frame",
    "ellipse",
    "circle",
    "rect",
    "custom-shape",
    "g",
    "a",
    "line",
    "polyline",
    "polygon",
    "path",
    "connector",
    "caption",
    "measure",
    "control",
    "regular-polygon",
}
_MAX_OBJECTS = 500
_TRIANGLE_PATH = "M 10800 0 L 21600 21600 0 21600 10800 0 Z N"


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def _inches(value: str | None) -> float | None:
    """A length of the format (``"2.5cm"``, ``"1in"``) in inches, or ``None`` if it is not one."""
    match = _LENGTH.fullmatch(value) if value else None
    return float(match.group(1)) * _INCHES[match.group(2)] if match else None


# -- reading a file ------------------------------------------------------------------------------------------------
def _read(data: bytes) -> dict[str, bytes]:
    """The parts of an odp file, or an ``OdfError`` saying why it is not one."""
    try:
        parts = read_parts(data)
    except BadZipFile as problem:
        raise OdfError("this is not an OpenDocument file: it is not a zip file") from problem
    kind = parts.get("mimetype")
    if kind is None or not kind.startswith(b"application/vnd.oasis.opendocument."):
        raise OdfError("this is not an OpenDocument file: it has no mimetype")
    if kind.strip() != MIME["presentation"].encode():
        raise OdfError("this OpenDocument file is not a presentation")
    if "content.xml" not in parts:
        raise OdfError("this is not an OpenDocument file: it has no content.xml")
    return parts


def _presentation(root: etree._Element) -> etree._Element:
    found = root.find("office:body/office:presentation", NS)
    if found is None:
        raise OdfError("this OpenDocument file is not a presentation: its content has no slides")
    return found


@dataclass
class _Object:
    """A thing on a slide that the model holds: its element, what it is, and where (in slide units)."""

    id: str
    element: etree._Element
    kind: str  # "text" or "shape"
    shape: str | None
    x: int
    y: int
    w: int
    h: int
    text: str
    paragraphs: list[etree._Element]


@dataclass
class _Slide:
    id: str
    element: etree._Element
    master: str | None
    size: tuple[float, float]  # inches
    objects: list[_Object] = field(default_factory=list)
    #: What is on the slide and not in the model, as ``(kind, detail)``: "picture", "table", "rotated-object"...
    left_out: list[tuple[str, str]] = field(default_factory=list)


class _Probe:
    """A throwaway model that answers whether it could hold an object: the model's own checks, the same ones every
    command goes through."""

    def __init__(self) -> None:
        self.model = SlideModel()
        self.model.insert_slide("probe")
        library = ShapeLibrary.load()
        for shape_id in set(_CUSTOM.values()):
            definition = library.get(shape_id)
            if definition is None:  # pragma: no cover - the three ids are always shipped
                raise ValueError(f"the built-in shape library has no shape {shape_id!r}")
            self.model.define_shape(definition)

    def holds(self, kind: str, shape: str | None, box: tuple[int, int, int, int], text: str) -> bool:
        style, words = _default_styles(kind)
        body = ObjectBody("o0", kind, box[2], box[3], style, paragraph_for("o0", words, text), shape=shape)
        try:
            self.model.check_object(VisualObject(body, SlideAnchor("probe", box[0], box[1])))
        except ValueError:
            return False
        return True


def _layouts(*roots: etree._Element | None) -> dict[str, tuple[float, float]]:
    sizes: dict[str, tuple[float, float]] = {}
    for root in roots:
        if root is None:
            continue
        for layout in root.iter(_q("style", "page-layout")):
            props = layout.find("style:page-layout-properties", NS)
            width = _inches(props.get(_q("fo", "page-width"))) if props is not None else None
            height = _inches(props.get(_q("fo", "page-height"))) if props is not None else None
            if width and height:
                sizes[layout.get(_q("style", "name")) or ""] = (width, height)
    return sizes


def _masters(styles: etree._Element | None) -> dict[str, str]:
    if styles is None:
        return {}
    return {
        master.get(_q("style", "name")) or "": master.get(_q("style", "page-layout-name")) or ""
        for master in styles.iter(_q("style", "master-page"))
    }


def _drawing_page_styles(*roots: etree._Element | None) -> dict[str, etree._Element]:
    found: dict[str, etree._Element] = {}
    for root in roots:
        if root is None:
            continue
        for style in root.iter(_q("style", "style")):
            if style.get(_q("style", "family")) == "drawing-page":
                found[style.get(_q("style", "name")) or ""] = style
    return found


def _graphic_styles(*roots: etree._Element | None) -> dict[str, etree._Element]:
    found: dict[str, etree._Element] = {}
    for root in roots:
        if root is None:
            continue
        for style in root.iter(_q("style", "style")):
            if style.get(_q("style", "family")) == "graphic":
                found.setdefault(style.get(_q("style", "name")) or "", style)
    return found


def _bare(element: etree._Element, graphics: dict[str, etree._Element]) -> bool:
    """Is this shape drawn with neither a fill nor an outline (its style, or one it is based on, says both are
    ``none``)? That is how LibreOffice writes what PowerPoint calls a text box: an unfilled rectangle with words in
    it."""
    fill = stroke = None
    name, seen = element.get(_q("draw", "style-name")), set()
    while name and name not in seen and name in graphics:
        seen.add(name)
        style = graphics[name]
        for props in style.findall("style:graphic-properties", NS):
            fill = fill or props.get(_q("draw", "fill"))
            stroke = stroke or props.get(_q("draw", "stroke"))
        name = style.get(_q("style", "parent-style-name"))
    return fill == "none" and stroke == "none"


def _has_words(element: etree._Element) -> bool:
    return any(read_text(p).strip() for p in element.iter(_q("text", "p"), _q("text", "h")))


def _has_transition(style: etree._Element | None) -> bool:
    if style is None:
        return False
    for props in style.iter(_q("style", "drawing-page-properties")):
        if any("transition" in str(key) or str(key).startswith(f"{{{NS['smil']}}}") for key in props.attrib):
            return True
    return False


def _classify(
    element: etree._Element, graphics: dict[str, etree._Element]
) -> tuple[str, str | None] | tuple[None, tuple[str, str]]:
    """``("text", None)`` or ``("shape", id)`` for what the model can be asked to hold; ``(None, (kind, detail))``
    for what is left out, by what it is."""
    tag = local_name(element.tag)
    if tag == "frame":
        inner = {local_name(child.tag) for child in element if isinstance(child.tag, str)}
        # a table or an object carries a preview picture of itself: what it is comes before the picture
        for name, kind in (("table", "table"), ("object", "object"), ("object-ole", "object"), ("image", "picture")):
            if name in inner:
                return None, (kind, "")
        if "text-box" in inner:
            return "text", None
        return None, ("frame", "")
    if tag in ("ellipse", "circle"):
        return "shape", "circle"
    if tag == "rect":
        return "shape", "rectangle"
    if tag == "custom-shape":
        geometry = element.find("draw:enhanced-geometry", NS)
        outline = geometry.get(_q("draw", "type")) if geometry is not None else None
        if outline in _CUSTOM:
            if _CUSTOM[outline] == "rectangle" and _has_words(element) and _bare(element, graphics):
                return "text", None
            return "shape", _CUSTOM[outline]
        return None, ("shape", outline or "custom")
    if tag in ("g", "a"):
        return None, ("group", "")
    return None, ("shape", tag)


def _words(element: etree._Element, kind: str) -> list[etree._Element]:
    """The paragraphs of an object, in the order they are written."""
    holder = element.find("draw:text-box", NS) if kind == "text" and local_name(element.tag) == "frame" else element
    if holder is None:
        return []
    return [p for p in holder.iter(_q("text", "p"), _q("text", "h")) if _own_words(p, element)]


def _own_words(paragraph: etree._Element, owner: etree._Element) -> bool:
    """Is this paragraph the object's own (not that of a frame inside it)?"""
    parent = paragraph.getparent()
    while parent is not None and parent is not owner:
        if parent.tag in (_q("draw", "frame"), _q("draw", "text-box")) and parent.getparent() is not owner:
            return False
        parent = parent.getparent()
    return True


def _box(element: etree._Element, size: tuple[float, float]) -> tuple[int, int, int, int] | str:
    """Where an element is, in slide units, or why it has no place (``"rotated"``, ``"unplaced"``, ``"off-slide"``)."""
    if element.get(_q("draw", "transform")) is not None:
        return "rotated"
    values = [_inches(element.get(_q("svg", name))) for name in ("x", "y", "width", "height")]
    if any(value is None for value in values):
        return "unplaced"
    x, y, w, h = (value for value in values if value is not None)
    per_x, per_y = size[0] / SLIDE_WIDTH, size[1] / SLIDE_HEIGHT
    box = (round(x / per_x), round(y / per_y), round(w / per_x), round(h / per_y))
    if box[0] < 0 or box[1] < 0 or box[0] + box[2] > SLIDE_WIDTH or box[1] + box[3] > SLIDE_HEIGHT:
        return "off-slide"
    return box


def _scan(content: etree._Element, styles: etree._Element | None) -> list[_Slide]:
    """Every slide of the deck, with the objects on it that the model holds and what else there is."""
    layouts = _layouts(styles, content)
    masters = _masters(styles)
    page_styles = _drawing_page_styles(content, styles)
    graphics = _graphic_styles(content, styles)
    probe, found, numbers = _Probe(), [], iter(range(1, 10**9))
    for index, page in enumerate(_presentation(content).findall("draw:page", NS), start=1):
        master = page.get(_q("draw", "master-page-name"))
        size = layouts.get(masters.get(master or "", ""))
        if size is None:
            size = next(iter(layouts.values()), (_SLIDE_CM[0] / _CM_PER_INCH, _SLIDE_CM[1] / _CM_PER_INCH))
        slide = _Slide(f"s{index}", page, master, size)
        for child in page:
            _scan_child(slide, child, probe, numbers, graphics)
        if page.get(_q("draw", "style-name")) and _has_transition(
            page_styles.get(page.get(_q("draw", "style-name")) or "")
        ):
            slide.left_out.append(("transition", ""))
        found.append(slide)
    return found


def _scan_child(
    slide: _Slide, child: etree._Element, probe: _Probe, numbers: Iterator[int], graphics: dict[str, etree._Element]
) -> None:
    tag = child.tag
    if not isinstance(tag, str):
        return
    namespace = etree.QName(tag).namespace
    if namespace == NS["anim"]:
        if ("animation", "") not in slide.left_out:
            slide.left_out.append(("animation", ""))
        return
    if tag == _q("presentation", "notes"):
        if _has_words(child):  # LibreOffice writes an empty notes page for every slide: nothing is hidden there
            slide.left_out.append(("notes", ""))
        return
    if namespace != NS["draw"] or local_name(tag) not in _DRAWN:
        return
    kind, what = _classify(child, graphics)
    if kind is None:
        assert isinstance(what, tuple)
        slide.left_out.append(what)
        return
    shape = what if isinstance(what, str) else None
    box = _box(child, slide.size)
    paragraphs = _words(child, kind)
    text = "\n".join(read_text(p) for p in paragraphs)
    if isinstance(box, str):
        slide.left_out.append((f"{box}-object", kind))
    elif len(slide.objects) >= _MAX_OBJECTS or not probe.holds(kind, shape, box, text):
        slide.left_out.append(("unfit-object", kind))
    else:
        slide.objects.append(_Object(f"o{next(numbers)}", child, kind, shape, *box, text, paragraphs))


def _document(data: bytes) -> tuple[dict[str, bytes], etree._Element, etree._Element | None, list[_Slide]]:
    parts = _read(data)
    try:
        content = etree.fromstring(parts["content.xml"], etree.XMLParser(resolve_entities=False, no_network=True))
        styles = (
            etree.fromstring(parts["styles.xml"], etree.XMLParser(resolve_entities=False, no_network=True))
            if "styles.xml" in parts
            else None
        )
    except etree.XMLSyntaxError as problem:
        raise OdfError(f"this OpenDocument file is not well-formed XML: {problem}") from problem
    return parts, content, styles, _scan(content, styles)


def _slide_ids(slides: list[_Slide]) -> list[str]:
    return [slide.id for slide in slides]


def odp_to_slides(odp_bytes: bytes) -> SlideModel:
    """``odp_bytes`` as a :class:`~claudia_creates.SlideModel`: a slide per page, in order, called ``s1``, ``s2``...,
    a text box, ellipse, rectangle or triangle on it an object, called ``o1``, ``o2``... by its place in the deck, in
    the order the file draws them, from bottom to top. Place and size are read through the slide's own size (not an
    assumed shape: a 4:3 deck comes in as 4:3). What the model does not hold is in :func:`odp_import_losses`. Raises
    :class:`~claudia_odf_io.OdfError` for a file that is not an odp."""
    _, _, _, slides = _document(odp_bytes)
    if not slides:
        return SlideModel.empty()
    model, library, defined = SlideModel(), ShapeLibrary.load(), set()
    for slide in slides:
        model.insert_slide(slide.id)
        for found in slide.objects:
            style, words = _default_styles(found.kind)
            if found.kind == "text":
                shape = None
            else:
                shape = found.shape
                if shape not in defined and shape is not None:
                    definition = library.get(shape)
                    assert definition is not None  # the three ids are always shipped
                    model.define_shape(definition)
                    defined.add(shape)
            body = ObjectBody(
                found.id, found.kind, found.w, found.h, style, paragraph_for(found.id, words, found.text), shape=shape
            )
            model.insert_object(VisualObject(body, SlideAnchor(slide.id, found.x, found.y)))
    return model


def odp_import_losses(odp_bytes: bytes) -> tuple[Loss, ...]:
    """What :func:`odp_to_slides` does not show of the file, each as a code (``"picture"``, ``"table"``, ``"group"``,
    ``"notes"``, ``"transition"``, ``"rotated-object"``...) with how many there are, in the order they come. None of it
    is lost from the *file*: an edit exported with :func:`apply_edits_to_odp` keeps all of it."""
    _, _, _, slides = _document(odp_bytes)
    losses = LossLog()
    looks = formatting = links = 0
    hidden: dict[str, int] = {}
    for slide in slides:
        for kind, detail in slide.left_out:
            losses.add(kind, detail)
        for found in slide.objects:
            if found.element.get(_q("draw", "style-name")) or any(
                p.get(_q("text", "style-name")) for p in found.paragraphs
            ):
                looks += 1
            for paragraph in found.paragraphs:
                formatting += sum(
                    1 for span in paragraph.iter(_q("text", "span")) if span.get(_q("text", "style-name"))
                )
                links += sum(1 for _ in paragraph.iter(_q("text", "a")))
                for kind in hidden_content(paragraph):
                    hidden[kind] = hidden.get(kind, 0) + 1
    for code, number in (("look", looks), ("formatting", formatting), ("link", links)):
        if number:
            losses.add(code, count=number)
    for kind, number in hidden.items():
        losses.add(kind, count=number)
    return _in_order(losses.result())


_ORDER = ("picture", "table", "object", "group", "shape", "frame")


def _in_order(losses: tuple[Loss, ...]) -> tuple[Loss, ...]:
    return tuple(sorted(losses, key=lambda loss: _ORDER.index(loss.kind) if loss.kind in _ORDER else len(_ORDER)))


# -- writing ---------------------------------------------------------------------------------------------------------
def _hex(colour: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*colour)


def _length(units: float, cm_per_unit: float) -> str:
    text = f"{units * cm_per_unit:.3f}".rstrip("0").rstrip(".")
    return f"{'0' if text in ('', '-0') else text}cm"


def _el(prefix: str, local: str, attributes: Mapping[str, str] | None = None) -> etree._Element:
    element = etree.Element(_q(prefix, local), nsmap=_NS_DECLS)
    for name, value in (attributes or {}).items():
        key_prefix, _, key_local = name.partition(":")
        element.set(_q(key_prefix, key_local), value)
    return element


class _Looks:
    """The automatic styles a write needs, each one made once: how a shape is filled and drawn, how words look."""

    def __init__(self, taken: set[str]) -> None:
        self.taken = taken
        self.elements: list[etree._Element] = []
        self._made: dict[tuple, str] = {}

    def _name(self, prefix: str) -> str:
        number = len(self._made) + 1
        while f"{prefix}{number}" in self.taken:
            number += 1
        name = f"{prefix}{number}"
        self.taken.add(name)
        return name

    def _style(self, key: tuple, prefix: str, family: str, properties: list[etree._Element]) -> str:
        if key not in self._made:
            name = self._name(prefix)
            self._made[key] = name
            style = _el("style", "style", {"style:name": name, "style:family": family})
            style.extend(properties)
            self.elements.append(style)
        return self._made[key]

    def graphic(self, css: dict[str, str], over: str | None, pt_per_unit: float) -> str:
        """A graphic style for a fill and a line: ``css``'s ``fill``, ``stroke`` and ``stroke-width``."""
        fill, stroke = colour_of(css, "fill", over), colour_of(css, "stroke", over)
        width = points_of(css, "stroke-width", pt_per_unit)
        props: dict[str, str] = {
            "draw:fill": "solid" if fill else "none",
            "draw:stroke": "solid" if stroke else "none",
        }
        if fill:
            props["draw:fill-color"] = _hex(fill)
        if stroke:
            props["svg:stroke-color"] = _hex(stroke)
            if width:
                props["svg:stroke-width"] = _length(width, _CM_PER_INCH / 72)
        key = ("graphic", *sorted(props.items()))
        return self._style(key, "clg", "graphic", [_el("style", "graphic-properties", props)])

    def paragraph(self, css: dict[str, str], over: str | None, pt_per_unit: float) -> str | None:
        """A paragraph style for the size, colour and alignment of words, or ``None`` if ``css`` says none of them."""
        size, colour = points_of(css, "font-size", pt_per_unit), colour_of(css, "color", over)
        align = {"left": "start", "right": "end", "center": "center", "justify": "justify"}.get(
            css.get("text-align", "")
        )
        text: dict[str, str] = {}
        if size:
            text["fo:font-size"] = f"{size:.1f}".rstrip("0").rstrip(".") + "pt"
        if colour:
            text["fo:color"] = _hex(colour)
        if not text and not align:
            return None
        properties = []
        if align:
            properties.append(_el("style", "paragraph-properties", {"fo:text-align": align}))
        if text:
            properties.append(_el("style", "text-properties", text))
        key = ("paragraph", align, *sorted(text.items()))
        return self._style(key, "clp", "paragraph", properties)


def _paragraphs(text: str, style_name: str | None) -> list[etree._Element]:
    paragraphs = []
    for line in text.split("\n"):
        paragraph = _el("text", "p", {"text:style-name": style_name} if style_name else None)
        set_text(paragraph, xml_safe(line))
        paragraphs.append(paragraph)
    return paragraphs


@dataclass
class _Writer:
    """What writing an object needs: the model it is from, the styles collected so far, the size of the slide."""

    model: SlideModel
    looks: _Looks
    cm_per_unit: tuple[float, float]
    pt_per_unit: float
    pictures: dict[str, str] = field(default_factory=dict)  # asset id -> name in the package
    rasterise: Rasterise | None = None  # draws an SVG as a PNG for the programs that cannot (see ``_raster``)
    rasters: dict[str, bytes] = field(default_factory=dict)  # name in the package -> a PNG drawn by ``rasterise``
    losses: LossLog = field(default_factory=LossLog)

    def object(self, obj: VisualObject) -> etree._Element | None:
        """The element of an object, or ``None`` for an image whose picture the model does not have."""
        body, anchor = obj.body, obj.anchor
        over = page_colour(self.model)
        placing = {
            "svg:x": _length(anchor.x, self.cm_per_unit[0]),
            "svg:y": _length(anchor.y, self.cm_per_unit[1]),
            "svg:width": _length(body.w, self.cm_per_unit[0]),
            "svg:height": _length(body.h, self.cm_per_unit[1]),
        }
        text = body.paragraph.text if body.paragraph is not None else ""
        words_css = look(self.model, body.paragraph.style) if body.paragraph is not None else {}
        words = self.looks.paragraph(words_css, over, self.pt_per_unit)
        if body.kind in ("image", "rendered"):
            return self._picture(body, placing)
        if body.kind == "text":
            graphic = self.looks.graphic({}, over, self.pt_per_unit)
            frame = _el("draw", "frame", {"draw:style-name": graphic, **placing})
            box = etree.SubElement(frame, _q("draw", "text-box"))
            box.extend(_paragraphs(text, words))
            return frame
        graphic = self.looks.graphic(look(self.model, body.style), over, self.pt_per_unit)
        definition = self.model.shapes.get(body.shape) if body.shape else None
        shape_id = definition.id if definition else "rectangle"
        if body.kind == "diagram":  # pragma: no cover - the presentation app has no diagram objects yet (E6.6)
            self.losses.add("diagram")
        attributes = {"draw:style-name": graphic, **placing}
        if shape_id == "circle":
            element = _el("draw", "ellipse", attributes)
            element.extend(_paragraphs(text, words) if text else [])
        elif shape_id == "triangle":
            element = _el("draw", "custom-shape", attributes)
            element.extend(_paragraphs(text, words))
            geometry = etree.SubElement(element, _q("draw", "enhanced-geometry"))
            geometry.set(_q("svg", "viewBox"), "0 0 21600 21600")
            geometry.set(_q("draw", "type"), "isosceles-triangle")
            geometry.set(_q("draw", "enhanced-path"), _TRIANGLE_PATH)
        else:
            element = _el("draw", "rect", attributes)
            element.extend(_paragraphs(text, words) if text else [])
        return element

    def _picture(self, body: ObjectBody, placing: dict[str, str]) -> etree._Element | None:
        picture = self.model.picture_of(body)
        asset = self.model.images.get(picture) if picture else None
        if asset is None:  # an image object's asset is always held (the model refuses otherwise)
            self.losses.add("rendering-pending" if body.kind == "rendered" else "image-missing")
            return None
        if asset.format == "svg" and self.rasterise is not None and body.kind == "rendered":
            href = f"Pictures/{asset.id}-{round(body.w)}x{round(body.h)}.png"
            if href not in self.rasters:
                self.rasters[href] = self.rasterise(asset.data, round(body.w), round(body.h))
        else:
            href = self.pictures.setdefault(
                asset.id,
                f"Pictures/{re.sub(r'[^A-Za-z0-9_-]', '_', asset.id)}.{_EXTENSION.get(asset.format, asset.format)}",
            )
        frame = _el("draw", "frame", placing)
        image = etree.SubElement(frame, _q("draw", "image"))
        for name, value in (("href", href), ("type", "simple"), ("show", "embed"), ("actuate", "onLoad")):
            image.set(_q("xlink", name), value)
        if body.description:  # a decorative picture has none: ODF 1.3 has no way to say more (see odp_export_losses)
            etree.SubElement(frame, _q("svg", "desc")).text = xml_safe(body.description)
        return frame


_EXTENSION = {"jpeg": "jpg"}
_MEDIA_TYPE = {"svg": "image/svg+xml"}


def _styles_part() -> bytes:
    width, height = (f"{value:g}cm" for value in _SLIDE_CM)
    declared = " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in _NS_DECLS.items())
    return (
        f"{_DECLARATION}<office:document-styles {declared} "
        f'office:version="1.3"><office:styles/><office:automatic-styles><style:page-layout style:name="PM1">'
        f'<style:page-layout-properties fo:page-width="{width}" fo:page-height="{height}" '
        'style:print-orientation="landscape" fo:margin-top="0cm" fo:margin-bottom="0cm" fo:margin-left="0cm" '
        'fo:margin-right="0cm"/></style:page-layout></office:automatic-styles><office:master-styles>'
        '<style:master-page style:name="Default" style:page-layout-name="PM1"/></office:master-styles>'
        "</office:document-styles>"
    ).encode()


def slides_to_odp(model: SlideModel, *, info: DocumentInfo | None = None, rasterise: Rasterise | None = None) -> bytes:
    """``model`` as odp bytes: a page per slide and, on it, an element per object from the bottom up, so that the last
    one is in front, as in the app. A text box is a frame with a text box, the three shapes are what they are, an image
    is a picture whose own bytes are in the package. What a style says (fill, line, size, colour) is written as an
    automatic style in values the file can hold. A rendered text container is the picture last made from its text: with
    ``rasterise`` (see ``_raster``) a PNG every program draws, without it the SVG itself. ``info`` is the metadata
    (D411). Anything the file cannot hold is in :func:`odp_export_losses`."""
    cm_per_unit = (_SLIDE_CM[0] / SLIDE_WIDTH, _SLIDE_CM[1] / SLIDE_HEIGHT)
    pt_per_unit = _SLIDE_CM[1] / _CM_PER_INCH * 72 / SLIDE_HEIGHT
    writer = _Writer(model, _Looks(set()), cm_per_unit, pt_per_unit, rasterise=rasterise)
    root = _el("office", "document-content", {"office:version": "1.3"})
    for name in ("scripts", "font-face-decls"):
        etree.SubElement(root, _q("office", name))
    automatic = etree.SubElement(root, _q("office", "automatic-styles"))
    presentation = etree.SubElement(etree.SubElement(root, _q("office", "body")), _q("office", "presentation"))
    for number, slide_id in enumerate(model.slides, start=1):
        page = etree.SubElement(presentation, _q("draw", "page"))
        page.set(_q("draw", "name"), f"page{number}")
        page.set(_q("draw", "master-page-name"), "Default")
        for obj in model.objects_on(slide_id):
            element = writer.object(obj)
            if element is not None:
                page.append(element)
    automatic.extend(writer.looks.elements)
    content = _DECLARATION + etree.tostring(root, encoding="unicode")
    extra = {
        name: (
            model.images[asset_id].data,
            _MEDIA_TYPE.get(model.images[asset_id].format, f"image/{model.images[asset_id].format}"),
        )
        for asset_id, name in writer.pictures.items()
    }
    extra.update({name: (png, "image/png") for name, png in writer.rasters.items()})
    return new_package(
        "presentation", content.encode(), _styles_part(), meta=new_meta(info or DocumentInfo()), extra=extra
    )


def odp_export_losses(model: SlideModel, *, rasterised: bool = False) -> tuple[Loss, ...]:
    """What :func:`slides_to_odp` cannot put into the file for ``model``, each as a code with how many: ``"authorship"``
    (who wrote which words of an object: an odp does not keep it), a ``"diagram"`` (written as a rectangle), an
    ``"image-missing"`` (an image the document has no picture for), ``"rendering-pending"`` (a rendered text container
    nothing has been drawn for yet: it is left out, and says so here), ``"svg-picture"`` (a rendered container
    written as the SVG itself, because nothing could draw it as a PNG: programs other than PowerPoint may leave out
    colours or text of a diagram; none with ``rasterised``) and ``"decorative"`` (an object marked as
    decoration: ODF 1.3 has no attribute for it, so a reader of the file sees an object nobody described)."""
    losses = LossLog()
    authored = sum(
        1
        for obj in model.objects.values()
        if obj.body.paragraph is not None and any(run.author is not None for run in obj.body.paragraph.runs)
    )
    if authored:
        losses.add("authorship", count=authored)
    decorative = sum(1 for obj in model.objects.values() if obj.body.decorative)
    if decorative:
        losses.add("decorative", count=decorative)
    for obj in model.objects.values():  # pragma: no cover - neither can be in a presentation yet (see above)
        if obj.body.kind == "diagram":
            losses.add("diagram")
        elif obj.body.kind == "image" and obj.body.image not in model.images:
            losses.add("image-missing")
    pending = sum(
        1 for obj in model.objects.values() if obj.body.kind == "rendered" and model.picture_of(obj.body) is None
    )
    if pending:
        losses.add("rendering-pending", count=pending)
    if not rasterised:
        vector = sum(
            1
            for obj in model.objects.values()
            if obj.body.kind == "rendered"
            and (a := model.images.get(model.picture_of(obj.body) or ""))
            and a.format == "svg"
        )
        if vector:
            losses.add("svg-picture", count=vector)
    return losses.result()


# -- edit and re-export ----------------------------------------------------------------------------------------------
class _Patch:
    """One run of :func:`apply_edits_to_odp`: the original's parts, what is to change and the edits recorded so far."""

    def __init__(
        self,
        original: bytes,
        baseline: SlideModel,
        current: SlideModel,
        *,
        losses: LossLog | None,
        info: DocumentInfo | None,
    ) -> None:
        self.original, self.baseline, self.current = original, baseline, current
        self.losses, self.info = losses, info
        self.parts = _read(original)
        self.part = XmlPart(self.parts["content.xml"])
        self.styles_root = (
            etree.fromstring(self.parts["styles.xml"], etree.XMLParser(resolve_entities=False, no_network=True))
            if "styles.xml" in self.parts
            else None
        )
        self.slides = _scan(self.part.root, self.styles_root)
        self.presentation = _presentation(self.part.root)
        self.by_id = {slide.id: slide for slide in self.slides}
        self.found = {obj.id: obj for slide in self.slides for obj in slide.objects}
        self.looks = _Looks(self._style_names())
        self.changed = False
        self._page_names = {p.get(_q("draw", "name")) for p in self.presentation.findall("draw:page", NS)}
        self._after: dict[int, tuple[etree._Element, list[etree._Element]]] = {}
        self._into: dict[int, tuple[etree._Element, list[etree._Element]]] = {}
        self._before: dict[int, tuple[etree._Element, list[etree._Element]]] = {}
        self._check_baseline()

    def _style_names(self) -> set[str]:
        return {
            element.get(_q("style", "name")) or ""
            for root in (self.part.root, self.styles_root)
            if root is not None
            for element in root.iter(_q("style", "style"))
        }

    def _check_baseline(self) -> None:
        if not self.slides:
            if self.baseline.slides != SlideModel.empty().slides or self.baseline.objects:
                raise UnsupportedEdit("the baseline is not the deck this file holds")
            return
        if list(self.baseline.slides) != _slide_ids(self.slides):
            raise UnsupportedEdit("the baseline is not the deck this file holds")
        for slide in self.slides:
            if list(self.baseline.stack_of(slide.id)) != [obj.id for obj in slide.objects]:
                raise UnsupportedEdit("the baseline is not the deck this file holds")
        kept = [slide_id for slide_id in self.current.slides if slide_id in self.by_id]
        if kept != [slide_id for slide_id in self.baseline.slides if slide_id in set(kept)]:
            raise UnsupportedEdit("slides cannot be moved relative to each other in the file")
        for slide_id in kept:
            now = [i for i in self.current.stack_of(slide_id) if i in self.found]
            then = [i for i in self.baseline.stack_of(slide_id) if i in set(now)]
            if now != then:
                raise UnsupportedEdit("objects cannot be moved relative to each other on a slide in the file")

    # -- the run ---------------------------------------------------------------------------------------------------
    def run(self) -> bytes:
        for slide in self.slides:
            if slide.id not in self.current.slides:
                self._remove_slide(slide)
        self._patch_slides()
        self._flush()
        if not self.changed:
            return self.original
        self._add_styles()
        self.parts["content.xml"] = self.part.result()
        if self.info is not None:
            update_package_meta(self.parts, self.info)
        return write_parts(self.parts)

    def _remove_slide(self, slide: _Slide) -> None:
        if self.losses is not None:
            for kind, detail in slide.left_out:
                self.losses.add(f"removed-{kind}", detail)
            for obj in slide.objects:
                self._note_removed_words(obj)
        self.part.remove(slide.element)
        self.changed = True

    def _note_removed_words(self, obj: _Object) -> None:
        if self.losses is not None:
            for paragraph in obj.paragraphs:
                for kind in hidden_content(paragraph):
                    self.losses.add(f"removed-{kind}")

    def _patch_slides(self) -> None:
        previous: etree._Element | None = None  # the page of the slide before this one in the file
        for slide_id in self.current.slides:
            slide = self.by_id.get(slide_id)
            if slide is not None:
                self._patch_slide(slide)
                previous = slide.element
                continue
            objects = self.current.objects_on(slide_id)
            if not objects and not self.slides:
                continue  # the one empty slide of a deck with no pages is not a page
            self._new_slide(slide_id, objects, previous)

    def _per_cm(self, slide_size: tuple[float, float]) -> tuple[float, float]:
        return slide_size[0] * _CM_PER_INCH / SLIDE_WIDTH, slide_size[1] * _CM_PER_INCH / SLIDE_HEIGHT

    def _writer(self, size: tuple[float, float]) -> _Writer:
        return _Writer(self.current, self.looks, self._per_cm(size), size[1] * 72 / SLIDE_HEIGHT)

    def _patch_slide(self, slide: _Slide) -> None:
        writer = self._writer(slide.size)
        for obj in slide.objects:
            if obj.id not in self.current.objects:
                self._note_removed_words(obj)
                self.part.remove(obj.element)
                self.changed = True
        after: etree._Element | None = None  # the element the next new object goes behind
        first = slide.objects[0].element if slide.objects else None
        for object_id in self.current.stack_of(slide.id):
            kept = self.found.get(object_id)
            if kept is not None and object_id in self.baseline.objects:
                self._patch_object(kept, self.baseline.objects[object_id], self.current.objects[object_id], slide)
                after = kept.element
                continue
            element = writer.object(self.current.objects[object_id])
            if element is None:
                continue
            self._put(slide.element, element, after, first)
            self.changed = True
        self._lose(writer)

    def _lose(self, writer: _Writer) -> None:
        if self.losses is not None:
            for loss in writer.losses.result():
                self.losses.add(loss.kind, loss.detail, loss.count)

    def _put(
        self, page: etree._Element, element: etree._Element, after: etree._Element | None, first: etree._Element | None
    ) -> None:
        if after is not None:
            self._after.setdefault(id(after), (after, []))[1].append(element)
        elif first is not None:
            self._before.setdefault(id(first), (first, []))[1].append(element)
        else:
            anchor = self._last_drawn(page)
            if anchor is None:
                self._into.setdefault(id(page), (page, []))[1].append(element)
            else:
                self._after.setdefault(id(anchor), (anchor, []))[1].append(element)

    @staticmethod
    def _last_drawn(page: etree._Element) -> etree._Element | None:
        drawn = [c for c in page if isinstance(c.tag, str) and etree.QName(c.tag).namespace == NS["draw"]]
        if drawn:
            return drawn[-1]
        return page.find("office:forms", NS)

    def _new_slide(self, slide_id: str, objects: list[VisualObject], previous: etree._Element | None) -> None:
        neighbour = next((s for s in self.slides if s.element is previous), None) or (
            self.slides[0] if self.slides else None
        )
        master = neighbour.master if neighbour is not None else self._first_master()
        size = neighbour.size if neighbour is not None else (_SLIDE_CM[0] / _CM_PER_INCH, _SLIDE_CM[1] / _CM_PER_INCH)
        page = _el("draw", "page", {"draw:name": self._page_name()})
        if master:
            page.set(_q("draw", "master-page-name"), master)
        writer = self._writer(size)
        for obj in objects:
            element = writer.object(obj)
            if element is not None:
                page.append(element)
        self._lose(writer)
        if previous is not None:
            self._after.setdefault(id(previous), (previous, []))[1].append(page)
        elif self.slides:
            first = self.slides[0].element
            self._before.setdefault(id(first), (first, []))[1].append(page)
        else:
            self._into.setdefault(id(self.presentation), (self.presentation, []))[1].append(page)
        self.changed = True

    def _first_master(self) -> str | None:
        masters = list(_masters(self.styles_root))
        return masters[0] if masters else None

    def _page_name(self) -> str:
        number = 1
        while f"page{number}" in self._page_names:
            number += 1
        self._page_names.add(f"page{number}")
        return f"page{number}"

    def _flush(self) -> None:
        for anchor, elements in self._before.values():
            for element in elements:
                self.part.insert_before(anchor, element)
        for anchor, elements in self._after.values():
            for element in elements:
                self.part.insert_after(anchor, element)
        for parent, elements in self._into.values():
            self.part.insert_into(parent, *elements, at_start=True)

    def _add_styles(self) -> None:
        if not self.looks.elements:
            return
        holder = self.part.root.find("office:automatic-styles", NS)
        if holder is None:
            raise OdfError("this file has no automatic styles to add the look of an object to")
        self.part.insert_into(holder, *self.looks.elements)

    # -- one object ------------------------------------------------------------------------------------------------
    def _patch_object(self, found: _Object, before: VisualObject, after: VisualObject, slide: _Slide) -> None:
        if before == after:
            return
        if before.body.kind != after.body.kind or before.body.shape != after.body.shape:
            raise UnsupportedEdit("changing an object's kind or shape outline cannot be patched onto the file yet")
        per_x, per_y = self._per_cm(slide.size)
        attributes: dict[str, str] = {}
        for name, then, now, per in (
            ("svg:x", before.anchor.x, after.anchor.x, per_x),
            ("svg:y", before.anchor.y, after.anchor.y, per_y),
            ("svg:width", before.body.w, after.body.w, per_x),
            ("svg:height", before.body.h, after.body.h, per_y),
        ):
            if then != now:
                attributes[name] = _length(now, per)
        over, pt_per_unit = page_colour(self.current), slide.size[1] * 72 / SLIDE_HEIGHT
        if after.body.kind == "shape":
            old_look = look(self.baseline, before.body.style)
            new_look = look(self.current, after.body.style)
            if _graphic_of(old_look) != _graphic_of(new_look):
                attributes["draw:style-name"] = self.looks.graphic(new_look, over, pt_per_unit)
        words_before = before.body.paragraph
        words_after = after.body.paragraph
        style_name: str | None | bool = False  # False: the style of the words stays as it is
        if words_after is not None and words_before is not None:
            old_words = look(self.baseline, words_before.style)
            new_words = look(self.current, words_after.style)
            if _words_of(old_words) != _words_of(new_words):
                style_name = self.looks.paragraph(new_words, over, pt_per_unit)
        text = words_after.text if words_after is not None else ""
        if attributes:
            self.part.set_attributes(found.element, attributes)
            self.changed = True
        if text != found.text or style_name is not False:
            self._retext(found, text, style_name)
            self.changed = True

    def _retext(self, found: _Object, text: str, style_name: str | None | bool) -> None:
        lines = text.split("\n")
        paragraphs = found.paragraphs
        for index in range(min(len(lines), len(paragraphs))):
            self._rewrite(paragraphs[index], lines[index], style_name)
        for index in range(len(lines), len(paragraphs)):
            self._drop(paragraphs[index])
        if len(lines) > len(paragraphs):
            extra = lines[len(paragraphs) :]
            if paragraphs:
                template = paragraphs[-1]
                for line in extra:
                    copied = copy.deepcopy(template)
                    set_text(copied, xml_safe(line))
                    if style_name is not False:
                        self._apply_style(copied, style_name)
                    self.part.insert_after(template, copied)
            else:
                self._put_words(found, extra, style_name)

    def _rewrite(self, paragraph: etree._Element, line: str, style_name: str | None | bool) -> None:
        if read_text(paragraph) == line:
            if style_name:
                self.part.set_attributes(paragraph, {"text:style-name": str(style_name)})
            return
        edited = copy.deepcopy(paragraph)
        set_text(edited, xml_safe(line))
        if style_name is not False:
            self._apply_style(edited, style_name)
        self.part.replace(paragraph, edited)

    @staticmethod
    def _apply_style(paragraph: etree._Element, style_name: str | None | bool) -> None:
        key = _q("text", "style-name")
        if style_name:
            paragraph.set(key, str(style_name))
        elif key in paragraph.attrib:
            del paragraph.attrib[key]

    def _drop(self, paragraph: etree._Element) -> None:
        if self.losses is not None:
            for kind in hidden_content(paragraph):
                self.losses.add(f"removed-{kind}")
        self.part.remove(paragraph)

    def _put_words(self, found: _Object, lines: list[str], style_name: str | None | bool) -> None:
        paragraphs = _paragraphs("\n".join(lines), style_name if isinstance(style_name, str) else None)
        holder = found.element.find("draw:text-box", NS)
        if holder is not None:
            self.part.insert_into(holder, *paragraphs)
            return
        geometry = found.element.find("draw:enhanced-geometry", NS)
        if geometry is not None:
            for paragraph in paragraphs:
                self.part.insert_before(geometry, paragraph)
        else:
            self.part.insert_into(found.element, *paragraphs)


def _graphic_of(css: dict[str, str]) -> tuple[str | None, str | None, str | None]:
    return css.get("fill"), css.get("stroke"), css.get("stroke-width")


def _words_of(css: dict[str, str]) -> tuple[str | None, str | None, str | None]:
    return css.get("font-size"), css.get("color"), css.get("text-align")


def apply_edits_to_odp(
    original_bytes: bytes,
    baseline: SlideModel,
    current: SlideModel,
    *,
    losses: LossLog | None = None,
    info: DocumentInfo | None = None,
) -> bytes:
    """Re-export ``current`` to odp by patching what changed since ``baseline`` (the model as :func:`odp_to_slides`
    read it from ``original_bytes``) onto those same bytes -- so a picture, a table, a group, the notes, a transition,
    anything the app does not model, is still in the file, and every byte of ``content.xml`` outside what was edited is
    the original's. Every other part of the package is exactly as it was. With nothing changed the result *is*
    ``original_bytes``.

    What it patches: where an object is and how big (only the values that changed are written, into the start tag
    and nowhere else), its words (edited in place, line by line: a paragraph keeps its spans and links), its look
    (a new automatic style; the one the file had stays for whoever else uses it), objects and slides that were added
    or removed (``losses`` gets a ``removed-...`` entry for each thing that went with a removed slide or paragraph).
    ``info`` brings ``meta.xml`` up to date for a file that was changed (D411).

    Raises :class:`UnsupportedEdit` for what cannot be patched: a baseline that is not what the file holds, slides or
    objects moved relative to each other, and an object that changed what it is."""
    return _Patch(original_bytes, baseline, current, losses=losses, info=info).run()
