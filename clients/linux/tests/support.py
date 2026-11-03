"""Helpers for the GTK tests."""

from __future__ import annotations

import time
from collections.abc import Callable


def pump(condition: Callable[[], object], timeout: float = 8.0, what: str = "the condition") -> None:
    """Run the GLib main loop until ``condition()`` is true."""
    from claudia_shell_gtk._gi import GLib

    context = GLib.MainContext.default()
    end = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < end, f"gave up waiting for {what}"
        context.iteration(False)
        time.sleep(0.005)


def pump_for(seconds: float) -> None:
    """Run the main loop for a while (to show that something does *not* happen)."""
    from claudia_shell_gtk._gi import GLib

    context = GLib.MainContext.default()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        context.iteration(False)
        time.sleep(0.005)


def evaluate(view, source: str, *, world: str | None = None, timeout: float = 8.0) -> str:
    """Run JavaScript in the web view and return the result as text (pumping the main loop while waiting)."""
    answer: list[str] = []

    def done(web_view, task) -> None:
        try:
            answer.append(web_view.evaluate_javascript_finish(task).to_string())
        except Exception as problem:  # the page threw: tests want to see that
            answer.append(f"error: {problem}")

    view.evaluate_javascript(source, -1, world, None, None, done)
    pump(lambda: answer, timeout=timeout, what=f"the answer to {source[:50]!r}")
    return answer[0]
