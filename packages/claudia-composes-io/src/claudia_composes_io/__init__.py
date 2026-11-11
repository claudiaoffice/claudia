"""claudia-composes-io: docx and odt import/export for the text app, outside the kernel (E9.5, D147, D217, D401).

Docx first, as a first slice: a minimal base export (``text_to_docx``) with tracked changes as an additive
extension python-docx itself cannot write (D147), a real import (``docx_to_text``), and an edit-and-reexport path
(``apply_edits_to_docx``) that patches only what changed onto the original bytes instead of rebuilding from the
model alone, so content claudia never modeled survives (D217).

Odt is the ODF-first story of E9.5 (D5, D70), with maximum preservation from the start (D401): the same three
paths (``text_to_odt``, ``odt_to_text``, ``apply_edits_to_odt``) over ``claudia-odf-io``, with a list of what a
file could not hold in each direction (``odt_export_losses``, ``odt_import_losses``).

docx   text_to_docx, docx_to_text, apply_edits_to_docx, UnsupportedEdit
odt    text_to_odt, odt_to_text, apply_edits_to_odt, odt_import_losses, odt_export_losses (D401)
"""

from ._version import __version__
from .docx import UnsupportedEdit, apply_edits_to_docx, docx_to_text, text_to_docx
from .odt import apply_edits_to_odt, odt_export_losses, odt_import_losses, odt_to_text, text_to_odt

__all__ = [
    "__version__",
    "UnsupportedEdit",
    "apply_edits_to_docx",
    "apply_edits_to_odt",
    "docx_to_text",
    "odt_export_losses",
    "odt_import_losses",
    "odt_to_text",
    "text_to_docx",
    "text_to_odt",
]
