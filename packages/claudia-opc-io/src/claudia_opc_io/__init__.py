"""claudia-opc-io: generic Open Packaging Conventions mechanics shared by every format's io package (D217).

package     read_parts/write_parts -- a zip package as a plain dict of its parts, and back
limits      check_package/PackageLimits -- how much a package may unpack to, judged before it is unpacked (SEC-15)
xml         parse_xml -- the one way the XML of a package is read: entities never expanded (SEC-15)
reconcile   owns/reconcile -- restore whatever a format library's save() was not asked to touch
properties  stamp_core_properties/stamp_package -- who made a fresh file and when (D466)
theme       ThemeFonts -- the heading and body fonts of the Office theme docx and pptx share (E3.13)

Deliberately knows nothing about any one format: no cell, no paragraph, no shape. openpyxl/python-docx/
python-pptx/odfdo (and claudia's own ``*_io`` packages built on them) stay exactly as they are; this sits below
all of them, patching their output back against the file they started from.
"""

from ._version import __version__
from .limits import DEFAULT_LIMITS, PackageLimits, PackageRefused, check_package
from .package import read_parts, write_parts
from .properties import APPLICATION, CORE_PART, stamp_core_properties, stamp_package, utc_second
from .reconcile import OwnedTest, owns, reconcile
from .theme import ThemeFonts
from .xml import parse_xml

__all__ = [
    "APPLICATION",
    "CORE_PART",
    "DEFAULT_LIMITS",
    "OwnedTest",
    "PackageLimits",
    "PackageRefused",
    "ThemeFonts",
    "__version__",
    "check_package",
    "owns",
    "parse_xml",
    "read_parts",
    "reconcile",
    "stamp_core_properties",
    "stamp_package",
    "utc_second",
    "write_parts",
]
