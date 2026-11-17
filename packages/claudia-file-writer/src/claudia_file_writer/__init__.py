"""claudia-file-writer: how a Claudia server writes a file (CODE-34, D701).

A file is written next to its place and moved there in one step (:func:`write_atomically`, :func:`atomic_file`), so a
reader sees the old file or the new one, never a part of either. On Windows the move can be refused for a moment,
because antivirus scanning and indexing hold a file just written; :class:`Replacer` waits and tries again there. A file
named by what is in it, such as a cache entry named by a hash, is written once (:func:`write_once`).

Files that a lock pins by URL and SHA-256, such as the fonts every server has and the hyphenation patterns, are fetched
with :func:`fetch_pinned`, which refuses any other bytes.

The package uses the standard library only, so every package that writes files can depend on it. It is not part of
the kernel: ``claudia_core`` does no I/O at all (its purity test).

Modules:

    atomic   write_atomically, atomic_file, write_once, Replacer, fsync_directory
    pinned   PinnedFile, fetch_pinned, download, FetchError
"""

from ._version import __version__
from .atomic import Replacer, atomic_file, fsync_directory, write_atomically, write_once
from .pinned import FetchError, PinnedFile, download, fetch_pinned

__all__ = [
    "__version__",
    "FetchError",
    "PinnedFile",
    "Replacer",
    "atomic_file",
    "download",
    "fetch_pinned",
    "fsync_directory",
    "write_atomically",
    "write_once",
]
