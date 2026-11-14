"""Pictures for programs that cannot draw an SVG as it is (D394).

A rendered text container is an SVG, and the programs that open an office file differ in what they draw of one:
PowerPoint 2016 and later draw it; LibreOffice leaves out what a diagram's ``<style>`` colours and text. A caller that
has a rasteriser (the server, with ``rsvg-convert``) gives it to the export, and the file gets a picture every program
draws; one that has none gets the SVG alone, and the export report says so.
"""

import struct
import zlib
from collections.abc import Callable

FALLBACK_SIDE = 32  # pixels on the longer side of the empty picture that stands in when nothing can draw the SVG

#: Draws an SVG (its bytes, the frame's width and height in slide units) as a PNG; see :func:`slides_to_pptx`.
Rasterise = Callable[[bytes, int, int], bytes]


def blank_png(width: int, height: int) -> bytes:
    """A transparent PNG of the frame's proportions: what a program that cannot draw SVG shows (nothing, in the right
    place). Written by hand (zlib and struct) because no rasteriser is part of this package."""
    longer = max(width, height, 1)
    w, h = max(1, round(FALLBACK_SIDE * width / longer)), max(1, round(FALLBACK_SIDE * height / longer))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(b"\x00" + b"\x00\x00\x00\x00" * w for _ in range(h))
    header = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")
