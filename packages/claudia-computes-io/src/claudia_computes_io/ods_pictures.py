"""Pictures in an ods file (D1233).

A picture of a sheet is a ``draw:frame`` with a ``draw:image`` in the ``table:shapes`` of its sheet (where its charts
are too), at its place in pixels from the sheet's corner, and a part of the package of its own (``Pictures/…``) that the
frame reaches by ``xlink:href``. What it says to someone who cannot see it is the ``svg:desc`` of the frame. A turned
one has no place of its own: its ``draw:transform`` turns it about its centre and puts it there (the same words every
drawing of the suite uses, :func:`claudia_odf_io.transform_of`). ODF 1.3 has no way to say a picture is decorative, so
that is reported (``decorative``). Where there is nothing to draw an SVG as a PNG, the SVG is the picture
(``svg-fallback``).
"""

from __future__ import annotations

import re

from lxml import etree

from claudia_computes import SheetId, WorkbookModel
from claudia_odf_io import NS, qname, transform_of, xml_safe

from ._pictures import MEDIA_TYPES, WrittenPicture
from .chart_plan import offset_of
from .ods_charts import Parts
from .ods_layout import _CM_PER_PIXEL, text_of  # noqa: PLC2701 (one length, one conversion)

#: What the package calls each format: ``image/jpeg`` pictures are ``.jpg`` files in an OpenDocument package.
EXTENSIONS = {"jpeg": "jpg", "png": "png", "gif": "gif", "bmp": "bmp", "svg": "svg"}


def part_name(picture: WrittenPicture) -> str:
    """Where the bytes of a picture are in the package: one name for what is shown, however many frames show it."""
    return f"Pictures/{re.sub(r'[^A-Za-z0-9_-]', '_', picture.asset)}.{EXTENSIONS[picture.format]}"


def picture_frame(picture: WrittenPicture, offset: tuple[float, float], number: int) -> etree._Element:
    """The ``draw:frame`` of ``picture`` on a sheet whose cell ``(row, col)`` is ``offset`` pixels from its corner;
    ``number`` names a picture that has no name of its own."""
    frame = etree.Element(qname("draw:frame"), nsmap={p: u for p, u in NS.items() if p != "xml"})
    attributes = {
        "draw:z-index": str(picture.layer),
        "draw:name": xml_safe(picture.name or f"Picture {number}"),
        "svg:width": text_of(picture.width),
        "svg:height": text_of(picture.height),
    }
    box = tuple(pixels * _CM_PER_PIXEL for pixels in (*offset, picture.width, picture.height))
    transform = transform_of(picture.rotation, box)  # type: ignore[arg-type]
    if transform is None:
        attributes |= {"svg:x": text_of(offset[0]), "svg:y": text_of(offset[1])}
    else:
        attributes["draw:transform"] = transform
    for key, value in attributes.items():
        frame.set(qname(key), value)
    image = etree.SubElement(frame, qname("draw:image"))
    for key, value in (("href", part_name(picture)), ("type", "simple"), ("show", "embed"), ("actuate", "onLoad")):
        image.set(qname(f"xlink:{key}"), value)
    if picture.description:
        etree.SubElement(frame, qname("svg:desc")).text = xml_safe(picture.description)
    return frame


def add_pictures(
    model: WorkbookModel,
    pictures: tuple[WrittenPicture, ...],
    shapes: dict[SheetId, etree._Element],
    new_shapes,  # noqa: ANN001 (``ods_charts.new_shapes``: an empty ``table:shapes``)
) -> Parts:
    """The frames of ``pictures`` put into the ``table:shapes`` of their sheets (made where a sheet has none yet),
    and the parts that hold their bytes, each once."""
    parts: Parts = {}
    for number, picture in enumerate(pictures, start=1):
        sheet = model.sheets[picture.sheet]
        shapes.setdefault(picture.sheet, new_shapes()).append(
            picture_frame(picture, offset_of(sheet.col_widths, sheet.row_heights, picture.row, picture.col), number)
        )
        parts[part_name(picture)] = (picture.data, MEDIA_TYPES[picture.format])
    return parts


def decorative_count(pictures: tuple[WrittenPicture, ...]) -> int:
    """How many pictures say they have nothing to say: a file cannot hold that."""
    return sum(1 for picture in pictures if picture.decorative)


__all__ = ["add_pictures", "decorative_count", "part_name", "picture_frame"]
