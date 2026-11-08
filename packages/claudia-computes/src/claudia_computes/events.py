"""State events the computes model raises through ``Context.emit`` (the kernel adds its own)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .refs import Position, SheetId, StructuralEdit

if TYPE_CHECKING:
    from claudia_core import ImageAsset

    from .model import SheetObject


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
class LinesResized:
    """Rows or columns of one sheet were given a size, or returned to the sheet's default (``size`` is ``None``)."""

    sheet: SheetId
    axis: str
    sizes: tuple[tuple[int, float | None], ...]

    def to_data(self) -> dict:
        return {"type": "sizes", "sheet": self.sheet, "axis": self.axis, "sizes": [[i, s] for i, s in self.sizes]}


@dataclass(frozen=True)
class ObjectsChanged:
    """Objects of one sheet changed. ``changed`` are their new state (added or altered), ``removed`` their ids, and
    ``order`` is the stacking order of the whole sheet afterwards (bottom first), so a view needs no query."""

    sheet: SheetId
    changed: tuple[SheetObject, ...]
    removed: tuple[str, ...]
    order: tuple[str, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event. Carries every ``changed`` object's import record unmasked; a client
        that goes straight to this (rather than through ``to_data_for``) is trusted with the full record, as the
        log is."""
        return {
            "type": "objects",
            "sheet": self.sheet,
            "changed": [obj.to_data() for obj in self.changed],
            "removed": list(self.removed),
            "order": list(self.order),
        }

    def to_data_for(self, viewer: str) -> dict:
        """What ``viewer`` is sent: as :meth:`to_data`, with each changed image's import record masked for anyone
        but the person who imported it (``hub.py`` calls this per connection when an event offers it)."""
        return {**self.to_data(), "changed": [obj.to_data_for(viewer) for obj in self.changed]}


@dataclass(frozen=True)
class ImagesChanged:
    """The document learned an image (``asset`` is it) or forgot one (``asset`` is ``None``)."""

    image_id: str
    asset: ImageAsset | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "image",
            "id": self.image_id,
            "asset": None if self.asset is None else self.asset.to_data(),
        }
