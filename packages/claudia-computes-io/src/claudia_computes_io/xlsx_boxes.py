"""Text boxes and shapes on a slide's tab in an xlsx file (E6.31, D1479).

A box is an ``xdr:sp`` in the drawing of the tab, pinned like a chart or a picture (:func:`.xlsx_charts.pinned_at`):
its outline a preset of DrawingML (``rect``, ``ellipse``, ``triangle``), its fill and line the look of its style
(:func:`claudia_odf_io.look_of`), a text box marked ``txBox``. Its words are one paragraph of one run, formatted
directly with what the style of the words says (an xlsx has no paragraph styles for a drawing): the font, its size,
bold, italic, underlined or struck, its colour, and how the paragraph is aligned.

Read back (:func:`held_box`), a shape of the drawing is a box the model holds when it shows it as it is: one of the
three outlines, not flipped, one paragraph of plain words; a rectangle marked ``txBox`` (or one that draws nothing but
its words) is a text box. Its look is what the file says, for :func:`._boxes.styled` to compare.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from xml.sax.saxutils import escape

from lxml import etree

from claudia_computes import MIN_OBJECT_SIZE
from claudia_computes.styles import DEFAULT_STYLE
from claudia_core import ASPECT_TOLERANCE, SHAPE_LABEL_STYLE, box_body
from claudia_core.stand_ins import file_font
from claudia_odf_io import BoxLook, xml_safe
from claudia_opc_io import (
    ANGLE,
    PRESET,
    SHAPE_OF,
    is_decorative,
    look_in,
    mark_decorative,
    outline,
    solid,
    turn_of,
)

from ._placed import Placed
from ._read_back import FileObject
from .cell_looks import points
from .cell_looks import solid as css_solid
from .xlsx_charts import NS, DrawnAnchor, emu, names_of, pinned_at

#: How a paragraph is aligned, in DrawingML.
_ALIGN = {"left": "l", "start": "l", "center": "ctr", "right": "r", "end": "r", "justify": "just"}
_BOLD = 600


def _run_properties(css: Mapping[str, str]) -> str:
    """The ``a:rPr`` of words in the look ``css`` gives them."""
    size = points(css.get("font-size", ""))
    weight = css.get("font-weight", "normal")
    bold = weight in ("bold", "bolder") or (weight.isdigit() and int(weight) >= _BOLD)
    decoration = css.get("text-decoration", "")
    said = {
        "lang": "en-US",
        "sz": str(round(size * 100)) if size else None,
        "b": "1" if bold else "0",
        "i": "1" if css.get("font-style") in ("italic", "oblique") else "0",
        "u": "sng" if "underline" in decoration else None,
        "strike": "sngStrike" if "line-through" in decoration else None,
    }
    attributes = "".join(f' {key}="{value}"' for key, value in said.items() if value is not None)
    colour = css_solid(css.get("color", ""))
    fill = f'<a:solidFill><a:srgbClr val="{colour}"/></a:solidFill>' if colour else ""
    family = file_font(css.get("font-family", ""))
    font = f'<a:latin typeface="{escape(family, {chr(34): "&quot;"})}"/>' if family else ""
    return f"<a:rPr{attributes}>{fill}{font}</a:rPr>"


def box_anchor(placed: Placed, number: int, name: str, look: BoxLook, words: Mapping[str, str]) -> etree._Element:
    """The ``oneCellAnchor`` of the text box or shape ``placed`` called ``name``, the ``number``-th shape of its
    drawing, drawn with ``look`` and its words in the look ``words`` (the CSS of their style)."""
    body = placed.obj.body
    is_box = body.kind == "text"
    preset = "rect" if is_box else PRESET[body.shape or "rectangle"]
    turn = f' rot="{body.rotation * ANGLE}"' if body.rotation else ""
    text = "" if body.paragraph is None else body.paragraph.text
    align = _ALIGN.get(words.get("text-align", ""), "l" if is_box else "ctr")
    inset = ' lIns="0" tIns="0" rIns="0" bIns="0"' if is_box else ""
    flag = ' txBox="1"' if is_box else ""
    run = f"<a:r>{_run_properties(words)}<a:t>{escape(xml_safe(text))}</a:t></a:r>" if text else ""
    xml = (
        f'<xdr:oneCellAnchor xmlns:xdr="{NS["xdr"]}" xmlns:a="{NS["a"]}">'
        f"{pinned_at(placed.pin, placed.width, placed.height)}"
        f'<xdr:sp macro="" textlink=""><xdr:nvSpPr><xdr:cNvPr/><xdr:cNvSpPr{flag}/>'
        f'</xdr:nvSpPr><xdr:spPr><a:xfrm{turn}><a:off x="0" y="0"/>'
        f'<a:ext cx="{emu(placed.width)}" cy="{emu(placed.height)}"/></a:xfrm>'
        f'<a:prstGeom prst="{preset}"><a:avLst/></a:prstGeom>{solid(look.fill)}{outline(look.line, look.width)}'
        f'</xdr:spPr><xdr:txBody><a:bodyPr wrap="square" anchor="{"t" if is_box else "ctr"}"{inset}><a:noAutofit/>'
        f'</a:bodyPr><a:lstStyle/><a:p><a:pPr algn="{align}"/>{run}</a:p></xdr:txBody></xdr:sp><xdr:clientData/>'
        "</xdr:oneCellAnchor>"
    )
    anchor = etree.fromstring(xml)
    properties = anchor.find("xdr:sp/xdr:nvSpPr/xdr:cNvPr", NS)
    assert properties is not None
    properties.set("id", str(number))
    properties.set("name", xml_safe(name))
    if body.decorative:
        mark_decorative(properties)
    elif body.description:
        properties.set("descr", xml_safe(body.description))
    return anchor


# ------------------------------------------------------------------------------------------------------ reading
def _words_of(text_body: etree._Element | None) -> str | None:
    """The words of an ``xdr:txBody`` that holds one paragraph of plain runs; ``None`` for anything else."""
    if text_body is None:
        return ""
    paragraphs = text_body.findall("a:p", NS)
    if len(paragraphs) > 1:
        return None
    words = []
    for child in paragraphs[0] if paragraphs else ():
        name = etree.QName(child).localname
        if name == "r":
            words.append(child.findtext("a:t", "", NS))
        elif name not in ("pPr", "endParaRPr"):
            return None
    return "".join(words)


def held_box(drawn: DrawnAnchor, object_id: str) -> FileObject | None:
    """The box of a shape anchored on a sheet, or ``None`` when it is none the model shows as it is."""
    shape = drawn.anchor.find("xdr:sp", NS)
    if shape is None or drawn.size is None:
        return None
    properties = shape.find("xdr:spPr", NS)
    geometry = None if properties is None else properties.find("a:prstGeom", NS)
    preset = None if geometry is None else geometry.get("prst")
    rotation = turn_of(None if properties is None else properties.find("a:xfrm", NS))
    words = _words_of(shape.find("xdr:txBody", NS))
    if preset not in SHAPE_OF or rotation is None or words is None:
        return None
    look = BoxLook(*look_in(properties, styled=shape.find("xdr:style", NS) is not None))
    flagged = shape.find("xdr:nvSpPr/xdr:cNvSpPr", NS)
    is_box = preset == "rect" and (
        (flagged is not None and flagged.get("txBox") in ("1", "true")) or (look.fill is None and look.line is None)
    )
    ours = None if is_box else SHAPE_OF[preset]
    size = drawn.size
    if min(size) < MIN_OBJECT_SIZE or (ours == "circle" and abs(size[0] - size[1]) > ASPECT_TOLERANCE):
        return None
    named = shape.find("xdr:nvSpPr/xdr:cNvPr", NS)
    name, description = names_of(named)
    body = box_body(
        object_id,
        size,
        words,
        DEFAULT_STYLE if is_box else SHAPE_LABEL_STYLE,
        shape=ours,
        description=description,
        decorative=is_decorative(named),
        rotation=rotation,
    )
    body = replace(body, name=name)
    return FileObject(drawn.sheet.sheet_id, drawn.row, drawn.col, drawn.corner, body, "shape", drawn.order, look=look)
