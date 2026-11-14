"""Converting between a :class:`~claudia_creates.SlideModel` and pptx, and adding a slide transition additively.

``slides_to_pptx`` is a minimal base export (text boxes, the three built-in shapes, pictures, best-effort styling)
-- not the ODF-first, loss-reporting import/export story of E10.3 (D5, D70), only enough of a real deck for
``add_transition`` to have something to attach to. Templates, layouts and groups (E10.4, E10.8) are not here yet,
same as the model itself (model.py's own docstring).

``add_transition`` is the additive extension the spike validated: python-pptx cannot write a ``<p:transition>``, so
this edits the slide's own already-written XML directly with ``lxml`` -- a transition lives inline in the slide
part, so no new parts, relationships or content-type overrides are needed, the simplest of the three extensions.
``fade`` is the one the spike checked against LibreOffice; ``wipe`` and ``push`` share the identical empty-element
shape in the schema and are offered on that basis, not independently checked against a real reader.

``pptx_to_slides`` and ``apply_edits_to_pptx`` close the loop D217 opened for docx, now for pptx (D219): a text box
or one of the three built-in autoshapes becomes a :class:`~claudia_creates.SlideObject`, and re-exporting an
*edited* import patches only the slides whose objects actually changed onto the original bytes (through
``claudia_opc_io.reconcile``), so a table, a picture, a slide claudia never modeled at all survives untouched. A
picture already in a pptx read this way is not imported as claudia's own "image" object kind either -- decoding
an arbitrary embedded picture back into an :class:`~claudia_core.ImageAsset` is separate, not-yet-built work
(unlike export, D213, this has no existing asset to fall back on) -- so it stays beyond-claudia content, same as
a table or a chart.

A slide's speaker notes are the notes page of its slide (D347): the Markdown of the model written as paragraphs of
bold and italic runs (``_notes.py``) and read back the same way, and an edit to them is patched onto the original's
notes page. A planned time (D343) is *not* written: the only time a pptx holds is the one that advances a slide by
itself, which is not the time a person means to spend on it, so planned times travel in claudia's own format.
"""

from __future__ import annotations

import posixpath
import zipfile
from io import BytesIO
from itertools import count

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.opc.package import Part
from pptx.util import Emu, Pt

from claudia_creates import (
    MAX_NOTES_LENGTH,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    ObjectBody,
    ShapeLibrary,
    SlideAnchor,
    SlideModel,
    VisualObject,
    paragraph_for,
)
from claudia_odf_io import Loss, LossLog
from claudia_opc_io import owns, reconcile

from ._notes import BULLET, Line, Run, lines_to_markdown, markdown_to_lines
from ._raster import Rasterise, blank_png
from ._styling import colour_of, look, page_colour, points_of

PNS = "http://schemas.openxmlformats.org/presentationml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ANS = "http://schemas.openxmlformats.org/drawingml/2006/main"

#: A 16:9 widescreen deck, the aspect ratio ``SLIDE_WIDTH``/``SLIDE_HEIGHT`` already is.
_DECK_WIDTH, _DECK_HEIGHT = Emu(12_192_000), Emu(6_858_000)
_BLANK_LAYOUT = 6

#: The three shapes claudia-creates ships (builtin_shapes/); a custom shape falls back to a plain rectangle.
_AUTOSHAPE = {
    "circle": MSO_SHAPE.OVAL,
    "rectangle": MSO_SHAPE.RECTANGLE,
    "triangle": MSO_SHAPE.ISOSCELES_TRIANGLE,
}
#: The reverse of ``_AUTOSHAPE``, for import: an autoshape of any other type (a star, a custom geometry) is not
#: one of claudia's three built-in shapes, so it is left as beyond-claudia content, same as a table or a picture.
_SHAPE_ID = {autoshape: claudia_id for claudia_id, autoshape in _AUTOSHAPE.items()}
#: The default styles a reimported object is given: pptx carries no named-style concept to map back from
#: (unlike docx's own style names), so every text box's words become "body-text" and every autoshape "plain-shape"
#: -- the same fallback ``slides_to_pptx`` itself falls back to when an object's style id is not a built-in one.
#: The other slot of each gets its own default (D304, D310): a text box's box "plain-box", a shape's words
#: "shape-label".
_DEFAULT_TEXT_STYLE, _DEFAULT_SHAPE_STYLE, _DEFAULT_LABEL_STYLE = "body-text", "plain-shape", "shape-label"
_DEFAULT_BOX_STYLE = "plain-box"

_TRANSITIONS = ("fade", "wipe", "push", "none")
_SPEEDS = ("fast", "med", "slow")


class UnsupportedEdit(Exception):
    """Raised by :func:`apply_edits_to_pptx` for an edit it cannot patch onto the original file yet: adding,
    removing or reordering a slide or an object, reordering the objects on a slide (stacking order lives outside
    any one object's own fields, so there is nothing a per-object diff can patch), or changing which kind of
    object (text/shape) or which shape outline an existing object uses. Moving, resizing, restyling or retexting
    an existing object is supported; see the implementation note for what is still missing."""


def _pt(css: dict[str, str], prop: str, pt_per_unit: float) -> Pt | None:
    """``css[prop]`` as python-pptx points, or ``None`` (see :func:`._styling.points_of`)."""
    found = points_of(css, prop, pt_per_unit)
    return Pt(found) if found is not None else None


def _rgb(css: dict[str, str], prop: str, over: str | None = None) -> RGBColor | None:
    """``css[prop]`` as a pptx colour, or ``None`` (see :func:`._styling.colour_of`)."""
    found = colour_of(css, prop, over)
    return RGBColor(*found) if found is not None else None


def _style_text(text_frame, css: dict[str, str], pt_per_unit: float, over: str | None = None) -> None:
    size = _pt(css, "font-size", pt_per_unit)
    color = _rgb(css, "color", over)
    for paragraph in text_frame.paragraphs:
        for run in paragraph.runs:
            if size is not None:
                run.font.size = size
            if color is not None:
                run.font.color.rgb = color


def _style_shape(shape, css: dict[str, str], pt_per_unit: float, over: str | None = None) -> None:
    fill = _rgb(css, "fill", over)
    if fill is not None:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    stroke = _rgb(css, "stroke", over)
    if stroke is not None:
        shape.line.color.rgb = stroke
    width = _pt(css, "stroke-width", pt_per_unit)
    if width is not None:
        shape.line.width = width


_DRAWINGML = "http://schemas.openxmlformats.org/drawingml/2006/main"
#: How PowerPoint (2019 and later) marks an object as decorative: an extension of its non-visual properties.
_DECORATIVE_NS = "http://schemas.microsoft.com/office/drawing/2017/decorative"
_DECORATIVE_URI = "{C183D7F6-B498-43B3-948B-1728B52AA6E4}"


def _describe(shape, body: ObjectBody) -> None:  # noqa: ANN001 (python-pptx's own shape classes are not one type)
    """What the object says to someone who cannot see it (BITV 1.1.1): its description as the alt text PowerPoint
    keeps on the shape, or — for a decorative object, which has no text alternative — PowerPoint's own mark."""
    properties = shape._element.xpath("./*[1]/p:cNvPr")[0]
    if body.decorative:
        properties.set("descr", "")  # (python-pptx names a picture's alt text after its file: "image.gif")
        ext = etree.SubElement(etree.SubElement(properties, f"{{{_DRAWINGML}}}extLst"), f"{{{_DRAWINGML}}}ext")
        ext.set("uri", _DECORATIVE_URI)
        mark = etree.SubElement(ext, f"{{{_DECORATIVE_NS}}}decorative", nsmap={"adec": _DECORATIVE_NS})
        mark.set("val", "1")
    elif body.description:
        properties.set("descr", body.description)


#: How a picture is drawn in PowerPoint 2016 and later: the SVG itself, next to an ordinary picture as its fallback.
_SVG_BLIP_URI = "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"
_SVG_BLIP_NS = "http://schemas.microsoft.com/office/drawing/2016/SVG/main"
_IMAGE_RELATIONSHIP = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
_BLIP_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_RELATIONSHIPS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _add_picture(slide, asset, box, body: ObjectBody, rasterise: Rasterise | None):  # noqa: ANN001, ANN202
    """A picture of ``asset`` on ``slide``. An SVG is drawn by ``rasterise`` into an ordinary picture if there is one:
    every program then shows the same thing, which LibreOffice does not for the SVG itself (it prefers the SVG to its
    fallback and leaves out what a diagram's style sheet gives). With none, it is written the way PowerPoint writes
    one: an empty picture and the drawing beside it, which PowerPoint 2016 and later show instead."""
    if asset.format != "svg":
        return slide.shapes.add_picture(BytesIO(asset.data), *box)
    if rasterise is not None:
        return slide.shapes.add_picture(BytesIO(rasterise(asset.data, round(body.w), round(body.h))), *box)
    picture = slide.shapes.add_picture(BytesIO(blank_png(round(body.w), round(body.h))), *box)
    package = slide.part.package
    name = package.next_partname("/ppt/media/svg%d.svg")
    svg_part = Part(name, "image/svg+xml", package, asset.data)
    relation = slide.part.relate_to(svg_part, _IMAGE_RELATIONSHIP)
    blip = picture._element.xpath(".//a:blip")[0]
    extensions = etree.SubElement(blip, f"{{{_BLIP_NS}}}extLst")
    extension = etree.SubElement(extensions, f"{{{_BLIP_NS}}}ext", uri=_SVG_BLIP_URI)
    svg = etree.SubElement(extension, f"{{{_SVG_BLIP_NS}}}svgBlip", nsmap={"asvg": _SVG_BLIP_NS})
    svg.set(f"{{{_RELATIONSHIPS}}}embed", relation)
    return picture


def pptx_export_losses(model: SlideModel, *, rasterised: bool = False) -> tuple[Loss, ...]:
    """What :func:`slides_to_pptx` cannot keep for ``model``: ``"svg-fallback"`` (a picture drawn as SVG, which only
    PowerPoint 2016 and later show; other programs show an empty picture unless a rasteriser was given, ``rasterised``)
    and ``"rendering-pending"`` (a rendered text container nothing has been drawn for yet: left out)."""
    losses = LossLog()
    for obj in model.objects.values():
        picture = model.picture_of(obj.body)
        asset = model.images.get(picture) if picture else None
        if obj.body.kind == "rendered" and asset is None:
            losses.add("rendering-pending")
        elif asset is not None and asset.format == "svg" and not rasterised:
            losses.add("svg-fallback")
    return losses.result()


def slides_to_pptx(model: SlideModel, *, rasterise: Rasterise | None = None) -> bytes:
    """``model`` as pptx bytes: one slide per slide id, its objects added bottom to top so the stacking order
    (the last one is in front) comes out the same as it is drawn in claudia-creates. An image object is written
    as a real picture, its asset's own bytes embedded as-is (D213) — python-pptx reads the format back out of
    them itself, the same way it would for a file opened from disk."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = _DECK_WIDTH, _DECK_HEIGHT
    scale_x, scale_y = _DECK_WIDTH / SLIDE_WIDTH, _DECK_HEIGHT / SLIDE_HEIGHT
    pt_per_unit = (_DECK_HEIGHT / 914_400 * 72) / SLIDE_HEIGHT
    layout = prs.slide_layouts[_BLANK_LAYOUT]
    page = page_colour(model)
    for slide_id in model.slides:
        slide = prs.slides.add_slide(layout)
        if model.notes_of(slide_id):
            _write_notes(slide, model.notes_of(slide_id))
        for obj in model.objects_on(slide_id):
            body, anchor = obj.body, obj.anchor
            box = (
                Emu(round(anchor.x * scale_x)),
                Emu(round(anchor.y * scale_y)),
                Emu(round(body.w * scale_x)),
                Emu(round(body.h * scale_y)),
            )

            css = look(model, body.style)
            words = body.paragraph.text if body.paragraph else ""
            text_css = look(model, body.paragraph.style) if body.paragraph else {}
            if body.kind == "text":
                shape = slide.shapes.add_textbox(*box)
                shape.text_frame.text = words
                _style_text(shape.text_frame, text_css, pt_per_unit, page)
                _describe(shape, body)
            elif body.kind in ("image", "rendered"):
                picture = model.picture_of(body)
                asset = model.images.get(picture) if picture else None
                if asset is not None:
                    _describe(_add_picture(slide, asset, box, body, rasterise), body)
            else:
                definition = model.shapes.get(body.shape) if body.shape else None
                auto_shape = _AUTOSHAPE.get(definition.id if definition else "", MSO_SHAPE.RECTANGLE)
                shape = slide.shapes.add_shape(auto_shape, *box)
                shape.text_frame.text = words
                _style_shape(shape, css, pt_per_unit, page)
                _style_text(shape.text_frame, text_css, pt_per_unit, page)
                _describe(shape, body)
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


def _notes_frame(slide):  # noqa: ANN001, ANN202
    """The text frame the notes of ``slide`` are in: the notes placeholder, or -- LibreOffice does not make one -- the
    one plain text box of the notes page (the only shape on it that is not a placeholder and has words); ``None`` if
    there is no such place."""
    notes_slide = slide.notes_slide
    if notes_slide.notes_text_frame is not None:
        return notes_slide.notes_text_frame
    boxes = [shape for shape in notes_slide.shapes if not shape.is_placeholder and shape.has_text_frame]
    return boxes[0].text_frame if len(boxes) == 1 else None


def _write_notes(slide, markdown: str) -> None:  # noqa: ANN001
    """Put ``markdown`` (the notes of the model) on the notes page of ``slide``, replacing the words that were there;
    a notes page is made if the slide has none. Raises :class:`UnsupportedEdit` for a notes page with no place for
    words."""
    frame = _notes_frame(slide)
    if frame is None:
        raise UnsupportedEdit("the notes page of this slide has no place for notes")
    frame.clear()
    lines, _ = markdown_to_lines(markdown)
    for number, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if number == 0 else frame.add_paragraph()
        for words in line:
            run = paragraph.add_run()
            run.text = words.text
            if words.bold:
                run.font.bold = True
            if words.italic:
                run.font.italic = True


def _is_on(value: str | None) -> bool:
    return value in ("1", "true")


def _paragraph_lines(paragraph) -> list[Line]:  # noqa: ANN001
    """The lines of one paragraph of a notes page: a line break starts a new line, a bullet or a number of the
    paragraph is the text ``"\u2022 "`` or ``"1. "`` in front of its first line, two spaces for each level."""
    lines: list[Line] = [[]]
    for child in paragraph._p:  # noqa: SLF001 -- python-pptx has no public way to see a line break
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag in ("r", "fld"):
            text = child.find(f"{{{ANS}}}t")
            properties = child.find(f"{{{ANS}}}rPr")
            bold = properties is not None and _is_on(properties.get("b"))
            italic = properties is not None and _is_on(properties.get("i"))
            lines[-1].append(Run(text.text or "" if text is not None else "", bold, italic))
        elif tag == "br":
            lines.append([])
    properties = paragraph._p.pPr  # noqa: SLF001
    if properties is not None:
        mark = (
            f"{BULLET} "
            if properties.find(f"{{{ANS}}}buChar") is not None
            else "1. "
            if properties.find(f"{{{ANS}}}buAutoNum") is not None
            else ""
        )
        if mark:
            lines[0].insert(0, Run("  " * paragraph.level + mark))
    return lines


def _notes_markdown(slide) -> str:  # noqa: ANN001
    """The notes page of ``slide`` as Markdown, ``""`` if there are none."""
    if not slide.has_notes_slide:
        return ""
    frame = _notes_frame(slide)
    if frame is None:
        return ""
    return lines_to_markdown(line for paragraph in frame.paragraphs for line in _paragraph_lines(paragraph))


def _classify(shape) -> str | None:  # noqa: ANN001 (python-pptx's own shape classes are not exported as one type)
    """``"text"``/``"shape"`` for a shape :func:`pptx_to_slides` models, ``None`` for anything else (a table, a
    picture, a chart, a group, an autoshape outside the three built-in ones) -- left as beyond-claudia content,
    same as a table or a picture that claudia has no model for at all."""
    if shape.shape_type == MSO_SHAPE_TYPE.TEXT_BOX:
        return "text"
    if shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and shape.auto_shape_type in _SHAPE_ID:
        return "shape"
    return None


def _slide_scale(prs) -> tuple[float, float]:  # noqa: ANN001
    """``(scale_x, scale_y)``: EMU per claudia unit along each axis, from the presentation's own slide size --
    not a fixed 16:9 assumption, so a deck of any aspect ratio imports onto claudia's 1600x900 slide space. A
    freshly opened or newly created presentation always has both (python-pptx's own stubs type them optional
    only because a bare, unsaved part could lack them, which never happens for a file that was just read back)."""
    width, height = prs.slide_width, prs.slide_height
    assert width is not None and height is not None
    return width / SLIDE_WIDTH, height / SLIDE_HEIGHT


def _modeled_shape_indices(pptx_slide) -> list[int]:  # noqa: ANN001
    """The indices into ``pptx_slide.shapes`` (in that same order) of the shapes :func:`pptx_to_slides` turns into
    objects -- shared with :func:`apply_edits_to_pptx` so the nth object :func:`pptx_to_slides` put on a slide and
    the nth index this returns for that same slide always refer to the same real shape, without carrying a
    side-channel index through :class:`~claudia_creates.SlideObject` itself."""
    return [index for index, shape in enumerate(pptx_slide.shapes) if _classify(shape) is not None]


def pptx_to_slides(pptx_bytes: bytes) -> SlideModel:
    """``pptx_bytes`` as a :class:`~claudia_creates.SlideModel`: one slide per slide, in order, a text box or one
    of the three built-in autoshapes on it becoming an object (bottom to top, same order ``pptx_bytes`` draws
    them in). Anything else on a slide -- a table, a picture, a chart, a group, an autoshape outside the three
    built-in ones -- is simply not added: claudia has no model for it, same as a table is invisible to
    ``docx_to_text``. Position and size are read back through the presentation's own slide size (not a fixed
    16:9 assumption), so a deck of any aspect ratio imports onto claudia's 1600x900 slide space. Rotation is read
    back too (``slides_to_pptx`` does not write one yet, so it is always 0 for anything claudia itself exported).
    Neither an object's own style nor its words' style can be recovered -- pptx carries no named-style concept
    the way Word does -- so every text box becomes ``"body-text"`` and every autoshape ``"plain-shape"``, for
    both, the same two styles ``slides_to_pptx`` itself falls back to."""
    prs = Presentation(BytesIO(pptx_bytes))
    model = SlideModel()
    if len(prs.slides) == 0:
        return SlideModel.empty()
    scale_x, scale_y = _slide_scale(prs)
    library = ShapeLibrary.load()
    defined: set[str] = set()
    object_ids = count(1)
    for slide_number, pptx_slide in enumerate(prs.slides, start=1):
        slide_id = f"s{slide_number}"
        model.insert_slide(slide_id)
        notes = _notes_markdown(pptx_slide)
        if 0 < len(notes) <= MAX_NOTES_LENGTH:  # longer is left in the file and out of the model (see the patch)
            model.set_notes(slide_id, notes)
        for index in _modeled_shape_indices(pptx_slide):
            shape = pptx_slide.shapes[index]
            kind = _classify(shape)
            assert kind is not None  # index came from _modeled_shape_indices, which keeps only classified shapes
            x, y = round(shape.left / scale_x), round(shape.top / scale_y)
            w, h = round(shape.width / scale_x), round(shape.height / scale_y)
            text = shape.text_frame.text if shape.has_text_frame else ""
            rotation = round(shape.rotation) % 360
            object_id = f"o{next(object_ids)}"
            if kind == "text":
                style, words, shape_id = _DEFAULT_BOX_STYLE, _DEFAULT_TEXT_STYLE, None
            else:
                style, words, shape_id = _DEFAULT_SHAPE_STYLE, _DEFAULT_LABEL_STYLE, _SHAPE_ID[shape.auto_shape_type]
                if shape_id not in defined:
                    definition = library.get(shape_id)
                    if definition is None:  # pragma: no cover -- the three ids in _SHAPE_ID are always shipped
                        raise ValueError(f"the built-in shape library has no shape {shape_id!r}")
                    model.define_shape(definition)
                    defined.add(shape_id)
            body = ObjectBody(
                object_id, kind, w, h, style, paragraph_for(object_id, words, text), shape=shape_id, rotation=rotation
            )
            model.insert_object(VisualObject(body, SlideAnchor(slide_id, x, y)))
    return model


def _qn(tag: str, ns: str = PNS) -> str:
    return f"{{{ns}}}{tag}"


def _resolve_target(source_dir: str, target: str) -> str:
    """An OPC relationship ``Target`` resolved against the directory of the part that references it: package-
    absolute (a leading ``/``) from the zip root, otherwise relative to ``source_dir``."""
    return target[1:] if target.startswith("/") else posixpath.normpath(posixpath.join(source_dir, target))


def _slide_part(members: dict[str, bytes], slide_index: int) -> str:
    """The zip member holding slide ``slide_index``'s XML, resolved through ``presentation.xml`` and its rels."""
    presentation = etree.fromstring(members["ppt/presentation.xml"])
    rels = etree.fromstring(members["ppt/_rels/presentation.xml.rels"])
    sld_id_lst = presentation.find(_qn("sldIdLst"))
    if sld_id_lst is None:
        raise ValueError("ppt/presentation.xml has no <p:sldIdLst>: not a well-formed presentation part")
    slide_ids = list(sld_id_lst)
    if not 0 <= slide_index < len(slide_ids):
        raise ValueError(f"slide_index must be from 0 to {len(slide_ids) - 1}, not {slide_index}")
    rid = slide_ids[slide_index].get(_qn("id", RNS))
    target = next((rel.get("Target") for rel in rels if rel.get("Id") == rid), None)
    if target is None:
        raise ValueError(f"ppt/_rels/presentation.xml.rels has no Target for relationship {rid!r}")
    return _resolve_target("ppt", target)


def _patch_notes(
    prs,  # noqa: ANN001
    members: dict[str, bytes],
    slide_number: int,
    baseline: SlideModel,
    current: SlideModel,
    slide_id: str,
) -> set[str]:
    """Write the notes of ``slide_id`` if they changed since ``baseline``; the names of the parts that holds
    claudia's to rewrite, ``set()`` if the notes did not change. A first notes page for a slide is a new part, and
    the slide's relationships and the content types have to say so, so those are claudia's too."""
    then, now = baseline.notes_of(slide_id), current.notes_of(slide_id)
    if then == now:
        return set()
    slide = prs.slides[slide_number]
    if _notes_markdown(slide) != then:
        raise UnsupportedEdit(
            f"the notes of slide {slide_number + 1} are too long to be held, so they cannot be replaced in the file"
        )
    had_page = slide.has_notes_slide
    _write_notes(slide, now)
    if had_page:
        return {str(slide.notes_slide.part.partname).lstrip("/")}
    part = _slide_part(members, slide_number)
    directory, _, name = part.rpartition("/")
    return {
        "[Content_Types].xml",
        "ppt/presentation.xml",
        "ppt/_rels/presentation.xml.rels",
        f"{directory}/_rels/{name}.rels",
    }


def apply_edits_to_pptx(original_bytes: bytes, baseline: SlideModel, current: SlideModel) -> bytes:
    """Re-export ``current`` to pptx by patching only the slides whose objects actually changed since
    ``baseline`` (the model as it stood right after :func:`pptx_to_slides` imported ``original_bytes``) onto
    those same bytes, instead of rebuilding the file from the model alone -- so a table, a picture, any slide
    claudia never touched survives untouched (D219, following D217's docx design). Unlike docx's single
    ``word/document.xml``, pptx keeps each slide in its own part, so the parts :func:`claudia_opc_io.reconcile`
    is told claudia owns are exactly the slides an edit actually reaches, computed fresh each call -- every other
    slide, layout, master, theme and media part comes back byte-for-byte as it was, not just semantically
    unchanged.

    Raises :class:`UnsupportedEdit` if a slide or an object was added, removed or reordered since ``baseline``,
    if the objects on a slide were reordered (stacking order is not one object's own field, so a per-object diff
    cannot see it), or if an object's kind or shape outline changed. Moving, resizing, retexting or restyling an
    existing object is supported, and so are the notes of a slide: they are written to its notes page (a slide's first
    notes make one), and the notes page is the only part that changes -- unless the file's notes were too long for
    the model to read, which are not replaced (:class:`UnsupportedEdit`)."""
    if baseline.slides != current.slides:
        raise UnsupportedEdit("adding, removing or reordering a slide cannot be patched onto the original file yet")
    baseline_by_id, current_by_id = dict(baseline.objects), dict(current.objects)
    added, removed = current_by_id.keys() - baseline_by_id.keys(), baseline_by_id.keys() - current_by_id.keys()
    if added or removed:
        raise UnsupportedEdit("adding or removing an object cannot be patched onto the original file yet")
    for slide_id in baseline.slides:
        before_order = [obj.id for obj in baseline.objects_on(slide_id)]
        after_order = [obj.id for obj in current.objects_on(slide_id)]
        if before_order != after_order:
            raise UnsupportedEdit("reordering the objects on a slide cannot be patched onto the original file yet")

    prs = Presentation(BytesIO(original_bytes))
    with zipfile.ZipFile(BytesIO(original_bytes)) as z:
        members = {name: z.read(name) for name in z.namelist()}
    scale_x, scale_y = _slide_scale(prs)
    slide_height = prs.slide_height
    assert slide_height is not None
    pt_per_unit = (slide_height / 914_400 * 72) / SLIDE_HEIGHT
    page = page_colour(current)

    touched_parts: set[str] = set()
    for slide_number, slide_id in enumerate(baseline.slides):
        touched_parts |= _patch_notes(prs, members, slide_number, baseline, current, slide_id)
        shape_indices = _modeled_shape_indices(prs.slides[slide_number])
        for position, object_id in enumerate(obj.id for obj in baseline.objects_on(slide_id)):
            before, after = baseline_by_id[object_id], current_by_id[object_id]
            if before == after:
                continue  # nothing about this object changed: leave its shape exactly as is
            if before.body.kind != after.body.kind or before.body.shape != after.body.shape:
                raise UnsupportedEdit(
                    "changing an object's kind or shape outline cannot be patched onto the original file yet"
                )
            shape = prs.slides[slide_number].shapes[shape_indices[position]]
            anchor, body = after.anchor, after.body
            shape.left, shape.top = Emu(round(anchor.x * scale_x)), Emu(round(anchor.y * scale_y))
            shape.width, shape.height = Emu(round(body.w * scale_x)), Emu(round(body.h * scale_y))
            shape.rotation = body.rotation
            shape.text_frame.text = body.paragraph.text if body.paragraph is not None else ""
            # Resolved against the document's own palette and style book, exactly as `slides_to_pptx` does it:
            # *computed* CSS still holds palette roles (``@accent/14``), which no file format can hold, so a
            # patched file came out with its colours missing (bugtracker UX-15).
            words_css = look(current, body.paragraph.style) if body.paragraph is not None else {}
            _style_text(shape.text_frame, words_css, pt_per_unit, page)
            if body.kind == "shape":
                _style_shape(shape, look(current, body.style), pt_per_unit, page)
            touched_parts.add(_slide_part(members, slide_number))

    patched = BytesIO()
    prs.save(patched)
    return reconcile(original_bytes, patched.getvalue(), owns(touched_parts))


def add_transition(
    pptx_bytes: bytes,
    *,
    slide_index: int,
    kind: str = "fade",
    speed: str = "slow",
    advance_on_click: bool = True,
) -> bytes:
    """``pptx_bytes`` with slide ``slide_index`` (0-based) given a ``<p:transition>``; ``kind="none"`` removes one
    instead. Replaces any transition the slide already had -- a slide carries at most one."""
    if kind not in _TRANSITIONS:
        raise ValueError(f"kind must be one of {_TRANSITIONS}, not {kind!r}")
    if speed not in _SPEEDS:
        raise ValueError(f"speed must be one of {_SPEEDS}, not {speed!r}")

    with zipfile.ZipFile(BytesIO(pptx_bytes)) as z:
        members = {name: z.read(name) for name in z.namelist()}
    part_name = _slide_part(members, slide_index)
    root = etree.fromstring(members[part_name])

    existing = root.find(_qn("transition"))
    if existing is not None:
        root.remove(existing)
    if kind != "none":
        attrs = f' spd="{speed}" advClick="{1 if advance_on_click else 0}"'
        transition_xml = f'<p:transition xmlns:p="{PNS}"{attrs}><p:{kind}/></p:transition>'
        transition_el = etree.fromstring(transition_xml)
        anchor = root.find(_qn("clrMapOvr"))
        if anchor is None:
            anchor = root.find(_qn("cSld"))
        if anchor is None:
            raise ValueError(f"slide {slide_index}'s XML has neither <p:clrMapOvr> nor <p:cSld>: not a slide part")
        anchor.addnext(transition_el)

    members[part_name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    return out.getvalue()
