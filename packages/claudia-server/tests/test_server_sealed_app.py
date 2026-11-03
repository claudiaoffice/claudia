"""The sealed store through the real application: create, edit, restart the server, and look at the disk."""

import json
import zipfile

import pytest
from starlette.testclient import TestClient
from test_server_app import INSERT, Peer, refused

from claudia_container import KdfParams
from claudia_core.testing import ListModel
from claudia_server.app import create_app
from claudia_server.hub import Hub
from claudia_server.sealed import SealedDocuments

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
ANN, ANN_PW = "Annabelle", "Correct-Horse-9"
BEN, BEN_PW = "Bertram", "Battery-Staple-7"
VERA, VERA_PW = "Cornelia", "Purple-Monkey-5"


def server(tmp_path):
    """A server on the folder; building another one is a restart."""
    store = SealedDocuments(tmp_path, ListModel, kdf=CHEAP)
    return TestClient(create_app(Hub(store), store))


def all_bytes(folder):
    data = b""
    for file in folder.rglob("*"):
        if file.is_file():
            data += file.read_bytes()
            if file.suffix == ".claudia":
                with zipfile.ZipFile(file) as z:
                    data += b"".join(z.read(n) for n in z.namelist())
    return data


def test_a_session_survives_a_restart_and_leaves_nothing_readable(tmp_path):
    with server(tmp_path) as client:
        ann = Peer(client, user=ANN, password=ANN_PW, create=True)
        assert ann.hello["result"]["role"] == "owner"
        assert ann.request("apply", {"command": INSERT})["ok"]
        ann.request("chat", {"text": "the-forecast-is-confidential-4711"})
        assert ann.request("add_user", {"name": BEN, "password": BEN_PW, "role": "editor"})["ok"]
        ann.close()

    data = all_bytes(tmp_path)
    for secret in [ANN, BEN, ANN_PW, BEN_PW, "confidential-4711"]:
        assert secret.encode() not in data, secret

    with server(tmp_path) as client:  # restarted
        ben = Peer(client, user="bertram", password=BEN_PW)
        assert ben.hello["result"]["role"] == "editor"
        assert ben.request("snapshot")["result"]["state"] == {"items": [5]}
        ben.close()


def test_a_wrong_password_an_unknown_name_and_a_missing_document_look_the_same(tmp_path):
    with server(tmp_path) as client:
        Peer(client, user=ANN, password=ANN_PW, create=True).close()
        answers = {
            refused(client, user=ANN, password="wrong-Pass-1"),
            refused(client, user="Nobody", password=ANN_PW),
            refused(client, doc="nothing-here", user=ANN, password=ANN_PW),
        }
    assert answers == {(4401, "unauthorized")}


def test_a_viewer_reads_while_the_document_is_open_but_cannot_write(tmp_path):
    with server(tmp_path) as client:
        ann = Peer(client, user=ANN, password=ANN_PW, create=True)
        ann.request("add_user", {"name": VERA, "password": VERA_PW, "role": "viewer"})
        vera = Peer(client, user=VERA, password=VERA_PW)
        assert vera.hello["result"]["role"] == "viewer"
        assert vera.request("apply", {"command": INSERT})["error"]["code"] == "forbidden"
        vera.close()
        ann.close()


def test_after_a_restart_a_viewer_is_told_to_ask_an_editor(tmp_path):
    with server(tmp_path) as client:
        ann = Peer(client, user=ANN, password=ANN_PW, create=True)
        ann.request("add_user", {"name": VERA, "password": VERA_PW, "role": "viewer"})
        ann.close()
    with server(tmp_path) as client:
        code, error = refused(client, user=VERA, password=VERA_PW)
        assert (code, error) == (4423, "sealed")  # its own answer: a client may wait and try again
        with client.websocket_connect("/api/docs/plan/ws") as ws:
            ws.send_text(json.dumps({"id": 1, "method": "hello", "params": {"user": VERA, "password": VERA_PW}}))
            message = ws.receive_json()["error"]["message"]
        assert "sealed" in message
        ann = Peer(client, user=ANN, password=ANN_PW)  # an owner brings it up ...
        assert ann.hello["result"]["role"] == "owner"
        vera = Peer(client, user=VERA, password=VERA_PW)  # ... and now the viewer may come in
        assert vera.hello["result"]["role"] == "viewer"
        vera.close()
        ann.close()


def test_a_weak_password_creates_nothing(tmp_path):
    with server(tmp_path) as client:
        peer = Peer(client, doc="draft", user=ANN, password="short", create=True)
        assert peer.hello["error"]["code"] == "bad_request"
        assert "8 characters" in peer.hello["error"]["message"]
        peer.close()
        assert client.get("/api/docs").json()["documents"] == []
    assert list((tmp_path / "docs").iterdir()) == []


def test_the_list_of_documents_shows_sealed_documents_without_a_password(tmp_path):
    with server(tmp_path) as client:
        Peer(client, doc="budget", user=ANN, password=ANN_PW, create=True).close()
    with server(tmp_path) as client:
        listing = client.get("/api/docs").json()["documents"]
        assert [d["id"] for d in listing] == ["budget"]
        assert set(listing[0]) == {"id", "app", "modified", "online"}


@pytest.mark.parametrize("who", ["owner", "newcomer"])
def test_somebody_who_is_not_a_person_of_the_document_cannot_create_it_again(tmp_path, who):
    with server(tmp_path) as client:
        Peer(client, user=ANN, password=ANN_PW, create=True).close()
        user, password = (ANN, "wrong-Pass-1") if who == "owner" else ("Mallory", "Mallory-Pass-1")
        assert refused(client, user=user, password=password, create=True) == (4401, "unauthorized")
