"""claudia-composes: a stub. Paragraphs of text with insert/delete, and the ± n words Region of D11.

Just enough to show that the kernel's Region, presence and undo work for text without any change to it.
The real model (blocks, inline marks, structure) is E9.1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar, Self

from claudia_core import Command, CommandRegistry, Context, DocumentModel, Region, new_registry


class TextModel(DocumentModel):
    app: ClassVar[str] = "composes"
    state_schema: ClassVar[int] = 1
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(self, blocks: list[str] | None = None):
        self.blocks: list[str] = blocks or [""]

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self) -> dict:
        return {"blocks": list(self.blocks)}

    @classmethod
    def restore(cls, state: dict) -> Self:
        return cls(list(state["blocks"]))

    def region_from_data(self, data: dict) -> Region:
        return TextRange(data["block"], data["start"], data["end"])


@dataclass(frozen=True)
class TextRange:
    """Characters ``start <= i < end`` of one block: where a cursor and its protected zone are."""

    kind: ClassVar[str] = "text"
    block: int
    start: int
    end: int

    def overlaps(self, other: Region) -> bool:
        return (
            isinstance(other, TextRange)
            and self.block == other.block
            and self.start < other.end
            and other.start < self.end
        )

    def transformed(self, command: Command) -> TextRange | None:
        if isinstance(command, InsertText) and command.block == self.block:
            n = len(command.text)
            if command.offset <= self.start:
                return TextRange(self.block, self.start + n, self.end + n)
            if command.offset < self.end:
                return TextRange(self.block, self.start, self.end + n)
        if isinstance(command, DeleteText) and command.block == self.block:
            cut_from, cut_to = command.offset, command.offset + command.length
            start = self.start - max(0, min(cut_to, self.start) - cut_from)
            end = self.end - max(0, min(cut_to, self.end) - cut_from)
            return None if end <= start else TextRange(self.block, start, end)
        return self

    def to_data(self) -> dict:
        return {"kind": self.kind, "block": self.block, "start": self.start, "end": self.end}


_WORD = re.compile(r"\w+", re.UNICODE)


def word_window(text: str, cursor: int, n: int, block: int = 0) -> TextRange:
    """The zone of D11: from ``n`` words before the cursor to ``n`` words after it.

    A word is a run of letters or digits."""
    words = [(m.start(), m.end()) for m in _WORD.finditer(text)]
    before = [w for w in words if w[1] <= cursor]
    after = [w for w in words if w[0] >= cursor]
    inside = [w for w in words if w[0] < cursor < w[1]]
    start = (before[-n][0] if len(before) >= n else 0) if n else cursor
    if inside:
        start = min(start, inside[0][0])
    end = (after[n - 1][1] if len(after) >= n else len(text)) if n else cursor
    if inside:
        end = max(end, inside[0][1])
    return TextRange(block, start, end)


@TextModel.registry.register
@dataclass(frozen=True)
class InsertText(Command):
    kind: ClassVar[str] = "composes.InsertText"
    block: int
    offset: int
    text: str

    @property
    def label(self) -> str:
        return "Type"

    def apply(self, ctx: Context[TextModel]) -> Command:
        blocks = ctx.model.blocks
        if not (0 <= self.block < len(blocks) and 0 <= self.offset <= len(blocks[self.block])):
            raise IndexError("insert outside the text")
        text = blocks[self.block]
        blocks[self.block] = text[: self.offset] + self.text + text[self.offset :]
        return DeleteText(self.block, self.offset, len(self.text))

    def to_data(self) -> dict:
        return {"block": self.block, "offset": self.offset, "text": self.text}

    @classmethod
    def from_data(cls, data, registry) -> InsertText:
        return cls(data["block"], data["offset"], data["text"])

    def regions(self, model) -> tuple[Region, ...]:
        return (TextRange(self.block, self.offset, self.offset + max(1, len(self.text))),)

    def shifted_by(self, other: Command) -> Command | None:
        if isinstance(other, InsertText) and other.block == self.block and other.offset <= self.offset:
            return InsertText(self.block, self.offset + len(other.text), self.text)
        if isinstance(other, DeleteText) and other.block == self.block and other.offset < self.offset:
            return InsertText(self.block, max(other.offset, self.offset - other.length), self.text)
        return self

    def redacted(self) -> Command:
        return InsertText(self.block, self.offset, "█" * len(self.text))  # same length, so later offsets still hold


@TextModel.registry.register
@dataclass(frozen=True)
class DeleteText(Command):
    kind: ClassVar[str] = "composes.DeleteText"
    block: int
    offset: int
    length: int

    @property
    def label(self) -> str:
        return "Delete text"

    def apply(self, ctx: Context[TextModel]) -> Command:
        blocks = ctx.model.blocks
        fits = (
            0 <= self.block < len(blocks) and self.offset >= 0 and self.offset + self.length <= len(blocks[self.block])
        )
        if not fits:
            raise IndexError("delete outside the text")
        text = blocks[self.block]
        removed = text[self.offset : self.offset + self.length]
        blocks[self.block] = text[: self.offset] + text[self.offset + self.length :]
        return InsertText(self.block, self.offset, removed)

    def to_data(self) -> dict:
        return {"block": self.block, "offset": self.offset, "length": self.length}

    @classmethod
    def from_data(cls, data, registry) -> DeleteText:
        return cls(data["block"], data["offset"], data["length"])

    def regions(self, model) -> tuple[Region, ...]:
        return (TextRange(self.block, self.offset, self.offset + self.length),)

    def shifted_by(self, other: Command) -> Command | None:
        """Deleting what I typed: follow colleagues' typing before it; refuse if they typed inside it or it is gone."""
        if isinstance(other, InsertText) and other.block == self.block:
            if other.offset <= self.offset:
                return DeleteText(self.block, self.offset + len(other.text), self.length)
            if other.offset < self.offset + self.length:
                return None  # their words are inside my passage: deleting it would take them too
        if isinstance(other, DeleteText) and other.block == self.block:
            if other.offset + other.length <= self.offset:
                return DeleteText(self.block, self.offset - other.length, self.length)
            if other.offset < self.offset + self.length:
                return None
        return self

    def redacted(self) -> Command:
        return self
