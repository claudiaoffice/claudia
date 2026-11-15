"""The pictures of a presentation file, as the model holds them (D460): an image object with its asset.

A picture comes in when the model can hold it as it is shown: its bytes are an image the app decodes (PNG, JPEG, GIF,
BMP or SVG), it is not cropped or flipped, and it has the proportions of the picture itself (a picture stretched to
some other shape would change when it is written back, and an image object keeps its own proportions). Every other
picture stays in the file and is reported as a ``"picture"`` of what the model does not show.

What the file says of the picture becomes its description (the alt text, BITV 1.1.1) and, where the format has the
mark, its being decorative. The model asks for an import record of every image: a file has no importer of ours, so the
record names the file's own name for the picture and no time.
"""

from __future__ import annotations

from claudia_core import ASPECT_TOLERANCE, ImageAsset, ImageError, ImageImport, ObjectBody, decode_image
from claudia_core.assets import MAX_ALT_CHARS, MAX_SOURCE_NAME_CHARS

#: The style an image object comes in with (its box: the border and fill the model gives a picture).
IMAGE_STYLE = "plain-image"
#: Who a picture of a file was imported by, and when: neither is known of a file.
FILE_IMPORTER = "file"
UNKNOWN_TIME = "1970-01-01T00:00:00.000Z"


def asset_of(data: bytes | None) -> ImageAsset | None:
    """``data`` as an image the app holds, or ``None`` when it is none (or none the app decodes)."""
    if not data:
        return None
    try:
        return decode_image(data)
    except ImageError:
        return None


def keeps_proportions(asset: ImageAsset, w: int, h: int) -> bool:
    """Does an object of this size show the picture in its own proportions (as the model requires)?"""
    return abs(w - asset.aspect * h) <= ASPECT_TOLERANCE


def body_of(
    object_id: str,
    asset: ImageAsset,
    size: tuple[int, int],
    *,
    name: str = "",
    description: str = "",
    decorative: bool = False,
    rotation: int = 0,
) -> ObjectBody:
    """The body of the image object for a picture of a file: its size, what the file says of it and how it is turned."""
    alt = "" if decorative else description[:MAX_ALT_CHARS]
    record = ImageImport(asset.id, alt, FILE_IMPORTER, UNKNOWN_TIME, "disk", name[:MAX_SOURCE_NAME_CHARS])
    return ObjectBody(
        object_id,
        "image",
        size[0],
        size[1],
        IMAGE_STYLE,
        image=asset.id,
        imported=record,
        rotation=rotation,
        description=alt,
        decorative=decorative,
    )
