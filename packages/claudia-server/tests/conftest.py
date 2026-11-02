import pytest

from claudia_core import Document, MemoryStore
from claudia_core.testing import FakeClock, ListModel
from claudia_server.auth import Account


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def doc(clock):
    return Document(ListModel(), clock=clock.time, lock_clock=clock.lock_time, store=MemoryStore())


@pytest.fixture
def ann():
    return Account("ann", "owner")


@pytest.fixture
def ben():
    return Account("ben", "editor")


@pytest.fixture
def vera():
    return Account("vera", "viewer")
