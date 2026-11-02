"""Password hashing must not freeze the server (SEC-03) and must happen for every attempt (SEC-04)."""

import asyncio
import threading
import time

from claudia_core.testing import ListModel
from claudia_server.app import Gateway
from claudia_server.auth import Account, Credentials
from claudia_server.hub import Hub, MemoryProvider

PASSWORD = "Correct-Horse-9"


class SlowDirectory:
    """A directory whose checks take long, and which counts how many run at once."""

    def __init__(self, seconds=0.3):
        self.seconds = seconds
        self.calls: list[tuple[str, str | None]] = []
        self.running = 0
        self.most = 0
        self._lock = threading.Lock()

    def _work(self):
        with self._lock:
            self.running += 1
            self.most = max(self.most, self.running)
        time.sleep(self.seconds)
        with self._lock:
            self.running -= 1

    def verify(self, doc_id, credentials):
        self.calls.append((doc_id, credentials.user))
        self._work()
        known = doc_id == "plan" and credentials.password == PASSWORD
        return Account("ann", "owner") if known else None

    def add_user(self, doc_id, name, password, role="editor"):
        self._work()
        return Account(name, role)

    def remove_user(self, doc_id, name):
        pass


async def worst_pause_while(task):
    """The longest time the event loop took for a 10 ms nap while ``task`` ran: how long it was blocked."""
    worst, last = 0.0, time.perf_counter()
    while not task.done():
        await asyncio.sleep(0.01)
        now = time.perf_counter()
        worst, last = max(worst, now - last), now
    return worst


def gateway_with(directory, **options):
    hub = Hub(MemoryProvider(ListModel))
    return hub, Gateway(hub, directory, set(), **options)


def test_checking_a_password_does_not_block_the_event_loop():
    async def scenario():
        directory = SlowDirectory(0.3)
        hub, gateway = gateway_with(directory)
        await hub.open("plan", create=True)
        check = asyncio.create_task(gateway.admit("plan", Credentials("ann", PASSWORD), create=False))
        return await worst_pause_while(check), await check

    worst, account = asyncio.run(scenario())
    assert account is not None
    assert worst < 0.15, f"the loop stood still for {worst:.2f} s"


def test_creating_a_document_does_not_block_the_event_loop_either():
    async def scenario():
        hub, gateway = gateway_with(SlowDirectory(0.3))
        creation = asyncio.create_task(gateway.admit("plan", Credentials("ann", PASSWORD), create=True))
        return await worst_pause_while(creation), await creation

    worst, account = asyncio.run(scenario())
    assert account is not None
    assert worst < 0.15, f"the loop stood still for {worst:.2f} s"


def test_only_a_few_passwords_are_hashed_at_once():
    async def scenario():
        directory = SlowDirectory(0.1)
        hub, gateway = gateway_with(directory, max_hashing=2)
        await hub.open("plan", create=True)
        await asyncio.gather(*(gateway.admit("plan", Credentials(f"u{i}", "x"), create=False) for i in range(8)))
        return directory

    directory = asyncio.run(scenario())
    assert len(directory.calls) == 8
    assert directory.most <= 2


def test_a_missing_document_is_checked_like_an_existing_one():
    """The directory does the same work whether or not the document is there, so the time says nothing (SEC-04)."""

    async def scenario():
        directory = SlowDirectory(0.01)
        _, gateway = gateway_with(directory)
        return directory, await gateway.admit("nothing-here", Credentials("ann", PASSWORD), create=False)

    directory, account = asyncio.run(scenario())
    assert directory.calls == [("nothing-here", "ann")]
    assert account is None
