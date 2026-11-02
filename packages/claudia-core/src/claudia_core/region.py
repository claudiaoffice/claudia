"""Region: the one abstraction behind presence, locks and AI edits (D17, E1.5).

A region is "the part of the document somebody is looking at, holding or changing": a cell range in
computes, a window of words around a cursor in composes, a set of objects on a slide in creates.
The kernel only needs three things from it, and everything else (presence, locks, undo refusal, the AI's
working area) is written once against this interface:

* ``overlaps``     do two regions of the same app touch each other?
* ``transformed``  where is this region after a command ran? ``None`` means it is gone. This is how a
                   region "moves with the edits" (the generalisation of ``refs.py`` in the demo).
* ``to_data``      a plain-data form for the wire (regions are never stored in the log).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .commands import Command


@runtime_checkable
class Region(Protocol):
    """A part of a document that somebody looks at, holds or changes (see the module description)."""

    kind: ClassVar[str]

    def overlaps(self, other: Region) -> bool:
        """Do the two regions touch each other? Regions of different kinds never do."""

    def transformed(self, command: Command) -> Region | None:
        """The region after one *leaf* command (never a Batch; see ``transform``)."""
        ...

    def to_data(self) -> dict:
        """The plain-data form for the wire (regions are never stored in the log)."""


def transform(region: Region, command: Command) -> Region | None:
    """Move ``region`` through ``command`` (a Batch is applied leaf by leaf, in order)."""
    for leaf in command.leaves():
        region = region.transformed(leaf)  # type: ignore[assignment]
        if region is None:
            return None
    return region
