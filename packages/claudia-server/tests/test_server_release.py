"""A document that is unloaded from memory is released from its storage: a sealed store forgets its keys (E2.7)."""

import asyncio

from claudia_core.testing import FakeClock, ListModel
from claudia_server.hub import Hub, MemoryProvider


class Recording(MemoryProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.released: list[str] = []

    def release(self, doc_id):
        self.released.append(doc_id)


def test_an_idle_document_is_released_when_it_is_unloaded():
    clock = FakeClock()
    provider = Recording(ListModel)
    hub = Hub(provider, idle_unload=60, clock=clock.lock_time)
    asyncio.run(hub.open("plan", create=True))
    hub.sweep()
    assert provider.released == []
    clock.advance(61)
    hub.sweep()
    assert provider.released == ["plan"]
    assert not hub.is_loaded("plan")


def test_the_built_in_providers_accept_a_release(tmp_path):
    from claudia_server.filestore import FileProvider

    MemoryProvider(ListModel).release("anything")
    FileProvider(tmp_path, ListModel).release("anything")
