"""Pictures in an ods file (D1233).

A picture of a sheet is a ``draw:frame`` with a ``draw:image`` in the ``table:shapes`` of its sheet (where its charts
are too), at its place in pixels from the sheet's corner, and a part of the package of its own (``Pictures/…``) that the
frame reaches by ``xlink:href``. What it says to someone who cannot see it is the ``svg:desc`` of the frame. A turned
one has no place of its own: its ``draw:transform`` turns it about its centre and puts it there (the same words every
drawing of the suite uses, :func:`claudia_odf_io.transform_of`). ODF 1.3 has no way to say a picture is decorative, so
that is reported (``decorative``). Where there is nothing to draw an SVG as a PNG, the SVG is the picture
(``svg-fallback``).

A picture of a file comes in as an image object (CODE-67, D1478) when the model can show it as it is
(:func:`claudia_odf_io.held_frame`); every other picture stays in the file and is reported as ``picture``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING

from lxml import etree

from claudia_core import picture_body
from claudia_odf_io import NS, description_of, held_frame, name_of, qname, xml_safe

from ._pictures import WrittenPicture
from ._read_back import FileObject
from .ods_chart_files import drawn_frames
from .ods_charts import place_of

if TYPE_CHECKING:
    from .ods import _Table

#: What the package calls each format: ``image/jpeg`` pictures are ``.jpg`` files in an OpenDocument package.
EXTENSIONS = {"jpeg": "jpg", "png": "png", "gif": "gif", "bmp": "bmp", "svg": "svg"}


def part_name(picture: WrittenPicture) -> str:
    """Where the bytes of a picture are in the package: one name for what is shown, however many frames show it."""
    return f"Pictures/{re.sub(r'[^A-Za-z0-9_-]', '_', picture.asset)}.{EXTENSIONS[picture.format]}"


def picture_frame(picture: WrittenPicture, number: int) -> etree._Element:
    """The ``draw:frame`` of ``picture``; ``number`` names a picture that has no name of its own."""
    placed = picture.placed
    frame = etree.Element(qname("draw:frame"), nsmap={p: u for p, u in NS.items() if p != "xml"})
    attributes = {
        "draw:z-index": str(placed.layer),
        "draw:name": xml_safe(picture.name or f"Picture {number}"),
        **place_of(placed, placed.obj.body.rotation),
    }
    for key, value in attributes.items():
        frame.set(qname(key), value)
    image = etree.SubElement(frame, qname("draw:image"))
    for key, value in (("href", part_name(picture)), ("type", "simple"), ("show", "embed"), ("actuate", "onLoad")):
        image.set(qname(f"xlink:{key}"), value)
    if picture.description:
        etree.SubElement(frame, qname("svg:desc")).text = xml_safe(picture.description)
    return frame


def file_pictures(
    tables: Sequence[_Table], parts: Mapping[str, bytes], graphics: Mapping[str, etree._Element], first: int
) -> list[FileObject]:
    """The pictures of the sheets of a file the model holds, in the order of the file; the ``n``-th is the object
    ``o{first + n - 1}`` (the ids before ``first`` are the charts'). ``graphics`` are the file's graphic styles."""
    found: list[FileObject] = []
    for drawn in drawn_frames(tables):
        held = None if drawn.frame.find("draw:image", NS) is None else held_frame(drawn.frame, graphics, parts)
        if held is None:
            continue
        asset, size, rotation = held
        body = picture_body(
            f"o{first + len(found)}",
            asset,
            size,
            name=name_of(drawn.frame),
            description=description_of(drawn.frame),
            rotation=rotation,
        )
        name = (drawn.frame.get(qname("draw:name")) or "").strip()
        body = replace(body, name=name)
        found.append(
            FileObject(drawn.sheet, drawn.row, drawn.col, drawn.corner, body, "picture", drawn.order, image=asset)
        )
    return found


def decorative_count(pictures: tuple[WrittenPicture, ...]) -> int:
    """How many pictures say they have nothing to say: a file cannot hold that."""
    return sum(1 for picture in pictures if picture.decorative)


__all__ = ["decorative_count", "file_pictures", "part_name", "picture_frame"]
