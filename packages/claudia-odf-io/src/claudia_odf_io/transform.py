"""How an OpenDocument drawing object is turned (D459, D464).

A file turns an object with ``draw:transform="rotate (a) translate (x y)"`` and no ``svg:x`` or ``svg:y``: the object is
drawn at its own size with its top left corner at the origin, turned about that corner by ``a``, and then moved by
``(x, y)``. ``a`` is in radians and counts *counter*-clockwise; the model counts whole degrees clockwise (as PowerPoint
does), and its box (``x``, ``y``, ``w``, ``h``) is the box before it is turned, which the object turns about the centre
of. LibreOffice writes exactly this form (checked with LibreOffice 24.2: a rectangle turned by 30 degrees in a pptx
comes out of it as ``rotate (-0.523598775598299) translate (2.929cm 1.2cm)``).

A transform of any other kind (a skew, a scale, a translation alone) is not a rotation the model can hold.
All lengths here are in centimetres, except what :func:`inches` reads.
"""

from __future__ import annotations

import math
import re

#: Centimetres in an inch, and in a pixel (96 to the inch).
CM_PER_INCH = 2.54
CM_PER_PIXEL = CM_PER_INCH / 96
_INCHES = {"cm": 1 / 2.54, "mm": 1 / 25.4, "in": 1.0, "pt": 1 / 72, "pc": 1 / 6, "px": 1 / 96}
_NUMBER = r"-?(?:\d+\.?\d*|\.\d+)"
_LENGTH = re.compile(rf"\s*({_NUMBER})\s*(cm|mm|in|pt|pc|px)\s*")
#: LibreOffice writes ``skewX (-5.2E-017)`` before a rotation: a skew of nothing, which is none.
_NEGLIGIBLE_SKEW = 1e-9
_ANGLE = rf"({_NUMBER}(?:[eE][-+]?\d+)?)"
_LONG = rf"({_NUMBER}(?:cm|mm|in|pt|pc|px))"
_TRANSFORM = re.compile(
    rf"\s*(?:skewX\s*\(\s*{_ANGLE}\s*\)\s*)?rotate\s*\(\s*{_ANGLE}\s*\)\s*"
    rf"translate\s*\(\s*{_LONG}\s*[ ,]\s*{_LONG}\s*\)\s*"
)


def inches(value: str | None) -> float | None:
    """A length of the format (``"2.5cm"``, ``"1in"``) in inches, or ``None`` if it is not one."""
    match = _LENGTH.fullmatch(value) if value else None
    return float(match.group(1)) * _INCHES[match.group(2)] if match else None


def pixels(value: str | None) -> float | None:
    """A length of the format in pixels (96 to the inch); ``None`` when it is none."""
    found = inches(value)
    return None if found is None else found * 96


def _cm(length: str) -> float:
    in_inches = inches(length)
    assert in_inches is not None  # (the pattern only lets lengths through)
    return in_inches * 2.54


def _text(value: float) -> str:
    """A length of the format's centimetres to four places, without the zeros after them."""
    text = f"{value + 0.0:.4f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _rotation(transform: str) -> tuple[float, str, str] | None:
    """``(angle in radians counter-clockwise, x, y)`` of a rotation and a translation, or ``None`` for any other
    transform (a skew that is more than rounding included)."""
    match = _TRANSFORM.fullmatch(transform)
    if match is None or (match.group(1) is not None and abs(float(match.group(1))) > _NEGLIGIBLE_SKEW):
        return None
    return float(match.group(2)), match.group(3), match.group(4)


def angle_of(transform: str) -> float | None:
    """The angle of a ``draw:transform`` that is a rotation and a translation, in degrees clockwise (0 up to 360), or
    ``None`` for any other transform."""
    found = _rotation(transform)
    return None if found is None else math.degrees(-found[0]) % 360


def transform_of(degrees: int, box: tuple[float, float, float, float]) -> str | None:
    """The ``draw:transform`` that turns the box ``(x, y, w, h)`` (cm) by ``degrees`` clockwise about its centre;
    ``None`` for an object that is not turned (it has its place and its size as attributes)."""
    if degrees % 360 == 0:
        return None
    x, y, w, h = box
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)
    half_w, half_h = w / 2, h / 2
    # the corner goes where the centre's own turn leaves it: centre - R(angle) * (half the size)
    corner_x = x + half_w - (cos * half_w - sin * half_h)
    corner_y = y + half_h - (sin * half_w + cos * half_h)
    return f"rotate ({-angle:.15g}) translate ({_text(corner_x)}cm {_text(corner_y)}cm)"


def turned_box(transform: str, w: float, h: float) -> tuple[float, float, float] | None:
    """What a rotation-and-translation transform of an object ``w`` by ``h`` (cm) says: the angle in degrees clockwise
    and the top left corner (cm) of the box the object has before it is turned; ``None`` if it is no such transform."""
    found = _rotation(transform)
    if found is None:
        return None
    angle = -found[0]
    cos, sin = math.cos(angle), math.sin(angle)
    corner_x, corner_y = _cm(found[1]), _cm(found[2])
    half_w, half_h = w / 2, h / 2
    centre_x = corner_x + cos * half_w - sin * half_h
    centre_y = corner_y + sin * half_w + cos * half_h
    return math.degrees(angle) % 360, centre_x - half_w, centre_y - half_h
