"""Failed logins wait longer each time, without a lock-out (D1266, SEC-11; the state is kept in memory, D1276).

The caps on sockets waiting to be let in (SEC-02) bound how many connections wait, but nothing slowed a patient guesser
who fails, reconnects and tries again; with the hashing cost raised (D1267) one bad login per second would also keep the
server's hashing busy. So a failed login is counted twice:

* per **address** (a success from it clears the count), and
* per **document and name**, counted whether or not the document or the name exists, so that the answer still tells
  nothing about which there are (D50, SEC-04). A success does not clear it, or anybody could reset the count of a name
  by logging in somewhere else.

The first ``free_tries`` failures are free; then the wait is 1, 2, 4, 8… seconds, never more than ``address_cap`` for an
address and ``name_cap`` for a name, so a stranger who keeps guessing a colleague's name can delay her by ``name_cap``
seconds at most. The wait runs from the last failure. A login inside it is refused *before any hashing*
(``check``), so a guesser costs the server nothing. **Nothing is ever locked for good**: that would let anybody lock the
owner out.

The counters live in memory only and are forgotten after ``forget_after`` seconds without a failure; a restart forgets
them too, and a guesser regains at most one wait (D1276). They are bounded: when a table is full the entry that has been
quiet longest goes first. The clock is injected, so tests do not sleep.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from .auth import normalized

DEFAULT_FREE_TRIES = 3
DEFAULT_ADDRESS_CAP = 30.0  # seconds
DEFAULT_NAME_CAP = 10.0  # seconds
DEFAULT_FORGET_AFTER = 15 * 60.0  # seconds without a failure
DEFAULT_MAX_ENTRIES = 10_000  # per table


@dataclass
class _Count:
    failures: int
    last: float


class LoginThrottle:
    """The waits after failed logins (see the module docstring). Not thread-safe: the gateway runs on one event loop."""

    def __init__(
        self,
        *,
        free_tries: int = DEFAULT_FREE_TRIES,
        address_cap: float = DEFAULT_ADDRESS_CAP,
        name_cap: float = DEFAULT_NAME_CAP,
        forget_after: float = DEFAULT_FORGET_AFTER,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ):
        if free_tries < 0 or address_cap <= 0 or name_cap <= 0 or forget_after <= 0 or max_entries < 1:
            raise ValueError("a login throttle needs free tries of 0 or more and caps, a memory and a size above 0")
        self.free_tries = free_tries
        self.address_cap = address_cap
        self.name_cap = name_cap
        self.forget_after = forget_after
        self.max_entries = max_entries
        self._clock = clock
        self._addresses: OrderedDict[str, _Count] = OrderedDict()
        self._names: OrderedDict[tuple[str, str], _Count] = OrderedDict()

    # -- asking ---------------------------------------------------------------------------------
    def check(self, address: str, doc_id: str, name: object) -> float:
        """Seconds this login has to wait before it is looked at (0: now). Call before any hashing."""
        now = self._clock()
        return max(
            self._remaining(self._addresses.get(address), self.address_cap, now),
            self._remaining(self._names.get(self._key(doc_id, name)), self.name_cap, now),
        )

    def failed(self, address: str, doc_id: str, name: object) -> None:
        """A login from ``address`` for this document and name was refused (or the document or name does not exist)."""
        now = self._clock()
        self._count(self._addresses, address, now)
        self._count(self._names, self._key(doc_id, name), now)

    def succeeded(self, address: str) -> None:
        """A login from ``address`` was accepted: what it had failed is forgotten. What was failed *against a name* is
        not (anybody could clear it by logging in somewhere else)."""
        self._addresses.pop(address, None)

    def size(self) -> int:
        """How many counters are held (for tests and the server's own checks)."""
        return len(self._addresses) + len(self._names)

    # -- inside ---------------------------------------------------------------------------------
    @staticmethod
    def _key(doc_id: str, name: object) -> tuple[str, str]:
        """Names are compared the way the directory compares them, so capitals and spaces make no new name."""
        return doc_id, normalized(name) if isinstance(name, str) else ""

    def _wait(self, failures: int, cap: float) -> float:
        over = failures - self.free_tries
        return 0.0 if over <= 0 else min(cap, float(2 ** (over - 1)))

    def _remaining(self, count: _Count | None, cap: float, now: float) -> float:
        if count is None or now - count.last >= self.forget_after:
            return 0.0
        return max(0.0, count.last + self._wait(count.failures, cap) - now)

    def _count(self, table: OrderedDict, key, now: float) -> None:
        count = table.get(key)
        if count is None or now - count.last >= self.forget_after:
            count = _Count(0, now)
        count.failures += 1
        count.last = now
        table[key] = count
        table.move_to_end(key)
        while len(table) > self.max_entries:
            table.popitem(last=False)
