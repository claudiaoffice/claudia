"""Letting go of a document may take time (packing); it must not stop the server or race with opening it again."""

import asyncio
import threading

from claudia_ai.testing import Hold
from claudia_core.testing import FakeClock, ListModel
from claudia_server.hub import Hub, MemoryProvider


class SlowRelease(MemoryProvider):
    """Letting go takes until the test says so (``hold``); otherwise at once."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events: list[str] = []
        self.release_thread: int | None = None
        self.letting_go = Hold()

    def release(self, doc_id):
        self.events.append("release-start")
        self.release_thread = threading.get_ident()
        self.letting_go.wait_until_free()
        self.events.append("release-end")

    def open(self, doc_id):
        self.events.append("open")
        return super().open(doc_id)


def test_the_housekeeping_releases_in_a_thread_and_the_loop_keeps_running():
    async def scenario():
        clock = FakeClock()
        provider = SlowRelease(ListModel)
        hub = Hub(provider, idle_unload=60, clock=clock.lock_time, sweep_interval=0.01)
        await hub.open("plan", create=True)
        clock.advance(61)
        provider.letting_go.hold()
        await hub.start()
        await provider.letting_go.begun()
        went_on = "release-end" not in provider.events  # this ran while the release was held
        provider.letting_go.let_go()
        await hub.stop()
        return went_on, provider

    went_on, provider = asyncio.run(scenario())
    assert went_on, "the loop stood still while the document was let go"
    assert provider.release_thread != threading.main_thread().ident


def test_opening_a_document_waits_for_its_release_to_finish():
    async def scenario():
        clock = FakeClock()
        provider = SlowRelease(ListModel)
        hub = Hub(provider, idle_unload=60, clock=clock.lock_time, sweep_interval=0.01)
        await hub.open("plan", create=True)
        clock.advance(61)
        provider.letting_go.hold()
        await hub.start()
        await provider.letting_go.begun()
        opening = asyncio.create_task(hub.open("plan"))  # while the old copy is being let go
        # A wait for something that must not happen: on a slow machine it may miss the bug, it never fails a sound hub
        done, _ = await asyncio.wait({opening}, timeout=0.2)
        provider.letting_go.let_go()
        await opening
        await hub.stop()
        assert not done, "the document was opened again while it was still being let go"
        return provider.events

    events = asyncio.run(scenario())
    assert events.index("release-end") < events.index("open")


def test_stopping_the_hub_lets_go_of_every_open_document():
    async def scenario():
        provider = SlowRelease(ListModel)
        hub = Hub(provider, sweep_interval=60)
        await hub.open("plan", create=True)
        await hub.open("budget", create=True)
        await hub.start()
        await hub.stop()
        return hub, provider

    hub, provider = asyncio.run(scenario())
    assert provider.events.count("release-end") == 2
    assert not hub.is_loaded("plan") and not hub.is_loaded("budget")
