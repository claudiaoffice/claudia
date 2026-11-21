"""ParagraphAnchor: where an object sits in a text (E10.16, D179).

A text has no fixed page the way a slide has a stage, and no cell grid the way a sheet has one. What it has is
paragraphs, so an object is anchored to one: ``paragraph`` is the paragraph and ``offset`` the character in it the
object hangs from.

Things this anchor settles as decisions rather than leaving to chance:

* **How the text flows round it is part of where it hangs** (D1061): ``wrap`` is *over* the text (the words do not
  give way, and a document that never set a wrap reads this way), *around* it, *above and below* it, or *behind* the
  text, and ``gap`` is how far the words keep from it. The model only keeps the choice; the layout makes the words
  give way. A new object starts *above and below*, but that is the caller's choice (``claudia_server``), not the
  anchor's: an anchor read from a log that says nothing is *over* the text.
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

from dataclasses import dataclass, replace
from typing import ClassVar, TypeIs

from .spans import Span

#: How the text flows round an object, in the order the one key (Format ▸ Wrap Text) steps through them (D1064).
WRAPS = ("over", "around", "above-below", "behind")

#: How far the words keep from an object that is not over the text, in the document's units, when nothing says.
DEFAULT_WRAP_GAP = 8

#: The most the words may keep from an object, in the document's units.
MAX_WRAP_GAP = 200

#: How far an object may float from its anchor character, in either direction and on either axis. A page is a few
#: thousand units wide; this keeps an object near its words and a hostile client from sending a number that overflows
#: a renderer.
MAX_ANCHOR_OFFSET = 10_000


def _is_whole(value: object) -> TypeIs[int]:
    """``True`` for a plain ``int`` (not a ``bool``), narrowing the type for the caller."""
    return type(value) is int


@dataclass(frozen=True)
class ParagraphAnchor:
    """Where an object hangs in a text: character ``offset`` of the paragraph ``paragraph``, and where its top-left
    corner floats relative to that character: ``dx`` to the right and ``dy`` down (negative: left and up). ``wrap``
    is how the text flows round it (one of :data:`~claudia_composes.anchors.WRAPS`) and ``gap`` how far it keeps from
    it."""

    kind: ClassVar[str] = "paragraph"
    paragraph: str
    offset: int = 0
    dx: int = 0
    dy: int = 0
    wrap: str = "over"
    gap: int = DEFAULT_WRAP_GAP

    @property
    def holder(self) -> str:
        """The paragraph this object belongs to."""
        return self.paragraph

    @property
    def span(self) -> Span:
        """The anchor as an empty ``(paragraph, start, end)`` span, so that it can follow a text command."""
        return (self.paragraph, self.offset, self.offset)

    def followed(self, span: Span) -> ParagraphAnchor:
        """The anchor at the place ``span`` (the output of ``TextCommand.follow`` on :attr:`span`) now names."""
        paragraph, start, _ = span
        return replace(self, paragraph=paragraph, offset=start)

    def carried_to(self, paragraph: str, shift: int) -> ParagraphAnchor:
        """The anchor ``shift`` characters further along, in the paragraph ``paragraph`` (a join carries its
        objects)."""
        return replace(self, paragraph=paragraph, offset=self.offset + shift)

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        data = {"kind": self.kind, "holder": self.paragraph, "offset": self.offset, "dx": self.dx, "dy": self.dy}
        if self.wrap != "over":  # an anchor that does nothing special stays as it was written before wrapping existed
            data["wrap"] = self.wrap
        if self.gap != DEFAULT_WRAP_GAP:
            data["gap"] = self.gap
        return data

    @classmethod
    def from_data(cls, data: dict) -> ParagraphAnchor:
        """Read an anchor sent by a client or stored in the log; ``ValueError`` if it is not one. An anchor written
        before objects could float has no ``dx`` and ``dy`` and reads as sitting on its character."""
        if data.get("kind") != cls.kind:
            raise ValueError(f"composes knows only paragraph anchors, not {data.get('kind')!r}")
        paragraph, offset = data.get("holder"), data.get("offset")
        if not isinstance(paragraph, str) or not _is_whole(offset):
            raise ValueError("a paragraph anchor names a paragraph and a whole offset")
        anchor = cls(
            paragraph,
            offset,
            data.get("dx", 0),
            data.get("dy", 0),
            data.get("wrap", "over"),
            data.get("gap", DEFAULT_WRAP_GAP),
        )
        anchor.check_floating()
        anchor.check_wrap()
        return anchor

    def check_floating(self) -> None:
        """``ValueError`` with a sentence unless ``dx`` and ``dy`` are whole numbers within reach of the anchor."""
        for name, value in (("dx", self.dx), ("dy", self.dy)):
            if not _is_whole(value) or abs(value) > MAX_ANCHOR_OFFSET:
                raise ValueError(
                    f"the offset {name} of an object from its anchor is a whole number of at most "
                    f"{MAX_ANCHOR_OFFSET} units either way"
                )

    def check_wrap(self) -> None:
        """``ValueError`` with a sentence unless ``wrap`` is one of :data:`~claudia_composes.anchors.WRAPS` and ``gap``
        a whole number from 0 to :data:`~claudia_composes.anchors.MAX_WRAP_GAP`."""
        if self.wrap not in WRAPS:
            raise ValueError(f"the wrap of an object is one of {', '.join(WRAPS)}, not {self.wrap!r}")
        if not _is_whole(self.gap) or not 0 <= self.gap <= MAX_WRAP_GAP:
            raise ValueError(f"the gap between an object and the text is a whole number from 0 to {MAX_WRAP_GAP} units")
