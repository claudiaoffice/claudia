"""Converting between a :class:`~claudia_creates.SlideModel` and pptx, and adding a slide transition additively.

``slides_to_pptx`` is a minimal base export (text boxes, the three built-in shapes, best-effort styling) -- not the
ODF-first, loss-reporting import/export story of E10.3 (D5, D70), only enough of a real deck for ``add_transition``
to have something to attach to. Templates, layouts, images and groups (E10.4, E10.8) are not here yet, same as the
model itself (model.py's own docstring).

``add_transition`` is the additive extension the spike validated: python-pptx cannot write a ``<p:transition>``, so
this edits the slide's own already-written XML directly with ``lxml`` -- a transition lives inline in the slide
part, so no new parts, relationships or content-type overrides are needed, the simplest of the three extensions.
``fade`` is the one the spike checked against LibreOffice; ``wipe`` and ``push`` share the identical empty-element
shape in the schema and are offered on that basis, not independently checked against a real reader.

``pptx_to_slides`` and ``apply_edits_to_pptx`` close the loop D177 opened for docx, now for pptx (D179): a text box
or one of the three built-in autoshapes becomes a :class:`~claudia_creates.SlideObject`, and re-exporting an
*edited* import patches only the slides whose objects actually changed onto the original bytes (through
``claudia_opc_io.reconcile``), so a table, a picture, a slide claudia never modeled at all survives untouched. A
picture is not imported as claudia's own "image" object kind: ``slides_to_pptx`` cannot write one yet either (the
model.py docstring), so there would be nothing symmetrical to export it back out as -- it stays beyond-claudia
content, same as a table or a chart.
"""

from __future__ import annotations

import posixpath
import re
import zipfile
from io import BytesIO
from itertools import count

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.util import Emu, Pt

from claudia_creates import BUILTIN_STYLES, SLIDE_HEIGHT, SLIDE_WIDTH, ShapeLibrary, SlideModel, SlideObject, Style
from claudia_opc_io import owns, reconcile

PNS = "http://schemas.openxmlformats.org/presentationml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

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
#: The two default styles a reimported object is given: pptx carries no named-style concept to map back from
#: (unlike docx's own style names), so every text box becomes "body-text" and every autoshape "plain-shape" --
#: the same fallback ``slides_to_pptx`` itself falls back to when an object's style id is not a built-in one.
_DEFAULT_TEXT_STYLE, _DEFAULT_SHAPE_STYLE = "body-text", "plain-shape"

_TRANSITIONS = ("fade", "wipe", "push", "none")
_SPEEDS = ("fast", "med", "slow")
_HEX = re.compile(r"#([0-9a-fA-F]{6})\b")
_NUMBER = re.compile(r"[\d.]+")


class UnsupportedEdit(Exception):
    """Raised by :func:`apply_edits_to_pptx` for an edit it cannot patch onto the original file yet: adding,
    removing or reordering a slide or an object, reordering the objects on a slide (stacking order lives outside
    any one object's own fields, so there is nothing a per-object diff can patch), or changing which kind of
    object (text/shape) or which shape outline an existing object uses. Moving, resizing, restyling or retexting
    an existing object is supported; see the implementation note for what is still missing."""


def _pt(css: dict[str, str], prop: str, pt_per_unit: float) -> Pt | None:
    """``css[prop]`` (CSS pixels, a unit of the slide's own 1600x900 space) as points, or ``None``."""
    value = css.get(prop)
    match = _NUMBER.search(value) if value else None
    return Pt(float(match.group()) * pt_per_unit) if match else None


def _rgb(css: dict[str, str], prop: str) -> RGBColor | None:
    value = css.get(prop)
    match = _HEX.search(value) if value else None
    return RGBColor.from_string(match.group(1)) if match else None


def _style_text(text_frame, style: Style, pt_per_unit: float) -> None:
    size = _pt(style.css, "font-size", pt_per_unit)
    color = _rgb(style.css, "color")
    for paragraph in text_frame.paragraphs:
        for run in paragraph.runs:
            if size is not None:
                run.font.size = size
            if color is not None:
                run.font.color.rgb = color


def _style_shape(shape, style: Style, pt_per_unit: float) -> None:
    fill = _rgb(style.css, "fill")
    if fill is not None:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    stroke = _rgb(style.css, "stroke")
    if stroke is not None:
        shape.line.color.rgb = stroke
    width = _pt(style.css, "stroke-width", pt_per_unit)
    if width is not None:
        shape.line.width = width


def slides_to_pptx(model: SlideModel) -> bytes:
    """``model`` as pptx bytes: one slide per slide id, its objects added bottom to top so the stacking order
    (the last one is in front) comes out the same as it is drawn in claudia-creates."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = _DECK_WIDTH, _DECK_HEIGHT
    scale_x, scale_y = _DECK_WIDTH / SLIDE_WIDTH, _DECK_HEIGHT / SLIDE_HEIGHT
    pt_per_unit = (_DECK_HEIGHT / 914_400 * 72) / SLIDE_HEIGHT
    layout = prs.slide_layouts[_BLANK_LAYOUT]
    for slide_id in model.slides:
        slide = prs.slides.add_slide(layout)
        for obj in model.objects_on(slide_id):
            box = (
                Emu(round(obj.x * scale_x)),
                Emu(round(obj.y * scale_y)),
                Emu(round(obj.w * scale_x)),
                Emu(round(obj.h * scale_y)),
            )
            style = BUILTIN_STYLES.get(obj.style)
            if obj.kind == "text":
                shape = slide.shapes.add_textbox(*box)
                shape.text_frame.text = obj.text
                if style is not None:
                    _style_text(shape.text_frame, style, pt_per_unit)
            else:
                definition = model.shapes.get(obj.shape) if obj.shape else None
                auto_shape = _AUTOSHAPE.get(definition.id if definition else "", MSO_SHAPE.RECTANGLE)
                shape = slide.shapes.add_shape(auto_shape, *box)
                shape.text_frame.text = obj.text
                if style is not None:
                    _style_shape(shape, style, pt_per_unit)
                    _style_text(shape.text_frame, style, pt_per_unit)
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


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
    of the three built-in autoshapes on it becoming a :class:`~claudia_creates.SlideObject` (bottom to top, same
    order ``pptx_bytes`` draws them in). Anything else on a slide -- a table, a picture, a chart, a group, an
    autoshape outside the three built-in ones -- is simply not added: claudia has no model for it, same as a
    table is invisible to ``docx_to_text``. Position and size are read back through the presentation's own slide
    size (not a fixed 16:9 assumption), so a deck of any aspect ratio imports onto claudia's 1600x900 slide space.
    An object's style cannot be recovered -- pptx carries no named-style concept the way Word does -- so every
    text box becomes ``"body-text"`` and every autoshape ``"plain-shape"``, the same two styles ``slides_to_pptx``
    itself falls back to."""
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
        for index in _modeled_shape_indices(pptx_slide):
            shape = pptx_slide.shapes[index]
            kind = _classify(shape)
            x, y = round(shape.left / scale_x), round(shape.top / scale_y)
            w, h = round(shape.width / scale_x), round(shape.height / scale_y)
            text = shape.text_frame.text if shape.has_text_frame else ""
            if kind == "text":
                obj = SlideObject(f"o{next(object_ids)}", slide_id, "text", x, y, w, h, _DEFAULT_TEXT_STYLE, text)
            else:
                shape_id = _SHAPE_ID[shape.auto_shape_type]
                if shape_id not in defined:
                    definition = library.get(shape_id)
                    if definition is None:  # pragma: no cover -- the three ids in _SHAPE_ID are always shipped
                        raise ValueError(f"the built-in shape library has no shape {shape_id!r}")
                    model.define_shape(definition)
                    defined.add(shape_id)
                obj = SlideObject(
                    f"o{next(object_ids)}", slide_id, "shape", x, y, w, h, _DEFAULT_SHAPE_STYLE, text, shape_id
                )
            model.insert_object(obj)
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


def apply_edits_to_pptx(original_bytes: bytes, baseline: SlideModel, current: SlideModel) -> bytes:
    """Re-export ``current`` to pptx by patching only the slides whose objects actually changed since
    ``baseline`` (the model as it stood right after :func:`pptx_to_slides` imported ``original_bytes``) onto
    those same bytes, instead of rebuilding the file from the model alone -- so a table, a picture, any slide
    claudia never touched survives untouched (D179, following D177's docx design). Unlike docx's single
    ``word/document.xml``, pptx keeps each slide in its own part, so the parts :func:`claudia_opc_io.reconcile`
    is told claudia owns are exactly the slides an edit actually reaches, computed fresh each call -- every other
    slide, layout, master, theme and media part comes back byte-for-byte as it was, not just semantically
    unchanged.

    Raises :class:`UnsupportedEdit` if a slide or an object was added, removed or reordered since ``baseline``,
    if the objects on a slide were reordered (stacking order is not one object's own field, so a per-object diff
    cannot see it), or if an object's kind or shape outline changed. Moving, resizing, retexting or restyling an
    existing object is supported."""
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

    touched_parts: set[str] = set()
    for slide_number, slide_id in enumerate(baseline.slides):
        shape_indices = _modeled_shape_indices(prs.slides[slide_number])
        for position, object_id in enumerate(obj.id for obj in baseline.objects_on(slide_id)):
            before, after = baseline_by_id[object_id], current_by_id[object_id]
            if before == after:
                continue  # nothing about this object changed: leave its shape exactly as is
            if before.kind != after.kind or before.shape != after.shape:
                raise UnsupportedEdit(
                    "changing an object's kind or shape outline cannot be patched onto the original file yet"
                )
            shape = prs.slides[slide_number].shapes[shape_indices[position]]
            shape.left, shape.top = Emu(round(after.x * scale_x)), Emu(round(after.y * scale_y))
            shape.width, shape.height = Emu(round(after.w * scale_x)), Emu(round(after.h * scale_y))
            shape.text_frame.text = after.text
            style = BUILTIN_STYLES.get(after.style)
            if style is not None:
                _style_text(shape.text_frame, style, pt_per_unit)
                if after.kind == "shape":
                    _style_shape(shape, style, pt_per_unit)
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
