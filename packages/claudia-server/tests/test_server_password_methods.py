"""A request that confirms a password must not stop the server while it hashes (SEC-21, D1267).

At 0.75 s a hash per request would freeze every connection of the server for that long, and a person with a password
could ask in a loop. The hashing is done in a thread, behind the same cap as a login (SEC-03), before the request is
handled; the handler then finds the result ready.
"""

import functools
import json
import threading
import time

import pytest
from starlette.testclient import TestClient
from test_server_app import Peer

from claudia_container import KdfParams
from claudia_container.kdf import calibrate
from claudia_core.testing import ListModel
from claudia_server.app import create_app
from claudia_server.hub import Hub
from claudia_server.login_throttle import LoginThrottle
from claudia_server.sealed import SealedDocuments

SLOW = KdfParams(iterations=3, memory_kib=64 * 1024, lanes=1)  # the least: a tenth of a second on a fast machine
SEEN_AFTER = 0.15
"""Hashing must take longer than this for "another window is answered quickly" to mean anything (PROC-38)."""


@functools.cache
def slow_enough() -> KdfParams:
    """``SLOW``, with as many passes as this machine needs to take about twice ``SEEN_AFTER`` per hash (PROC-38).

    A fixed cost took 0.12 s on the runners of CI, below what the test needs, and 0.15 s or more on a slower machine;
    what the test needs is a time, not a number of passes, so it measures the machine like the server does (D1267).
    """
    return calibrate(2 * SEEN_AFTER, max_memory_kib=SLOW.memory_kib, floor=SLOW)


ANN, ANN_PW = "Annabelle", "Correct-Horse-9"
BEN, BEN_PW = "Bertram", "Battery-Staple-7"
NEW_PW = "Fresh-Start-42"


OPEN: list[Peer] = []
"""The windows a test opened: closed before the server is, or its shutdown waits for them."""


def window(client, **kw):
    peer = Peer(client, **kw)
    OPEN.append(peer)
    return peer


@pytest.fixture
def served(tmp_path):
    store = SealedDocuments(tmp_path, ListModel, kdf=slow_enough())
    app = create_app(Hub(store), store, login_throttle=LoginThrottle(free_tries=10**6))
    with TestClient(app) as client:
        try:
            yield client, store
        finally:
            while OPEN:
                OPEN.pop().close()


def send(peer, method, params=None):
    """Send a request without waiting for the answer; returns its id."""
    peer._next += 1
    peer.socket.send_text(json.dumps({"id": peer._next, "method": method, "params": params}))
    return peer._next


def pings_while(other, busy):
    """How long a ``ping`` of ``other`` takes while ``busy`` (a request of another window) is being worked on."""
    request = send(busy[0], *busy[1:])
    time.sleep(0.02)  # let the server start on it
    started = time.perf_counter()
    assert other.request("ping")["ok"]
    waited = time.perf_counter() - started
    assert busy[0].wait_for(request)["ok"], "the slow request itself is answered"
    return waited


def hashing_takes_long_enough_to_see(store):
    started = time.perf_counter()
    store.verify("plan", __import__("claudia_server").auth.Credentials(ANN, "wrong-Pass-1"))
    return time.perf_counter() - started


def two_windows(client):
    first = window(client, user=ANN, password=ANN_PW, create=True)
    second = window(client, user=ANN, password=ANN_PW)
    return first, second


@pytest.mark.parametrize(
    "call",
    [
        ("set_details", {"password": ANN_PW, "description": "d", "tags": []}),
        ("download_claudia", {"password": ANN_PW}),
        ("change_password", {"old_password": ANN_PW, "new_password": NEW_PW}),
        ("add_user", {"name": BEN, "password": BEN_PW, "role": "editor"}),
    ],
    ids=lambda call: call[0],
)
def test_another_window_is_answered_quickly_while_a_password_is_hashed(served, call):
    client, store = served
    first, second = two_windows(client)
    took = hashing_takes_long_enough_to_see(store)
    assert took > SEEN_AFTER, f"this machine hashes too fast for the test to mean anything ({took:.3f} s)"
    waited = pings_while(second, (first, *call))
    assert waited < 0.05, f"{call[0]} stopped the other window for {waited:.3f} s"


def test_the_work_really_is_done_by_the_request(served):
    client, store = served
    first, _ = two_windows(client)
    assert first.request("set_details", {"password": ANN_PW, "description": "plan of the year", "tags": ["a"]})["ok"]
    assert first.request("download_claudia", {"password": ANN_PW})["result"]["format"] == "claudia"
    assert first.request("change_password", {"old_password": ANN_PW, "new_password": NEW_PW})["ok"]
    assert first.request("leave", {"password": "wrong-Pass-1"})["ok"] is False


def test_a_wrong_password_is_refused_as_before(served):
    client, _ = served
    first, _ = two_windows(client)
    answer = first.request("delete_document", {"password": "wrong-Pass-1"})
    assert answer["ok"] is False and answer["error"]["code"] == "unauthorized"


def test_no_more_than_the_cap_hash_at_once(tmp_path):
    store = SealedDocuments(tmp_path, ListModel, kdf=SLOW)
    running, most = [0], [0]
    lock = threading.Lock()
    original = store.warm

    def counting(doc_id, name, password):
        with lock:
            running[0] += 1
            most[0] = max(most[0], running[0])
        try:
            return original(doc_id, name, password)
        finally:
            with lock:
                running[0] -= 1

    store.warm = counting
    app = create_app(Hub(store), store, login_throttle=LoginThrottle(free_tries=10**6))
    with TestClient(app) as client:
        windows = [window(client, user=ANN, password=ANN_PW, create=True)] + [
            window(client, user=ANN, password=ANN_PW) for _ in range(4)
        ]
        try:
            ids = [(w, send(w, "set_details", {"password": ANN_PW, "description": "d", "tags": []})) for w in windows]
            for peer, request in ids:
                assert peer.wait_for(request)["ok"]
        finally:
            while OPEN:
                OPEN.pop().close()
    assert 1 <= most[0] <= 2, "the same cap as the logins (SEC-03)"
