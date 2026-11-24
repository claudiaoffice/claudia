"""claudia-opc-io: generic Open Packaging Conventions mechanics shared by every format's io package (D217).

package     read_parts/write_parts -- a zip package as a plain dict of its parts, and back
limits      check_package/PackageLimits -- how much a package may unpack to, judged before it is unpacked (SEC-15)
xml         parse_xml -- the one way the XML of a package is read: entities never expanded (SEC-15)
reconcile   owns/reconcile -- restore whatever a format library's save() was not asked to touch
properties  stamp_core_properties/stamp_package -- who made a fresh file and when (D466)
custom      custom_properties/set_custom_properties -- the custom properties of a file (D1478)
drawingml   turn_of/cropped/shown_part/is_decorative/look_in, solid/outline -- what a DrawingML drawing says of itself
and how a shape is filled and outlined (D1478, D1479)
theme       ThemeFonts -- the heading and body fonts of the Office theme docx and pptx share (E3.13)

Deliberately knows nothing about any one format: no cell, no paragraph, no shape. openpyxl/python-docx/
python-pptx/odfdo (and claudia's own ``*_io`` packages built on them) stay exactly as they are; this sits below
all of them, patching their output back against the file they started from.
"""

from ._version import __version__
from .custom import CUSTOM_PART, custom_properties, set_custom_properties
from .drawingml import (
    ANGLE,
    DECORATIVE_URI,
    DRAWINGML,
    EMU_PER_PIXEL,
    EMU_PER_POINT,
    PRESET,
    SHAPE_OF,
    SVG_URI,
    UNKNOWN,
    cropped,
    is_decorative,
    look_in,
    mark_decorative,
    outline,
    shown_part,
    solid,
    turn_of,
)
from .limits import DEFAULT_LIMITS, PackageLimits, PackageRefused, check_package
from .package import read_parts, write_parts
from .properties import APPLICATION, CORE_PART, stamp_core_properties, stamp_package, utc_second
from .reconcile import OwnedTest, owns, reconcile
from .theme import ThemeFonts
from .xml import parse_xml

__all__ = [
    "ANGLE",
    "APPLICATION",
    "CORE_PART",
    "CUSTOM_PART",
    "DECORATIVE_URI",
    "DEFAULT_LIMITS",
    "DRAWINGML",
    "EMU_PER_PIXEL",
    "EMU_PER_POINT",
    "OwnedTest",
    "PRESET",
    "PackageLimits",
    "PackageRefused",
    "SHAPE_OF",
    "SVG_URI",
    "ThemeFonts",
    "UNKNOWN",
    "__version__",
    "check_package",
    "cropped",
    "custom_properties",
    "is_decorative",
    "look_in",
    "mark_decorative",
    "outline",
    "owns",
    "parse_xml",
    "read_parts",
    "reconcile",
    "set_custom_properties",
    "shown_part",
    "solid",
    "stamp_core_properties",
    "stamp_package",
    "turn_of",
    "utc_second",
    "write_parts",
]
