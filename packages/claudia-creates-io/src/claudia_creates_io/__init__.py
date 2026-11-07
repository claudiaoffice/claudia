"""claudia-creates-io: pptx export for the presentation app, outside the kernel (E10.3, D147).

This is a first slice, not the ODF-first import/export story of E10.3 (D5, D70): a minimal base export
(``slides_to_pptx``) and one additive extension python-pptx itself cannot write, slide transitions
(``add_transition``), built by editing the slide part's own XML directly with ``lxml`` -- transitions live inline
in the slide, so nothing needs to be registered elsewhere, unlike the other two extensions (D147). odfdo is not a
dependency yet: nothing here is ODF, and D70 wants odp before pptx when that story is built.

pptx   slides_to_pptx, add_transition
"""

from .pptx import add_transition, slides_to_pptx

__all__ = [
    "add_transition",
    "slides_to_pptx",
]
