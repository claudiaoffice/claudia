"""State events the computes model raises through ``Context.emit`` (the kernel adds its own).

``ObjectsChanged``, ``ImagesChanged``, ``ShapesChanged`` and ``DiagramsChanged`` are the same events in all
three apps and live in :mod:`claudia_core.objects` (E10.16); they are re-exported here, where this module's
users have always imported them from. What is only a workbook's own is below — including ``ChartsChanged``,
since a chart *tab* is computes' own concept even though the diagram it shows is shared (E6.6).
"""

from __future__ import annotations

from dataclasses import dataclass

from claudia_core import DiagramsChanged, ImagesChanged, ObjectsChanged, ShapesChanged  # noqa: F401  (re-exported)

from .refs import Position, SheetId, StructuralEdit


@dataclass(frozen=True)
class CellsChanged:
    """Cells of one sheet changed. ``cells`` are their new contents (``None``: now empty), so a view needs no query."""

    sheet: SheetId
    positions: frozenset[Position]
    cells: tuple[tuple[int, int, dict | None], ...] = ()

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "cells",
            "sheet": self.sheet,
            "positions": sorted([r, c] for r, c in self.positions),
            "cells": [[r, c, content] for r, c, content in sorted(self.cells, key=lambda t: t[:2])],
        }


@dataclass(frozen=True)
class StructureChanged:
    edit: StructuralEdit

    def to_data(self) -> dict:
        e = self.edit
        return {"type": "structure", "sheet": e.sheet, "axis": e.axis, "insert": e.insert, "at": e.at, "count": e.count}


@dataclass(frozen=True)
class SheetsChanged:
    def to_data(self) -> dict:
        return {"type": "sheets"}


@dataclass(frozen=True)
class ChartsChanged:
    """The tab strip's charts changed (one was added or removed, or the tab order moved)."""

    def to_data(self) -> dict:
        """The event as it goes to the clients: only its type, since they read the new tab strip off the state."""
        return {"type": "charts"}


@dataclass(frozen=True)
class NamesChanged:
    """A name (a named range, a table or a query result) was defined, changed, renamed, grown or removed."""

    def to_data(self) -> dict:
        """The event as it goes to the clients: only its type, since they read the names off the state."""
        return {"type": "names"}


@dataclass(frozen=True)
class LinesResized:
    """Rows or columns of one sheet were given a size, or returned to the sheet's default (``size`` is ``None``)."""

    sheet: SheetId
    axis: str
    sizes: tuple[tuple[int, float | None], ...]

    def to_data(self) -> dict:
        return {"type": "sizes", "sheet": self.sheet, "axis": self.axis, "sizes": [[i, s] for i, s in self.sizes]}
