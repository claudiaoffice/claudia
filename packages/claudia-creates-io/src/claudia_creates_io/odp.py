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

A slide's speaker notes are the words of its notes page (D347): the Markdown of the model is written as paragraphs with
bold and italic spans (``_notes.py``), read back the same way, and an edit patches only the text box of the notes
frame. A planned time (D343) is not written -- an odp has no such thing -- and ``odp_export_losses`` says so.

What the model sees of an odp: every ``draw:page`` is a slide (``s1``, ``s2``... by its place) and every text box
(a ``draw:frame`` holding a ``draw:text-box``), ellipse, rectangle and triangle directly on it is an object (``o1``,
``o2``... by its place over the whole deck), in the order the file draws them. An object is *modeled* only if the app
can hold it as it is: it needs a place and a size in lengths (turned only by a plain rotation, D459), all of it on
the slide, and it must pass the checks the model makes of every object (a size of at least a few units, a circle that
is round...). The same function decides that on the way in and on the way back, so an id means the same thing both
times.

What an object looks like is not mapped (D407, as for odt): every text box comes in as "plain-box" with "body-text"
words and every shape as "plain-shape" with "shape-label" words (D310), and its look in the file is untouched until
somebody gives it another look.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from html import escape
from zipfile import BadZipFile

from lxml import etree

from claudia_core import (
    MIN_OBJECT_SIZE,
    ImageAsset,
    ListItem,
    ObjectBody,
    Rasterise,
    VisualObject,
    name_key,
    nudge_into,
    paragraph_for,
    picture_body,
)
from claudia_core.stand_ins import file_font
from claudia_creates import MAX_NOTES_LENGTH, SLIDE_HEIGHT, SLIDE_WIDTH, ShapeLibrary, SlideAnchor, SlideModel
from claudia_odf_io import (
    CM_PER_INCH,
    MIME,
    NS,
    OUTLINES,
    BoxLook,
    DocumentInfo,
    Loss,
    LossLog,
    OdfError,
    XmlPart,
    default_style_xml,
    description_element,
    description_of,
    fill_and_line,
    graphic_styles,
    hex_of,
    hidden_content,
    inches,
    local_name,
    name_of,
    new_meta,
    new_package,
    odf_properties,
    outline_element,
    patch_language,
    picture_of,
    put_words,
    read_language,
    read_text,
    set_text,
    transform_of,
    turned_box,
    update_package_meta,
    xml_safe,
)
from claudia_opc_io import EMU_PER_POINT, read_parts, write_parts

from ._file_looks import Look, LookBook
from ._items import Mark, OdpListReader, OdpLists, agendas, list_styles, marks_of, odp_level, references, words_of
from ._names import FileNames
from ._notes import BULLET, Line, Run, lines_to_markdown, markdown_to_lines
from ._odp_fonts import DeckFonts
from ._odp_looks import StyleIndex, read_look
from ._styling import colour_of, is_bold, look, page_colour, points_of, style_for_font, take_body_font
from ._unwritten import ODP_WRITTEN, authored_objects, notes_losses, slides_unwritten_changes
from .pptx import UnsupportedEdit

_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>\n'
_NS_DECLS = {prefix: uri for prefix, uri in NS.items() if prefix != "xml"}

#: The size of a new slide, 16:9 the way LibreOffice makes one: what a model's 1600 by 900 units are written as.
_SLIDE_CM = (28.0, 15.75)

_DEFAULT_TEXT_STYLE, _DEFAULT_SHAPE_STYLE, _DEFAULT_LABEL_STYLE = "body-text", "plain-shape", "shape-label"
#: A text box's own box (D310): its words are Body text, its box this style without properties.
_DEFAULT_BOX_STYLE = "plain-box"


def _default_styles(kind: str) -> tuple[str, str]:
    """The styles an object of ``kind`` comes in with, for its two slots (D304, D310): a text box's box and words,
    a shape's outline and label — as ``pptx_to_slides`` gives them."""
    if kind == "text":
        return _DEFAULT_BOX_STYLE, _DEFAULT_TEXT_STYLE
    return _DEFAULT_SHAPE_STYLE, _DEFAULT_LABEL_STYLE


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


#: What a program writes as the name of a page nobody named: its number (``page1``, as LibreOffice and this module
#: write it). Read as no name (CODE-25).
_NUMBERED_PAGE = re.compile(r"page\d+")


def _page_names(model: SlideModel) -> list[str]:
    """The ``draw:name`` of each page, in order: the slide's name, or for a slide without one the first ``page<n>`` that
    no page or other thing of the document is called (a page name is one of a kind in the file)."""
    taken = {name_key(name) for name in model.names_in_use()}
    names: list[str] = []
    for slide_id in model.order:
        name = model.thing_name(slide_id)
        if not name:
            number = len(names) + 1
            while name_key(f"page{number}") in taken:
                number += 1
            name = f"page{number}"
        taken.add(name_key(name))
        names.append(name)
    return names


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


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
    rotation: int = 0  # whole degrees clockwise (D459)
    asset: ImageAsset | None = None  # the picture of an "image"
    description: str = ""  # what an "image" says to someone who cannot see it
    look: Look = field(default_factory=Look)  # how it looks, as far as the model has properties for it (D467)


_WHITE = "#ffffff"  # what a page is where a file says nothing of its colour


@dataclass
class _Slide:
    id: str
    element: etree._Element
    master: str | None
    size: tuple[float, float]  # inches
    background: str | None = None  # the colour of the page, as ``#rrggbb``, when the file says one (D467)
    objects: list[_Object] = field(default_factory=list)
    #: What is on the slide and not in the model, as ``(kind, detail)``: "picture", "table", "rotated-object"...
    left_out: list[tuple[str, str]] = field(default_factory=list)
    #: The notes page, and in it the frame and the text box of the notes (the frame of class "notes"), as far as
    #: the file has them; the notes as Markdown, and whether the file has notes the model could not read.
    notes_page: etree._Element | None = None
    notes_frame: etree._Element | None = None
    notes_box: etree._Element | None = None
    notes: str = ""
    notes_unread: bool = False


class _Probe:
    """A throwaway model that answers whether it could hold an object: the model's own checks, the same ones every
    command goes through."""

    def __init__(self) -> None:
        self.model = SlideModel()
        self.model.insert_slide("probe")
        library = ShapeLibrary.load()
        for shape_id in set(OUTLINES.values()):
            definition = library.get(shape_id)
            if definition is None:  # pragma: no cover - the three ids are always shipped
                raise ValueError(f"the built-in shape library has no shape {shape_id!r}")
            self.model.shapes.define(definition)

    def holds(
        self,
        kind: str,
        shape: str | None,
        box: tuple[int, int, int, int, int],
        text: str,
        asset: ImageAsset | None = None,
    ) -> bool:
        """Whether the model takes an object of this kind at ``box`` (``x, y, w, h, rotation``): a turned one is judged
        by its outline (D1022)."""
        if kind == "image":
            if asset is None:
                return False
            if asset.id not in self.model.images:
                self.model.images.define(asset)
            body = picture_body("o0", asset, (box[2], box[3]), rotation=box[4])
        else:
            style, words = _default_styles(kind)
            body = ObjectBody(
                "o0", kind, box[2], box[3], style, paragraph_for("o0", words, text), ref=shape, rotation=box[4]
            )
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
            width = inches(props.get(_q("fo", "page-width"))) if props is not None else None
            height = inches(props.get(_q("fo", "page-height"))) if props is not None else None
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


def _bare(element: etree._Element, graphics: dict[str, etree._Element]) -> bool:
    """Is this shape drawn with neither a fill nor an outline (its style, or one it is based on, says both are
    ``none``)? That is how LibreOffice writes what PowerPoint calls a text box: an unfilled rectangle with words in
    it."""
    said = odf_properties(element, graphics)
    return said.get("draw:fill") == "none" and said.get("draw:stroke") == "none"


def _background(
    page: etree._Element, master: str | None, index: StyleIndex, styles: etree._Element | None
) -> str | None:
    """The colour a page is filled with, as ``#rrggbb``: the page's own style says, or else that of its master page."""
    style = page.get(_q("draw", "style-name"))
    if style is None and styles is not None:
        found = next((m for m in styles.iter(_q("style", "master-page")) if m.get(_q("style", "name")) == master), None)
        style = found.get(_q("draw", "style-name")) if found is not None else None
    said = index.attributes("drawing-page", style, "style:drawing-page-properties")
    colour = said.get("draw:fill-color")
    return colour.lower() if said.get("draw:fill") == "solid" and colour and len(colour) == 7 else None


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
    element: etree._Element, graphics: dict[str, etree._Element], parts: Mapping[str, bytes]
) -> tuple[str, str | None] | tuple[None, tuple[str, str]]:
    """``("text", None)``, ``("shape", id)`` or ``("image", None)`` for what the model can be asked to hold;
    ``(None, (kind, detail))`` for what is left out, by what it is."""
    tag = local_name(element.tag)
    if tag == "frame":
        inner = {local_name(child.tag) for child in element if isinstance(child.tag, str)}
        # a table or an object carries a preview picture of itself: what it is comes before the picture
        for name, kind in (("table", "table"), ("object", "object"), ("object-ole", "object")):
            if name in inner:
                return None, (kind, "")
        if "image" in inner:
            return ("image", None) if picture_of(element, graphics, parts) is not None else (None, ("picture", ""))
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
        if outline in OUTLINES:
            if OUTLINES[outline] == "rectangle" and _has_words(element) and _bare(element, graphics):
                return "text", None
            return "shape", OUTLINES[outline]
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


def _box(element: etree._Element, size: tuple[float, float]) -> tuple[int, int, int, int, int, bool] | str:
    """Where an element is, in slide units, how far it is turned (whole degrees clockwise) and whether it was cut
    back to the slide (an unturned box that hangs over an edge, as a placeholder sized for another slide shape does),
    or why it has no place (``"rotated"``: a transform that is more than a rotation, ``"unplaced"``, ``"off-slide"``:
    nothing of it, or too little, is on the slide). A turned element is placed by its outline, as the model asks
    (D1022): one whose outline sticks out of the slide is off it."""
    transform = element.get(_q("draw", "transform"))
    values = [inches(element.get(_q("svg", name))) for name in ("x", "y", "width", "height")]
    turn = 0
    if transform is not None:
        if values[0] is not None or values[1] is not None or values[2] is None or values[3] is None:
            return "rotated"
        turned = turned_box(transform, values[2] * 2.54, values[3] * 2.54)
        if turned is None:
            return "rotated"
        degrees, x_cm, y_cm = turned
        turn = round(degrees) % 360
        values[0], values[1] = x_cm / 2.54, y_cm / 2.54
    if any(value is None for value in values):
        return "unplaced"
    x, y, w, h = (value for value in values if value is not None)
    per_x, per_y = size[0] / SLIDE_WIDTH, size[1] / SLIDE_HEIGHT
    box = (round(x / per_x), round(y / per_y), round(w / per_x), round(h / per_y))
    if nudge_into(*box, turn, SLIDE_WIDTH, SLIDE_HEIGHT) == box[:2]:
        return (*box, turn, False)
    if turn:
        return "off-slide"
    left, top = max(box[0], 0), max(box[1], 0)
    cut = (left, top, min(box[0] + box[2], SLIDE_WIDTH) - left, min(box[1] + box[3], SLIDE_HEIGHT) - top)
    if min(cut[2], cut[3]) < MIN_OBJECT_SIZE:
        return "off-slide"
    return (*cut, 0, True)


class _TextLooks:
    """How words look in a file, as far as notes need it: bold and italic, from the text and paragraph styles of
    both parts, with what a style is based on, and whether a list is numbered or bulleted."""

    def __init__(self, *roots: etree._Element | None) -> None:
        self._styles: dict[tuple[str, str], etree._Element] = {}
        self._numbered: dict[str, bool] = {}
        for root in roots:
            if root is None:
                continue
            for style in root.iter(_q("style", "style")):
                key = (style.get(_q("style", "family")) or "", style.get(_q("style", "name")) or "")
                self._styles.setdefault(key, style)
            for listing in root.iter(_q("text", "list-style")):
                level = next((c for c in listing if isinstance(c.tag, str) and "level-style" in c.tag), None)
                number = level is not None and local_name(level.tag) == "list-level-style-number"
                self._numbered.setdefault(listing.get(_q("style", "name")) or "", number)

    def of(self, family: str, name: str | None) -> tuple[bool | None, bool | None]:
        """``(bold, italic)`` of a style, each ``None`` if neither it nor what it is based on says."""
        bold = italic = None
        seen: set[str] = set()
        while name and name not in seen and (family, name) in self._styles:
            seen.add(name)
            style = self._styles[family, name]
            for props in style.findall("style:text-properties", NS):
                weight, slant = props.get(_q("fo", "font-weight")), props.get(_q("fo", "font-style"))
                if bold is None and weight:
                    bold = weight in ("bold", "600", "700", "800", "900")
                if italic is None and slant:
                    italic = slant in ("italic", "oblique")
            name = style.get(_q("style", "parent-style-name"))
        return bold, italic

    def numbered(self, name: str | None) -> bool:
        return self._numbered.get(name or "", False)


def _read_notes(slide: _Slide, looks: _TextLooks) -> None:
    """Find the notes frame of the slide's notes page and read its words as Markdown into ``slide``."""
    if slide.notes_page is None:
        return
    slide.notes_frame = next(
        (f for f in slide.notes_page.findall("draw:frame", NS) if f.get(_q("presentation", "class")) == "notes"), None
    )
    slide.notes_box = slide.notes_frame.find("draw:text-box", NS) if slide.notes_frame is not None else None
    if slide.notes_box is None:
        return
    lines: list[Line] = []
    _read_blocks(slide.notes_box, looks, lines, 0, None)
    markdown = lines_to_markdown(lines)
    if len(markdown) > MAX_NOTES_LENGTH:
        slide.notes_unread = True
        slide.left_out.append(("notes", "too-long"))
    else:
        slide.notes = markdown


def _read_blocks(
    holder: etree._Element, looks: _TextLooks, lines: list[Line], depth: int, list_style: str | None
) -> None:
    """The paragraphs under ``holder`` (a text box or a list item) as lines, a list's items with a marker."""
    for child in holder:
        if not isinstance(child.tag, str):
            continue
        name = local_name(child.tag)
        if name in ("p", "h"):
            made = _read_paragraph(child, looks, bold=name == "h")
            if depth:
                mark = "1. " if looks.numbered(list_style) else f"{BULLET} "
                made[0].insert(0, Run("  " * (depth - 1) + mark))
            lines.extend(made)
        elif name == "list":
            _read_blocks(child, looks, lines, depth, child.get(_q("text", "style-name")) or list_style)
        elif name == "list-item":
            _read_blocks(child, looks, lines, depth + 1, list_style)


def _read_paragraph(paragraph: etree._Element, looks: _TextLooks, *, bold: bool) -> list[Line]:
    """One paragraph as lines (a line break starts one), its spans as runs that are bold or italic."""
    base_bold, base_italic = looks.of("paragraph", paragraph.get(_q("text", "style-name")))
    lines: list[Line] = [[]]

    def add(text: str, is_bold: bool, is_italic: bool) -> None:
        if text:
            lines[-1].append(Run(text, is_bold, is_italic))

    def walk(element: etree._Element, is_bold: bool, is_italic: bool) -> None:
        add(re.sub(r"\s+", " ", element.text or ""), is_bold, is_italic)
        for child in element:
            if isinstance(child.tag, str):
                name = local_name(child.tag)
                if name == "s":
                    add(" " * int(child.get(_q("text", "c")) or 1), is_bold, is_italic)
                elif name == "tab":
                    add("\t", is_bold, is_italic)
                elif name == "line-break":
                    lines.append([])
                else:
                    span_bold, span_italic = looks.of("text", child.get(_q("text", "style-name")))
                    walk(
                        child,
                        is_bold if span_bold is None else span_bold,
                        is_italic if span_italic is None else span_italic,
                    )
            add(re.sub(r"\s+", " ", child.tail or ""), is_bold, is_italic)

    walk(paragraph, bold or bool(base_bold), bool(base_italic))
    return lines


def _scan(content: etree._Element, styles: etree._Element | None, parts: Mapping[str, bytes]) -> list[_Slide]:
    """Every slide of the deck, with the objects on it that the model holds, its notes and what else there is."""
    layouts = _layouts(styles, content)
    looks = _TextLooks(content, styles)
    masters = _masters(styles)
    page_styles = _drawing_page_styles(content, styles)
    graphics = graphic_styles(content, styles)
    index = StyleIndex(content, styles)
    probe, found, numbers = _Probe(), [], iter(range(1, 10**9))
    for number, page in enumerate(_presentation(content).findall("draw:page", NS), start=1):
        master = page.get(_q("draw", "master-page-name"))
        size = layouts.get(masters.get(master or "", ""))
        if size is None:
            size = next(iter(layouts.values()), (_SLIDE_CM[0] / CM_PER_INCH, _SLIDE_CM[1] / CM_PER_INCH))
        slide = _Slide(f"s{number}", page, master, size, _background(page, master, index, styles))
        for child in page:
            _scan_child(slide, child, probe, numbers, (graphics, parts, index))
        _read_notes(slide, looks)
        if page.get(_q("draw", "style-name")) and _has_transition(
            page_styles.get(page.get(_q("draw", "style-name")) or "")
        ):
            slide.left_out.append(("transition", ""))
        found.append(slide)
    return found


def _scan_child(
    slide: _Slide,
    child: etree._Element,
    probe: _Probe,
    numbers: Iterator[int],
    held: tuple[dict[str, etree._Element], Mapping[str, bytes], StyleIndex],
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
        if slide.notes_page is None:
            slide.notes_page = child
        return
    if namespace != NS["draw"] or local_name(tag) not in _DRAWN:
        return
    graphics, parts, index = held
    kind, what = _classify(child, graphics, parts)
    if kind is None:
        assert isinstance(what, tuple)
        slide.left_out.append(what)
        return
    shape = what if isinstance(what, str) else None
    box = _box(child, slide.size)
    paragraphs = _words(child, kind)
    text = "\n".join(read_text(p) for p in paragraphs)
    asset = picture_of(child, graphics, parts) if kind == "image" else None
    if isinstance(box, str):
        slide.left_out.append((f"{box}-object", kind))
    elif len(slide.objects) >= _MAX_OBJECTS or not probe.holds(kind, shape, box[:5], text, asset):
        slide.left_out.append(("unfit-object", kind))
    else:
        if box[5]:
            slide.left_out.append(("overhanging-object", kind))
        description = description_of(child) if kind == "image" else ""
        found = _Object(f"o{next(numbers)}", child, kind, shape, *box[:4], text, paragraphs, box[4], asset, description)
        if kind != "image":
            found.look = read_look(child, paragraphs, index, slide.size, shape=kind == "shape")
        slide.objects.append(found)


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
    return parts, content, styles, _scan(content, styles, parts)


def _slide_ids(slides: list[_Slide]) -> list[str]:
    return [slide.id for slide in slides]


def odp_to_slides(odp_bytes: bytes) -> SlideModel:
    """``odp_bytes`` as a :class:`~claudia_creates.SlideModel`: a slide per page, in order, called ``s1``, ``s2``...,
    a text box, ellipse, rectangle or triangle on it an object, called ``o1``, ``o2``... by its place in the deck, in
    the order the file draws them, from bottom to top. Place and size are read through the slide's own size (not an
    assumed shape: a 4:3 deck comes in as 4:3). What the model does not hold is in :func:`odp_import_losses`. Raises
    :class:`~claudia_odf_io.OdfError` for a file that is not an odp."""
    _, content, styles, slides = _document(odp_bytes)
    if not slides:
        empty = SlideModel.empty()
        empty.language = read_language(styles)
        return empty
    model, library, defined = SlideModel(), ShapeLibrary.load(), set()
    model.language = read_language(styles)
    items = OdpListReader(list_styles(content, styles), model.lists, model.schemes)
    fonts = DeckFonts(content, styles)
    take_body_font(model, fonts.body)
    looks = LookBook(model)
    # one palette for the deck: the page colour of its first slide, white where a file says none (D467)
    model.palette.set_colour("page", slides[0].background or _WHITE)
    names = FileNames()
    for slide in slides:
        model.insert_slide(slide.id, notes=slide.notes)
        said = slide.element.get(_q("draw", "name")) or ""
        if not _NUMBERED_PAGE.fullmatch(said) and (named := names.take(said)):
            model.slides.rename(slide.id, named)
        for found in slide.objects:
            called = names.take(found.element.get(_q("draw", "name")))
            if found.kind == "image":
                assert found.asset is not None  # the scan keeps an image only with its asset
                if found.asset.id not in model.images:
                    model.images.define(found.asset)
                body = picture_body(
                    found.id,
                    found.asset,
                    (found.w, found.h),
                    name=name_of(found.element),
                    description=found.description,
                    rotation=found.rotation,
                )
                body = replace(body, name=called)  # what the file calls it, not the file name of its picture
                model.insert_object(VisualObject(body, SlideAnchor(slide.id, found.x, found.y)))
                continue
            style, words = _default_styles(found.kind)
            if found.kind != "text":
                style = looks.outline(style, found.look.outline)
            words = looks.words(words, found.look.words)
            words = style_for_font(model, words, fonts.of_object(found.element, found.paragraphs))
            if found.kind == "text":
                shape = None
            else:
                shape = found.shape
                if shape not in defined and shape is not None:
                    definition = library.get(shape)
                    assert definition is not None  # the three ids are always shipped
                    model.shapes.define(definition)
                    defined.add(shape)
            body = ObjectBody(
                found.id,
                found.kind,
                found.w,
                found.h,
                style,
                paragraph_for(found.id, words, found.text).with_item(_item_of(found, items)),
                ref=shape,
                rotation=found.rotation,
                name=called,
            )
            model.insert_object(VisualObject(body, SlideAnchor(slide.id, found.x, found.y)))
    return model


def _item_of(found: _Object, items: OdpListReader) -> ListItem | None:
    """The item the words of an object are: its first paragraph is the first of an item of a list."""
    placed = odp_level(found.paragraphs[0], found.element) if found.paragraphs else None
    return None if placed is None else items.item(*placed)


def odp_import_losses(odp_bytes: bytes) -> tuple[Loss, ...]:
    """What :func:`odp_to_slides` does not show of the file, each as a code (``"picture"``, ``"table"``, ``"group"``,
    ``"notes"``, ``"transition"``, ``"rotated-object"``, ``"overhanging-object"`` (cut back to the slide)...) with how
    many there are, in the order they come. None of it is lost from the *file*: an edit exported with
    :func:`apply_edits_to_odp` keeps all of it."""
    _, content, styles, slides = _document(odp_bytes)
    fonts = DeckFonts(content, styles)
    losses = LossLog()
    looks = formatting = links = 0
    items = OdpListReader(list_styles(content, styles))
    hidden: dict[str, int] = {}
    page = slides[0].background if slides else None
    for slide in slides:
        for kind, detail in slide.left_out:
            losses.add(kind, detail)
        looks += slide.background != page  # one palette for the deck: the colour of another slide's page is not shown
        for found in slide.objects:
            if found.kind == "image":
                continue  # a picture has no look of its own that the model leaves out
            _item_of(found, items)
            looks += found.look.unread
            formatting += fonts.mixes(found.element, found.paragraphs)
            for paragraph in found.paragraphs:
                formatting += sum(
                    1
                    for span in paragraph.iter(_q("text", "span"))
                    if span.get(_q("text", "style-name")) and not fonts.only_a_font(span.get(_q("text", "style-name")))
                )
                links += sum(1 for _ in paragraph.iter(_q("text", "a")))
                for kind in hidden_content(paragraph):
                    hidden[kind] = hidden.get(kind, 0) + 1
    counted = (("look", looks), ("formatting", formatting), ("link", links), ("list-look", items.odd_looks))
    for code, number in counted:
        if number:
            losses.add(code, count=number)
    for kind, number in hidden.items():
        losses.add(kind, count=number)
    return _in_order(losses.result())


_ORDER = ("picture", "table", "object", "group", "shape", "frame")


def _in_order(losses: tuple[Loss, ...]) -> tuple[Loss, ...]:
    return tuple(sorted(losses, key=lambda loss: _ORDER.index(loss.kind) if loss.kind in _ORDER else len(_ORDER)))


# -- writing ---------------------------------------------------------------------------------------------------------
def _length(units: float, cm_per_unit: float) -> str:
    text = f"{units * cm_per_unit:.3f}".rstrip("0").rstrip(".")
    return f"{'0' if text in ('', '-0') else text}cm"


def _drawn(shape: str | None, attributes: Mapping[str, str]) -> etree._Element:
    """The element of a text box (``shape`` ``None``) or of the outline ``shape``, with ``attributes``."""
    element = outline_element(shape)
    for name, value in attributes.items():
        key_prefix, _, key_local = name.partition(":")
        element.set(_q(key_prefix, key_local), value)
    return element


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
        width = points_of(css, "stroke-width", pt_per_unit) or 0
        said = fill_and_line(BoxLook(fill, stroke, round(width * EMU_PER_POINT) if stroke else 0))
        properties = etree.fromstring(
            f'<style:graphic-properties xmlns:style="{NS["style"]}" xmlns:draw="{NS["draw"]}" '
            f'xmlns:svg="{NS["svg"]}" {said}/>'
        )
        return self._style(("graphic", said), "clg", "graphic", [properties])

    def text(self, *, bold: bool, italic: bool) -> str:
        """A text style that makes words bold, italic or both."""
        props: dict[str, str] = {}
        if bold:
            props["fo:font-weight"] = "bold"
        if italic:
            props["fo:font-style"] = "italic"
        return self._style(("text", bold, italic), "clt", "text", [_el("style", "text-properties", props)])

    def page(self, colour: tuple[int, int, int]) -> str:
        """A drawing page style that fills the page with ``colour``."""
        props = {"draw:fill": "solid", "draw:fill-color": hex_of(colour)}
        return self._style(
            ("page", *props.items()), "dp", "drawing-page", [_el("style", "drawing-page-properties", props)]
        )

    def paragraph(
        self, css: dict[str, str], over: str | None, pt_per_unit: float, font: str | None = None
    ) -> str | None:
        """A paragraph style for the size, colour, weight, slant and alignment of words and their ``font`` (the name the
        file is to say: never a stand-in, E3.13), or ``None`` if none of them is said."""
        size, colour = points_of(css, "font-size", pt_per_unit), colour_of(css, "color", over)
        align = {"left": "start", "right": "end", "center": "center", "justify": "justify"}.get(
            css.get("text-align", "")
        )
        text: dict[str, str] = {}
        if size:
            text["fo:font-size"] = f"{size:.1f}".rstrip("0").rstrip(".") + "pt"
        if colour:
            text["fo:color"] = hex_of(colour)
        if is_bold(css):
            text["fo:font-weight"] = "bold"
        if css.get("font-style") in ("italic", "oblique"):
            text["fo:font-style"] = "italic"
        if font:
            text["fo:font-family"] = _font_family(font)
        if not text and not align:
            return None
        properties = []
        if align:
            properties.append(_el("style", "paragraph-properties", {"fo:text-align": align}))
        if text:
            properties.append(_el("style", "text-properties", text))
        key = ("paragraph", align, *sorted(text.items()))
        return self._style(key, "clp", "paragraph", properties)


def _put_text(parent: etree._Element, text: str) -> None:
    """Add ``text`` at the end of ``parent`` the way an odf file holds it. White space is collapsed when a file is
    read, so a space is only written as itself between two words; any other (at the edge of a run, next to
    another) is a ``text:s``, and a tab a ``text:tab``."""
    pieces = re.split(r"( +|\t)", xml_safe(text))
    for index, piece in enumerate(pieces):
        if not piece:
            continue
        last = parent[-1] if len(parent) else None
        if piece == "\t":
            etree.SubElement(parent, _q("text", "tab"))
        elif piece[0] == " " and not (len(piece) == 1 and pieces[index - 1] and pieces[index + 1]):
            etree.SubElement(parent, _q("text", "s")).set(_q("text", "c"), str(len(piece)))
        elif last is None:
            parent.text = (parent.text or "") + piece
        else:
            last.tail = (last.tail or "") + piece


def _paragraphs(text: str, style_name: str | None) -> list[etree._Element]:
    paragraphs = []
    for line in text.split("\n"):
        paragraph = _el("text", "p", {"text:style-name": style_name} if style_name else None)
        set_text(paragraph, xml_safe(line))
        paragraphs.append(paragraph)
    return paragraphs


def _placing(anchor: SlideAnchor, body: ObjectBody, cm_per_unit: tuple[float, float]) -> dict[str, str]:
    """The attributes that put an object on its slide: its place and size, or -- for an object that is turned -- its
    size and the transform that turns it and puts it there (D459)."""
    per_x, per_y = cm_per_unit
    sizes = {"svg:width": _length(body.w, per_x), "svg:height": _length(body.h, per_y)}
    box = (anchor.x * per_x, anchor.y * per_y, body.w * per_x, body.h * per_y)
    transform = transform_of(body.rotation, box)
    if transform is None:
        return {"svg:x": _length(anchor.x, per_x), "svg:y": _length(anchor.y, per_y), **sizes}
    return {**sizes, "draw:transform": transform}


@dataclass
class _Writer:
    """What writing an object needs: the model it is from, the styles collected so far, the size of the slide."""

    model: SlideModel
    looks: _Looks
    cm_per_unit: tuple[float, float]
    pt_per_unit: float
    pictures: dict[str, str] = field(default_factory=dict)  # asset id -> name in the package
    rasterise: Rasterise | None = (
        None  # draws an SVG as a PNG for the programs that cannot (see ``claudia_core.raster``)
    )
    rasters: dict[str, bytes] = field(default_factory=dict)  # name in the package -> a PNG drawn by ``rasterise``
    losses: LossLog = field(default_factory=LossLog)
    marks: dict[str, Mark] = field(default_factory=dict)  # the list mark of each object's words, by object id
    lists: OdpLists | None = None  # the list styles and links written so far

    def words(self, obj: VisualObject, text: str, style: str | None, *, empty: bool = True) -> list[etree._Element]:
        """The paragraphs of an object's words (none for no words unless ``empty``), as the item of a list when they
        are one."""
        paragraphs = _paragraphs(text, style) if text or empty else []
        mark = self.marks.get(obj.body.id)
        if mark is None or not paragraphs or self.lists is None:
            return paragraphs
        return [self.lists.wrap(paragraphs, mark)]

    def object(self, obj: VisualObject) -> etree._Element | None:
        """The element of an object, called what people call it (``draw:name``, CODE-25), or ``None`` for an image
        whose picture the model does not have."""
        element = self._drawn(obj)
        if element is not None and obj.body.name:
            element.set(_q("draw", "name"), obj.body.name)
        return element

    def _drawn(self, obj: VisualObject) -> etree._Element | None:
        body, anchor = obj.body, obj.anchor
        over = page_colour(self.model)
        placing = _placing(anchor, body, self.cm_per_unit)
        text = words_of(self.model, body)
        words_css = look(self.model, body.paragraph.style) if body.paragraph is not None else {}
        words = self.looks.paragraph(words_css, over, self.pt_per_unit, _own_font(self.model, words_css))
        if body.kind in ("image", "container"):
            return self._picture(body, placing)
        if body.kind == "text":
            frame = _drawn(None, {"draw:style-name": self.looks.graphic({}, over, self.pt_per_unit), **placing})
            put_words(frame, self.words(obj, text, words))
            return frame
        graphic = self.looks.graphic(look(self.model, body.style), over, self.pt_per_unit)
        definition = self.model.shapes.get(body.shape) if body.shape else None
        shape_id = definition.id if definition else "rectangle"
        if body.kind == "chart":  # pragma: no cover - the presentation app has no chart objects yet (E6.6)
            self.losses.add("chart")
        element = _drawn(shape_id, {"draw:style-name": graphic, **placing})
        put_words(element, self.words(obj, text, words, empty=shape_id == "triangle"))
        return element

    def notes(self, markdown: str) -> etree._Element:
        """The notes page of a slide: its thumbnail and the notes frame, laid out as LibreOffice lays them out."""
        thumbnail = {
            "draw:layer": "layout",
            "svg:width": "12.699cm",
            "svg:height": "9.524cm",
            "svg:x": "3.175cm",
            "svg:y": "1.905cm",
            "presentation:class": "page",
        }
        page = _el("presentation", "notes")
        page.extend([_el("draw", "page-thumbnail", thumbnail), self.notes_frame(markdown)])
        return page

    def notes_frame(self, markdown: str) -> etree._Element:
        """The frame of the notes on a notes page, with the notes as the paragraphs of its text box."""
        frame = _el("draw", "frame", _NOTES_FRAME)
        etree.SubElement(frame, _q("draw", "text-box")).extend(self.note_paragraphs(markdown))
        return frame

    def note_paragraphs(self, markdown: str) -> list[etree._Element]:
        """The paragraphs of the notes: a line each, its bold and italic runs as spans with a style of their own."""
        paragraphs = []
        for line in markdown_to_lines(markdown)[0]:
            paragraph = _el("text", "p")
            for run in line:
                if run.bold or run.italic:
                    span = etree.SubElement(paragraph, _q("text", "span"))
                    span.set(_q("text", "style-name"), self.looks.text(bold=run.bold, italic=run.italic))
                    _put_text(span, run.text)
                else:
                    _put_text(paragraph, run.text)
            paragraphs.append(paragraph)
        return paragraphs

    def _picture(self, body: ObjectBody, placing: dict[str, str]) -> etree._Element | None:
        picture = self.model.picture_of(body)
        asset = self.model.images.get(picture) if picture else None
        if asset is None:  # an image object's asset is always held (the model refuses otherwise)
            self.losses.add("rendering-pending" if body.kind == "container" else "image-missing")
            return None
        if asset.format == "svg" and self.rasterise is not None and body.kind == "container":
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
#: Where the notes of a slide are on its notes page, as LibreOffice puts them.
_NOTES_FRAME = {
    "presentation:class": "notes",
    "draw:layer": "layout",
    "svg:width": "15.239cm",
    "svg:height": "11.429cm",
    "svg:x": "1.905cm",
    "svg:y": "12.065cm",
}


def _font_family(font: str) -> str:
    """``font`` as the value of ``fo:font-family``: quoted if it has a space."""
    return f"'{font}'" if " " in font else font


def _body_font(model: SlideModel) -> str | None:
    """The font the file is to name for Body text (E3.13)."""
    return file_font(look(model, _DEFAULT_TEXT_STYLE).get("font-family", ""))


def _own_font(model: SlideModel, css: dict[str, str]) -> str | None:
    """The font words in ``css`` are to name of their own: none if it is the body font, which the deck names once."""
    font = file_font(css.get("font-family", ""))
    return font if font != _body_font(model) else None


def _default_graphic_xml(font: str | None) -> str:
    """The default style of drawn things, which names the deck's body font; nothing for none."""
    if not font:
        return ""
    family = escape(xml_safe(_font_family(font)), quote=True)
    return (
        '<style:default-style style:family="graphic">'
        f'<style:text-properties fo:font-family="{family}"/></style:default-style>'
    )


def _styles_part(language: str | None, font: str | None = None) -> bytes:
    width, height = (f"{value:g}cm" for value in _SLIDE_CM)
    declared = " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in _NS_DECLS.items())
    return (
        f"{_DECLARATION}<office:document-styles {declared} "
        f'office:version="1.3"><office:styles>{default_style_xml(language)}{_default_graphic_xml(font)}</office:styles>'
        '<office:automatic-styles><style:page-layout style:name="PM1">'
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
    automatic style in values the file can hold. A container is the picture last made from its text: with
    ``rasterise`` (see ``claudia_core.raster``) a PNG every program draws, without it the SVG itself. ``info`` is the
    metadata (D411). Anything the file cannot hold is in :func:`odp_export_losses`."""
    cm_per_unit = (_SLIDE_CM[0] / SLIDE_WIDTH, _SLIDE_CM[1] / SLIDE_HEIGHT)
    pt_per_unit = _SLIDE_CM[1] / CM_PER_INCH * 72 / SLIDE_HEIGHT
    writer = _Writer(model, _Looks(set()), cm_per_unit, pt_per_unit, rasterise=rasterise)
    writer.marks, writer.lists = marks_of(model), OdpLists(model)
    root = _el("office", "document-content", {"office:version": "1.3"})
    for name in ("scripts", "font-face-decls"):
        etree.SubElement(root, _q("office", name))
    automatic = etree.SubElement(root, _q("office", "automatic-styles"))
    presentation = etree.SubElement(etree.SubElement(root, _q("office", "body")), _q("office", "presentation"))
    background = colour_of({"fill": page_colour(model) or ""}, "fill")
    for slide_id, name in zip(model.order, _page_names(model), strict=True):
        page = etree.SubElement(presentation, _q("draw", "page"))
        page.set(_q("draw", "name"), name)
        if background:
            page.set(_q("draw", "style-name"), writer.looks.page(background))
        page.set(_q("draw", "master-page-name"), "Default")
        for obj in model.objects_on(slide_id):
            element = writer.object(obj)
            if element is not None:
                page.append(element)
        if model.notes_of(slide_id):
            page.append(writer.notes(model.notes_of(slide_id)))
    automatic.extend(writer.looks.elements)
    automatic.extend(etree.fromstring(style) for style in writer.lists.styles)
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
        "presentation",
        content.encode(),
        _styles_part(model.language, _body_font(model)),
        meta=new_meta(info or DocumentInfo()),
        extra=extra,
    )


def odp_export_losses(model: SlideModel, *, rasterised: bool = False) -> tuple[Loss, ...]:
    """What :func:`slides_to_odp` cannot put into the file for ``model``, each as a code with how many: ``"authorship"``
    (who wrote which words of an object: an odp does not keep it), a ``"chart"`` (written as a rectangle), an
    ``"image-missing"`` (an image the document has no picture for), ``"rendering-pending"`` (a container
    nothing has been drawn for yet: it is left out, and says so here), ``"svg-picture"`` (a container
    written as the SVG itself, because nothing could draw it as a PNG: programs other than PowerPoint may leave out
    colours or text of a diagram; none with ``rasterised``) and ``"decorative"`` (an object marked as
    decoration: ODF 1.3 has no attribute for it, so a reader of the file sees an object nobody described); for notes
    ``"notes-link"``, ``"notes-image"``, ``"notes-code"`` and ``"notes-quote"`` (how many slides use what the file shows
    only as plain words), and ``"planned-time"`` (how many slides have a planned time, which an odp has no place for,
    D343)."""
    losses = LossLog()
    if authored := authored_objects(model):
        losses.add("authorship", count=authored)
    if written := agendas(model):
        losses.add("agenda", count=written)  # written as the lines it shows: it no longer follows the slides
    if written := references(model):
        losses.add("reference", count=written)  # written as what it reads as: it no longer follows its target
    for loss in notes_losses(model):
        losses.add(loss.kind, loss.detail, loss.count)
    decorative = sum(1 for obj in model.objects.values() if obj.body.decorative)
    if decorative:
        losses.add("decorative", count=decorative)
    for obj in model.objects.values():  # pragma: no cover - neither can be in a presentation yet (see above)
        if obj.body.kind == "chart":
            losses.add("chart")
        elif obj.body.kind == "image" and obj.body.image not in model.images:
            losses.add("image-missing")
    pending = sum(
        1 for obj in model.objects.values() if obj.body.kind == "container" and model.picture_of(obj.body) is None
    )
    if pending:
        losses.add("rendering-pending", count=pending)
    if not rasterised:
        vector = sum(
            1
            for obj in model.objects.values()
            if obj.body.kind == "container"
            and (a := model.images.get(model.picture_of(obj.body) or ""))
            and a.format == "svg"
        )
        if vector:
            losses.add("svg-picture", count=vector)
    return (*losses.result(), *odp_unwritten_changes(model))


def odp_unwritten_changes(model: SlideModel, baseline: SlideModel | None = None) -> tuple[Loss, ...]:
    """What changed in ``model`` that the odp converters do not write, each as a code with how many entries differ from
    ``baseline`` -- the model the original file was read as, for an edit-and-reexport -- or from an empty presentation,
    for a fresh file (``None``): ``"planned-time"`` (slides with a planned time, which an odp has no place for, D343),
    and the facets ``"print_setup"`` and ``"language"`` as ``"not-written"``."""
    return slides_unwritten_changes(model, baseline, written=ODP_WRITTEN)


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
        self.slides = _scan(self.part.root, self.styles_root, self.parts)
        self.presentation = _presentation(self.part.root)
        self.by_id = {slide.id: slide for slide in self.slides}
        self.found = {obj.id: obj for slide in self.slides for obj in slide.objects}
        self.looks = _Looks(self._style_names())
        self.changed = False
        self._page_names = {p.get(_q("draw", "name")) for p in self.presentation.findall("draw:page", NS)}
        self._after: dict[int, tuple[etree._Element, list[etree._Element]]] = {}
        self._into: dict[int, tuple[etree._Element, list[etree._Element]]] = {}
        self._before: dict[int, tuple[etree._Element, list[etree._Element]]] = {}
        self._tail: list[tuple[etree._Element, etree._Element]] = []  # notes pages, after all else on a page
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
            if self.baseline.order != SlideModel.empty().order or self.baseline.objects:
                raise UnsupportedEdit("the baseline is not the deck this file holds")
            return
        if list(self.baseline.order) != _slide_ids(self.slides):
            raise UnsupportedEdit("the baseline is not the deck this file holds")
        for slide in self.slides:
            if list(self.baseline.stack_of(slide.id)) != [obj.id for obj in slide.objects]:
                raise UnsupportedEdit("the baseline is not the deck this file holds")
        kept = [slide_id for slide_id in self.current.order if slide_id in self.by_id]
        if kept != [slide_id for slide_id in self.baseline.order if slide_id in set(kept)]:
            raise UnsupportedEdit("slides cannot be moved relative to each other in the file")
        for slide_id in kept:
            now = [i for i in self.current.stack_of(slide_id) if i in self.found]
            then = [i for i in self.baseline.stack_of(slide_id) if i in set(now)]
            if now != then:
                raise UnsupportedEdit("objects cannot be moved relative to each other on a slide in the file")

    # -- the run ---------------------------------------------------------------------------------------------------
    def run(self) -> bytes:
        if marks_of(self.baseline) != marks_of(self.current):
            raise UnsupportedEdit("lists in text boxes cannot be patched onto the original file yet")
        if any(
            words_of(self.baseline, obj.body) != words_of(self.current, self.current.objects[object_id].body)
            for object_id, obj in self.baseline.objects.items()
            if object_id in self.current.objects and obj.body.paragraph is not None and obj.body.paragraph.generated
        ):
            raise UnsupportedEdit("an agenda that changed cannot be patched onto the original file yet")
        for slide in self.slides:
            if slide.id not in self.current.order:
                self._remove_slide(slide)
        self._patch_slides()
        self._flush()
        self._patch_language()
        if not self.changed:
            return self.original
        self._add_styles()
        self.parts["content.xml"] = self.part.result()
        if self.info is not None:
            update_package_meta(self.parts, self.info)
        return write_parts(self.parts)

    def _patch_language(self) -> None:
        """Give the file the language of the presentation, in the default style of its ``styles.xml`` (D461)."""
        if self.baseline.language == self.current.language:
            return
        if "styles.xml" not in self.parts:
            raise UnsupportedEdit("this file has no styles.xml to say the language in")
        styles = XmlPart(self.parts["styles.xml"])
        try:
            changed = patch_language(styles, self.baseline.language, self.current.language)
        except OdfError as problem:
            raise UnsupportedEdit(str(problem)) from problem
        if changed:
            self.parts["styles.xml"] = styles.result()
            self.changed = True

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
        for slide_id in self.current.order:
            slide = self.by_id.get(slide_id)
            if slide is not None:
                self._patch_slide(slide)
                previous = slide.element
                continue
            objects = self.current.objects_on(slide_id)
            if not objects and not self.slides and not self.current.notes_of(slide_id):
                continue  # the one empty slide of a deck with no pages is not a page
            self._new_slide(slide_id, objects, previous)

    def _per_cm(self, slide_size: tuple[float, float]) -> tuple[float, float]:
        return slide_size[0] * CM_PER_INCH / SLIDE_WIDTH, slide_size[1] * CM_PER_INCH / SLIDE_HEIGHT

    def _writer(self, size: tuple[float, float]) -> _Writer:
        return _Writer(self.current, self.looks, self._per_cm(size), size[1] * 72 / SLIDE_HEIGHT)

    def _patch_slide(self, slide: _Slide) -> None:
        name = self.current.thing_name(slide.id)
        if name != self.baseline.thing_name(slide.id):
            self.part.set_attributes(slide.element, {"draw:name": name or self._page_name()})
            self.changed = True
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
        self._patch_notes(slide, writer)
        self._lose(writer)

    def _patch_notes(self, slide: _Slide, writer: _Writer) -> None:
        """Write the notes of a slide if they changed: the words of the notes frame are replaced and nothing else of
        the notes page is touched; a slide with no notes page, or none with a frame for them, gets what is missing."""
        then, now = self.baseline.notes_of(slide.id), self.current.notes_of(slide.id)
        if then == now:
            return
        if slide.notes_unread:
            raise UnsupportedEdit("the notes of this slide are too long to be held, so they cannot be replaced")
        if slide.notes_box is not None:
            words = copy.deepcopy(slide.notes_box)  # the box as it was, with its attributes, but for what is in it
            words.text = None
            for child in list(words):
                words.remove(child)
            words.extend(writer.note_paragraphs(now))
            self.part.replace(slide.notes_box, words)
        elif slide.notes_frame is not None:
            box = _el("draw", "text-box")
            box.extend(writer.note_paragraphs(now))
            self.part.insert_into(slide.notes_frame, box)
        elif slide.notes_page is not None:
            self.part.insert_into(slide.notes_page, writer.notes_frame(now))
        else:
            drawn = [child for child in slide.element if isinstance(child.tag, str)]
            if drawn:
                self._tail.append((drawn[-1], writer.notes(now)))
            else:
                self._into.setdefault(id(slide.element), (slide.element, []))[1].append(writer.notes(now))
        self.changed = True

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
        size = neighbour.size if neighbour is not None else (_SLIDE_CM[0] / CM_PER_INCH, _SLIDE_CM[1] / CM_PER_INCH)
        page = _el("draw", "page", {"draw:name": self.current.thing_name(slide_id) or self._page_name()})
        if master:
            page.set(_q("draw", "master-page-name"), master)
        writer = self._writer(size)
        for obj in objects:
            element = writer.object(obj)
            if element is not None:
                page.append(element)
        if self.current.notes_of(slide_id):
            page.append(writer.notes(self.current.notes_of(slide_id)))
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
        for anchor, notes in self._tail:  # after the objects that went in at the same place
            self.part.insert_after(anchor, notes)

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
        attributes, taken = self._moved(before, after, self._per_cm(slide.size))
        if before.body.name != after.body.name:
            if after.body.name:
                attributes["draw:name"] = after.body.name
            else:
                taken = (*taken, "draw:name")
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
                style_name = self.looks.paragraph(new_words, over, pt_per_unit, _own_font(self.current, new_words))
        text = words_after.text if words_after is not None else ""
        if attributes or taken:
            self.part.set_attributes(found.element, attributes, remove=taken)
            self.changed = True
        if after.body.kind == "image" and before.body.description != after.body.description:
            self._redescribe(found.element, after.body.description)
            self.changed = True
        if text != found.text or style_name is not False:
            self._retext(found, text, style_name)
            self.changed = True

    def _redescribe(self, frame: etree._Element, description: str) -> None:
        """Say ``description`` as the ``svg:desc`` of a picture's frame (none for no description)."""
        existing = description_element(frame)
        if not description:
            if existing is not None:
                self.part.remove(existing)
            return
        new = _el("svg", "desc")
        new.text = xml_safe(description)
        if existing is not None:
            self.part.replace(existing, new)
        else:
            self.part.insert_into(frame, new)

    @staticmethod
    def _moved(
        before: VisualObject, after: VisualObject, per_cm: tuple[float, float]
    ) -> tuple[dict[str, str], tuple[str, ...]]:
        """The attributes to set and those to take off for the new place, size and turn of an object (D459): only what
        differs between where the object was and where it is, so a turn alone leaves the file's own size as it is
        (D1021). Turning an object takes ``svg:x`` and ``svg:y`` off, turning it back upright the transform."""
        then, now = _placing(before.anchor, before.body, per_cm), _placing(after.anchor, after.body, per_cm)
        return {name: value for name, value in now.items() if then.get(name) != value}, tuple(
            name for name in then if name not in now
        )

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


def _words_of(css: dict[str, str]) -> tuple[str | None, ...]:
    return css.get("font-size"), css.get("color"), css.get("text-align"), css.get("font-family")


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
