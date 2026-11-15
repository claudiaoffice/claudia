"""How far a turned object reaches (D910, rotation-ui), in whole units, with no floating-point sine.

An object is turned about the centre of its frame, so a turned object reaches further than its frame does. A
slide keeps its objects on the slide, and it must reach the same verdict about the same document on every server:
the arithmetic here is integer, from a table of sines to a millionth, exactly as the display list's is (D910).

``turned_extent`` is how wide and how tall the turned outline is, rounded up so the outline never reaches further than
the number says. ``nudge_into`` is the nearest place for the object to be at which that outline is inside a space.
"""

from __future__ import annotations

#: ``sin(d°)`` in millionths for the whole degrees from 0 to 90 (rounded, from the true sine). Every other angle
#: is a reflection of one of these.
SINE_MILLIONTHS: tuple[int, ...] = (
    0, 17452, 34899, 52336, 69756, 87156, 104528, 121869, 139173, 156434,
    173648, 190809, 207912, 224951, 241922, 258819, 275637, 292372, 309017, 325568,
    342020, 358368, 374607, 390731, 406737, 422618, 438371, 453990, 469472, 484810,
    500000, 515038, 529919, 544639, 559193, 573576, 587785, 601815, 615661, 629320,
    642788, 656059, 669131, 681998, 694658, 707107, 719340, 731354, 743145, 754710,
    766044, 777146, 788011, 798636, 809017, 819152, 829038, 838671, 848048, 857167,
    866025, 874620, 882948, 891007, 898794, 906308, 913545, 920505, 927184, 933580,
    939693, 945519, 951057, 956305, 961262, 965926, 970296, 974370, 978148, 981627,
    984808, 987688, 990268, 992546, 994522, 996195, 997564, 998630, 999391, 999848,
    1_000_000,
)  # fmt: skip
_MILLION = 1_000_000


def _sine_cosine_magnitudes(rotation: int) -> tuple[int, int]:
    """``|sin|`` and ``|cos|`` of a whole number of degrees, in millionths. Both are what an outline's extent needs."""
    degrees = rotation % 180
    folded = degrees if degrees <= 90 else 180 - degrees
    return SINE_MILLIONTHS[folded], SINE_MILLIONTHS[90 - folded]


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def turned_extent(w: int, h: int, rotation: int) -> tuple[int, int]:
    """Width and height of the outline of a ``w`` by ``h`` frame turned ``rotation`` whole degrees about its centre,
    rounded up to whole units."""
    sine, cosine = _sine_cosine_magnitudes(rotation)
    return (
        _ceil_div(w * cosine + h * sine, _MILLION),
        _ceil_div(w * sine + h * cosine, _MILLION),
    )


def _range_for(size: int, extent: int, space: int) -> tuple[int, int]:
    """The lowest and highest top-left coordinate at which an outline ``extent`` wide, centred on a frame ``size``
    wide, lies inside ``0 … space``. Worked in doubled units, because a centre may lie between two units."""
    return _ceil_div(extent - size, 2), (2 * space - size - extent) // 2


def nudge_into(x: int, y: int, w: int, h: int, rotation: int, width: int, height: int) -> tuple[int, int] | None:
    """The top-left corner nearest ``(x, y)`` at which a ``w`` by ``h`` frame, turned ``rotation`` degrees, has its
    whole outline inside a space ``width`` by ``height``; ``None`` if it cannot be inside at all. The corner is that of
    the unturned frame, so for a turned object it may itself lie outside the space."""
    out_w, out_h = turned_extent(w, h, rotation)
    low_x, high_x = _range_for(w, out_w, width)
    low_y, high_y = _range_for(h, out_h, height)
    if low_x > high_x or low_y > high_y:
        return None
    return min(max(x, low_x), high_x), min(max(y, low_y), high_y)
