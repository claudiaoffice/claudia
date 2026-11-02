"""The FastAPI application over a real WebSocket (ported from the demo's app tests, rewritten for name + password).

Starlette's test client speaks the same protocol as a browser or the desktop client, without opening a port.
"""

import json
import re

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from claudia_core.testing import ListModel
from claudia_server import app as app_module
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.hub import Hub, MemoryProvider

INSERT = {"k": "list.Insert", "s": 1, "d": {"index": 0, "value": 5}}
PASSWORD = "correct horse battery"


@pytest.fixture
def provider():
    return MemoryProvider(ListModel)


@pytest.fixture
def directory():
    return ScryptDirectory(cost=2**4)


def build(provider, directory, **hub_options):
    allowed = hub_options.pop("allowed_origins", ())
    web_dir = hub_options.pop("web_dir", None)
    return create_app(Hub(provider, **hub_options), directory, allowed_origins=allowed, web_dir=web_dir)


@pytest.fixture
def client(provider, directory):
    with TestClient(build(provider, directory)) as c:
        yield c


class Peer:
    """One WebSocket connection that has said hello."""

    def __init__(self, client, doc="plan", user="ann", password=PASSWORD, create=False, **headers):
        self.socket = client.websocket_connect(f"/api/docs/{doc}/ws", headers=headers).__enter__()
        self.socket.send_text(
            json.dumps({"id": 1, "method": "hello", "params": {"user": user, "password": password, "create": create}})
        )
        self.hello = self.socket.receive_json()
        self._next = 1
        self.pushed: list[dict] = []

    def request(self, method, params=None):
        self._next += 1
        self.socket.send_text(json.dumps({"id": self._next, "method": method, "params": params}))
        return self.wait_for(self._next)

    def wait_for(self, request_id):
        while True:
            frame = self.socket.receive_json()
            if frame.get("id") == request_id:
                return frame
            self.pushed.append(frame)

    def close(self):
        self.socket.__exit__(None, None, None)


def refused(client, *, doc="plan", **kw):
    """The close code and error code when the handshake fails (``None`` for the error if there was no answer)."""
    error = None
    peer = None
    try:
        with pytest.raises(WebSocketDisconnect) as closed:
            peer = Peer(client, doc=doc, **kw)
            error = peer.hello["error"]["code"]
            peer.socket.receive_json()  # the socket must now be closed
    finally:
        if peer is not None:
            peer.close()
    return closed.value.code, error


def test_logging_in_to_an_existing_document_needs_its_name_and_password(client, directory):
    Peer(client, create=True).close()
    directory.add_user("plan", "Ben", "another good password", "editor")
    peer = Peer(client, user="ben", password="another good password")  # (the spelling of the name does not matter)
    assert peer.hello["result"]["role"] == "editor" and peer.hello["result"]["user"] == "Ben"
    peer.close()


def test_a_wrong_password_an_unknown_name_and_a_missing_document_look_the_same(client):
    Peer(client, create=True).close()
    answers = {
        refused(client, user="ann", password="not the password"),
        refused(client, user="nobody", password=PASSWORD),
        refused(client, doc="nothing-here", user="ann", password=PASSWORD),
    }
    assert answers == {(4401, "unauthorized")}


def test_the_name_ai_cannot_log_in_or_create(client):
    assert refused(client, user="ai", password=PASSWORD, create=True) == (4401, "unauthorized")
    peer = Peer(client, user="AI", password=PASSWORD, create=True)
    assert "AI assistant" in peer.hello["error"]["message"]
    peer.close()


def test_creating_needs_an_acceptable_name_and_password_and_leaves_nothing_behind(client):
    code, error = refused(client, doc="short", user="ann", password="short", create=True)
    assert (code, error) == (4400, "bad_request")
    code, error = refused(client, doc="short", user="ann\nben", password=PASSWORD, create=True)
    assert (code, error) == (4400, "bad_request")
    assert refused(client, doc="short", user="ann", password="short") == (4401, "unauthorized"), "no document, no user"


def test_creation_can_be_switched_off(provider, directory):
    with TestClient(build(provider, directory, allow_create=False)) as c:
        assert refused(c, create=True) == (4401, "unauthorized")


def test_creating_a_document_that_exists_is_just_logging_in(client):
    Peer(client, create=True).close()
    assert refused(client, user="mallory", password="mallory's password", create=True) == (4401, "unauthorized")
    Peer(client, create=True).close()  # the owner may pass the flag again


def test_failed_handshakes_close_with_a_code(client):
    with client.websocket_connect("/api/docs/plan/ws") as ws:
        ws.send_text("not json")
        assert ws.receive_json()["error"]["code"] == "bad_request"
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 4400
    with client.websocket_connect("/api/docs/plan/ws") as ws:
        ws.send_text(json.dumps({"id": 1, "method": "ping"}))
        assert ws.receive_json()["error"]["message"].startswith("the first message must be hello")
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 4400


def test_no_hello_in_time_closes_with_4408(provider, directory, monkeypatch):
    monkeypatch.setattr(app_module, "HELLO_TIMEOUT", 0.05)
    with TestClient(build(provider, directory)) as c, c.websocket_connect("/api/docs/plan/ws") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 4408


def test_document_ids_are_validated(client):
    for bad in ("dot.dot", "has%20space", "x" * 65, "%C3%A4"):
        assert refused(client, doc=bad, create=True) == (4400, "bad_request"), bad


# --------------------------------------------------------------------------------------- working
def test_two_people_see_each_others_edits_and_the_response_comes_last(client, directory):
    ann = Peer(client, create=True)
    directory.add_user("plan", "Ben", "another good password", "editor")
    ben = Peer(client, user="Ben", password="another good password")
    ann.pushed, ben.pushed = [], []
    response = ann.request("apply", {"command": INSERT})
    assert response["ok"] and response["result"] == {"revision": "main:1"}
    assert [f["data"]["revision"] for f in ann.pushed if f["event"] == "command"] == ["main:1"]
    ben_view = ben.request("snapshot")["result"]
    assert ben_view["state"] == {"items": [5]}
    assert any(f["event"] == "command" and f["data"]["author"] == "ann" for f in ben.pushed)
    ann.close(), ben.close()


def test_a_closed_client_does_not_disturb_the_others(client, directory):
    ann = Peer(client, create=True)
    directory.add_user("plan", "Ben", "another good password", "editor")
    ben = Peer(client, user="Ben", password="another good password")
    ben.close()
    assert ann.request("apply", {"command": INSERT})["ok"]
    ann.close()


def test_edits_survive_a_restart(provider, directory):
    with TestClient(build(provider, directory)) as first:
        peer = Peer(first, create=True)
        peer.request("apply", {"command": INSERT})
        peer.close()
    with TestClient(build(provider, directory)) as second:  # a new hub on the same storage and users
        peer = Peer(second)
        assert peer.request("snapshot")["result"]["state"] == {"items": [5]}
        assert peer.request("history")["result"]["can_undo"] is True
        peer.close()


def test_the_connection_limit_closes_with_1013(provider, directory):
    with TestClient(build(provider, directory, max_connections=1)) as c:
        first = Peer(c, create=True)
        directory.add_user("plan", "Ben", "another good password", "editor")
        assert refused(c, user="Ben", password="another good password") == (1013, "unavailable")
        first.close()


def test_oversized_frames_are_rejected_without_closing(provider, directory):
    from claudia_server.protocol import Limits

    with TestClient(build(provider, directory, limits=Limits(max_message_bytes=2000))) as c:
        peer = Peer(c, create=True)
        peer.socket.send_text(json.dumps({"id": 5, "method": "chat", "params": {"text": "x" * 3000}}))
        frame = peer.socket.receive_json()
        assert frame["error"]["code"] == "bad_request" and frame["error"]["message"] == "message too large"
        assert peer.request("ping")["ok"], "the connection stays open"
        peer.close()


def test_binary_frames_are_handled(client):
    peer = Peer(client, create=True)
    peer.socket.send_bytes(b'{"id": 9, "method": "ping"}')
    assert peer.socket.receive_json()["ok"] is True
    peer.close()


def test_presence_and_locks_over_the_websocket(client, directory):
    ann = Peer(client, create=True)
    directory.add_user("plan", "Ben", "another good password", "editor")
    ben = Peer(client, user="Ben", password="another good password")
    assert ann.request("lock", {"regions": [{"kind": "interval", "start": 0, "end": 1}]})["ok"]
    assert ben.request("apply", {"command": INSERT})["error"]["code"] == "locked"
    ann.close()  # a dropped connection releases the lock
    assert ben.request("apply", {"command": INSERT})["ok"]
    ben.close()


def test_an_edit_in_flight_during_a_restore_is_refused_over_the_wire(provider, directory):
    app = build(provider, directory)
    with TestClient(app) as c:
        ann = Peer(c, create=True)
        ann.request("apply", {"command": INSERT})
        ann.request("save_checkpoint", {"label": "good"})
        ann.request("apply", {"command": INSERT})
        seen = ann.request("ping")["result"]["revision"]
        hub = app.state.hub
        hosted = hub._documents["plan"]  # the server-side act; the wire method waits for the rules of a live session
        c.portal.call(lambda: hosted.document.restore_checkpoint(1, author="ann"))
        reply = ann.request("apply", {"command": INSERT, "base": seen})
        assert reply["error"]["code"] == "stale"
        assert any(f["event"] == "branch" for f in ann.pushed) and any(f["event"] == "rebuilt" for f in ann.pushed)
        assert ann.request("snapshot")["result"]["state"] == {"items": [5]}
        ann.close()


# ------------------------------------------------------------------------------------- browsers
def test_origin_rules(provider, directory):
    with TestClient(build(provider, directory)) as c:
        Peer(c, create=True, origin="http://testserver").close()  # the page came from this server
        with pytest.raises(WebSocketDisconnect):
            Peer(c, origin="https://evil.example")


def test_a_configured_origin_may_connect_and_gets_cors(provider, directory):
    with TestClient(build(provider, directory, allowed_origins=["https://app.example"])) as c:
        Peer(c, create=True, origin="https://app.example").close()
        reply = c.get("/api/health", headers={"Origin": "https://app.example"})
        assert reply.headers["access-control-allow-origin"] == "https://app.example"
        assert (
            "access-control-allow-origin"
            not in c.get("/api/health", headers={"Origin": "https://evil.example"}).headers
        )


def test_the_landing_page_names_no_secrets(client):
    assert not re.search(r"token|secret|key", client.get("/").text, re.IGNORECASE)
