"""Images: content-addressed assets shared by every app that can hold a picture (E10.8).

Decoding happens once, wherever an app takes bytes in (a file picked from disk today; the clipboard and
drag-and-drop land later, per the product decision to build those last), and turns them into an
:class:`ImageAsset`: its format, pixel size, whether it is animated, and the bytes a view needs to show it.
The asset is identified by the sha256 of the bytes it was decoded from, so that two imports of the same
picture — even by different people, even into different documents — share one asset once an app chooses to
reuse it; this module only decodes, an app's model decides whether and how to deduplicate.

An asset carries no opinion about where it sits on a page or a slide, exactly as
``claudia_creates.shapes.ShapeDefinition`` carries no colour or position — that is each app's object model's
business. :class:`ImageImport` is the separate, small record of how one copy of an asset entered one
document: who, when, and from where. It is kept apart from :class:`ImageAsset` so that an app's object (a
``SlideObject``, a sheet's picture, a composes anchor, ...) can carry one import record without re-deciding
what that record looks like, and so that :meth:`ImageImport.masked` can hide where it came from from
everyone but the importer (the product decision that a colleague sees "imported from disk", not the
importer's own filesystem path) without touching the asset at all.

Decoding is pure Python and dependency-free, matching the kernel's own ``dependencies = []``: just enough of
each format is read to find its pixel dimensions and, for an animated GIF, to count its frames and slice out
the bytes of a still first frame. Nothing here renders, re-encodes or even fully parses a pixel — a JPEG's
entropy-coded scan data, a BMP's pixel array and a GIF's LZW streams are all passed through untouched.
"""

from __future__ import annotations

import base64
import hashlib
import re
import struct
from collections.abc import Iterator
from dataclasses import dataclass, replace
from xml.etree import ElementTree

SUPPORTED_IMAGE_FORMATS = ("jpeg", "png", "gif", "bmp", "svg")
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # a single asset's encoded size (the source bytes, not any first frame)
_MAX_BASE64_CHARS = ((MAX_IMAGE_BYTES + 2) // 3) * 4  # the longest base64 text that can decode to <= MAX_IMAGE_BYTES
MAX_ALT_CHARS = 300
MAX_SOURCE_NAME_CHARS = 200

_HASH_ID = re.compile(r"[0-9a-f]{64}")  # a sha256 hex digest: the id of an asset

# SVG sanitization: elements and attributes that can run script or reach outside the document are dropped
# rather than merely rejecting the whole file, so that an otherwise-fine drawing with one stray handler still
# imports. A DOCTYPE or ENTITY is rejected outright, at the text level, before anything parses it: that is
# how an XML entity-expansion bomb or an external-entity read (XXE) is built, and stdlib ElementTree does not
# guard against either on its own.
_SVG_DOCTYPE_OR_ENTITY = re.compile(r"<!(DOCTYPE|ENTITY)\b", re.IGNORECASE)
_SVG_DISALLOWED_LOCAL_NAMES = {
    "script",
    "foreignobject",
    "iframe",
    "use",
    "animate",
    "animatemotion",
    "animatetransform",
    "set",
}
_SVG_EVENT_ATTR = re.compile(r"^on[a-z]+$", re.IGNORECASE)
_SVG_HREF_LOCAL_NAMES = {"href"}  # covers xlink:href too: ElementTree strips the namespace prefix off local-name()


class ImageError(ValueError):
    """An image that cannot be taken in; the message says what is wrong, for a dialog to show as it stands."""


def _qualify(tag: str) -> str:
    """The local name of a (possibly namespaced, ``{uri}name``) XML tag or attribute, lower-cased."""
    return (tag.rsplit("}", 1)[-1] if "}" in tag else tag).lower()


@dataclass(frozen=True)
class ImageAsset:
    """One decoded image. ``data`` is the original bytes, exactly as they were decoded; for an animated GIF,
    ``first_frame`` is additionally the bytes of a still GIF showing only the first frame, so a view can show
    something before the person asks to play the animation, without shipping every frame twice."""

    id: str
    format: str
    width: int
    height: int
    animated: bool
    data: bytes
    first_frame: bytes | None = None

    @property
    def size_bytes(self) -> int:
        """The size of the original bytes (not counting ``first_frame``)."""
        return len(self.data)

    @property
    def aspect(self) -> float:
        """Width divided by height, for an object that must keep the picture's own proportions."""
        return self.width / self.height

    def to_data(self) -> dict:
        """The plain-data (JSON-compatible) form stored in a document and sent to clients."""
        return {
            "id": self.id,
            "format": self.format,
            "width": self.width,
            "height": self.height,
            "animated": self.animated,
            "data": base64.b64encode(self.data).decode("ascii"),
            "first_frame": None if self.first_frame is None else base64.b64encode(self.first_frame).decode("ascii"),
        }

    @classmethod
    def from_data(cls, data: dict) -> ImageAsset:
        """Inverse of :meth:`to_data`; raises :class:`ImageError` naming the first thing that is wrong."""
        if not isinstance(data, dict):
            raise ImageError("an image asset is one JSON object")
        try:
            image_id, fmt = data["id"], data["format"]
            width, height, animated = data["width"], data["height"], data["animated"]
            encoded, first_frame = data["data"], data.get("first_frame")
        except KeyError as error:
            raise ImageError(f"an image asset needs {error.args[0]!r}") from None
        if not isinstance(image_id, str) or not _HASH_ID.fullmatch(image_id):
            raise ImageError("id: must be a sha256 digest (64 lower-case hex digits)")
        if fmt not in SUPPORTED_IMAGE_FORMATS:
            raise ImageError(f"format: must be one of {', '.join(SUPPORTED_IMAGE_FORMATS)}, not {fmt!r}")
        if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
            raise ImageError("width and height must be whole numbers greater than 0")
        if not isinstance(animated, bool):
            raise ImageError("animated must be true or false")
        # Cheap, before any decoding: a base64 string this long cannot possibly decode under the cap, so there
        # is no reason to spend the memory decoding it just to reject it a moment later. decode_image() enforces
        # MAX_IMAGE_BYTES before doing any decode work for the same reason; from_data() is a separate path (a
        # command log replay, a document loaded from storage) that must not be a way around that cap.
        oversized_text = (not isinstance(encoded, str) or len(encoded) > _MAX_BASE64_CHARS) or (
            first_frame is not None and (not isinstance(first_frame, str) or len(first_frame) > _MAX_BASE64_CHARS)
        )
        if oversized_text:
            raise ImageError(f"an image is at most {MAX_IMAGE_BYTES // (1024 * 1024)} MB")
        try:
            raw = base64.b64decode(encoded, validate=True)
            raw_first = None if first_frame is None else base64.b64decode(first_frame, validate=True)
        except (ValueError, TypeError) as error:
            raise ImageError(f"data is not valid base64: {error}") from None
        if len(raw) > MAX_IMAGE_BYTES or (raw_first is not None and len(raw_first) > MAX_IMAGE_BYTES):
            raise ImageError(f"an image is at most {MAX_IMAGE_BYTES // (1024 * 1024)} MB")
        return cls(image_id, fmt, width, height, animated, raw, raw_first)


@dataclass(frozen=True)
class ImageImport:
    """How one copy of an :class:`ImageAsset` entered one document: who, when, with what alt text, and from
    where. ``source`` is ``"disk"`` today (``"clipboard"`` is a later addition, per the product decision to
    build it last); ``source_name`` is the file name as the browser or client exposed it, and ``source_path``
    is the full path *if the client could supply one* — a plain web browser cannot, for its own security
    (``file.name`` only, never a filesystem path), so it is commonly ``None`` even for a disk import.

    ``imported_by`` and ``imported_at`` are final values, set once by the server when the import happens
    (never recomputed on replay), exactly as every other command carries final values rather than working
    them out again."""

    asset: str  # the ImageAsset's id
    alt: str
    imported_by: str
    imported_at: str
    source: str  # "disk" (clipboard follows later)
    source_name: str
    source_path: str | None = None

    def to_data(self) -> dict:
        """The plain-data form: what a command and the log store. Carries the full record, unmasked."""
        return {
            "asset": self.asset,
            "alt": self.alt,
            "imported_by": self.imported_by,
            "imported_at": self.imported_at,
            "source": self.source,
            "source_name": self.source_name,
            "source_path": self.source_path,
        }

    @classmethod
    def from_data(cls, data: dict) -> ImageImport:
        """Inverse of :meth:`to_data`; raises :class:`ImageError` naming the first thing that is wrong."""
        if not isinstance(data, dict):
            raise ImageError("an image import record is one JSON object")
        fields = ("asset", "alt", "imported_by", "imported_at", "source", "source_name", "source_path")
        if set(data) != set(fields):
            raise ImageError("an image import record has exactly these fields: " + ", ".join(fields))
        if not isinstance(data["alt"], str):
            raise ImageError("alt: text (empty for a decorative picture)")
        if len(data["alt"]) > MAX_ALT_CHARS:
            raise ImageError(f"alt: at most {MAX_ALT_CHARS} characters")
        if not isinstance(data["source_name"], str) or len(data["source_name"]) > MAX_SOURCE_NAME_CHARS:
            raise ImageError(f"source_name: text of at most {MAX_SOURCE_NAME_CHARS} characters")
        if data["source"] not in ("disk", "clipboard"):
            raise ImageError("source: 'disk' or 'clipboard'")
        if data["source_path"] is not None and not isinstance(data["source_path"], str):
            raise ImageError("source_path: text, or null when the client could not supply one")
        return cls(**data)

    def masked(self, viewer: str) -> ImageImport:
        """This record as ``viewer`` may see it: ``source_path`` only to the person who imported it (D… the
        product decision that a colleague sees "imported from disk", not the importer's own filesystem path),
        everything else — including that it *was* imported from disk, and by whom — the same for everyone."""
        if viewer == self.imported_by or self.source_path is None:
            return self
        return replace(self, source_path=None)


def decode_image(data: bytes, *, checked_drawing: bool = False) -> ImageAsset:
    """Decode ``data`` (the bytes of a file) into an :class:`ImageAsset`; raises :class:`ImageError` if the
    bytes are too large, or are not one of :data:`SUPPORTED_IMAGE_FORMATS`, or are not well-formed enough to
    find a pixel size in.

    ``checked_drawing`` is for an SVG that a renderer of the server made and the server has already checked against
    an allowlist of drawing elements (``claudia_typeset.check_svg``): such a picture is made of ``<use>`` elements
    (every glyph of a typeset page is one), which a picture somebody imports may not have. A ``<use>`` that points
    anywhere but into the picture is still removed, and so is everything else unsafe (D344)."""
    if not isinstance(data, bytes) or not data:
        raise ImageError("no image data")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageError(f"an image is at most {MAX_IMAGE_BYTES // (1024 * 1024)} MB")
    fmt = _sniff_format(data)
    image_id = hashlib.sha256(data).hexdigest()
    if fmt == "jpeg":
        width, height = _jpeg_dimensions(data)
        return ImageAsset(image_id, fmt, width, height, False, data)
    if fmt == "bmp":
        width, height = _bmp_dimensions(data)
        return ImageAsset(image_id, fmt, width, height, False, data)
    if fmt == "png":
        width, height, animated = _png_info(data)
        first_frame = _png_first_frame_bytes(data) if animated else None
        return ImageAsset(image_id, fmt, width, height, animated, data, first_frame)
    if fmt == "gif":
        width, height, frames = _gif_info(data)
        animated = frames > 1
        first_frame = _gif_first_frame_bytes(data) if animated else None
        return ImageAsset(image_id, fmt, width, height, animated, data, first_frame)
    sanitized = _sanitize_svg(data, keep=frozenset({"use"}) if checked_drawing else frozenset())
    width, height = _svg_dimensions(sanitized)
    return ImageAsset(image_id, "svg", width, height, False, sanitized)


def _sniff_format(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(_PNG_SIGNATURE):
        return "png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data.startswith(b"BM"):
        return "bmp"
    stripped = data.lstrip(b" \t\r\n\xef\xbb\xbf")  # leading whitespace, or a UTF-8 BOM
    if stripped.startswith(b"<?xml") or stripped.startswith(b"<svg") or b"<svg" in stripped[:4096]:
        return "svg"
    raise ImageError(f"not a supported image: expected one of {', '.join(SUPPORTED_IMAGE_FORMATS)}")


# -- JPEG: scan the markers for the first Start Of Frame -------------------------------------------------------
_JPEG_SOF = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})
_JPEG_NO_LENGTH = frozenset({0xD8, 0xD9, 0x01, *range(0xD0, 0xD8)})  # SOI, EOI, TEM, RSTn: no length field follows


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    position = 2  # past the SOI marker (already checked by _sniff_format)
    while position + 1 < len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        marker = data[position + 1]
        position += 2
        if marker in _JPEG_NO_LENGTH or marker == 0xFF:
            continue
        if position + 2 > len(data):
            break
        (length,) = struct.unpack_from(">H", data, position)
        if marker in _JPEG_SOF:
            if position + 7 > len(data):
                break
            height, width = struct.unpack_from(">HH", data, position + 3)
            if width > 0 and height > 0:
                return width, height
            break
        position += length
    raise ImageError("not a well-formed JPEG: no frame header with a size was found")


# -- BMP: the BITMAPINFOHEADER follows the 14-byte file header --------------------------------------------------
def _bmp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 26:
        raise ImageError("not a well-formed BMP: too short for a header")
    width, raw_height = struct.unpack_from("<ii", data, 18)
    height = abs(raw_height)  # a negative height means the rows run top-down; the size is still positive
    if width <= 0 or height <= 0:
        raise ImageError("not a well-formed BMP: no positive width and height in the header")
    return width, height


# -- PNG: a walk of the chunk structure (no pixel decoding) -----------------------------------------------------
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
#: The chunks that make a PNG an *animated* PNG (APNG). Everything else is an ordinary still image, and a
#: viewer that does not understand these three shows the default image — which is why dropping them is all it
#: takes to get a still first frame out of an APNG.
_APNG_CHUNKS = frozenset({b"acTL", b"fcTL", b"fdAT"})


def _png_chunks(data: bytes) -> Iterator[tuple[bytes, int, int]]:
    """``(type, start, end)`` of each chunk, ``start``/``end`` spanning the whole chunk (length, type, data, CRC).

    A PNG is its 8-byte signature and then nothing but chunks, so this is the whole file structure."""
    position = len(_PNG_SIGNATURE)
    while position + 8 <= len(data):
        (length,) = struct.unpack_from(">I", data, position)
        kind = data[position + 4 : position + 8]
        end = position + 12 + length  # 4 length + 4 type + data + 4 CRC
        if length > len(data) or end > len(data):
            raise ImageError("not a well-formed PNG: a chunk runs past the end of the file")
        yield kind, position, end
        if kind == b"IEND":
            return
        position = end


def _png_info(data: bytes) -> tuple[int, int, bool]:
    """``(width, height, animated)``. The size is IHDR's, which a PNG must open with; ``animated`` is whether the
    file carries the APNG control chunk.

    The whole chunk list is walked, and the walk must reach IEND: a file that simply stops partway is refused
    rather than read as a shorter one (the same reasoning as the GIF sub-block walk below — a reader that only
    looked at where it got to would take a truncated file for a well-formed one)."""
    if len(data) < 24:
        raise ImageError("not a well-formed PNG: too short for a header")
    kinds = [kind for kind, _, _ in _png_chunks(data)]
    if not kinds or kinds[0] != b"IHDR":
        raise ImageError("not a well-formed PNG: the first chunk must be IHDR")
    if kinds[-1] != b"IEND":
        raise ImageError("not a well-formed PNG: the chunks end without IEND")
    width, height = struct.unpack_from(">II", data, len(_PNG_SIGNATURE) + 8)
    if width <= 0 or height <= 0:
        raise ImageError("not a well-formed PNG: no positive width and height in the header")
    return width, height, b"acTL" in kinds


def _png_first_frame_bytes(data: bytes) -> bytes:
    """An APNG as a still PNG: the same file with the three animation chunks dropped.

    Every other chunk is copied byte for byte, CRC included, so nothing has to be recomputed — what is left is
    the default image, exactly what a viewer with no APNG support would already have shown."""
    kept = [_PNG_SIGNATURE]
    kept += [data[start:end] for kind, start, end in _png_chunks(data) if kind not in _APNG_CHUNKS]
    return b"".join(kept)


# -- GIF: a hand-rolled walk of the block structure (no pixel decoding) -----------------------------------------
def _gif_data_subblocks(data: bytes, position: int) -> int:
    """The position just past a run of GIF "data sub-blocks" (a length byte then that many bytes, until 0)."""
    while True:
        if position >= len(data):
            # A length byte claimed more data than remains (or the terminator was never reached): this must be
            # refused outright, not silently stop here — a caller that only checks the position it gets back
            # would otherwise read this as "no more blocks" and undercount frames instead of seeing an error.
            raise ImageError("not a well-formed GIF: a truncated data sub-block")
        if data[position] == 0:
            return position + 1
        position += 1 + data[position]


def _gif_blocks(data: bytes) -> list[tuple[int, int]]:
    """``(start, end)`` of each top-level block after the header and logical screen descriptor, up to the trailer."""
    if len(data) < 13:
        raise ImageError("not a well-formed GIF: too short for a header")
    position = 13
    if data[10] & 0x80:  # a global color table follows, sized by the low 3 bits of the packed byte
        position += 3 * (2 << (data[10] & 0x07))
    blocks: list[tuple[int, int]] = []
    while position < len(data):
        start = position
        tag = data[position]
        if tag == 0x3B:  # trailer
            break
        if tag == 0x21:  # extension: introducer, label, then data sub-blocks
            position = _gif_data_subblocks(data, position + 2)
        elif tag == 0x2C:  # image descriptor
            position += 10
            if position > len(data):
                raise ImageError("not a well-formed GIF: a truncated image descriptor")
            if data[position - 1] & 0x80:  # a local color table follows
                position += 3 * (2 << (data[position - 1] & 0x07))
            position += 1  # the LZW minimum code size byte
            position = _gif_data_subblocks(data, position)
        else:
            raise ImageError(f"not a well-formed GIF: unexpected block {tag:#x}")
        blocks.append((start, position))
    return blocks


def _gif_info(data: bytes) -> tuple[int, int, int]:
    width, height = struct.unpack_from("<HH", data, 6)
    if width <= 0 or height <= 0:
        raise ImageError("not a well-formed GIF: no positive width and height in the header")
    frames = sum(1 for start, _ in _gif_blocks(data) if data[start] == 0x2C)
    if frames == 0:
        raise ImageError("not a well-formed GIF: no image in it")
    return width, height, frames


def _gif_first_frame_bytes(data: bytes) -> bytes:
    """A complete, still GIF holding only the first frame (plus whatever preceded it, such as a Graphic Control
    Extension, so the frame's own timing/disposal data stays with it) — everything after is dropped."""
    end = 13 if (data[10] & 0x80) == 0 else 13 + 3 * (2 << (data[10] & 0x07))
    for start, block_end in _gif_blocks(data):
        end = block_end
        if data[start] == 0x2C:
            break
    return data[:end] + b"\x3b"


# -- SVG: stdlib XML, sanitized rather than merely rejected ------------------------------------------------------
def _sanitize_svg(data: bytes, keep: frozenset[str] = frozenset()) -> bytes:
    # The whole file, not just an early prefix: a DOCTYPE/ENTITY is still well-formed XML (and still reaches
    # the parser) if it is pushed past any fixed-size window by padding earlier in the prolog (e.g. a long
    # comment), so a bounded scan here would be a bypass, not a defense.
    if _SVG_DOCTYPE_OR_ENTITY.search(data.decode("utf-8", errors="ignore")):
        raise ImageError("not a safe SVG: a DOCTYPE or ENTITY declaration is not allowed")
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        raise ImageError(f"not a well-formed SVG: {error}") from None
    if _qualify(root.tag) != "svg":
        raise ImageError("not an SVG: the root element must be <svg>")
    _strip_unsafe(root, _SVG_DISALLOWED_LOCAL_NAMES - keep)
    if root.tag.startswith("{"):
        # Keep the familiar `xmlns="..."` form on the way out; without this, ElementTree invents an "ns0:"
        # prefix for the default namespace, which is needless noise on every element of the sanitized file.
        ElementTree.register_namespace("", root.tag[1:].rsplit("}", 1)[0])
    ElementTree.register_namespace("xlink", "http://www.w3.org/1999/xlink")  # not an invented "ns1": see the tests
    return ElementTree.tostring(root, encoding="utf-8")


def _strip_unsafe(element: ElementTree.Element, disallowed: frozenset[str] | set[str]) -> None:
    """Remove script-capable elements, event-handler attributes, and attributes that reach outside the file."""
    for child in list(element):
        if _qualify(child.tag) in disallowed:
            element.remove(child)
        else:
            _strip_unsafe(child, disallowed)
    for name in list(element.attrib):
        local = _qualify(name)
        unsafe_href = local in _SVG_HREF_LOCAL_NAMES and not element.attrib[name].startswith("#")
        if _SVG_EVENT_ATTR.match(local) or unsafe_href:
            del element.attrib[name]


_LENGTH = re.compile(r"[-+]?\d*\.?\d+")


def _svg_dimensions(sanitized: bytes) -> tuple[int, int]:
    root = ElementTree.fromstring(sanitized)
    width = _length_of(root.get("width"))
    height = _length_of(root.get("height"))
    if width is None or height is None:
        box = root.get("viewBox")
        if box is not None:
            parts = box.replace(",", " ").split()
            if len(parts) == 4:
                try:
                    _, _, box_w, box_h = (float(p) for p in parts)
                    width, height = width or box_w, height or box_h
                except ValueError:
                    pass
    if not width or not height or width <= 0 or height <= 0:
        raise ImageError("not a usable SVG: it has no positive width and height, nor a viewBox to read them from")
    return round(width), round(height)


def _length_of(value: str | None) -> float | None:
    if not value:
        return None
    if value.strip().endswith("%"):
        return None  # a share of whatever it is put in is no size
    found = _LENGTH.match(value.strip())
    return float(found.group()) if found else None
