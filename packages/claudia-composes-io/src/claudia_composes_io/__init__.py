"""claudia-composes-io: docx import/export for the text app, outside the kernel (E9.5, D147, D217).

This is a first slice, not the ODF-first import/export story of E9.5 (D5, D70): a minimal base export
(``text_to_docx``) with tracked changes as an additive extension python-docx itself cannot write (D147), a real
import (``docx_to_text``), and an edit-and-reexport path (``apply_edits_to_docx``) that patches only what
changed onto the original bytes instead of rebuilding from the model alone, so content claudia never modeled
survives (D217). odfdo is not a dependency yet: nothing here is ODF, and D70 wants odt before docx when that
story is built.

docx   text_to_docx, docx_to_text, apply_edits_to_docx, UnsupportedEdit
"""

from ._version import __version__
from .docx import UnsupportedEdit, apply_edits_to_docx, docx_to_text, text_to_docx

__all__ = [
    "__version__",
    "UnsupportedEdit",
    "apply_edits_to_docx",
    "docx_to_text",
    "text_to_docx",
]
