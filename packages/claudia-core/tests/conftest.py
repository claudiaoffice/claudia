import pytest

from claudia_core import Document, MemoryStore
from claudia_core.testing import FakeClock, ListModel


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def make_doc(clock):
    def make(**options):
        options.setdefault("store", MemoryStore())
        return Document(ListModel(), clock=clock.time, lock_clock=clock.lock_time, **options)

    return make


@pytest.fixture
def doc(make_doc):
    return make_doc()
