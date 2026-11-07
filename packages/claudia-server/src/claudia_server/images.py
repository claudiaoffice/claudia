"""The ``"image"`` parameter kind: the bytes of a picture someone imports, shared by every app that takes one.

The wire protocol is JSON text frames (``protocol.py``), so there is no binary upload channel: a client sends an
image as base64 text, decoded here into the plain bytes :func:`claudia_core.decode_image` reads. This module has
no app-specific knowledge; composes and computes register the same ``"image"`` kind on their own extended table,
exactly as ``creates.py`` does (``table.kind("image")(image_bytes)``).
"""

from __future__ import annotations

import base64
from typing import Any

from claudia_core import MAX_IMAGE_BYTES

from .protocol import Limits


def image_bytes(value: Any, limits: Limits) -> bytes:
    """base64 text of an image file, decoding to at most claudia_core.MAX_IMAGE_BYTES"""
    if not isinstance(value, str):
        raise ValueError("must be base64 text")
    try:
        raw = base64.b64decode(value, validate=True)
    except ValueError, TypeError:
        raise ValueError("must be valid base64 text") from None
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(f"an image is at most {MAX_IMAGE_BYTES // (1024 * 1024)} MB")
    return raw
