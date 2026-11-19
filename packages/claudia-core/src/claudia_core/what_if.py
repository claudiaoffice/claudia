"""What-ifs and proposals (D236, D263, D1308): try something on a private copy of the document, then carry it out on the
live document as one step if nobody has worked on the same places since.

A :class:`WhatIf` is a :meth:`~claudia_core.Document.scratch` that remembers the commands it was given. What it
remembers is a :class:`Proposal`: plain data (the step it started from, the commands, who made it) that can be shown,
kept with a chat record, sent, and handed to :meth:`~claudia_core.Document.apply_proposal`. A what-if is never a line of
the log (D48): there is no fork, no checkpoint and no merge, and a proposal that does not fit any more is refused with
the places named (:class:`~claudia_core.ProposalOutdated`), never rebased.

The *places* of a proposal (``footprint``) are what its commands touch, read as ``Document.changes_since`` reads
them: each command's own regions and its inverse's, against the state after it. A step that came after the proposal's
base makes it outdated when it touches one of those places, or when it moves one (an insert before it: the positions the
proposal names would be other things now). A step that moves only places after it does not.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .commands import Command, CommandRegistry, encode
from .context import Context
from .region import Region
from .revision import Revision

if TYPE_CHECKING:
    from .document import Applied, Document
    from .model import DocumentModel


@dataclass(frozen=True)
class Proposal:
    """What a what-if would do, as plain data: ``commands`` to run on the state after ``base`` (``None``: the empty
    document), made by ``author``."""

    base: Revision | None
    commands: tuple[Command, ...]
    author: str | None = None

    def to_data(self) -> dict:
        """The plain-data form, for a chat record or the wire."""
        return {
            "base": self.base.to_data() if self.base else None,
            "commands": [encode(command) for command in self.commands],
            "author": self.author,
        }

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> Proposal:
        """Inverse of :meth:`to_data`; the registry decodes the commands."""
        base = data.get("base")
        return cls(
            Revision.parse(base) if base else None,
            tuple(registry.decode(each) for each in data.get("commands", ())),
            data.get("author"),
        )


def places(
    model: DocumentModel, commands: Iterable[Command], when: str, author: str | None = None
) -> tuple[Region, ...]:
    """Where ``commands`` act, each place once, in order: every command's regions and its inverse's, read against the
    state after the command. ``model`` is changed (the commands are run on it): give it a copy."""
    found: list[Region] = []
    seen: set[str] = set()
    for command in commands:
        ctx = Context(model, author, when, None, "do")
        inverse = model.apply(command, ctx)
        model.settle(ctx)
        for each in (command, inverse):
            try:
                regions = each.regions(model)
            except (KeyError, ValueError, IndexError):
                continue  # a command that cannot say where it acts adds nothing
            for region in regions:
                key = json.dumps(region.to_data(), sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    found.append(region)
    return tuple(found)


class WhatIf:
    """A private copy of a document that remembers the commands it was given (see the module description).

    ``document`` is the copy: a full :class:`~claudia_core.Document` with its own log, events, locks and per-author
    undo, and no store, so nothing reaches the live document. Read it to see the result; change it only through
    :meth:`apply` and :meth:`undo_last`, so that what is remembered is what happened."""

    def __init__(self, live: Document, at: Revision | None, author: str | None):
        self.base: Revision | None = at if at is not None else live.revision
        self.author = author
        self.document: Document = live.scratch(at)
        self._live = live
        self._commands: list[Command] = []

    def apply(self, command: Command) -> Applied:
        """Run ``command`` on the copy exactly as the live document would, and remember it."""
        applied = self.document.execute(command, author=self.author)
        self._commands.append(command)
        return applied

    def undo_last(self) -> Applied | None:
        """Take the last command back, from the copy and from what is remembered; ``None`` if there is none."""
        if not self._commands:
            return None
        applied = self.document.undo(self.author)
        if applied is not None:
            self._commands.pop()
        return applied

    def proposal(self) -> Proposal:
        """What this what-if would do, as plain data."""
        return Proposal(self.base, tuple(self._commands), self.author)

    def changes(self) -> tuple[Region, ...]:
        """The places the commands would change: what a person is shown as "this would change"."""
        return self._live.footprint(self.proposal())

    def what_if(self) -> WhatIf:
        """A what-if of this one: starts from the copy's state as it is now."""
        return self.document.what_if(author=self.author)

    def __len__(self) -> int:
        return len(self._commands)
