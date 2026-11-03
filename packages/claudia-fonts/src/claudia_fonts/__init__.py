"""claudia-fonts: the font collection of a Claudia server (E3.3).

A *collection* is a folder of font files with a ``collection.json`` that states the licence
(:mod:`claudia_fonts.collection`). The :class:`Catalogue` reads collections and knows the fonts a server has, what it
refused and why, and which family stands in for a missing one (:mod:`claudia_fonts.catalogue`). Two consumers use it
with the same files: clients get WOFF2 web fonts and the CSS for them (:mod:`claudia_fonts.webfonts`), and a
typesetting engine gets a fontconfig setup that shows it exactly these fonts (:mod:`claudia_fonts.fontconfig`).

The package does no networking and reads no document: it is a library the servers use. It is not part of the kernel
(``claudia-core``), which stays standard-library only.
"""

from ._version import __version__
from .catalogue import DEFAULT_SUBSTITUTIONS, Catalogue, Problem, Resolution
from .collection import COLLECTION_FILE, Collection, CollectionRecord, RecordError
from .font import FontFile, FontProblem, read_font
from .fontconfig import JobFonts, write_fontconfig
from .webfonts import NotServable, WebFontCache, font_face_css

__all__ = [
    "COLLECTION_FILE",
    "DEFAULT_SUBSTITUTIONS",
    "Catalogue",
    "Collection",
    "CollectionRecord",
    "FontFile",
    "FontProblem",
    "JobFonts",
    "NotServable",
    "Problem",
    "RecordError",
    "Resolution",
    "WebFontCache",
    "__version__",
    "font_face_css",
    "read_font",
    "write_fontconfig",
]
