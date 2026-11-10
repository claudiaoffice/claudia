"""Runs: who wrote which stretch of a paragraph (E9.3).

Since E10.17 (D181) this is ``claudia_core.paragraphs``: a paragraph stopped being a composes idea when a
creates text box and the label inside a shape on a sheet started carrying the same one, so the entity and its
arithmetic moved into the kernel. Everything is re-exported here, where this app has always imported it from,
and there is exactly one ``Run`` type in the suite — two would have meant a run crossing from an object into a
document was a different kind of thing on each side.
"""

from __future__ import annotations

from claudia_core.paragraphs import (
    Run,
    delete_runs,
    insert_runs,
    normalized,
    runs_from_data,
    runs_to_data,
    slice_runs,
    total,
)

__all__ = [
    "Run",
    "delete_runs",
    "insert_runs",
    "normalized",
    "runs_from_data",
    "runs_to_data",
    "slice_runs",
    "total",
]
