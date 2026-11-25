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
from dataclasses import replace
from io import BytesIO
from itertools import count

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.opc.package import Part
from pptx.util import Emu, Pt

from claudia_core import Rasterise, blank_png, nudge_into, picture_body
from claudia_core.assets import MAX_ALT_CHARS
from claudia_core.stand_ins import file_font
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
from claudia_odf_io import DocumentInfo, Loss, LossLog, stamp_office_meta
from claudia_opc_io import (
    DRAWINGML,
    PRESET,
    ThemeFonts,
    add_svg,
    mark_decorative,
    owns,
    parse_xml,
    read_parts,
    reconcile,
)

from ._file_looks import LookBook
from ._items import (
    ItemReader,
    agendas,
    marks_of,
    read_pptx_mark,
    references,
    sayable_in_pptx,
    words_of,
    write_pptx_mark,
)
from ._names import FileNames
from ._notes import BULLET, Line, Run, lines_to_markdown, markdown_to_lines
from ._pptx_fonts import deck_theme, mixes_fonts, shape_font, write_body_font
from ._pptx_looks import Theme, read_look
from ._pptx_placeholders import for_words, list_styles
from ._styling import colour_of, is_bold, look, page_colour, points_of, style_for_font, take_body_font
from ._unwritten import PPTX_WRITTEN, authored_objects, notes_losses, slides_unwritten_changes
from .pptx_pictures import alt_text_of, held_picture
from .pptx_setup import part_names, read_print_setup, speak, spoken, write_print_setup

PNS = "http://schemas.openxmlformats.org/presentationml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ANS = "http://schemas.openxmlformats.org/drawingml/2006/main"

#: A 16:9 widescreen deck, the aspect ratio ``SLIDE_WIDTH``/``SLIDE_HEIGHT`` already is.
_DECK_WIDTH, _DECK_HEIGHT = Emu(12_192_000), Emu(6_858_000)
_BLANK_LAYOUT = 6

#: The three shapes claudia-creates ships (builtin_shapes/), by the preset DrawingML names them with
#: (:data:`claudia_opc_io.PRESET`); a custom shape falls back to a plain rectangle.
_AUTOSHAPE = {shape: MSO_SHAPE.from_xml(preset) for shape, preset in PRESET.items()}
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


_ALIGNMENT = {
    "left": PP_ALIGN.LEFT,
    "center": PP_ALIGN.CENTER,
    "right": PP_ALIGN.RIGHT,
    "justify": PP_ALIGN.JUSTIFY,
}


def _style_text(text_frame, css: dict[str, str], pt_per_unit: float, over: str | None = None) -> None:
    size = _pt(css, "font-size", pt_per_unit)
    color = _rgb(css, "color", over)
    # the font the words are shown in, a generic family as the font that shows it (E3.13, CODE-42)
    font = file_font(css["font-family"]) if "font-family" in css else None
    align = _ALIGNMENT.get(css.get("text-align", ""))
    for paragraph in text_frame.paragraphs:
        if align is not None:
            paragraph.alignment = align
        for run in paragraph.runs:
            if size is not None:
                run.font.size = size
            if color is not None:
                run.font.color.rgb = color
            if is_bold(css):
                run.font.bold = True
            if css.get("font-style") in ("italic", "oblique"):
                run.font.italic = True
            if font is not None:
                run.font.name = font


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


def _turn(shape, body: ObjectBody) -> None:  # noqa: ANN001 (python-pptx's own shape classes are not one type)
    """Write the turn of ``body``: whole degrees clockwise about the centre, which is what ``a:xfrm rot`` is too (D459).
    The shape keeps the place and size of the *unturned* frame, as PowerPoint writes them. An upright object gets no
    attribute at all, so a file of upright objects is the file it always was."""
    if body.rotation:
        shape.rotation = body.rotation


def _call(shape, name: str) -> None:  # noqa: ANN001 (python-pptx's own shape classes are not one type)
    """Write what people call the object (D550, CODE-25); one without a name keeps the name the file gives it."""
    if name:
        shape.name = name


def _finish(shape, body: ObjectBody) -> None:  # noqa: ANN001 (python-pptx's own shape classes are not one type)
    """What every kind of object writes on its shape: its turn, what it says to someone who cannot see it, its name."""
    _turn(shape, body)
    _describe(shape, body)
    _call(shape, body.name)


def _call_slide(slide, name: str) -> None:  # noqa: ANN001
    """Write what people call the slide (``p:cSld/@name``, D550, CODE-25); ``""`` takes the name away."""
    page = slide._element.find(_qn("cSld"))  # noqa: SLF001
    if name:
        page.set("name", name)
    else:
        page.attrib.pop("name", None)


def _describe(shape, body: ObjectBody) -> None:  # noqa: ANN001 (python-pptx's own shape classes are not one type)
    """What the object says to someone who cannot see it (BITV 1.1.1): its description as the alt text PowerPoint
    keeps on the shape, or — for a decorative object, which has no text alternative — PowerPoint's own mark."""
    properties = shape._element.xpath("./*[1]/p:cNvPr")[0]
    properties.attrib.pop("descr", None)
    for old in properties.findall(f"{{{DRAWINGML['a']}}}extLst"):  # the mark of an earlier writing
        properties.remove(old)
    if body.decorative:
        mark_decorative(properties)  # (and no description: python-pptx names a picture's after its file, "image.gif")
    elif body.description:
        properties.set("descr", body.description)


_IMAGE_RELATIONSHIP = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


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
    add_svg(picture._element.xpath(".//a:blip")[0], relation)
    return picture


def pptx_export_losses(model: SlideModel, *, rasterised: bool = False) -> tuple[Loss, ...]:
    """What :func:`slides_to_pptx` cannot keep for ``model``, each as a code with how many: ``"authorship"`` (who wrote
    which words of an object: a pptx does not keep it), ``"notes-link"``, ``"notes-image"``, ``"notes-code"`` and
    ``"notes-quote"`` (slides whose notes use what the file shows only as plain words), ``"svg-fallback"`` (a picture
    drawn as SVG, which only PowerPoint 2016 and later show; other programs show an empty picture unless a rasteriser
    was given, ``rasterised``), ``"rendering-pending"`` (a container nothing has been drawn for yet:
    left out), ``"list-look"`` (a list marker PowerPoint has no automatic number for, such as ``2.1``: left out),
    ``"agenda"`` (an agenda, written as the lines it shows: it no longer follows the slides) and
    what :func:`pptx_unwritten_changes` says of a fresh file (``"planned-time"``...)."""
    losses = LossLog()
    if authored := authored_objects(model):
        losses.add("authorship", count=authored)
    if unsaid := sum(1 for mark in marks_of(model).values() if not sayable_in_pptx(mark)):
        losses.add("list-look", count=unsaid)
    if written := agendas(model):
        losses.add("agenda", count=written)
    if written := references(model):
        losses.add("reference", count=written)  # written as what it reads as: it no longer follows its target
    for loss in notes_losses(model):
        losses.add(loss.kind, loss.detail, loss.count)
    for obj in model.objects.values():
        picture = model.picture_of(obj.body)
        asset = model.images.get(picture) if picture else None
        if obj.body.kind == "container" and asset is None:
            losses.add("rendering-pending")
        elif asset is not None and asset.format == "svg" and not rasterised:
            losses.add("svg-fallback")
    return (*losses.result(), *pptx_unwritten_changes(model))


def pptx_unwritten_changes(model: SlideModel, baseline: SlideModel | None = None) -> tuple[Loss, ...]:
    """What changed in ``model`` that the pptx converters do not write, each as a code with how many entries differ from
    ``baseline`` -- the model the original file was read as, for an edit-and-reexport -- or from an empty presentation,
    for a fresh file (``None``): ``"planned-time"`` (slides with a planned time: the only time a pptx holds advances
    a slide by itself, D343), ``"print_setup"`` as ``"not-written"`` for what a pptx has no place for (the margins and
    the page numbers: the layout, paper and orientation are written) and ``"language"`` too for a kept file, whose
    runs keep the language they have (a fresh file says it on every run, D461)."""
    written = PPTX_WRITTEN | ({"language"} if baseline is None else frozenset())
    return slides_unwritten_changes(model, baseline, written=written, keeps_print_layout=True)


def pptx_import_losses(pptx_bytes: bytes) -> tuple[Loss, ...]:
    """What :func:`pptx_to_slides` does not show of the file, each as a code (``"picture"``, ``"table"``, ``"chart"``,
    ``"group"``, ``"object"`` for any other shape, ``"transition"``, ``"animation"``, ``"notes"`` too long for the
    model, ``"turn"`` an object turned so far that it cannot lie on the slide, which is read upright, and on the objects
    it models ``"look"``, ``"formatting"`` and ``"link"``: what the model, which gives every object the default look,
    does not show) with how many there are, in the order they come. None of it is lost from
    the *file*: an edit exported with :func:`apply_edits_to_pptx` keeps all of it."""
    prs = Presentation(BytesIO(pptx_bytes))
    losses = LossLog()
    scale_x, scale_y = _slide_scale(prs)
    theme, colours = deck_theme(prs), _theme_of(prs)
    page = _background(prs, prs.slides[0], colours) if len(prs.slides) else None
    for pptx_slide in prs.slides:
        if _background(prs, pptx_slide, colours) != page:
            losses.add("look")  # one palette for the deck: the page colour of another slide is not shown
        for shape in pptx_slide.shapes:
            if _classify(shape) is None and not for_words(shape):  # an empty title or body shows nothing
                losses.add(_UNMODELED.get(shape.shape_type, "object"))
            elif _cannot_turn(shape, scale_x, scale_y):
                losses.add("turn")
        for shape in pptx_slide.shapes:
            if (kind := _classify(shape)) is not None:
                _note_words_and_look(shape, kind, losses, theme, colours, scale_x)
        for code, tag in (("transition", "transition"), ("animation", "timing")):
            if pptx_slide._element.find(_qn(tag)) is not None:
                losses.add(code)
        if len(_notes_markdown(pptx_slide)) > MAX_NOTES_LENGTH:
            losses.add("notes")
    return losses.result()


def _theme_of(prs) -> Theme:  # noqa: ANN001
    """The colours of the theme the deck's slide master uses (none, for a deck that has no theme part)."""
    try:
        return Theme(prs.slide_master.part.part_related_by(RT.THEME).blob)
    except KeyError:
        return Theme()


def _background(prs, pptx_slide, colours: Theme) -> str | None:  # noqa: ANN001
    """The colour of the page of ``pptx_slide`` as ``#rrggbb``: its own, else its layout's, else its master's, as far as
    that is one plain colour (a gradient or a picture is none)."""
    for owner in (pptx_slide, pptx_slide.slide_layout, prs.slide_master):
        element = owner._element.find(f"{_qn('cSld')}/{_qn('bg')}")
        if element is None:
            continue
        fill = element.find(f"{_qn('bgPr')}/{{{ANS}}}solidFill")
        if fill is not None:
            return colours.colour(fill)[0]
        reference = element.find(_qn("bgRef"))
        return colours.colour(reference)[0] if reference is not None else None
    return None


def _note_words_and_look(  # noqa: ANN001
    shape, kind: str, losses: LossLog, theme: ThemeFonts, colours: Theme, scale_x: float
) -> None:
    """Add to ``losses`` what the model does not show of a modeled ``shape`` of ``kind``: ``"look"`` (a fill, outline or
    colour the model has no property for, or one made lighter or translucent), ``"formatting"`` (a bold, italic or
    underlined run, or words in more than one font) and ``"link"`` (D461). The font is not a look the model leaves
    out: it comes in as the words' style (E3.13)."""
    if kind == "image":
        return  # a picture has no look of its own the model leaves out
    if read_look(shape._element, colours, 1 / scale_x, outline=kind == "shape").unread:
        losses.add("look")
    if mixes_fonts(shape, theme):
        losses.add("formatting")
    if shape.has_text_frame:
        for run in (run for paragraph in shape.text_frame.paragraphs for run in paragraph.runs):
            if run.font.bold or run.font.italic or run.font.underline:
                losses.add("formatting")
            if run.hyperlink.address is not None:
                losses.add("link")


def _cannot_turn(shape, scale_x: float, scale_y: float) -> bool:  # noqa: ANN001
    """Is ``shape`` turned so far that its outline cannot lie on the slide, so that it is read upright (D1022)?"""
    rotation = round(shape.rotation) % 360
    if rotation == 0:
        return False
    x, y = round(shape.left / scale_x), round(shape.top / scale_y)
    w, h = round(shape.width / scale_x), round(shape.height / scale_y)
    return nudge_into(x, y, w, h, rotation, SLIDE_WIDTH, SLIDE_HEIGHT) is None


#: The kinds of shape a pptx has that the model does not show, by the code they are reported under.
_UNMODELED = {
    MSO_SHAPE_TYPE.PICTURE: "picture",
    MSO_SHAPE_TYPE.TABLE: "table",
    MSO_SHAPE_TYPE.CHART: "chart",
    MSO_SHAPE_TYPE.GROUP: "group",
}


def slides_to_pptx(model: SlideModel, *, rasterise: Rasterise | None = None, info: DocumentInfo | None = None) -> bytes:
    """``model`` as pptx bytes: one slide per slide id, its objects added bottom to top so the stacking order
    (the last one is in front) comes out the same as it is drawn in claudia-creates. An image object is written
    as a real picture, its asset's own bytes embedded as-is (D213) — python-pptx reads the format back out of
    them itself, the same way it would for a file opened from disk. The file says in its properties who made the deck
    and when and who changed it last, from ``info``; what ``info`` does not know it leaves out (D466)."""
    prs = Presentation()
    write_body_font(prs, file_font(look(model, "body-text").get("font-family", "")))
    prs.slide_width, prs.slide_height = _DECK_WIDTH, _DECK_HEIGHT
    scale_x, scale_y = _DECK_WIDTH / SLIDE_WIDTH, _DECK_HEIGHT / SLIDE_HEIGHT
    pt_per_unit = (_DECK_HEIGHT / 914_400 * 72) / SLIDE_HEIGHT
    layout = prs.slide_layouts[_BLANK_LAYOUT]
    page = page_colour(model)
    marks = marks_of(model)
    background = colour_of({"fill": page or ""}, "fill")
    for slide_id in model.order:
        slide = prs.slides.add_slide(layout)
        _call_slide(slide, model.thing_name(slide_id))
        if background is not None:
            slide.background.fill.solid()
            slide.background.fill.fore_color.rgb = RGBColor(*background)
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
            words = words_of(model, body)
            text_css = look(model, body.paragraph.style) if body.paragraph else {}
            if body.kind == "text":
                shape = slide.shapes.add_textbox(*box)
                shape.text_frame.text = words
                _style_text(shape.text_frame, text_css, pt_per_unit, page)
                write_pptx_mark(shape.text_frame.paragraphs[0]._p, marks.get(body.id))  # noqa: SLF001
                _finish(shape, body)
            elif body.kind in ("image", "container"):
                picture = model.picture_of(body)
                asset = model.images.get(picture) if picture else None
                if asset is not None:
                    shape = _add_picture(slide, asset, box, body, rasterise)
                    _finish(shape, body)
            else:
                definition = model.shapes.get(body.shape) if body.shape else None
                auto_shape = _AUTOSHAPE.get(definition.id if definition else "", MSO_SHAPE.RECTANGLE)
                shape = slide.shapes.add_shape(auto_shape, *box)
                shape.text_frame.text = words
                _style_shape(shape, css, pt_per_unit, page)
                _style_text(shape.text_frame, text_css, pt_per_unit, page)
                write_pptx_mark(shape.text_frame.paragraphs[0]._p, marks.get(body.id))  # noqa: SLF001
                _finish(shape, body)
    write_print_setup(prs, model.print_setup)  # a new presentation always has the part that says it
    speak(_runs_of_words(prs.slides), model.language)
    out = BytesIO()
    prs.save(out)
    return stamp_office_meta(out.getvalue(), info)


def _runs_of_words(slides):  # noqa: ANN001, ANN202
    """The runs of every text of ``slides`` that claudia owns: a modeled shape's words and the notes."""
    for slide in slides:
        frames = [shape.text_frame for shape in slide.shapes if shape.has_text_frame]
        if slide.has_notes_slide and (notes := _notes_frame(slide)) is not None:
            frames.append(notes)
        for frame in frames:
            for paragraph in frame.paragraphs:
                yield from paragraph.runs


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
    """``"text"``/``"shape"``/``"image"`` for a shape :func:`pptx_to_slides` models, ``None`` for anything else (a
    table, a picture the model cannot hold as it is, a chart, a group, an autoshape outside the three built-in ones,
    a footer -- left as beyond-claudia content, same as a table that claudia has no model for at all -- and a title or
    body placeholder with no words, which shows nothing). A title or body placeholder with words is a text box
    (CODE-45)."""
    if shape.shape_type == MSO_SHAPE_TYPE.TEXT_BOX or (for_words(shape) and shape.text_frame.text):
        return "text"
    if shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and shape.auto_shape_type in _SHAPE_ID:
        return "shape"
    if held_picture(shape) is not None:
        return "image"
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


def _turned_place(x: int, y: int, w: int, h: int, rotation: int) -> tuple[int, int, int]:
    """Where an object read from a file goes and how it is turned, as ``(x, y, rotation)``. A turned object has to lie
    on the slide by its outline (D1022), which PowerPoint does not ask: an outline that sticks out is moved the least
    that brings it back, and one that cannot fit at all (it would be too large turned) is read upright."""
    if rotation == 0:
        return x, y, 0
    place = nudge_into(x, y, w, h, rotation, SLIDE_WIDTH, SLIDE_HEIGHT)
    return (*place, rotation) if place is not None else (x, y, 0)


def pptx_to_slides(pptx_bytes: bytes) -> SlideModel:
    """``pptx_bytes`` as a :class:`~claudia_creates.SlideModel`: one slide per slide, in order, a text box or one
    of the three built-in autoshapes on it becoming an object, and a picture an image (D460) (bottom to top, same
    order ``pptx_bytes`` draws them in). Anything else on a slide -- a table, a chart, a group, an autoshape outside
    the three built-in ones -- is simply not added: claudia has no model for it, same as a table is invisible to
    ``docx_to_text``. Position and size are read back through the presentation's own slide size (not a fixed
    16:9 assumption), so a deck of any aspect ratio imports onto claudia's 1600x900 slide space. A turn is read
    back too (D1022: one whose outline would stick out of the slide moves the object back in, and one too large to
    turn at all is read upright; ``pptx_import_losses`` says how many).
    Neither an object's own style nor its words' style can be recovered -- pptx carries no named-style concept
    the way Word does -- so every text box becomes ``"body-text"`` and every autoshape ``"plain-shape"``, for
    both, the same two styles ``slides_to_pptx`` itself falls back to. Their fonts can (E3.13): Body text takes the
    theme's body font, and words in another font (a title in the heading font, a font somebody picked) get a style of
    their own based on their usual one, named by the font until somebody names it."""
    prs = Presentation(BytesIO(pptx_bytes))
    model = SlideModel()
    if len(prs.slides) == 0:
        return _with_setup(SlideModel.empty(), prs)
    theme = deck_theme(prs)
    take_body_font(model, theme.minor)
    scale_x, scale_y = _slide_scale(prs)
    library = ShapeLibrary.load()
    defined: set[str] = set()
    object_ids = count(1)
    items = ItemReader(model.lists, model.schemes)
    colours, looks, names = _theme_of(prs), LookBook(model), FileNames()
    # one palette for the deck: the page of its first slide, white where a file says none (D467)
    model.palette.set_colour("page", _background(prs, prs.slides[0], colours) or "#ffffff")
    for slide_number, pptx_slide in enumerate(prs.slides, start=1):
        slide_id = f"s{slide_number}"
        _read_slide(model, slide_id, pptx_slide, names)
        for index in _modeled_shape_indices(pptx_slide):
            shape = pptx_slide.shapes[index]
            kind = _classify(shape)
            assert kind is not None  # index came from _modeled_shape_indices, which keeps only classified shapes
            x, y = round(shape.left / scale_x), round(shape.top / scale_y)
            w, h = round(shape.width / scale_x), round(shape.height / scale_y)
            text = shape.text_frame.text if shape.has_text_frame else ""
            said = (
                read_pptx_mark(shape.text_frame.paragraphs[0]._p, list_styles(shape))  # noqa: SLF001
                if shape.has_text_frame
                else None
            )
            x, y, rotation = _turned_place(x, y, w, h, round(shape.rotation) % 360)
            object_id = f"o{next(object_ids)}"
            if kind == "image":
                asset = held_picture(shape)
                assert asset is not None  # _classify said so
                if asset.id not in model.images:
                    model.images.define(asset)
                description, decorative = alt_text_of(shape)
                body = picture_body(
                    object_id,
                    asset,
                    (w, h),
                    name=shape.name,
                    description=description,
                    decorative=decorative,
                    rotation=rotation,
                )
                called = replace(body, name=names.take(shape.name))  # what the file calls it, not its file name
                model.insert_object(VisualObject(called, SlideAnchor(slide_id, x, y)))
                continue
            if kind == "text":
                style, words, shape_id = _DEFAULT_BOX_STYLE, _DEFAULT_TEXT_STYLE, None
            else:
                style, words, shape_id = _DEFAULT_SHAPE_STYLE, _DEFAULT_LABEL_STYLE, _SHAPE_ID[shape.auto_shape_type]
                if shape_id not in defined:
                    definition = library.get(shape_id)
                    if definition is None:  # pragma: no cover -- the three ids in _SHAPE_ID are always shipped
                        raise ValueError(f"the built-in shape library has no shape {shape_id!r}")
                    model.shapes.define(definition)
                    defined.add(shape_id)
            description, decorative = alt_text_of(shape)
            style, words = _styles_of(shape, kind, (style, words), (model, looks, theme, colours), 1 / scale_x)
            body = ObjectBody(
                object_id,
                kind,
                w,
                h,
                style,
                paragraph_for(object_id, words, text).with_item(None if said is None else items.item(*said)),
                ref=shape_id,
                rotation=rotation,
                name=names.take(shape.name),
                description="" if decorative else description[:MAX_ALT_CHARS],
                decorative=decorative,
            )
            model.insert_object(VisualObject(body, SlideAnchor(slide_id, x, y)))
    return _with_setup(model, prs)


def _read_slide(model: SlideModel, slide_id: str, pptx_slide, names: FileNames) -> None:  # noqa: ANN001
    """Add the slide ``slide_id`` with what the file calls it (``p:cSld/@name``, CODE-25) and its notes; notes longer
    than the model holds are left in the file and out of the model (see the patch)."""
    model.insert_slide(slide_id)
    named = names.take(pptx_slide._element.find(_qn("cSld")).get("name"))  # noqa: SLF001
    if named:
        model.slides.rename(slide_id, named)
    notes = _notes_markdown(pptx_slide)
    if 0 < len(notes) <= MAX_NOTES_LENGTH:
        model.set_notes(slide_id, notes)


def _styles_of(  # noqa: ANN001
    shape, kind: str, styles: tuple[str, str], reading: tuple[SlideModel, LookBook, ThemeFonts, Theme], scale: float
) -> tuple[str, str]:
    """The styles of the model for the box and the words of ``shape`` of ``kind``, from the default ones ``styles``:
    what the shape says of its look (D467) and of its font (E3.13) becomes styles based on them."""
    model, looks, theme, colours = reading
    box, words = styles
    found = read_look(shape._element, colours, scale, outline=kind == "shape")
    if kind == "shape":
        box = looks.outline(box, found.outline)
    return box, style_for_font(model, looks.words(words, found.words), shape_font(shape, theme))


def _with_setup(model: SlideModel, prs) -> SlideModel:  # noqa: ANN001
    """``model`` with the print setup and the language ``prs`` says (D461)."""
    model.print_setup = read_print_setup(prs)
    model.language = spoken(_runs_of_words(prs.slides))
    return model


def _qn(tag: str, ns: str = PNS) -> str:
    return f"{{{ns}}}{tag}"


def _resolve_target(source_dir: str, target: str) -> str:
    """An OPC relationship ``Target`` resolved against the directory of the part that references it: package-
    absolute (a leading ``/``) from the zip root, otherwise relative to ``source_dir``."""
    return target[1:] if target.startswith("/") else posixpath.normpath(posixpath.join(source_dir, target))


def _slide_part(members: dict[str, bytes], slide_index: int) -> str:
    """The zip member holding slide ``slide_index``'s XML, resolved through ``presentation.xml`` and its rels."""
    presentation = parse_xml(members["ppt/presentation.xml"])
    rels = parse_xml(members["ppt/_rels/presentation.xml.rels"])
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


def _patch_shape(  # noqa: ANN001, PLR0913
    shape,
    before: VisualObject,
    after: VisualObject,
    scale: tuple[float, float],
    pt_per_unit: float,
    current: SlideModel,
) -> None:
    """Make ``shape`` what ``after`` says: where it is, how big and how turned, what it says to someone who cannot see
    it and -- for an object with words -- the words and their look, resolved against the document's own palette and
    style book as :func:`slides_to_pptx` does it (*computed* CSS still holds palette roles such as ``@accent/14``, which
    no file format can hold: a patched file came out with its colours missing, bugtracker UX-15)."""
    anchor, body = after.anchor, after.body
    shape.left, shape.top = Emu(round(anchor.x * scale[0])), Emu(round(anchor.y * scale[1]))
    shape.width, shape.height = Emu(round(body.w * scale[0])), Emu(round(body.h * scale[1]))
    shape.rotation = body.rotation
    if (before.body.description, before.body.decorative) != (body.description, body.decorative):
        _describe(shape, body)
    if before.body.name != body.name:
        _call(shape, body.name)
    if body.kind == "image":
        return  # a picture has no words and no look of its own
    shape.text_frame.text = words_of(current, body)
    page = page_colour(current)
    words_css = look(current, body.paragraph.style) if body.paragraph is not None else {}
    _style_text(shape.text_frame, words_css, pt_per_unit, page)
    if body.kind == "shape":
        _style_shape(shape, look(current, body.style), pt_per_unit, page)


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
    if baseline.order != current.order:
        raise UnsupportedEdit("adding, removing or reordering a slide cannot be patched onto the original file yet")
    baseline_by_id, current_by_id = dict(baseline.objects), dict(current.objects)
    added, removed = current_by_id.keys() - baseline_by_id.keys(), baseline_by_id.keys() - current_by_id.keys()
    if added or removed:
        raise UnsupportedEdit("adding or removing an object cannot be patched onto the original file yet")
    for slide_id in baseline.order:
        before_order = [obj.id for obj in baseline.objects_on(slide_id)]
        after_order = [obj.id for obj in current.objects_on(slide_id)]
        if before_order != after_order:
            raise UnsupportedEdit("reordering the objects on a slide cannot be patched onto the original file yet")

    prs = Presentation(BytesIO(original_bytes))
    members = read_parts(original_bytes)
    scale_x, scale_y = _slide_scale(prs)
    slide_height = prs.slide_height
    assert slide_height is not None
    pt_per_unit = (slide_height / 914_400 * 72) / SLIDE_HEIGHT

    touched_parts: set[str] = set()
    marks_before, marks_after = marks_of(baseline), marks_of(current)
    for slide_number, slide_id in enumerate(baseline.order):
        touched_parts |= _patch_notes(prs, members, slide_number, baseline, current, slide_id)
        if baseline.thing_name(slide_id) != current.thing_name(slide_id):
            _call_slide(prs.slides[slide_number], current.thing_name(slide_id))
            touched_parts.add(_slide_part(members, slide_number))
        shape_indices = _modeled_shape_indices(prs.slides[slide_number])
        for position, object_id in enumerate(obj.id for obj in baseline.objects_on(slide_id)):
            before, after = baseline_by_id[object_id], current_by_id[object_id]
            same_words = words_of(baseline, before.body) == words_of(
                current, after.body
            )  # an agenda follows the slides
            if before == after and same_words and marks_before.get(object_id) == marks_after.get(object_id):
                continue  # nothing about this object changed: leave its shape exactly as is
            if before.body.kind != after.body.kind or before.body.shape != after.body.shape:
                raise UnsupportedEdit(
                    "changing an object's kind or shape outline cannot be patched onto the original file yet"
                )
            shape = prs.slides[slide_number].shapes[shape_indices[position]]
            _patch_shape(shape, before, after, (scale_x, scale_y), pt_per_unit, current)
            if after.body.kind != "image":
                paragraph = shape.text_frame.paragraphs[0]._p  # noqa: SLF001
                write_pptx_mark(paragraph, marks_after.get(object_id), list_styles(shape))
            touched_parts.add(_slide_part(members, slide_number))

    if baseline.print_setup != current.print_setup:
        if not write_print_setup(prs, current.print_setup):
            raise UnsupportedEdit("this file has no place to say how it is printed")
        touched_parts |= part_names(prs)

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

    members = read_parts(pptx_bytes)
    part_name = _slide_part(members, slide_index)
    root = parse_xml(members[part_name])

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
