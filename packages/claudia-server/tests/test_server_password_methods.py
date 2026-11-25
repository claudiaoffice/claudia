"""A request that confirms a password must not stop the server while it hashes (SEC-21, D1267).

At 0.75 s a hash per request would freeze every connection of the server for that long, and a person with a password
could ask in a loop. The hashing is done in a thread, behind the same cap as a login (SEC-03), before the request is
handled; the handler then finds the result ready.
"""

import json
import threading

import pytest
from starlette.testclient import TestClient
from test_server_app import Peer

from claudia_ai.testing import Hold
from claudia_core.testing import ListModel
from claudia_document_file import KdfParams, crypto
from claudia_server.app import create_app
from claudia_server.hub import Hub
from claudia_server.login_throttle import LoginThrottle
from claudia_server.sealed import SealedDocuments

SLOW = KdfParams(iterations=3, memory_kib=64 * 1024, lanes=1)  # the least: a tenth of a second on a fast machine
PATIENCE = 10.0
"""Seconds a test waits for something that happens at once when the server works: only a broken server reaches it."""


def held_hashing(monkeypatch) -> Hold:
    """Every password hash of the server waits until the test lets it go (PROC-66).

    "Another window is answered while a password is hashed" was measured with a stopwatch (a ping under 50 ms while a
    hash took 0.3 s), and a busy runner made it fail now and then. Held, the hash takes as long as the test wants: a
    server that hashed on its event loop could answer nobody until it is let go, on any machine."""
    hashing, real = Hold(), crypto.argon2id

    def held(*args, **kwargs):
        hashing.wait_until_free()
        return real(*args, **kwargs)

    monkeypatch.setattr(crypto, "argon2id", held)
    return hashing


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
    store = SealedDocuments(tmp_path, ListModel, kdf=SLOW)
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


def answered_in_time(peer, method) -> bool:
    """Whether ``peer``'s ``method`` is answered, and well, before ``PATIENCE`` runs out (asked from a thread, so a
    server that answers nobody fails the test instead of hanging it)."""
    answers = []
    asking = threading.Thread(target=lambda: answers.append(peer.request(method)), daemon=True)
    asking.start()
    asking.join(PATIENCE)
    return bool(answers) and answers[0]["ok"]


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
def test_another_window_is_answered_while_a_password_is_hashed(served, call, monkeypatch):
    client, _ = served
    first, second = two_windows(client)
    hashing = held_hashing(monkeypatch)
    hashing.hold()
    try:
        request = send(first, *call)
        assert hashing.started.wait(PATIENCE), f"{call[0]} hashed no password"
        assert answered_in_time(second, "ping"), f"{call[0]} stopped the other window while it hashed"
    finally:
        hashing.let_go()
    assert first.wait_for(request)["ok"], "the request that hashed is answered too"


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
