"""Who may make documents, how many there can be, and how many connections may wait to be let in (SEC-02).

Measured before this: 300 documents made without any credentials in 33 s, all of them kept, and no limit on sockets that
had connected but not yet logged in, so a flood of ``hello`` frames could queue behind the password hashing without end.
"""

import json

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from claudia_container import KdfParams
from claudia_core.testing import ListModel
from claudia_server import Hub, MemoryProvider, ScryptDirectory, create_app
from claudia_server.sealed import SealedDocuments

PASSWORD = "correct horse battery"
SECRET = "a-long-secret-nobody-guesses-1234"


class CountingDirectory(ScryptDirectory):
    """Remembers which documents it was asked to add a person to: adding a person costs hashing and disk."""

    def __init__(self):
        super().__init__(cost=2**4)
        self.added: list[str] = []

    def add_user(self, doc_id, name, password, role="editor"):
        self.added.append(doc_id)
        return super().add_user(doc_id, name, password, role)


def serve(*, provider=None, directory=None, hub_options=None, **options):
    hub = Hub(provider or MemoryProvider(ListModel), **(hub_options or {}))
    return create_app(hub, directory or CountingDirectory(), **options)


def hello(user="ann", password=PASSWORD, create=True, **extra):
    params = {"user": user, "password": password, "create": create, **extra}
    return json.dumps({"id": 1, "method": "hello", "params": params})


def closed_with(socket):
    """The code with which the server closes ``socket`` as soon as it has been let on."""
    with pytest.raises(WebSocketDisconnect) as closed:
        socket.receive_json()
    return closed.value.code


def answer(client, doc="plan", **params):
    """``("ok", None)`` if the person came in, else the close code and the error code the server gave."""
    with client.websocket_connect(f"/api/docs/{doc}/ws") as ws:
        ws.send_text(hello(**params))
        frame = ws.receive_json()
        if frame["ok"]:
            return "ok", None
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        return closed.value.code, frame["error"]["code"]


# ---------------------------------------------------------------------------- how many documents there can be
def test_the_server_holds_no_more_documents_than_it_is_set_to():
    directory = CountingDirectory()
    provider = MemoryProvider(ListModel)
    with TestClient(serve(provider=provider, directory=directory, hub_options={"max_documents": 2})) as client:
        assert answer(client, "one") == ("ok", None)
        assert answer(client, "two") == ("ok", None)
        assert answer(client, "three") == (1013, "unavailable")
    assert not provider.exists("three")
    assert directory.added == ["one", "two"], "a refused document costs no hashing and leaves no person behind"


def test_a_full_server_still_lets_its_people_in():
    with TestClient(serve(hub_options={"max_documents": 1})) as client:
        assert answer(client, "one") == ("ok", None)
        assert answer(client, "one") == ("ok", None)
        assert answer(client, "one", password="not the password") == (4401, "unauthorized")


def test_the_default_leaves_room_for_a_team_but_not_for_ever():
    assert 100 <= Hub(MemoryProvider(ListModel)).max_documents <= 100_000


# The sealed store (what ``--dir`` uses) makes a document's file when its first person is added, before the hub opens
# the document: a count that only looked at what the hub itself created would never see these.
CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
STRONG = "Correct-Horse-9"


def sealed_server(folder, **hub_options):
    store = SealedDocuments(folder, ListModel, kdf=CHEAP)
    return TestClient(create_app(Hub(store, **hub_options), store))


def test_the_cap_holds_for_the_sealed_store_too(tmp_path):
    with sealed_server(tmp_path, max_documents=2) as client:
        made = [answer(client, doc, user="Annabelle", password=STRONG) for doc in ("one", "two", "three")]
    assert made == [("ok", None), ("ok", None), (1013, "unavailable")]
    assert sorted(path.name for path in (tmp_path / "docs").glob("*.claudia")) == ["one.claudia", "two.claudia"]


def test_documents_that_are_already_stored_count_towards_the_cap(tmp_path):
    with sealed_server(tmp_path) as before:
        for doc in ("one", "two"):
            assert answer(before, doc, user="Annabelle", password=STRONG) == ("ok", None)
    with sealed_server(tmp_path, max_documents=2) as after:  # a restart, with a lower cap
        assert answer(after, "three", user="Annabelle", password=STRONG) == (1013, "unavailable")
        assert answer(after, "one", user="Annabelle", password=STRONG) == ("ok", None)


# ------------------------------------------------------------------ how many connections may wait to be let in
def test_only_so_many_connections_may_wait_to_be_let_in():
    with (
        TestClient(serve(max_waiting=2)) as client,
        client.websocket_connect("/api/docs/a/ws") as one,
        client.websocket_connect("/api/docs/b/ws") as two,
        client.websocket_connect("/api/docs/c/ws") as three,
    ):
        assert closed_with(three) == 1013
        one.send_text(hello())  # the two that were first can still come in
        assert one.receive_json()["ok"]
        two.send_text(hello())
        assert two.receive_json()["ok"]


def test_a_place_in_the_queue_is_given_back_when_the_person_is_in():
    with TestClient(serve(max_waiting=1)) as client:
        for doc in ("a", "b", "c"):
            assert answer(client, doc) == ("ok", None)


def test_a_place_in_the_queue_is_given_back_when_the_socket_goes_away():
    with TestClient(serve(max_waiting=1)) as client:
        with client.websocket_connect("/api/docs/a/ws"):
            pass
        assert answer(client, "b") == ("ok", None)


def test_one_address_cannot_use_up_all_the_places():
    with (
        TestClient(serve(max_waiting=10, max_waiting_per_address=1)) as client,
        client.websocket_connect("/api/docs/a/ws"),
        client.websocket_connect("/api/docs/b/ws") as second,
    ):
        assert closed_with(second) == 1013


# ---------------------------------------------------------------------------------------------- access secret
def test_without_a_secret_anybody_may_create_as_before():
    with TestClient(serve()) as client:
        assert answer(client, "plan") == ("ok", None)


def test_with_a_secret_only_those_who_know_it_may_create():
    directory = CountingDirectory()
    provider = MemoryProvider(ListModel)
    with TestClient(serve(provider=provider, directory=directory, access_secret=SECRET)) as client:
        assert answer(client, "plan") == (4401, "unauthorized")
        assert answer(client, "plan", access="wrong") == (4401, "unauthorized")
        assert answer(client, "plan", access=5) == (4401, "unauthorized")
        assert not provider.exists("plan")
        assert directory.added == [], "a refused creation costs no disk"
        assert answer(client, "plan", access=SECRET) == ("ok", None)
    assert provider.exists("plan")


def test_people_of_an_existing_document_do_not_need_the_secret_to_log_in():
    with TestClient(serve(access_secret=SECRET)) as client:
        assert answer(client, "plan", access=SECRET) == ("ok", None)
        assert answer(client, "plan") == ("ok", None)


def test_the_secret_does_not_make_a_missing_document_answer_differently():
    """Whether a document exists must stay hidden from somebody who has no password (D50)."""
    with TestClient(serve(access_secret=SECRET)) as client:
        assert answer(client, "plan", access=SECRET) == ("ok", None)
        existing = answer(client, "plan", password="not the password", create=True)
        missing = answer(client, "nothing-here", create=True)
    assert existing == missing == (4401, "unauthorized")


def test_with_a_secret_the_list_needs_it_too():
    with TestClient(serve(access_secret=SECRET)) as client:
        assert client.get("/api/docs").status_code == 401
        assert client.get("/api/docs").headers["www-authenticate"] == "Bearer"
        assert client.get("/api/docs", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.get("/api/docs", headers={"Authorization": f"Basic {SECRET}"}).status_code == 401
        assert client.get("/api/docs", headers={"Authorization": f"Bearer {SECRET}"}).status_code == 200
        assert client.get("/api/health").status_code == 200, "liveness stays open"


def test_a_secret_too_short_to_hold_is_refused():
    with pytest.raises(ValueError, match="at least"):
        serve(access_secret="short")
