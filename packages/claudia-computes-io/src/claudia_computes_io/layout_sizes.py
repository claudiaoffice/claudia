"""What the xlsx and ods converters share of the widths of columns and heights of rows (D458).

The model counts both in pixels (``Sheet.col_widths``, ``Sheet.row_heights``; a line that is not listed shows at the
default). A file counts them in its own units (:mod:`.xlsx_layout`, :mod:`.ods_layout`); what comes in is kept within
the sizes the model allows, and only the lines the model can show are read: the first ``MAX_SIZED_COLUMNS`` columns
and ``MAX_SIZED_ROWS`` rows. A file gives *every* column a width (LibreOffice writes one for a thousand columns past
the last used one), and nobody sees a width out there.
"""

from __future__ import annotations

from collections.abc import Mapping

from claudia_computes.model import MAX_COL_WIDTH, MAX_ROW_HEIGHT, MIN_COL_WIDTH, MIN_ROW_HEIGHT

MAX_SIZED_COLUMNS = 256
MAX_SIZED_ROWS = 10_000


def fit_width(pixels: float) -> int:
    """A column width in whole pixels, kept within what the model allows."""
    return int(min(MAX_COL_WIDTH, max(MIN_COL_WIDTH, round(pixels))))


def fit_height(pixels: float) -> int:
    """A row height in whole pixels, kept within what the model allows."""
    return int(min(MAX_ROW_HEIGHT, max(MIN_ROW_HEIGHT, round(pixels))))


def changed_sizes(before: Mapping[int, float], after: Mapping[int, float]) -> dict[int, float | None]:
    """The lines whose size is not what it was, with the new size (``None``: the line was given up)."""
    lines = sorted(before.keys() | after.keys())
    return {line: after.get(line) for line in lines if before.get(line) != after.get(line)}
