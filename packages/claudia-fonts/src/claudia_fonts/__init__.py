"""claudia-fonts: the font collection of a Claudia server (E3.3).

A *collection* is a folder of font files with a ``collection.json`` that states the licence
(:mod:`claudia_fonts.collection`). The :class:`Catalogue` reads collections and knows the fonts a server has, what it
refused and why, and which family stands in for a missing one and how close it is (:mod:`claudia_fonts.catalogue`,
on the table of :mod:`claudia_core.stand_ins`). Two consumers use it
with the same files: clients get WOFF2 web fonts and the CSS for them (:mod:`claudia_fonts.webfonts`), and a
typesetting engine gets a fontconfig setup that shows it exactly these fonts (:mod:`claudia_fonts.fontconfig`). Fonts
are added to a server through its settings with :mod:`claudia_fonts.adding` (check first, then add, D1041).

It reads no document, and the only network access is :func:`claudia_fonts.starter.fetch`, which an operator runs to
get the pinned starter set of open fonts. It is a library the servers use. It is not part of the kernel
(``claudia-core``), which stays standard-library only.
"""

from claudia_file_writer import FetchError

from ._version import __version__
from .adding import AddRefused, FileCheck, add_collection, check_files, remove_collection, rename_collection
from .catalogue import CLOSENESS, DEFAULT_GENERICS, DEFAULT_SUBSTITUTIONS, Catalogue, Closeness, Problem, Resolution
from .collection import COLLECTION_FILE, MAY_GO, Collection, CollectionRecord, MayGo, RecordError
from .font import Axis, FontFile, FontProblem, read_font
from .fontconfig import JobFonts, write_fontconfig
from .starter import LockedCollection, LockedFile, builtin_folder, collection_folders, fetch, read_lock
from .webfonts import NotServable, WebFontCache, font_face_css, to_woff2

__all__ = [
    "CLOSENESS",
    "COLLECTION_FILE",
    "MAY_GO",
    "AddRefused",
    "Axis",
    "DEFAULT_GENERICS",
    "DEFAULT_SUBSTITUTIONS",
    "Catalogue",
    "Closeness",
    "Collection",
    "CollectionRecord",
    "FetchError",
    "FileCheck",
    "FontFile",
    "FontProblem",
    "JobFonts",
    "LockedCollection",
    "LockedFile",
    "MayGo",
    "NotServable",
    "Problem",
    "RecordError",
    "Resolution",
    "WebFontCache",
    "__version__",
    "add_collection",
    "builtin_folder",
    "check_files",
    "collection_folders",
    "fetch",
    "font_face_css",
    "read_font",
    "read_lock",
    "remove_collection",
    "rename_collection",
    "to_woff2",
    "write_fontconfig",
]
