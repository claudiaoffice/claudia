"""claudia-creates-io: pptx and odp import/export for the presentation app, outside the kernel (E10.3, D219, D412).

pptx is a first slice, not the ODF-first story of E10.3 (D5, D70): a minimal base export (``slides_to_pptx``), a real
import/edit/export round trip (``pptx_to_slides``, ``apply_edits_to_pptx``, D219, following docx's D217), and one
additive extension python-pptx itself cannot write, slide transitions (``add_transition``), built by editing the slide
part's own XML directly with ``lxml`` -- transitions live inline in the slide, so nothing needs to be registered
elsewhere, unlike the other two extensions (D147). odp is the same three paths on the shared OpenDocument layer
(``claudia-odf-io``, D401): see ``odp.py``.

pptx   slides_to_pptx, pptx_to_slides, apply_edits_to_pptx, UnsupportedEdit, add_transition
odp    slides_to_odp, odp_to_slides, apply_edits_to_odp, odp_import_losses, odp_export_losses (D412)
"""

from ._raster import Rasterise
from ._version import __version__
from .odp import apply_edits_to_odp, odp_export_losses, odp_import_losses, odp_to_slides, slides_to_odp
from .pptx import (
    UnsupportedEdit,
    add_transition,
    apply_edits_to_pptx,
    pptx_export_losses,
    pptx_to_slides,
    slides_to_pptx,
)

__all__ = [
    "Rasterise",
    "__version__",
    "UnsupportedEdit",
    "add_transition",
    "apply_edits_to_odp",
    "apply_edits_to_pptx",
    "odp_export_losses",
    "odp_import_losses",
    "odp_to_slides",
    "pptx_export_losses",
    "pptx_to_slides",
    "slides_to_odp",
    "slides_to_pptx",
]
