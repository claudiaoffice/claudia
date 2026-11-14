"""Knowing when nobody uses the server any more, so that a server started for the desktop apps can stop (D434).

The server counts what keeps it in use: every open WebSocket — a document's live connection, or the presence socket
(``/api/presence``) that the start page holds while it is shown, because that page has no document open — and the
time of the last HTTP request. It is idle when no socket is open and no request came for ``seconds``.

``IdleWatch`` only notices; what happens then is the caller's: ``on_idle`` is called once. ``cli.py`` sets it to ask
uvicorn to stop the way Ctrl+C does (``Server.should_exit``), so the documents are packed and the process ends on
every platform the same way, without a signal.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable

log = logging.getLogger("claudia_server")


class IdleWatch:
    """How long the server has been unused, and a loop that calls ``on_idle`` once it has been for ``seconds``."""

    def __init__(
        self,
        seconds: float,
        *,
        on_idle: Callable[[], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
        interval: float = 1.0,
    ):
        if seconds <= 0:
            raise ValueError("the idle time must be positive")
        self.seconds = seconds
        self.on_idle = on_idle
        self._clock = clock
        self._interval = interval
        self._open = 0
        self._last = clock()
        self._fired = False
        self._task: asyncio.Task | None = None

    @property
    def open_sockets(self) -> int:
        """How many WebSockets are open now."""
        return self._open

    def touched(self) -> None:
        """Something used the server just now (an HTTP request)."""
        self._last = self._clock()

    def opened(self) -> None:
        """A WebSocket was let in."""
        self._open += 1
        self.touched()

    def closed(self) -> None:
        """A WebSocket ended."""
        self._open = max(0, self._open - 1)
        self.touched()

    def idle_for(self) -> float:
        """For how many seconds nothing has used the server; 0 while a socket is open."""
        return 0.0 if self._open else self._clock() - self._last

    def check(self) -> bool:
        """Call ``on_idle`` (once) if the server has been idle for ``seconds``; ``True`` if it is idle that long."""
        if self.idle_for() < self.seconds:
            return False
        if not self._fired:
            self._fired = True
            log.info("nobody has used the server for %s seconds: stopping", self.seconds)
            if self.on_idle is not None:
                self.on_idle()
        return True

    async def _loop(self) -> None:
        while not self.check():
            await asyncio.sleep(self._interval)

    async def start(self) -> None:
        """Watch in the background; the time counts from now."""
        self.touched()
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Stop watching."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None


class IdleMiddleware:
    """ASGI middleware that tells an :class:`IdleWatch` about every HTTP request and every WebSocket, whatever route
    it is for: a WebSocket counts as open from its first frame to its end, a request touches the watch when it comes
    and when its answer has been sent."""

    def __init__(self, app, watch: IdleWatch):  # noqa: ANN001 - an ASGI app
        self.app = app
        self.watch = watch

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001 - the ASGI interface
        if scope["type"] == "websocket":
            self.watch.opened()
            try:
                await self.app(scope, receive, send)
            finally:
                self.watch.closed()
        elif scope["type"] == "http":
            self.watch.touched()
            try:
                await self.app(scope, receive, send)
            finally:
                self.watch.touched()
        else:
            await self.app(scope, receive, send)
