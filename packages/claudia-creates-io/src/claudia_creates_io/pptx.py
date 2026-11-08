"""Exporting a :class:`~claudia_creates.SlideModel` to pptx, and adding a slide transition additively.

``slides_to_pptx`` is a minimal base export (text boxes, the three built-in shapes, best-effort styling) -- not the
ODF-first, loss-reporting import/export story of E10.3 (D5, D70), only enough of a real deck for ``add_transition``
to have something to attach to. Templates, layouts, images and groups (E10.4, E10.8) are not here yet, same as the
model itself (model.py's own docstring).

``add_transition`` is the additive extension the spike validated: python-pptx cannot write a ``<p:transition>``, so
this edits the slide's own already-written XML directly with ``lxml`` -- a transition lives inline in the slide
part, so no new parts, relationships or content-type overrides are needed, the simplest of the three extensions.
``fade`` is the one the spike checked against LibreOffice; ``wipe`` and ``push`` share the identical empty-element
shape in the schema and are offered on that basis, not independently checked against a real reader.
"""

from __future__ import annotations

import posixpath
import re
import zipfile
from io import BytesIO

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu, Pt

from claudia_creates import SLIDE_HEIGHT, SLIDE_WIDTH, SlideModel

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

_TRANSITIONS = ("fade", "wipe", "push", "none")
_SPEEDS = ("fast", "med", "slow")
_HEX = re.compile(r"#([0-9a-fA-F]{6})\b")
_NUMBER = re.compile(r"[\d.]+")


def _pt(css: dict[str, str], prop: str, pt_per_unit: float) -> Pt | None:
    """``css[prop]`` (CSS pixels, a unit of the slide's own 1600x900 space) as points, or ``None``."""
    value = css.get(prop)
    match = _NUMBER.search(value) if value else None
    return Pt(float(match.group()) * pt_per_unit) if match else None


def _rgb(css: dict[str, str], prop: str) -> RGBColor | None:
    value = css.get(prop)
    match = _HEX.search(value) if value else None
    return RGBColor.from_string(match.group(1)) if match else None


def _style_text(text_frame, css: dict[str, str], pt_per_unit: float) -> None:
    size = _pt(css, "font-size", pt_per_unit)
    color = _rgb(css, "color")
    for paragraph in text_frame.paragraphs:
        for run in paragraph.runs:
            if size is not None:
                run.font.size = size
            if color is not None:
                run.font.color.rgb = color


def _style_shape(shape, css: dict[str, str], pt_per_unit: float) -> None:
    fill = _rgb(css, "fill")
    if fill is not None:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    stroke = _rgb(css, "stroke")
    if stroke is not None:
        shape.line.color.rgb = stroke
    width = _pt(css, "stroke-width", pt_per_unit)
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
            body, anchor = obj.body, obj.anchor
            box = (
                Emu(round(anchor.x * scale_x)),
                Emu(round(anchor.y * scale_y)),
                Emu(round(body.w * scale_x)),
                Emu(round(body.h * scale_y)),
            )
            # The *computed* style: what the style really has once its parents are resolved (D73, E10.16).
            css = model.styles.computed(body.style) if body.style in model.styles else {}
            if body.kind == "text":
                shape = slide.shapes.add_textbox(*box)
                shape.text_frame.text = body.text
                _style_text(shape.text_frame, css, pt_per_unit)
            else:
                definition = model.shapes.get(body.shape) if body.shape else None
                auto_shape = _AUTOSHAPE.get(definition.id if definition else "", MSO_SHAPE.RECTANGLE)
                shape = slide.shapes.add_shape(auto_shape, *box)
                shape.text_frame.text = body.text
                _style_shape(shape, css, pt_per_unit)
                _style_text(shape.text_frame, css, pt_per_unit)
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


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
