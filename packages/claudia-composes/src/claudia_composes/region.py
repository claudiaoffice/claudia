"""The text region: a stretch of one paragraph, and the ± n words zone around a cursor (D11, D17)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from claudia_core import Command, Region

from .spans import Span, TextCommand


@dataclass(frozen=True)
class TextRange:
    """Characters ``start <= i < end`` of one paragraph: where a cursor and its protected zone are.

    An empty range is a caret. It overlaps nothing, but it moves with the text and is drawn."""

    kind: ClassVar[str] = "text"
    block: str
    start: int
    end: int

    @property
    def span(self) -> Span:
        """The range as a ``(block, start, end)`` triple."""
        return (self.block, self.start, self.end)

    def overlaps(self, other: Region) -> bool:
        """Do the two ranges share a character?"""
        return (
            isinstance(other, TextRange)
            and self.block == other.block
            and self.start < self.end
            and other.start < other.end
            and self.start < other.end
            and other.start < self.end
        )

    def transformed(self, command: Command) -> TextRange | None:
        """The range after one leaf command; ``None`` if the text it covered is gone."""
        if not isinstance(command, TextCommand):
            return self
        moved = TextRange(*command.follow(self.span))
        was_text, is_gone = self.start < self.end, moved.end <= moved.start
        return None if was_text and is_gone else moved

    def to_data(self) -> dict:
        """The plain-data form for the wire."""
        return {"kind": self.kind, "block": self.block, "start": self.start, "end": self.end}


_WORD = re.compile(r"\w+", re.UNICODE)


def word_window(text: str, cursor: int, n: int, block: str = "b1") -> TextRange:
    """The zone of D11: from ``n`` words before the cursor to ``n`` words after it.

    A word is a run of letters or digits. A cursor inside a word protects that word whole."""
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
