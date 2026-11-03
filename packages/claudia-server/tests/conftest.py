import pytest
from starlette.testclient import TestClient

from claudia_core import Document, MemoryStore
from claudia_core.testing import FakeClock, ListModel
from claudia_server.auth import Account


@pytest.fixture(autouse=True)
def _test_client_calls_the_server_by_a_name_it_answers_to(monkeypatch):
    """A server only answers to its own names (SEC-01). Starlette's test client calls itself ``testserver``, which is
    nobody's name, so here it is ``localhost``. Tests that are about the host name pass their own ``base_url``.

    Starlette's ``websocket_connect`` calls every socket ``testserver`` whatever the ``base_url`` says, so the host of
    the client is put in the headers of a socket unless the test names one."""
    original_init, original_connect = TestClient.__init__, TestClient.websocket_connect

    def init(self, app, base_url="http://localhost", *args, **kwargs):
        original_init(self, app, base_url, *args, **kwargs)

    def websocket_connect(self, url, *args, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        headers.setdefault("host", self.base_url.netloc.decode())
        return original_connect(self, url, *args, headers=headers, **kwargs)

    monkeypatch.setattr(TestClient, "__init__", init)
    monkeypatch.setattr(TestClient, "websocket_connect", websocket_connect)


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
