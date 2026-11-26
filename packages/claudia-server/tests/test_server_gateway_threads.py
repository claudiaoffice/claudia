"""Password hashing must not freeze the server (SEC-03) and must happen for every attempt (SEC-04)."""

import asyncio
import threading
import time

from claudia_ai.testing import Hold
from claudia_core.testing import ListModel
from claudia_server.app import Gateway
from claudia_server.auth import Account, Credentials
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.suite import Suite

PASSWORD = "Correct-Horse-9"


class SlowDirectory(Hold):
    """A directory whose checks take long (``seconds``, or until let go while held), and which counts how many run at
    once."""

    def __init__(self, seconds=0.0):
        super().__init__()
        self.seconds = seconds
        self.calls: list[tuple[str, str | None]] = []
        self.running = 0
        self.most = 0
        self._lock = threading.Lock()

    def _work(self):
        with self._lock:
            self.running += 1
            self.most = max(self.most, self.running)
        self.wait_until_free()
        time.sleep(self.seconds)  # work: the hashing
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


def gateway_with(directory, **options):
    hub = Hub(MemoryProvider(ListModel))
    return hub, Gateway(Suite.single(hub, directory), set(), **options)


async def held_while_the_loop_runs(directory, work):
    """Run ``work`` with ``directory`` held: whether the loop went on while the directory worked, and the result.

    Measured with a stopwatch, "the loop stood still for less than 0.15 s" failed on a busy machine (PROC-66). Held,
    the check takes as long as the test wants: a check on the event loop would stop the loop until it is let go."""
    directory.hold()
    task = asyncio.create_task(work)
    await directory.begun()
    went_on = not task.done()  # this line ran while the directory was held
    directory.let_go()
    return went_on, await task


def test_checking_a_password_does_not_block_the_event_loop():
    async def scenario():
        directory = SlowDirectory()
        hub, gateway = gateway_with(directory)
        await hub.open("plan", create=True)
        return await held_while_the_loop_runs(
            directory, gateway.admit("plan", Credentials("ann", PASSWORD), create=False)
        )

    went_on, account = asyncio.run(scenario())
    assert went_on, "the loop stood still while the password was checked"
    assert account is not None


def test_creating_a_document_does_not_block_the_event_loop_either():
    async def scenario():
        directory = SlowDirectory()
        _, gateway = gateway_with(directory)
        return await held_while_the_loop_runs(
            directory, gateway.admit("plan", Credentials("ann", PASSWORD), create=True)
        )

    went_on, account = asyncio.run(scenario())
    assert went_on, "the loop stood still while the document was created"
    assert account is not None


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
        directory = SlowDirectory()
        _, gateway = gateway_with(directory)
        return directory, await gateway.admit("nothing-here", Credentials("ann", PASSWORD), create=False)

    directory, account = asyncio.run(scenario())
    assert directory.calls == [("nothing-here", "ann")]
    assert account is None
