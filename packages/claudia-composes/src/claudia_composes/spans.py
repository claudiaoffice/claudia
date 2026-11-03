"""Where a stretch of text goes when other commands run (E1.5, E1.4).

A *span* is ``(block, start, end)``: characters ``start <= i < end`` of one paragraph; a caret is an empty span.
Cursors, zones, suggestions and the commands that undo old steps all hold spans, and all of them have to follow
edits made by somebody else. The rule for each command lives with the command (``TextCommand.follow``); regions,
suggestions and ``shifted_by`` only ask.
"""

from __future__ import annotations

from abc import ABC

from claudia_core import Command

Span = tuple[str, int, int]


class TextCommand(Command, ABC):
    """A command that changes the text or its paragraphs and therefore moves spans."""

    def follow(self, span: Span) -> Span:
        """Where ``span`` is after this command ran. Never fails: a stretch that was cut away becomes empty."""
        return span

    def breaks(self, span: Span) -> bool:
        """Does this command make ``span`` meaningless for undoing a step that was written for it?

        A colleague typing inside a passage, deleting part of it or splitting it in two does."""
        return False
