"""Letting go of a document may take time (packing); it must not stop the server or race with opening it again."""

import asyncio
import threading
import time

from claudia_core.testing import FakeClock, ListModel
from claudia_server.hub import Hub, MemoryProvider


class SlowRelease(MemoryProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events: list[str] = []
        self.release_thread: int | None = None

    def release(self, doc_id):
        self.events.append("release-start")
        self.release_thread = threading.get_ident()
        time.sleep(0.3)
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
        await hub.start()
        worst, last = 0.0, time.perf_counter()
        while "release-end" not in provider.events:
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            worst, last = max(worst, now - last), now
        await hub.stop()
        return worst, provider

    worst, provider = asyncio.run(scenario())
    assert worst < 0.15, f"the loop stood still for {worst:.2f} s"
    assert provider.release_thread != threading.main_thread().ident


def test_opening_a_document_waits_for_its_release_to_finish():
    async def scenario():
        clock = FakeClock()
        provider = SlowRelease(ListModel)
        hub = Hub(provider, idle_unload=60, clock=clock.lock_time, sweep_interval=0.01)
        await hub.open("plan", create=True)
        clock.advance(61)
        await hub.start()
        while "release-start" not in provider.events:
            await asyncio.sleep(0.005)
        await hub.open("plan")  # while the old copy is being let go
        await hub.stop()
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
