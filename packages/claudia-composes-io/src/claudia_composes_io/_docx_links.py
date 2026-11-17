"""The links of a paragraph of a kept docx when its words are written again (IEW-01).

A hyperlink holds its own words, which are also part of the text of its paragraph. When the words of a paragraph are
edited they are written again as plain runs, so a link that was left where it stood showed its words twice. A link is
therefore taken out of the paragraph before and put back where its words are now -- when they are still there,
untouched, in the new text -- and goes (as a link; its words stay) when they are not: a link is never made up for words
that were typed over, and one the edit leaves alone keeps its target and its looks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from os.path import commonprefix
from typing import Any

from docx.oxml.ns import qn

from ._docx_pictures import text_length

#: The longest text (in characters) that is matched word for word; a longer one is matched by what it starts and ends
#: with, which is where a person edits a long paragraph and costs nothing.
_MATCHED_WHOLE = 4000


@dataclass(frozen=True)
class Carried:
    """A link that stays: its element, and where its words are in the new text."""

    start: int
    length: int
    element: Any


def carry_links(
    paragraph: Any, before: str, after: str, anchors: Sequence[tuple[int, int]] = ()
) -> tuple[list[Carried], int]:  # noqa: ANN401
    """Take the hyperlinks out of ``paragraph`` (a ``w:p`` whose text is ``before``, about to say ``after``): the ones
    whose words are in ``after``, whole and in one piece, and not under one of the ``anchors`` (``(start, end)`` of
    the tracked changes written into the text), as what to put back, and how many were left out. The elements of
    both are detached."""
    blocks = _same_stretches(before, after)
    carried: list[Carried] = []
    dropped, position = 0, 0
    for child in list(paragraph):
        length = text_length(child)
        if child.tag == qn("w:hyperlink"):
            start = _moved(blocks, position, length)
            if start is None or any(first < start + length and start < last for first, last in anchors):
                dropped += 1
            else:
                carried.append(Carried(start, length, child))
            paragraph.remove(child)
        position += length
    return carried, dropped


def _moved(blocks: Sequence[tuple[int, int, int]], start: int, length: int) -> int | None:
    """Where the characters ``start`` to ``start + length`` of the old text are in the new one: ``None`` unless they
    are all in one stretch the two texts have in common."""
    for old, new, size in blocks:
        if old <= start and start + length <= old + size:
            return new + start - old
    return None


def _same_stretches(before: str, after: str) -> list[tuple[int, int, int]]:
    """The stretches ``before`` and ``after`` have in common: ``(where in before, where in after, how long)``."""
    if len(before) > _MATCHED_WHOLE or len(after) > _MATCHED_WHOLE:
        head = len(commonprefix([before, after]))
        tail = len(commonprefix([before[head:][::-1], after[head:][::-1]]))
        return [(0, 0, head), (len(before) - tail, len(after) - tail, tail)]
    matcher = SequenceMatcher(None, before, after, autojunk=False)
    return [(found.a, found.b, found.size) for found in matcher.get_matching_blocks()]
