"""CellRegion: a rectangle of cells that moves with the edits (the generalised ``refs.py``, E1.5).

ObjectSet: the other Region of this app (E10.11): some floating objects on one sheet, selected, held or being
worked on — mirrors creates' own ObjectSet, one per app since each app's objects (and so its regions) differ."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from claudia_core import Command

from .refs import RangeRef, SheetId

MAX_SELECTION = 64  # objects in one selection that arrives from a client


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


@dataclass(frozen=True)
class ObjectSet:
    """Some floating objects on one sheet (a selection, an area the AI is working on). It is also what a lock
    holds, same as creates' own ObjectSet."""

    kind: ClassVar[str] = "objects"
    sheet: SheetId
    ids: frozenset[str] = field(default_factory=frozenset)

    def overlaps(self, other) -> bool:
        """Do the two selections share an object of the same sheet?"""
        return isinstance(other, ObjectSet) and self.sheet == other.sheet and bool(self.ids & other.ids)

    def transformed(self, command: Command) -> ObjectSet | None:
        """The selection after a command: it loses an object that was removed, and is gone when none is left."""
        from .commands import RemoveObject

        if isinstance(command, RemoveObject) and command.id in self.ids:
            rest = self.ids - {command.id}
            return ObjectSet(self.sheet, rest) if rest else None
        return self

    def to_data(self) -> dict:
        """The plain-data form for the wire (regions are never stored in the log)."""
        return {"kind": self.kind, "sheet": self.sheet, "ids": sorted(self.ids)}

    @classmethod
    def from_data(cls, data: dict) -> ObjectSet:
        """Read a selection sent by a client; ``ValueError`` if it is not one."""
        sheet, ids = data.get("sheet"), data.get("ids")
        if not isinstance(sheet, str) or not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise ValueError("not a selection: it names a sheet and a list of object ids")
        if len(ids) > MAX_SELECTION:
            raise ValueError(f"a selection holds at most {MAX_SELECTION} objects")
        return cls(SheetId(sheet), frozenset(ids))
