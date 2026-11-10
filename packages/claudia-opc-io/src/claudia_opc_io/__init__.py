"""claudia-opc-io: generic Open Packaging Conventions mechanics shared by every format's io package (D217).

package     read_parts/write_parts -- a zip package as a plain dict of its parts, and back
reconcile   owns/reconcile -- restore whatever a format library's save() was not asked to touch

Deliberately knows nothing about any one format: no cell, no paragraph, no shape. openpyxl/python-docx/
python-pptx/odfdo (and claudia's own ``*_io`` packages built on them) stay exactly as they are; this sits below
all of them, patching their output back against the file they started from.
"""

from .package import read_parts, write_parts
from .reconcile import OwnedTest, owns, reconcile

__all__ = ["OwnedTest", "owns", "read_parts", "reconcile", "write_parts"]
