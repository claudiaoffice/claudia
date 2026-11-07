"""claudia-composes-io: docx export for the text app, outside the kernel (E9.5, D135).

This is a first slice, not the ODF-first import/export story of E9.5 (D5, D70): a minimal base export
(``text_to_docx``) and one additive extension python-docx itself cannot write, tracked changes, built with
``docx.oxml.OxmlElement`` -- python-docx's own documented way to reach markup it does not model (D135). odfdo is
not a dependency yet: nothing here is ODF, and D70 wants odt before docx when that story is built.

docx   text_to_docx
"""

from .docx import text_to_docx

__all__ = [
    "text_to_docx",
]
