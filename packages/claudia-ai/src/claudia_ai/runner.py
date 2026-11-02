"""One model for the whole server: the queue and the worker thread (E7.1).

A local model is slow, and answering two questions at once would only make both slower, so ``ModelRunner`` owns one
worker thread and answers one question at a time, in the order they came, whichever document they are from. Only
``LanguageModel.generate`` runs on that thread, on a ``Request`` that is a copy of what it needs; everything that
touches a document stays on the event loop.
"""

from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .agent import Agent, Request, Turn
from .model import LanguageModel, ModelError


class _Job:
    """One question on its way through the worker: what turns its generation off."""

    def __init__(self) -> None:
        self.cancelled = False
        self.timed_out = False


class ModelRunner:
    """Asks the model one question at a time on a worker thread.

    ``timeout`` is how many seconds one answer may take once the model has started on it (not counting the wait in
    the queue); ``max_new_tokens`` is the longest answer. ``close`` stops the running generation and the worker."""

    def __init__(
        self,
        model: LanguageModel,
        agent: Agent | None = None,
        *,
        max_new_tokens: int = 512,
        timeout: float = 180.0,
    ):
        if max_new_tokens < 1 or timeout <= 0:
            raise ValueError("max_new_tokens and timeout must be positive")
        self.model = model
        self.agent = agent or Agent()
        self.max_new_tokens = max_new_tokens
        self.timeout = timeout
        self._closing = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="claudia-ai")

    @property
    def name(self) -> str:
        """What model this is, for the operator."""
        return self.model.name

    async def answer(self, request: Request) -> Turn:
        """The model's answer to ``request``. Raises ``ModelError``; stops the generation if the caller is cancelled."""
        if self._closing.is_set():
            raise ModelError("the server is shutting down")
        job = _Job()
        try:
            turn = await asyncio.get_running_loop().run_in_executor(self._executor, self._generate, job, request)
        except asyncio.CancelledError:
            job.cancelled = True  # the worker may be in the middle of it: it stops at the next token
            raise
        except RuntimeError as exc:  # the executor was shut down while the question waited
            raise ModelError("the server is shutting down") from exc
        if job.timed_out:
            raise ModelError(f"that took longer than {self.timeout:g} seconds")
        if self._closing.is_set() and job.cancelled:
            raise ModelError("the server is shutting down")
        return turn

    def close(self) -> None:
        """Stop the running generation, drop what waits and end the worker. Returns when the worker is done."""
        self._closing.set()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _generate(self, job: _Job, request: Request) -> Turn:
        """On the worker thread."""
        deadline = time.monotonic() + self.timeout

        def stop() -> bool:
            if time.monotonic() > deadline:
                job.timed_out = True
            if self._closing.is_set():
                job.cancelled = True
            return job.cancelled or job.timed_out

        if stop():
            return Turn()
        try:
            return self.agent.respond(self.model, request, max_new_tokens=self.max_new_tokens, stop=stop)
        except ModelError:
            raise
        except Exception as exc:  # a model is a plug-in: whatever it does wrong, the asker is told in words
            raise ModelError(f"the model failed: {exc}") from exc
