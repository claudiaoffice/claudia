"""Pictures in an xlsx file (D1233).

A picture of a sheet is an ``xdr:pic`` in the drawing of the sheet (the one its charts are in), pinned by a
``oneCellAnchor`` to a cell with the size the picture is, and a part of its own (``xl/media/image1.png``) that the
drawing reaches by a relationship. A turn is the ``rot`` of its ``a:xfrm`` (sixty thousandths of a degree, clockwise
about the centre, the frame itself unturned: as the model has it); what it is called and says is on its ``cNvPr``
(``name``, ``descr``), and a picture that has nothing to say carries Office's mark for a decorative one.

An SVG is drawn as a PNG when there is something to draw it, and else written as Office 2016 and later write one: a
picture (here a blank one) with the SVG beside it, which Excel shows instead and other programs leave empty.

A picture of a file comes in as an image object (CODE-67, D1478) when the model can show it as it is
(:mod:`claudia_core.file_pictures`): an image the app decodes, not cropped, not flipped, in its own proportions. What
the file says of it -- its name, its description, whether it is decorative, its turn -- is the object's. Every other
picture stays in the file and is reported as ``picture``.
"""

from __future__ import annotations

from dataclasses import replace

from lxml import etree

from claudia_computes import MIN_OBJECT_SIZE
from claudia_core import asset_of, keeps_proportions, picture_body
from claudia_odf_io import xml_safe
from claudia_opc_io import ANGLE, DECORATIVE_URI, DRAWINGML, SVG_URI, cropped, is_decorative, shown_part, turn_of

from ._pictures import WrittenPicture
from ._read_back import FileObject
from .xlsx_charts import NS, DrawnAnchor, drawn_anchors, emu, pinned_at
from .xlsx_read import Package, relationships

DECORATIVE_NS = DRAWINGML["adec"]
SVG_NS = DRAWINGML["asvg"]


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


def _held(drawn: DrawnAnchor, package: Package, object_id: str) -> FileObject | None:
    """The image object of a picture anchored on a sheet, or ``None`` when it is none the model shows as it is."""
    picture = drawn.anchor.find("xdr:pic", NS)
    blip = None if picture is None else picture.find("xdr:blipFill/a:blip", NS)
    if picture is None or blip is None or drawn.size is None:
        return None
    if cropped(picture.find("xdr:blipFill/a:srcRect", NS)):
        return None
    rotation = turn_of(picture.find("xdr:spPr/a:xfrm", NS))
    targets = {rid: target for rid, _, target in relationships(package.parts, drawn.drawing)}
    asset = asset_of(package.parts.get(targets.get(shown_part(blip), "")))
    if rotation is None or asset is None or min(drawn.size) < MIN_OBJECT_SIZE:
        return None
    if not keeps_proportions(asset, *drawn.size):
        return None
    properties = picture.find("xdr:nvPicPr/xdr:cNvPr", NS)
    name = "" if properties is None else (properties.get("name") or "").strip()
    body = picture_body(
        object_id,
        asset,
        drawn.size,
        name=name,
        description="" if properties is None else (properties.get("descr") or properties.get("title") or "").strip(),
        decorative=is_decorative(properties),
        rotation=rotation,
    )
    body = replace(body, name=name)
    return FileObject(
        drawn.sheet.sheet_id, drawn.row, drawn.col, drawn.corner, body, "picture", drawn.order, image=asset
    )


def file_pictures(package: Package, first: int) -> list[FileObject]:
    """The pictures of the sheets of a file the model holds, in the order of the file; the ``n``-th is the object
    ``o{first + n - 1}`` (the ids before ``first`` are the charts')."""
    found: list[FileObject] = []
    for drawn in drawn_anchors(package, {}):
        held = _held(drawn, package, f"o{first + len(found)}")
        if held is not None:
            found.append(held)
    return found
