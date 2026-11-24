"""Reading the pictures of a pptx as image objects (D460): which a picture is that the model holds, its asset and what
the file says of it (see :mod:`claudia_core.file_pictures`)."""

from __future__ import annotations

from typing import Any

from lxml import etree
from pptx.enum.shapes import MSO_SHAPE_TYPE

from claudia_core import ImageAsset, asset_of, keeps_proportions
from claudia_creates import SLIDE_HEIGHT, SLIDE_WIDTH
from claudia_opc_io import DRAWINGML, is_decorative, shown_part, turn_of

_NS = {**DRAWINGML, "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
_BLIP = etree.XPath("./p:blipFill/a:blip", namespaces=_NS)
_PROPERTIES = etree.XPath("./*[1]/p:cNvPr", namespaces=_NS)
_TRANSFORM = etree.XPath("./p:spPr/a:xfrm", namespaces=_NS)


def _found(path: etree.XPath, shape: Any) -> list[Any]:  # noqa: ANN401 (python-pptx's own shape classes)
    """What the XPath ``path`` finds in ``shape``'s element (lxml types every result as a union)."""
    result: Any = path(shape._element)
    return list(result)


def _blob_of(shape) -> bytes | None:  # noqa: ANN001 (python-pptx's own shape classes are not one type)
    """What the picture draws: its SVG, when it has one beside the ordinary picture, else the picture itself."""
    blips = _found(_BLIP, shape)
    try:
        return shape.part.related_part(shown_part(blips[0])).blob if blips else shape.image.blob
    except (KeyError, ValueError, AttributeError):
        return None


def held_picture(shape) -> ImageAsset | None:  # noqa: ANN001
    """The asset of ``shape`` when it is a picture the model holds as it is shown (see
    :mod:`claudia_core.file_pictures`), else ``None``."""
    if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
        return None
    if any((shape.crop_left, shape.crop_right, shape.crop_top, shape.crop_bottom)):
        return None
    transform = _found(_TRANSFORM, shape)
    if turn_of(transform[0] if transform else None) is None:  # (flipped)
        return None
    asset = asset_of(_blob_of(shape))
    if asset is None:
        return None
    prs = shape.part.package.presentation_part.presentation
    w = round(shape.width / (prs.slide_width / SLIDE_WIDTH))
    h = round(shape.height / (prs.slide_height / SLIDE_HEIGHT))
    return asset if keeps_proportions(asset, w, h) else None


def alt_text_of(shape) -> tuple[str, bool]:  # noqa: ANN001
    """``(description, decorative)`` of a shape: its alt text, and whether PowerPoint's mark says it is decorative."""
    properties = _found(_PROPERTIES, shape)
    if not properties:
        return "", False
    return properties[0].get("descr", ""), is_decorative(properties[0])
