"""CellRegion: a rectangle of cells that moves with the edits (the generalised ``refs.py``, E1.5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from claudia_core import Command

from .refs import RangeRef, SheetId


@dataclass(frozen=True)
class CellRegion:
    kind: ClassVar[str] = "cells"
    range: RangeRef  # always with a sheet

    @classmethod
    def of(cls, sheet: SheetId, first_row: int, first_col: int, last_row: int, last_col: int) -> CellRegion:
        from .refs import CellRef

        return cls(RangeRef(CellRef(first_row, first_col, sheet), CellRef(last_row, last_col, sheet)))

    @property
    def sheet(self) -> SheetId:
        assert self.range.sheet is not None
        return self.range.sheet

    def overlaps(self, other) -> bool:
        return isinstance(other, CellRegion) and self.sheet == other.sheet and self.range.intersects(other.range)

    def transformed(self, command: Command) -> CellRegion | None:
        from .commands import RemoveSheet, Structure

        if isinstance(command, Structure):
            moved = self.range.adjusted(command.edit, self.sheet)
            return None if moved is None else CellRegion(moved)
        if isinstance(command, RemoveSheet) and command.id == self.sheet:
            return None
        return self

    def to_data(self) -> dict:
        return {"kind": self.kind, "range": self.range.to_dict()}

    @classmethod
    def from_data(cls, data: dict) -> CellRegion:
        return cls(RangeRef.from_dict(data["range"]))
