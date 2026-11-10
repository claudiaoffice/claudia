"""claudia-creates-io: pptx import/export for the presentation app, outside the kernel (E10.3, D147, D219).

This is a first slice, not the ODF-first import/export story of E10.3 (D5, D70): a minimal base export
(``slides_to_pptx``), a real import/edit/export round trip (``pptx_to_slides``, ``apply_edits_to_pptx``, D219,
following docx's D217), and one additive extension python-pptx itself cannot write, slide transitions
(``add_transition``), built by editing the slide part's own XML directly with ``lxml`` -- transitions live inline
in the slide, so nothing needs to be registered elsewhere, unlike the other two extensions (D147). odfdo is not a
dependency yet: nothing here is ODF, and D70 wants odp before pptx when that story is built.

pptx   slides_to_pptx, pptx_to_slides, apply_edits_to_pptx, UnsupportedEdit, add_transition
"""

from ._version import __version__
from .pptx import UnsupportedEdit, add_transition, apply_edits_to_pptx, pptx_to_slides, slides_to_pptx

__all__ = [
    "__version__",
    "UnsupportedEdit",
    "add_transition",
    "apply_edits_to_pptx",
    "pptx_to_slides",
    "slides_to_pptx",
]
