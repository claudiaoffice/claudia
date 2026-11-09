"""BlockAnchor: where an object sits in a text (E10.16, D179).

A text has no fixed page the way a slide has a stage, and no cell grid the way a sheet has one. What it has is
paragraphs, so an object is anchored to one: ``block`` is the paragraph and ``offset`` the character in it the
object hangs from.

Two things this anchor deliberately does *not* do, both settled as decisions rather than left to chance:

* **It does not reflow the text.** An object floats over the paragraph; the words around it do not wrap beside it
  and are not pushed down by it. That is the first step only — text wrap is a layout feature of its own and is
  not in this round.
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


def _is_whole(value: object) -> TypeIs[int]:
    """``True`` for a plain ``int`` (not a ``bool``), narrowing the type for the caller."""
    return type(value) is int


@dataclass(frozen=True)
class BlockAnchor:
    """Where an object hangs in a text: character ``offset`` of the paragraph ``block``."""

    kind: ClassVar[str] = "block"
    block: str
    offset: int = 0

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
        return BlockAnchor(block, start)

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {"kind": self.kind, "container": self.block, "offset": self.offset}

    @classmethod
    def from_data(cls, data: dict) -> BlockAnchor:
        """Read an anchor sent by a client or stored in the log; ``ValueError`` if it is not one."""
        if data.get("kind") != cls.kind:
            raise ValueError(f"composes knows only block anchors, not {data.get('kind')!r}")
        block, offset = data.get("container"), data.get("offset")
        if not isinstance(block, str) or not _is_whole(offset):
            raise ValueError("a block anchor names a paragraph and a whole offset")
        return cls(block, offset)
