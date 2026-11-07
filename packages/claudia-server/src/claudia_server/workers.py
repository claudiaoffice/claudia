"""Offloading slow or CPU-bound work off the event loop (E3.5; D37 specified this and it was not built; placed here
rather than in ``claudia-core`` by D134).

Every document on a running server is served from the same single thread (``hub.py``): ``Connection.handle`` is
synchronous and runs inside the event-loop coroutine, so anything slow in one request stalls every document that
server holds, not only the one that asked (QA review 2026-11-06, PERF-02, and the open half of D37 — "the worker
tier is not: everything runs on the event loop"). A ``WorkerPool`` runs such work in separate OS processes instead —
true parallelism, which the GIL would otherwise take back from a thread — and bridges the result into an ``await``.

Deliberately generic: this module knows nothing about cells, formulas or typesetting. It submits a function and its
arguments and returns what the function returns. ``Hub`` owns one instance per running server (D134: one process per
``--model``, not a pool shared across process boundaries) and calls :meth:`WorkerPool.stop` when the server stops.

A worker process can die outright (killed, a segfault inside a C extension) rather than raise an exception; that
breaks the ``ProcessPoolExecutor`` underneath, not just the one task. :meth:`WorkerPool.submit` replaces the broken
executor transparently on the next call, so the failure is isolated to the task that caused it — the caller sees an
ordinary exception, and every other document's work on this server, before and after it, is unaffected.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import ParamSpec, TypeVar

log = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

DEFAULT_WORKERS = 4


def _call(fn: Callable, args: tuple, kwargs: dict):
    """Runs in the worker process: ``run_in_executor`` only passes positional arguments to the target, so keyword
    arguments are carried through as a plain dict instead."""
    return fn(*args, **kwargs)


class WorkerPool:
    """A process pool reachable from the event loop. No process is started until the first :meth:`submit`."""

    def __init__(self, *, max_workers: int = DEFAULT_WORKERS):
        self.max_workers = max_workers
        self._executor: ProcessPoolExecutor | None = None

    def _ensure(self) -> ProcessPoolExecutor:
        if self._executor is None:
            self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        return self._executor

    async def submit(self, fn: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs) -> R:
        """Run ``fn(*args, **kwargs)`` in a worker process and await its result.

        ``fn`` and everything passed to it must be importable at module level and picklable: a plain function, not a
        closure, a lambda or a bound method of something holding a lock, a socket or an open file."""
        executor = self._ensure()
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(executor, _call, fn, args, kwargs)
        except BrokenProcessPool:
            log.warning("a worker process died; the pool will be replaced on the next submission")
            self._discard(executor)
            raise

    def _discard(self, executor: ProcessPoolExecutor) -> None:
        """Shut the given (broken) executor down, and clear it from ``self`` only if it is still the current one.

        Two tasks can break the same pool at once; each reaches here with its own reference to the executor that
        broke. If one of them has already been handled and a fresh pool created in the meantime, a second, slower
        handler must not null that fresh, working pool out from under it — it discards only what it was given.
        """
        executor.shutdown(wait=False, cancel_futures=True)
        if self._executor is executor:
            self._executor = None

    async def stop(self) -> None:
        """Let the worker processes go. Safe to call when nothing was ever submitted, and safe to call twice."""
        executor, self._executor = self._executor, None
        if executor is not None:
            await asyncio.get_running_loop().run_in_executor(None, executor.shutdown, True)
