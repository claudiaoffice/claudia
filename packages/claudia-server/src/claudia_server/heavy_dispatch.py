"""Dispatches a document's deferred heavy formula calls (``Calculator.pending_heavy``, see ``claudia_computes
.calc``) to a :class:`~claudia_server.workers.WorkerPool`, and applies or discards each result when it comes
back (PERF review 2026-11-08, D37, D177).

One :class:`HeavyDispatcher` per document, built the same way :class:`~claudia_server.assistant.Assistant` is:
it subscribes to the document's events and, for every call newly waiting in ``pending_heavy`` that it has not
already launched, submits the call to the pool and re-enters the document through ``execute`` once the answer
is in -- or, if the document moved on while the worker ran, discards the stale answer and lets the formula be
tried again (D37's "a worker computes on a copy at revision r and its result is discarded if the inputs
changed", now built).

**Scope of this round, deliberately:** a deferred call is only ever resolved here when the heavy call *is* the
formula -- ``=HEAVY(A1:A5)``, not ``=HEAVY(A1:A5)+1``. ``Deferred`` is raised deep inside the compiled
expression tree and carries only the one call's own bound function and arguments, with no way back to whatever
wraps it; running that one call on a worker and applying its result as the *whole* formula's value would be
wrong whenever something wraps it. :meth:`HeavyDispatcher._is_whole_formula` checks this before ever
submitting, so a wrapped heavy call simply stays deferred -- correct, if not yet resolved -- rather than
risking a silently wrong answer. Offloading part of an expression is a follow-up, not attempted here (open
decision-log item, see D177).

No "calculating" indicator is shown yet, per D177: a deferred cell keeps showing whatever it showed before
until the result lands. The UI for that needs its own screens-first round (the project's own rule for new
frontend work), not this patch.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Protocol

from claudia_computes import ApplyCalculated, WorkbookModel
from claudia_computes.calc import Key
from claudia_computes.formula import Call

from .workers import PoolBusy

if TYPE_CHECKING:
    from claudia_computes.calc import Calculator
    from claudia_computes.functions.base import Deferred
    from claudia_core import Document

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0  # seconds a deferred call may run on a worker before its answer is given up on


class Submittable(Protocol):
    """What :class:`HeavyDispatcher` needs from a worker pool: just ``submit`` (``WorkerPool``'s own shape), so
    a test can stand in a fake one without a real process pool."""

    async def submit(self, fn, /, *args, **kwargs):
        """Run ``fn(*args, **kwargs)`` somewhere off the event loop and return its result (``WorkerPool.submit``'s
        own contract: see there for what ``fn`` and its arguments must be)."""
        ...


class HeavyDispatcher:
    """Watches one document's deferred heavy calls (``calc.pending_heavy``) and runs the ones it can safely
    resolve on ``workers``, applying or discarding each result as it comes back. For workbook documents only
    (``document.model`` must be a :class:`~claudia_computes.WorkbookModel`)."""

    def __init__(self, document: Document, workers: Submittable, *, timeout: float = DEFAULT_TIMEOUT):
        assert isinstance(document.model, WorkbookModel), "HeavyDispatcher is for workbook documents only"
        self.document = document
        self.calc: Calculator = document.model.calc
        self.workers = workers
        self.timeout = timeout
        self._inflight: set[Key] = set()
        self._unsubscribe = document.subscribe(self._on_event)

    def close(self) -> None:
        """Stop watching (the document is being let go). In-flight tasks finish on their own; their ``execute``
        calls land harmlessly if the document is no longer in use -- nobody awaits :meth:`close`."""
        self._unsubscribe()

    # -- noticing work ---------------------------------------------------------------------
    def _on_event(self, event: object) -> None:
        for key, deferred in list(self.calc.pending_heavy.items()):
            if key in self._inflight:
                continue
            if not self._is_whole_formula(key, deferred):
                continue  # see the module docstring: not yet resolvable here, left deferred rather than guessed
            self._inflight.add(key)
            self._start(key, deferred)

    def _is_whole_formula(self, key: Key, deferred: Deferred) -> bool:
        """Is ``deferred``'s call the *entire* formula at ``key``, nothing wrapping it? Only then is the call's
        own result the formula's result."""
        compiled = self.calc.formulas.get(key)
        ast = compiled.formula.ast if compiled is not None else None
        return isinstance(ast, Call) and ast.name == deferred.bound.name

    def _start(self, key: Key, deferred: Deferred) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._inflight.discard(key)
            return  # no event loop (a test without one): left pending, nobody is waiting on an answer yet
        loop.create_task(self._run(key, deferred))

    # -- running and landing the answer -----------------------------------------------------
    async def _run(self, key: Key, deferred: Deferred) -> None:
        try:
            await self._resolve(key, deferred)
        except Exception:
            log.exception("a deferred heavy call failed")
            self._discard(key)
        finally:
            self._inflight.discard(key)

    async def _resolve(self, key: Key, deferred: Deferred) -> None:
        revision = self.document.revision
        try:
            value = await asyncio.wait_for(self.workers.submit(deferred.bound.invoke, deferred.call_args), self.timeout)
        except PoolBusy:
            return  # not an error: left pending, tried again the next time something wakes this document
        except TimeoutError:
            log.warning("%s timed out on the worker pool", deferred.bound.name)
            self._discard(key)
            return
        if self.document.revision != revision:
            self._discard(key)  # the inputs moved on while the worker ran: the answer is stale (D37)
            return
        sheet, row, col = key
        self.document.execute(ApplyCalculated(sheet, row, col, value), author="ai")

    def _discard(self, key: Key) -> None:
        self.calc.discard_heavy(key)
