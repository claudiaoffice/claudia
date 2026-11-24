"""Pictures in an xlsx file (D1233).

A picture of a sheet is an ``xdr:pic`` in the drawing of the sheet (the one its charts are in), pinned by a
``oneCellAnchor`` to a cell with the size the picture is, and a part of its own (``xl/media/image1.png``) that the
drawing reaches by a relationship. A turn is the ``rot`` of its ``a:xfrm`` (sixty thousandths of a degree, clockwise
about the centre, the frame itself unturned: as the model has it); what it is called and says is on its ``cNvPr``
(``name``, ``descr``), and a picture that has nothing to say carries Office's mark for a decorative one.

An SVG is drawn as a PNG when there is something to draw it, and else written as Office 2016 and later write one: a
picture (here a blank one) with the SVG beside it, which Excel shows instead and other programs leave empty.
"""

from __future__ import annotations

from lxml import etree

from claudia_odf_io import xml_safe

from ._pictures import WrittenPicture
from .xlsx_charts import NS, emu, pinned_at

DECORATIVE_URI = "{C183D7F6-B498-43B3-948B-1728B52AA6E4}"
DECORATIVE_NS = "http://schemas.microsoft.com/office/drawing/2017/decorative"
SVG_URI = "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"
SVG_NS = "http://schemas.microsoft.com/office/drawing/2016/SVG/main"
#: Sixty thousandths of a degree: how a drawing says an angle.
ANGLE = 60000


def picture_anchor(picture: WrittenPicture, number: int, rid: str, svg_rid: str | None = None) -> etree._Element:
    """The ``oneCellAnchor`` of a picture whose picture part ``rid`` points at (and, for an SVG shown as such,
    ``svg_rid`` its SVG), numbered ``number`` among the shapes of its drawing."""
    placed = picture.placed
    rotation = placed.obj.body.rotation % 360
    turn = f' rot="{rotation * ANGLE}"' if rotation else ""
    xml = (
        f'<xdr:oneCellAnchor xmlns:xdr="{NS["xdr"]}" xmlns:a="{NS["a"]}" xmlns:r="{NS["r"]}">'
        f"{pinned_at(placed.pin, placed.width, placed.height)}"
        '<xdr:pic><xdr:nvPicPr><xdr:cNvPr/><xdr:cNvPicPr><a:picLocks noChangeAspect="1"/></xdr:cNvPicPr></xdr:nvPicPr>'
        f'<xdr:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>'
        f'<xdr:spPr><a:xfrm{turn}><a:off x="0" y="0"/><a:ext cx="{emu(placed.width)}" cy="{emu(placed.height)}"/>'
        '</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/>'
        "</xdr:oneCellAnchor>"
    )
    anchor = etree.fromstring(xml)
    properties = anchor.find("xdr:pic/xdr:nvPicPr/xdr:cNvPr", NS)
    assert properties is not None
    properties.set("id", str(number))
    properties.set("name", xml_safe(picture.name or f"Picture {number - 1}"))
    if picture.decorative:
        properties.set("descr", "")
        ext = etree.SubElement(etree.SubElement(properties, f"{{{NS['a']}}}extLst"), f"{{{NS['a']}}}ext")
        ext.set("uri", DECORATIVE_URI)
        etree.SubElement(ext, f"{{{DECORATIVE_NS}}}decorative", nsmap={"adec": DECORATIVE_NS}).set("val", "1")
    elif picture.description:
        properties.set("descr", xml_safe(picture.description))
    if svg_rid is not None:
        blip = anchor.find("xdr:pic/xdr:blipFill/a:blip", NS)
        assert blip is not None
        extension = etree.SubElement(etree.SubElement(blip, f"{{{NS['a']}}}extLst"), f"{{{NS['a']}}}ext")
        extension.set("uri", SVG_URI)
        etree.SubElement(extension, f"{{{SVG_NS}}}svgBlip", nsmap={"asvg": SVG_NS}).set(f"{{{NS['r']}}}embed", svg_rid)
    return anchor
