"""The worker pool: offloading slow or CPU-bound work off the event loop, true parallelism and crash isolation
per task, not per server (E3.5, D37, D134).
"""

import asyncio
import os
from concurrent.futures import ProcessPoolExecutor

import pytest

from claudia_server.workers import WorkerPool


def _add(a, b):
    return a + b


def _pid():
    return os.getpid()


def _boom():
    raise ValueError("boom")


def _die():
    os._exit(1)  # a hard crash: nothing to catch, the process is simply gone


def test_submit_runs_in_a_worker_and_returns_the_result():
    async def scenario():
        pool = WorkerPool()
        try:
            assert await pool.submit(_add, 2, 3) == 5
        finally:
            await pool.stop()

    asyncio.run(scenario())


def test_submit_runs_in_a_different_process():
    async def scenario():
        pool = WorkerPool()
        try:
            worker_pid = await pool.submit(_pid)
            assert worker_pid != os.getpid()
        finally:
            await pool.stop()

    asyncio.run(scenario())


def test_an_exception_in_the_worker_surfaces_to_the_caller():
    async def scenario():
        pool = WorkerPool()
        try:
            with pytest.raises(ValueError, match="boom"):
                await pool.submit(_boom)
        finally:
            await pool.stop()

    asyncio.run(scenario())


def test_two_submissions_run_at_the_same_time_in_different_processes():
    async def scenario():
        pool = WorkerPool(max_workers=2)
        try:
            results = await asyncio.gather(pool.submit(_pid), pool.submit(_pid))
            assert len(set(results)) == 2, "two workers at once should mean two different process ids"
        finally:
            await pool.stop()

    asyncio.run(scenario())


def test_a_worker_process_dying_fails_only_that_task_not_the_pool():
    async def scenario():
        pool = WorkerPool()
        try:
            with pytest.raises(Exception, match="."):
                await pool.submit(_die)
            # the pool replaces itself transparently on the next submission; unrelated work is unaffected
            assert await pool.submit(_add, 1, 1) == 2
        finally:
            await pool.stop()

    asyncio.run(scenario())


def test_stop_is_safe_before_anything_was_submitted_and_safe_to_call_twice():
    async def scenario():
        pool = WorkerPool()
        await pool.stop()
        await pool.stop()

    asyncio.run(scenario())


def test_discarding_a_still_current_executor_clears_the_pool():
    pool = WorkerPool()
    current = pool._ensure()
    try:
        pool._discard(current)
        assert pool._executor is None
    finally:
        current.shutdown(wait=True)


def test_discarding_a_stale_executor_does_not_clobber_its_replacement():
    """Two submissions can break the same pool at once; each handler calls ``_discard`` with its own reference to
    the executor that broke. If one handler is slow and, by the time it runs, a *different* submission has already
    installed a fresh, healthy replacement, the slow handler must discard only the broken one it was given -- not
    null out the replacement from under whoever is now using it (the bug this guards against: an earlier, unguarded
    ``self._executor = None`` would have cleared it regardless of which executor was current)."""
    pool = WorkerPool()
    stale = pool._ensure()  # the pool that is about to "break"
    replacement = ProcessPoolExecutor(max_workers=1)  # a concurrent submission already installed a fresh one
    pool._executor = replacement
    try:
        pool._discard(stale)  # the slow handler for the stale pool's crash runs late
        assert pool._executor is replacement, "a stale handler must not clear a newer, healthy executor"
    finally:
        stale.shutdown(wait=True)
        replacement.shutdown(wait=True)
