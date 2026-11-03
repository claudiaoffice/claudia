"""A language model that needs no model, for tests: answers from a function, and can be slow."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from .model import Message


class FakeModel:
    """Answers with ``answer(messages)`` (an ``Exception`` it returns is raised) after ``delay`` seconds.

    It gives up early when asked to stop, and records what it was asked."""

    name = "fake model"

    def __init__(self, answer: Callable[[list[Message]], str | Exception] | None = None, delay: float = 0.0):
        self.answer = answer or (lambda messages: "ok")
        self.delay = delay
        self.calls: list[list[Message]] = []
        self.max_new_tokens: list[int] = []
        self.threads: set[threading.Thread] = set()
        self.most_at_once = 0
        self.stopped_early = False
        self._running = 0
        self._lock = threading.Lock()

    def generate(self, messages: list[Message], *, max_new_tokens: int, stop: Callable[[], bool]) -> str:
        """Like ``LanguageModel.generate``."""
        with self._lock:
            self.calls.append(messages)
            self.max_new_tokens.append(max_new_tokens)
            self.threads.add(threading.current_thread())
            self._running += 1
            self.most_at_once = max(self.most_at_once, self._running)
        try:
            end = time.monotonic() + self.delay
            while time.monotonic() < end:
                if stop():
                    self.stopped_early = True
                    return "partial"
                time.sleep(0.01)
            result = self.answer(messages)
            if isinstance(result, Exception):
                raise result
            return result
        finally:
            with self._lock:
                self._running -= 1
