"""Cell styles: a sheet's style ranges, in layers, for the two slots every cell has (E6.13, D304, D307, D311).

A cell has a **box** slot (background, borders, padding, vertical alignment, wrapping) and a **words** slot (font,
colour, alignment, line height). Neither is stored per cell: a sheet keeps *style ranges* — a rectangle and the id
of a style — so a whole column or a million cells cost one entry, and the grid can paint a range without an element
per cell.

Ranges live in four **layers**, and a range's layer follows from its shape (:func:`claudia_computes.layer_of`):

* ``sheet``  — every cell of the sheet (its default);
* ``column`` — whole columns;
* ``row``    — whole rows;
* ``range``  — anything else, a single cell included.

A cell's style in a slot is the one of its most specific layer that has a range covering it: range, then row, then
column, then sheet, then the sheet's built-in default (``DEFAULT_CELL_STYLE``). That order is fixed (D307), so
there is no "which came later" to reason about. *Inside* a layer ranges never overlap: putting a range in subtracts
it from whatever the layer had there, which leaves at most four pieces of each range it cut.

Rows and columns move the ranges (D135's lesson for sizes, applied to styles):
:meth:`claudia_computes.CellStyles.restructure` maps every range with the edit's own
:meth:`~claudia_computes.refs.StructuralEdit.map_span` — inserting inside a range grows it, deleting shrinks it —
and returns the pieces that lay on deleted lines, which is what an undo needs to put back exactly. A range that
spans the whole edited axis (a column style under a row edit) stays whole.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from .limits import MAX_COLS, MAX_ROWS
from .refs import StructuralEdit

#: The style a cell has in a slot when no range of the sheet says otherwise (D313).
DEFAULT_CELL_STYLE = "body-text"
#: The two slots of a cell (D304, D311).
CELL_SLOTS: tuple[str, ...] = ("box", "words")
#: The layers, from the least to the most specific (D307).
LAYERS: tuple[str, ...] = ("sheet", "column", "row", "range")
#: How many ranges one sheet may hold, all slots and layers together.
MAX_STYLE_RANGES = 20_000

Area = tuple[int, int, int, int]  # r0, c0, r1, c1, both ends included
Piece = tuple[Area, str]  # an area and the id of a style


def layer_of(area: Area) -> str:
    """The layer a range of this shape belongs to: whole sheet, whole columns, whole rows, or a range."""
    r0, c0, r1, c1 = area
    rows = r0 == 0 and r1 == MAX_ROWS - 1
    cols = c0 == 0 and c1 == MAX_COLS - 1
    if rows and cols:
        return "sheet"
    if rows:
        return "column"
    if cols:
        return "row"
    return "range"


def check_area(area: object) -> Area:
    """``area`` as a clean ``(r0, c0, r1, c1)``; ``ValueError`` unless it is four whole numbers inside the sheet,
    first corner first."""
    if not isinstance(area, list | tuple) or len(area) != 4 or not all(type(n) is int for n in area):
        raise ValueError("an area is four whole numbers: r0, c0, r1, c1")
    r0, c0, r1, c1 = area
    if not (0 <= r0 <= r1 < MAX_ROWS and 0 <= c0 <= c1 < MAX_COLS):
        raise ValueError(f"the area {list(area)} is not inside the sheet, first corner first")
    return (r0, c0, r1, c1)


def overlap(a: Area, b: Area) -> Area | None:
    """Where two areas meet; ``None`` if they do not."""
    r0, c0 = max(a[0], b[0]), max(a[1], b[1])
    r1, c1 = min(a[2], b[2]), min(a[3], b[3])
    return (r0, c0, r1, c1) if r0 <= r1 and c0 <= c1 else None


def subtract(a: Area, cut: Area) -> list[Area]:
    """``a`` without ``cut``: at most four areas — above, below, left and right of the cut."""
    met = overlap(a, cut)
    if met is None:
        return [a]
    r0, c0, r1, c1 = a
    m0, n0, m1, n1 = met
    out: list[Area] = []
    if r0 < m0:
        out.append((r0, c0, m0 - 1, c1))
    if m1 < r1:
        out.append((m1 + 1, c0, r1, c1))
    if c0 < n0:
        out.append((m0, c0, m1, n0 - 1))
    if n1 < c1:
        out.append((m0, n1 + 1, m1, c1))
    return out


def _contains(outer: Area, inner: Area) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and inner[2] <= outer[2] and inner[3] <= outer[3]


class CellStyles:
    """The style ranges of one sheet, by slot and layer (see the module description)."""

    def __init__(self) -> None:
        self._ranges: dict[tuple[str, str], list[Piece]] = {(s, layer): [] for s in CELL_SLOTS for layer in LAYERS}

    # -- reading -----------------------------------------------------------------
    def __len__(self) -> int:
        return sum(len(pieces) for pieces in self._ranges.values())

    def pieces(self, slot: str, layer: str, area: Area) -> tuple[Piece, ...]:
        """What the layer holds inside ``area``: each range that meets it, cut to it."""
        found = []
        for where, style in self._ranges[(slot, layer)]:
            met = overlap(where, area)
            if met is not None:
                found.append((met, style))
        return tuple(sorted(found))

    def style_at(self, row: int, col: int, slot: str) -> tuple[str, str]:
        """The style a cell has in ``slot`` and the layer it comes from (``"default"`` when no range covers it)."""
        for layer in reversed(LAYERS):
            for (r0, c0, r1, c1), style in self._ranges[(slot, layer)]:
                if r0 <= row <= r1 and c0 <= col <= c1:
                    return style, layer
        return DEFAULT_CELL_STYLE, "default"

    def ranges_in(self, window: Area) -> list[dict]:
        """Every range that meets ``window``, cut to it, as plain data ``{slot, layer, area, style}`` — what a
        client paints from, least specific layer first so that a later one paints over it."""
        out = []
        for layer in LAYERS:
            for slot in CELL_SLOTS:
                for area, style in self.pieces(slot, layer, window):
                    out.append({"slot": slot, "layer": layer, "area": list(area), "style": style})
        return out

    def uses(self) -> Counter[str]:
        """How many ranges name each style, one count per range and slot (a whole column counts once)."""
        return Counter(style for pieces in self._ranges.values() for _, style in pieces)

    def names(self, style_id: str) -> bool:
        """Does any range name this style?"""
        return any(style == style_id for pieces in self._ranges.values() for _, style in pieces)

    # -- changing ----------------------------------------------------------------
    def replace(self, slot: str, layer: str, area: Area, pieces: Iterable[Piece]) -> None:
        """Make ``area`` of the layer hold exactly ``pieces``: what was there goes, each piece comes in. Every piece
        must lie inside ``area`` and be of the layer's shape. ``ValueError`` (and nothing changed) otherwise, or if
        the sheet would hold more than ``MAX_STYLE_RANGES`` ranges."""
        if slot not in CELL_SLOTS:
            raise ValueError(f"a cell has no slot “{slot}”; it has {', '.join(CELL_SLOTS)}")
        if layer not in LAYERS or layer_of(area) != layer:
            raise ValueError(f"the area {list(area)} is not of the layer {layer!r}")
        given = list(pieces)
        for where, _ in given:
            if not _contains(area, where) or layer_of(where) != layer:
                raise ValueError(f"a piece {list(where)} lies outside {list(area)} or is not of the layer {layer!r}")
        ordered = sorted(area for area, _ in given)
        for i, a in enumerate(ordered):  # sorted by first row: only the pieces that start before this one ends
            for b in ordered[i + 1 :]:
                if b[0] > a[2]:
                    break
                if overlap(a, b):
                    raise ValueError("the pieces of one change may not overlap")
        kept: list[Piece] = []
        for where, style in self._ranges[(slot, layer)]:
            kept.extend((rest, style) for rest in subtract(where, area))
        kept.extend(given)
        if len(self) - len(self._ranges[(slot, layer)]) + len(kept) > MAX_STYLE_RANGES:
            raise ValueError(f"a sheet holds at most {MAX_STYLE_RANGES} style ranges")
        self._ranges[(slot, layer)] = kept

    def restructure(self, edit: StructuralEdit) -> list[tuple[str, str, Piece]]:
        """Move the ranges with an insert or a delete of rows or columns. Returns, for a delete, the pieces that lay
        on the deleted lines (``(slot, layer, piece)``) — an undo puts them back after inserting the lines again."""
        index = 0 if edit.axis == "row" else 1
        limit = MAX_ROWS if edit.axis == "row" else MAX_COLS
        band: Area = (
            (edit.at, 0, edit.at + edit.count - 1, MAX_COLS - 1)
            if index == 0
            else (0, edit.at, MAX_ROWS - 1, edit.at + edit.count - 1)
        )
        cut: list[tuple[str, str, Piece]] = []
        for (slot, layer), ranges in self._ranges.items():
            moved: list[Piece] = []
            for area, style in ranges:
                first, last = area[index], area[index + 2]
                if first == 0 and last == limit - 1:  # spans the whole edited axis: stays whole
                    moved.append((area, style))
                    continue
                if not edit.insert and (met := overlap(area, band)) is not None:
                    cut.append((slot, layer, (met, style)))
                span = edit.map_span(first, last)
                if span is None or span[0] >= limit:
                    continue
                lo, hi = span[0], min(span[1], limit - 1)
                new = (lo, area[1], hi, area[3]) if index == 0 else (area[0], lo, area[2], hi)
                moved.append((new, style))
            self._ranges[(slot, layer)] = moved
        return cut

    # -- plain data --------------------------------------------------------------
    def to_data(self) -> list[list]:
        """Every range as ``[slot, layer, r0, c0, r1, c1, style]``, in a fixed order."""
        return sorted(
            [slot, layer, *area, style] for (slot, layer), pieces in self._ranges.items() for area, style in pieces
        )

    @classmethod
    def from_data(cls, data: Iterable[list]) -> CellStyles:
        """Inverse of :meth:`to_data`."""
        made = cls()
        for slot, layer, r0, c0, r1, c1, style in data:
            made._ranges[(slot, layer)].append(((r0, c0, r1, c1), style))
        return made
