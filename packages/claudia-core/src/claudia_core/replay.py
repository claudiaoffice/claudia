"""Replaying a log onto a model. The one function every rebuild, snapshot check and restore goes through.

``replay_collecting`` is the shape to reach for when the replay itself should stay clear of any live object:
it needs nothing but ``model`` and the plain log ``entries`` -- no bound method of a ``Document``, no event
bus, nothing that cannot cross a process boundary. That is deliberate groundwork (open decision-log item,
D178): the loop in :func:`replay` is the CPU-bound part of opening a large document, and a future round may
want to run it on a :class:`~claudia_server.workers.WorkerPool` instead of inline. Nothing here dispatches it
there yet -- ``DocumentProvider.open`` stays synchronous this round -- but ``Document.open`` and
``Document._rebuild`` already call :func:`replay_collecting` rather than handing ``replay`` a bound method,
so the expensive step is already separable: the only thing a caller does with its live ``Document`` is the
cheap, local bookkeeping (rebuilding undo stacks) *after* the pairs come back."""

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


def replay_collecting(model: DocumentModel, entries: Iterable[Entry]) -> list[tuple[Entry, Command]]:
    """Like :func:`replay`, but returns the ``(entry, inverse)`` pairs instead of taking a callback.

    ``model`` is mutated in place, exactly as :func:`replay` would; the difference is only in how the caller
    gets its inverses back. That makes this call -- unlike handing :func:`replay` a bound method such as
    ``document._record_history`` -- a pure function of plain data (a model and a log), fit to run somewhere
    else entirely (see the module docstring, D178)."""
    applied: list[tuple[Entry, Command]] = []
    replay(model, entries, lambda entry, inverse: applied.append((entry, inverse)))
    return applied
