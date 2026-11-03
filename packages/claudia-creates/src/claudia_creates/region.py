"""ObjectSet: the Region of creates (D17): some objects on one slide, selected, held or being worked on."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from claudia_core import Command, Region

MAX_SELECTION = 64  # objects in one selection that arrives from a client


@dataclass(frozen=True)
class ObjectSet:
    """Some objects on one slide (a selection, an area the AI is working on). It is also what a lock holds (D67)."""

    kind: ClassVar[str] = "objects"
    slide: str
    ids: frozenset[str] = field(default_factory=frozenset)

    def overlaps(self, other: Region) -> bool:
        """Do the two selections share an object of the same slide?"""
        return isinstance(other, ObjectSet) and self.slide == other.slide and bool(self.ids & other.ids)

    def transformed(self, command: Command) -> ObjectSet | None:
        """The selection after a command: it loses an object that was removed, and is gone when none is left."""
        from .commands import RemoveObject

        if isinstance(command, RemoveObject) and command.id in self.ids:
            rest = self.ids - {command.id}
            return ObjectSet(self.slide, rest) if rest else None
        return self

    def to_data(self) -> dict:
        """The plain-data form for the wire (regions are never stored in the log)."""
        return {"kind": self.kind, "slide": self.slide, "ids": sorted(self.ids)}

    @classmethod
    def from_data(cls, data: dict) -> ObjectSet:
        """Read a selection sent by a client; ``ValueError`` if it is not one."""
        slide, ids = data.get("slide"), data.get("ids")
        if not isinstance(slide, str) or not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise ValueError("not a selection: it names a slide and a list of object ids")
        if len(ids) > MAX_SELECTION:
            raise ValueError(f"a selection holds at most {MAX_SELECTION} objects")
        return cls(slide, frozenset(ids))
