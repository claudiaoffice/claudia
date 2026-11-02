"""State events the computes model raises through ``Context.emit`` (the kernel adds its own)."""

from __future__ import annotations

from dataclasses import dataclass

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
