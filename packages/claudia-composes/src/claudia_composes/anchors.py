"""BlockAnchor: where an object sits in a text (E10.16, D179).

A text has no fixed page the way a slide has a stage, and no cell grid the way a sheet has one. What it has is
paragraphs, so an object is anchored to one: ``block`` is the paragraph and ``offset`` the character in it the
object hangs from.

Two things this anchor deliberately does *not* do, both settled as decisions rather than left to chance:

* **It does not reflow the text.** An object floats over the paragraph; the words around it do not wrap beside it
  and are not pushed down by it. That is the first step only — text wrap is a layout feature of its own and is
  not in this round.
* **It floats at a free offset.** ``dx`` and ``dy`` say how far the object's top-left corner sits from the
  anchor character, in the document's units (down and to the right are positive). An object can therefore lie in a
  margin or beside a paragraph while the anchor still names the word it belongs to; the offset travels with the
  anchor through every edit and is never itself moved by one.
* **It does follow the text.** Unlike a sheet anchor, which is frozen on purpose (a picture must not leap across
  a sheet because somebody inserted a row), a character offset is meaningless once the text under it shifts: it
  would point at a different word. So an anchor moves through other people's edits exactly as a cursor, a zone
  and a suggestion already do in this app — by ``TextCommand.follow`` (``claudia_composes.spans``). This is
  the clearest example of why an anchor is the per-app part of an object: the same picture wants frozen
  coordinates on a sheet and following ones in a paragraph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, TypeIs

from .spans import Span

#: How far an object may float from its anchor character, in either direction and on either axis. A page is a few
#: thousand units wide; this keeps an object near its words and a hostile client from sending a number that overflows
#: a renderer.
MAX_ANCHOR_OFFSET = 10_000


def _is_whole(value: object) -> TypeIs[int]:
    """``True`` for a plain ``int`` (not a ``bool``), narrowing the type for the caller."""
    return type(value) is int


@dataclass(frozen=True)
class BlockAnchor:
    """Where an object hangs in a text: character ``offset`` of the paragraph ``block``, and where its top-left
    corner floats relative to that character: ``dx`` to the right and ``dy`` down (negative: left and up)."""

    kind: ClassVar[str] = "block"
    block: str
    offset: int = 0
    dx: int = 0
    dy: int = 0

    @property
    def container(self) -> str:
        """The paragraph this object belongs to."""
        return self.block

    @property
    def span(self) -> Span:
        """The anchor as an empty ``(block, start, end)`` span, so that it can follow a text command."""
        return (self.block, self.offset, self.offset)

    def followed(self, span: Span) -> BlockAnchor:
        """The anchor at the place ``span`` (the output of ``TextCommand.follow`` on :attr:`span`) now names."""
        block, start, _ = span
        return BlockAnchor(block, start, self.dx, self.dy)

    def carried_to(self, block: str, shift: int) -> BlockAnchor:
        """The anchor ``shift`` characters further along, in the paragraph ``block`` (a join carries its objects)."""
        return BlockAnchor(block, self.offset + shift, self.dx, self.dy)

    def floated_to(self, dx: int, dy: int) -> BlockAnchor:
        """The same anchor character with the object floating at another offset."""
        return BlockAnchor(self.block, self.offset, dx, dy)

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {"kind": self.kind, "container": self.block, "offset": self.offset, "dx": self.dx, "dy": self.dy}

    @classmethod
    def from_data(cls, data: dict) -> BlockAnchor:
        """Read an anchor sent by a client or stored in the log; ``ValueError`` if it is not one. An anchor written
        before objects could float has no ``dx`` and ``dy`` and reads as sitting on its character."""
        if data.get("kind") != cls.kind:
            raise ValueError(f"composes knows only block anchors, not {data.get('kind')!r}")
        block, offset = data.get("container"), data.get("offset")
        if not isinstance(block, str) or not _is_whole(offset):
            raise ValueError("a block anchor names a paragraph and a whole offset")
        anchor = cls(block, offset, data.get("dx", 0), data.get("dy", 0))
        anchor.check_floating()
        return anchor

    def check_floating(self) -> None:
        """``ValueError`` with a sentence unless ``dx`` and ``dy`` are whole numbers within reach of the anchor."""
        for name, value in (("dx", self.dx), ("dy", self.dy)):
            if not _is_whole(value) or abs(value) > MAX_ANCHOR_OFFSET:
                raise ValueError(
                    f"the offset {name} of an object from its anchor is a whole number of at most "
                    f"{MAX_ANCHOR_OFFSET} units either way"
                )
