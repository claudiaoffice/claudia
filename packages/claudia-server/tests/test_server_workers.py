"""The worker pool: offloading slow or CPU-bound work off the event loop, true parallelism and crash isolation
per task, not per server (E3.5, D37, D134).
"""

import asyncio
import os
from concurrent.futures import Executor, Future
from concurrent.futures.process import BrokenProcessPool

import pytest

from claudia_server.workers import PoolBusy, WorkerPool


def _add(a, b):
    return a + b


def _pid():
    return os.getpid()


def _boom():
    raise ValueError("boom")


def _die():
    os._exit(1)  # a hard crash: nothing to catch, the process is simply gone


def _nap(seconds):
    import time

    time.sleep(seconds)  # work: what the worker is busy with
    return "done"


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


def test_max_waiting_refuses_a_submission_once_that_many_are_already_in_flight():
    """Mirrors Assistant.max_waiting: a bound document must not pile an unbounded queue behind the one pool every
    document on this server shares. Refused immediately (``PoolBusy``), not queued and not run inline."""

    async def scenario():
        pool = WorkerPool(max_workers=2, max_waiting=1)
        try:
            holding = asyncio.ensure_future(pool.submit(_nap, 0.2))
            await asyncio.sleep(0)  # a yield, not a wait: the first submission claims its slot before its first await
            with pytest.raises(PoolBusy):
                await pool.submit(_add, 1, 1)
            assert await holding == "done"
        finally:
            await pool.stop()

    asyncio.run(scenario())


def test_max_waiting_none_means_no_bound():
    async def scenario():
        pool = WorkerPool(max_workers=1, max_waiting=None)
        try:
            results = await asyncio.gather(*(pool.submit(_add, 1, i) for i in range(5)))
            assert results == [1 + i for i in range(5)]
        finally:
            await pool.stop()

    asyncio.run(scenario())


def test_a_slot_is_freed_again_once_the_submission_finishes():
    async def scenario():
        pool = WorkerPool(max_workers=1, max_waiting=1)
        try:
            assert await pool.submit(_add, 1, 1) == 2
            assert await pool.submit(_add, 2, 2) == 4  # the first submission's slot was freed, not leaked
        finally:
            await pool.stop()

    asyncio.run(scenario())


def test_a_slot_is_freed_even_when_the_submission_raises():
    async def scenario():
        pool = WorkerPool(max_workers=1, max_waiting=1)
        try:
            with pytest.raises(ValueError, match="boom"):
                await pool.submit(_boom)
            assert await pool.submit(_add, 1, 1) == 2  # the failed submission's slot was freed, not leaked
        finally:
            await pool.stop()

    asyncio.run(scenario())


def test_stop_is_safe_before_anything_was_submitted_and_safe_to_call_twice():
    async def scenario():
        pool = WorkerPool()
        await pool.stop()
        await pool.stop()

    asyncio.run(scenario())


class AnsweredByTheTest(Executor):
    """A pool of processes whose answers and crashes the test gives, one by one, so that it can time them."""

    def __init__(self):
        self.futures: list[Future] = []
        self.let_go = False

    def submit(self, fn, /, *args, **kwargs):
        self.futures.append(Future())
        return self.futures[-1]

    def shutdown(self, wait=True, *, cancel_futures=False):
        self.let_go = True


def test_a_crash_answered_late_does_not_lose_the_pool_that_replaced_the_broken_one():
    """Two submissions break the same pool; the first one's crash is answered only after a third submission has started
    a fresh pool. That late answer must leave the fresh pool alone: once it was dropped and never let go, its
    processes outliving the server (CODE-106: this was tested by calling the private ``_discard``)."""

    async def scenario():
        made: list[AnsweredByTheTest] = []

        def make(workers):
            made.append(AnsweredByTheTest())
            return made[-1]

        pool = WorkerPool(make_executor=make)
        late = asyncio.ensure_future(pool.submit(_add, 1, 1))
        early = asyncio.ensure_future(pool.submit(_add, 2, 2))
        await asyncio.sleep(0)  # a yield: both submissions reach the first pool
        made[0].futures[1].set_exception(BrokenProcessPool())
        await asyncio.wait({early})
        fresh = asyncio.ensure_future(pool.submit(_add, 3, 3))  # the next submission starts a fresh pool
        await asyncio.sleep(0)
        made[0].futures[0].set_exception(BrokenProcessPool())  # the late answer of the broken pool
        await asyncio.wait({late})
        made[1].futures[0].set_result(6)
        assert await fresh == 6
        await pool.stop()
        return made

    made = asyncio.run(scenario())
    assert len(made) == 2 and all(executor.let_go for executor in made), "every pool of processes is let go"
