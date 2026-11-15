"""How often one address may ask for something (D533): a window of time and a number of asks in it."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable


class Throttle:
    """At most ``limit`` asks per ``window`` seconds from each address.

    The asks it guards are cheap to answer but not free (the lookup of a document by its uid reads every manifest of
    the server), and there is no reason for one address to make many of them. Nothing is kept for an address whose
    last ask is older than the window."""

    def __init__(self, limit: int = 60, window: float = 60.0, *, clock: Callable[[], float] = time.monotonic):
        if limit < 1 or window <= 0:
            raise ValueError("a throttle lets at least one ask through in a window of some length")
        self.limit = limit
        self.window = window
        self._clock = clock
        self._asks: dict[str, deque[float]] = {}

    def allow(self, address: str) -> bool:
        """Count an ask from ``address``; ``False`` if it is over the limit (the ask is not counted then)."""
        now = self._clock()
        for stale in [a for a, times in self._asks.items() if times[-1] <= now - self.window]:
            del self._asks[stale]
        times = self._asks.setdefault(address, deque())
        while times and times[0] <= now - self.window:
            times.popleft()
        if len(times) >= self.limit:
            return False
        times.append(now)
        return True
