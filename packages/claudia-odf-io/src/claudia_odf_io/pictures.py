"""Reading the pictures of an OpenDocument file as image objects (D460, D464): a ``draw:frame`` with a ``draw:image`` in
it, which the model holds when its bytes are in the package and are an image the app decodes, it is not cropped, and
it has the proportions of the picture (:func:`held_frame`; see :mod:`claudia_core.file_pictures`). Texts and
spreadsheets read them alike (D1478)."""

from __future__ import annotations

import re
from collections.abc import Mapping

from lxml import etree

from claudia_core import MIN_OBJECT_SIZE, ImageAsset, asset_of, keeps_proportions

from .names import NS, local_name
from .transform import pixels, turned_box

_NO_CLIP = re.compile(r"rect\(\s*(?:0(?:\.0+)?(?:cm|mm|in|pt)?\s*,?\s*){4}\)")


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def _clipped(element: etree._Element, graphics: Mapping[str, etree._Element]) -> bool:
    """Does the style of the frame (or one it is based on) cut a part off the picture?"""
    name, seen = element.get(_q("draw", "style-name")), set()
    while name and name not in seen and name in graphics:
        seen.add(name)
        style = graphics[name]
        for props in style.findall("style:graphic-properties", NS):
            clip = props.get(_q("fo", "clip"))
            if clip and clip != "auto" and not _NO_CLIP.fullmatch(clip.strip()):
                return True
        name = style.get(_q("style", "parent-style-name"))
    return False


def graphic_styles(*roots: etree._Element | None) -> dict[str, etree._Element]:
    """Every style of graphics of the parts ``roots`` (content and styles), by name."""
    found: dict[str, etree._Element] = {}
    for root in roots:
        if root is None:
            continue
        for style in root.iter(_q("style", "style")):
            name = style.get(_q("style", "name"))
            if name and style.get(_q("style", "family")) == "graphic":
                found[name] = style
    return found


def picture_of(
    frame: etree._Element, graphics: Mapping[str, etree._Element], parts: Mapping[str, bytes]
) -> ImageAsset | None:
    """The asset of a ``draw:frame`` that holds one picture the model can hold, else ``None``."""
    images = [child for child in frame if isinstance(child.tag, str) and local_name(child.tag) == "image"]
    if len(images) != 1 or _clipped(frame, graphics):
        return None
    href = images[0].get(_q("xlink", "href")) or ""
    return asset_of(parts.get(href.removeprefix("./")))


def name_of(frame: etree._Element) -> str:
    """The file name of the picture of ``frame``, as the file says it."""
    image = frame.find("draw:image", NS)
    return (image.get(_q("xlink", "href")) or "").rsplit("/", 1)[-1] if image is not None else ""


def description_element(frame: etree._Element) -> etree._Element | None:
    """The ``svg:desc`` of ``frame``, if it has one."""
    return frame.find("svg:desc", NS)


def description_of(frame: etree._Element) -> str:
    """What ``frame`` says to someone who cannot see it: its ``svg:desc``, or else its ``svg:title``."""
    for name in ("desc", "title"):
        found = frame.find(f"svg:{name}", NS)
        if found is not None and (text := "".join(str(piece) for piece in found.itertext()).strip()):
            return text
    return ""


def held_frame(
    frame: etree._Element, graphics: Mapping[str, etree._Element], parts: Mapping[str, bytes]
) -> tuple[ImageAsset, tuple[int, int], int] | None:
    """``(asset, size in pixels, rotation)`` of a ``draw:frame`` that is a picture the model shows as it is, else
    ``None``."""
    asset = picture_of(frame, graphics, parts)
    width, height = pixels(frame.get(_q("svg", "width"))), pixels(frame.get(_q("svg", "height")))
    if asset is None or width is None or height is None:
        return None
    size = (round(width), round(height))
    rotation = 0
    if transform := frame.get(_q("draw", "transform")):
        turned = turned_box(transform, width, height)
        if turned is None:
            return None
        rotation = round(turned[0]) % 360
    if min(size) < MIN_OBJECT_SIZE or not keeps_proportions(asset, *size):
        return None
    return asset, size, rotation
