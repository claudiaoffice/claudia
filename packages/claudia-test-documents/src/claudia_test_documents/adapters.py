"""Per-format adapters: the two functions the runner needs from a format's own io package (D178).

A format with no ``apply_edits_fn`` yet (every format except docx, today) can still be catalogued for Tier 1
(import) checks; the runner reports the round-trip and preserve stages as ``"skipped"`` rather than failing a
format for a capability it does not have yet, so the catalogue grows with each format's own real import/export
work instead of waiting for all of them at once.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from claudia_composes_io import apply_edits_to_docx, docx_to_text

from .case import Model


@dataclass
class Adapter:
    """``import_fn`` turns a file's bytes into a model. ``apply_edits_fn`` (``original_bytes, baseline, current ->
    edited_bytes``) re-exports an edit by patching only what changed onto the original file -- the function the
    whole round-trip/preserve story depends on; ``None`` until a format has one."""

    import_fn: Callable[[bytes], Model]
    apply_edits_fn: Callable[[bytes, Model, Model], bytes] | None = None


#: One entry per format the catalogue can test. xlsx/pptx/odt/ods/odp are not here yet -- there is no adapter to
#: register until each gets its own real import and edit-and-reexport path, the same way docx just did (D177).
ADAPTERS: dict[str, Adapter] = {
    "docx": Adapter(import_fn=docx_to_text, apply_edits_fn=apply_edits_to_docx),
}
