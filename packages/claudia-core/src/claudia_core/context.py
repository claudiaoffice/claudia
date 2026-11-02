"""What a command gets to work with while it applies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .events import Event

if TYPE_CHECKING:
    from .model import DocumentModel
    from .revision import Revision


class Context[M: "DocumentModel"]:
    """Passed to ``Command.apply`` and ``DocumentModel.settle``.

    ``author`` and ``time`` are the facts commands may record; ``revision`` is the revision the command
    will get (``None`` while a log is replayed on a scratch model without numbering). A command mutates the model
    and calls ``emit`` for each state event; the Document publishes them after the whole command (and the
    model's ``settle``) has finished. ``failed`` is True when ``settle`` runs after a command was rolled back.
    """

    def __init__(
        self,
        model: M,
        author: str | None = None,
        time: str | None = None,
        revision: Revision | None = None,
        origin: str = "do",
    ):
        self.model = model
        self.author = author
        self.time = time
        self.revision = revision
        self.origin = origin
        self.failed = False
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        """Tell subscribers about something that happened while the command applied."""
        self.events.append(event)
