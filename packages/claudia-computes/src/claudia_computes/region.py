"""CellRegion: a rectangle of cells that moves with the edits (the generalised ``refs.py``, E1.5).

The other Region of this app is ``claudia_core.ObjectSet`` — some floating objects of one sheet, selected, held
or being worked on. It is the same region in all three apps now (E10.16), so it is not repeated here; it is
re-exported below, where this module's users have always imported it from."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from claudia_core import Command, ObjectSet  # noqa: F401  (re-exported)

from .refs import RangeRef, SheetId


@dataclass(frozen=True)
class CellRegion:
    """A rectangle of cells on one sheet, that moves with row and column edits: selected, held or being worked on."""

    kind: ClassVar[str] = "cells"
    range: RangeRef  # always with a sheet

    @classmethod
    def of(cls, sheet: SheetId, first_row: int, first_col: int, last_row: int, last_col: int) -> CellRegion:
        """The region from ``(first_row, first_col)`` to ``(last_row, last_col)`` on ``sheet``, all 0-based."""
        from .refs import CellRef

        return cls(RangeRef(CellRef(first_row, first_col, sheet), CellRef(last_row, last_col, sheet)))

    @property
    def sheet(self) -> SheetId:
        """The sheet the region is on."""
        assert self.range.sheet is not None
        return self.range.sheet

    def overlaps(self, other) -> bool:
        """Whether ``other`` is a cell region on the same sheet sharing at least one cell with this one."""
        return isinstance(other, CellRegion) and self.sheet == other.sheet and self.range.intersects(other.range)

    def transformed(self, command: Command) -> CellRegion | None:
        """Where the region is after ``command``: moved by a row or column edit, ``None`` once its cells are gone."""
        from .commands import RemoveSheet, Structure

        if isinstance(command, Structure):
            moved = self.range.adjusted(command.edit, self.sheet)
            return None if moved is None else CellRegion(moved)
        if isinstance(command, RemoveSheet) and command.id == self.sheet:
            return None
        return self

    def to_data(self) -> dict:
        """The region as plain data (its kind and range)."""
        return {"kind": self.kind, "range": self.range.to_dict()}

    @classmethod
    def from_data(cls, data: dict) -> CellRegion:
        """Read a region back from :meth:`to_data`'s plain data."""
        return cls(RangeRef.from_dict(data["range"]))
