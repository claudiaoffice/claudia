"""Replaying a log onto a model. The one function every rebuild, snapshot check and restore goes through."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .commands import Command
from .context import Context
from .errors import KernelError, ReplayError
from .log import Entry
from .model import DocumentModel


def replay(
    model: DocumentModel,
    entries: Iterable[Entry],
    on_applied: Callable[[Entry, Command], object] | None = None,
) -> DocumentModel:
    """Apply ``entries`` in order. Time, author and origin come from the entry, so the result is deterministic.

    ``on_applied(entry, inverse)`` lets the caller collect inverses (restore) or rebuild undo stacks."""
    for entry in entries:
        ctx = Context(model, entry.author, entry.time, entry.rev, entry.origin)
        try:
            inverse = model.apply(entry.command, ctx)
            model.settle(ctx)
        except KernelError:
            raise
        except Exception as exc:
            raise ReplayError(entry.rev, exc) from exc
        if on_applied is not None:
            on_applied(entry, inverse)
    return model
