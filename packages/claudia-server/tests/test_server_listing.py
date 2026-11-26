"""The list of documents on a server: ``GET /api/docs`` (supersedes D50's "no list")."""

import asyncio
from contextlib import contextmanager

from list_app import list_methods
from starlette.testclient import TestClient

from claudia_core.testing import Insert, ListModel
from claudia_creates import SlideModel
from claudia_document_file import KdfParams
from claudia_server import Hub, MemoryProvider, ScryptDirectory, create_app
from claudia_server.filestore import FileProvider
from claudia_server.sealed import SealedDocuments

PASSWORD = "correct horse battery"


def serve(provider, **options):
    return TestClient(create_app(Hub(provider, methods=list_methods), ScryptDirectory(cost=2**4), **options))


def test_an_empty_server_lists_nothing():
    with serve(MemoryProvider(ListModel)) as client:
        reply = client.get("/api/docs")
        assert reply.status_code == 200 and reply.json() == {"app": "test-list", "apps": ["test-list"], "documents": []}


def test_documents_are_listed_with_app_time_and_people_online():
    provider = MemoryProvider(ListModel)
    with serve(provider) as client:
        for doc_id in ("alpha", "beta"):
            with client.websocket_connect(f"/api/docs/{doc_id}/ws") as ws:
                ws.send_json(
                    {"id": 1, "method": "hello", "params": {"user": "ann", "password": PASSWORD, "create": True}}
                )
                assert ws.receive_json()["ok"]
                if doc_id == "beta":
                    ws.send_json({"id": 2, "method": "insert", "params": {"index": 0, "value": 1}})
                    while ws.receive_json().get("id") != 2:
                        pass
                    listed = client.get("/api/docs").json()["documents"]
                    assert {d["id"]: d["online"] for d in listed} == {"alpha": 0, "beta": 1}
        listed = client.get("/api/docs").json()["documents"]
        assert [d["id"] for d in listed] == ["beta", "alpha"], "most recently changed first"
        assert all(set(d) == {"id", "app", "modified", "online", "description", "tags"} for d in listed)
        assert listed[0]["app"] == "test-list" and listed[0]["modified"].endswith("Z")


def test_the_list_shows_no_names_and_no_content():
    provider = MemoryProvider(ListModel)
    with serve(provider) as client:
        with client.websocket_connect("/api/docs/alpha/ws") as ws:
            ws.send_json({"id": 1, "method": "hello", "params": {"user": "ann", "password": PASSWORD, "create": True}})
            ws.receive_json()
        text = client.get("/api/docs").text
        assert "ann" not in text and PASSWORD not in text


def test_listing_can_be_switched_off():
    with serve(MemoryProvider(ListModel), list_documents=False) as client:
        assert client.get("/api/docs").status_code == 404


def test_the_list_tells_which_app_the_server_hosts_so_that_a_new_document_can_be_the_right_kind(tmp_path):
    with serve(MemoryProvider(SlideModel)) as client:
        assert client.get("/api/docs").json()["app"] == "creates"
    with serve(FileProvider(tmp_path, ListModel)) as client:
        assert client.get("/api/docs").json()["app"] == "test-list"


def test_the_list_reads_a_file_store(tmp_path):
    provider = FileProvider(tmp_path, ListModel)
    provider.create("kept").execute(Insert(0, 1), author="ann")
    with serve(FileProvider(tmp_path, ListModel)) as client:
        assert [d["id"] for d in client.get("/api/docs").json()["documents"]] == ["kept"]


def test_hub_listing_counts_each_person_once():
    async def scenario():
        hub = Hub(MemoryProvider(ListModel))
        hosted = await hub.open("plan", create=True)
        from claudia_server.auth import Account

        hosted.connect(Account("ann", "owner"), lambda text: None)
        hosted.connect(Account("ann", "owner"), lambda text: None)
        hosted.connect(Account.assistant(), lambda text: None)
        return hub.listing()

    (info,) = asyncio.run(scenario())
    assert info["online"] == 1


# ------------------------------------------------------------------------- description and tags (plain manifest)
SEALED_PASSWORD = "Correct-Horse-9"
CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)


def sealed_server(tmp_path):
    """A server on a folder of document files: the store is the directory too."""
    store = SealedDocuments(tmp_path, ListModel, kdf=CHEAP)
    return store, TestClient(create_app(Hub(store), store))


@contextmanager
def made(client, doc_id, user="ann", password=SEALED_PASSWORD):
    """A person who made the document ``doc_id`` and is connected to it."""
    with client.websocket_connect(f"/api/docs/{doc_id}/ws") as sock:
        sock.send_json({"id": 1, "method": "hello", "params": {"user": user, "password": password, "create": True}})
        assert sock.receive_json()["ok"]
        yield sock


def call(sock, method, params, request_id=2):
    sock.send_json({"id": request_id, "method": method, "params": params})
    while True:
        frame = sock.receive_json()
        if frame.get("id") == request_id:
            return frame


def test_the_list_carries_description_and_tags_and_empty_ones_by_default(tmp_path):
    provider, client = sealed_server(tmp_path)
    with client:
        with made(client, "alpha"):
            pass
        (entry,) = client.get("/api/docs").json()["documents"]
        assert entry["description"] == "" and entry["tags"] == []
        assert set(entry) == {"id", "app", "modified", "online", "description", "tags"}


def test_the_owner_sets_description_and_tags_and_anyone_can_read_them_in_the_list(tmp_path):
    provider, client = sealed_server(tmp_path)
    with client:
        with made(client, "alpha") as sock:
            frame = call(
                sock,
                "set_details",
                {"password": SEALED_PASSWORD, "description": "Q3 **budget**", "tags": ["Finance", "q3"]},
            )
            assert frame["ok"] and frame["result"] == {"description": "Q3 **budget**", "tags": ["finance", "q3"]}
        (entry,) = client.get("/api/docs").json()["documents"]
        assert entry["description"] == "Q3 **budget**" and entry["tags"] == ["finance", "q3"]


def test_details_are_plain_in_the_file_so_that_they_need_no_password(tmp_path):
    from claudia_document_file import read_manifest

    provider, client = sealed_server(tmp_path)
    with client, made(client, "alpha") as sock:
        assert call(sock, "set_details", {"password": SEALED_PASSWORD, "description": "open to all", "tags": ["x"]})[
            "ok"
        ]
    manifest = read_manifest(tmp_path / "docs" / "alpha.claudia")  # the file anybody can see in the folder
    assert manifest.description == "open to all" and manifest.tags == ("x",)


def test_a_wrong_password_cannot_change_the_details(tmp_path):
    provider, client = sealed_server(tmp_path)
    with client, made(client, "alpha") as sock:
        wrong = call(sock, "set_details", {"password": "not the password", "description": "x", "tags": []})
        assert not wrong["ok"] and wrong["error"]["code"] == "unauthorized"
    (entry,) = client.get("/api/docs").json()["documents"]
    assert entry["description"] == "" and entry["tags"] == []


def test_an_editor_may_change_the_details_with_their_own_password(tmp_path):
    provider, client = sealed_server(tmp_path)
    with client:
        with made(client, "alpha"):
            provider.add_user("alpha", "bob", "Another-Pass-77", "editor")
        with client.websocket_connect("/api/docs/alpha/ws") as other:
            other.send_json({"id": 1, "method": "hello", "params": {"user": "bob", "password": "Another-Pass-77"}})
            assert other.receive_json()["ok"]
            done = call(other, "set_details", {"password": "Another-Pass-77", "description": "by bob", "tags": ["B"]})
            assert done["ok"] and done["result"] == {"description": "by bob", "tags": ["b"]}
            wrong = call(other, "set_details", {"password": SEALED_PASSWORD, "description": "x", "tags": []})
            assert not wrong["ok"] and wrong["error"]["code"] == "unauthorized"  # the owner's password is not bob's
        (entry,) = client.get("/api/docs").json()["documents"]
        assert entry["description"] == "by bob" and entry["tags"] == ["b"]


def test_a_viewer_cannot_change_the_details(tmp_path):
    provider, client = sealed_server(tmp_path)
    with client:
        with made(client, "alpha"):
            provider.add_user("alpha", "vera", "Another-Pass-77", "viewer")
        with client.websocket_connect("/api/docs/alpha/ws") as other:
            other.send_json({"id": 1, "method": "hello", "params": {"user": "vera", "password": "Another-Pass-77"}})
            assert other.receive_json()["ok"]
            refused = call(other, "set_details", {"password": "Another-Pass-77", "description": "x", "tags": []})
            assert not refused["ok"] and refused["error"]["code"] == "forbidden"
        (entry,) = client.get("/api/docs").json()["documents"]
        assert entry["description"] == "" and entry["tags"] == []


def test_details_that_do_not_fit_are_refused_with_a_sentence(tmp_path):
    provider, client = sealed_server(tmp_path)
    with client, made(client, "alpha") as sock:
        too_long = call(sock, "set_details", {"password": SEALED_PASSWORD, "description": "x" * 5000, "tags": []})
        assert not too_long["ok"] and too_long["error"]["code"] == "command_error"
        many = call(
            sock,
            "set_details",
            {"password": SEALED_PASSWORD, "description": "", "tags": [f"t{i}" for i in range(50)]},
        )
        assert not many["ok"] and many["error"]["code"] == "command_error"


def test_a_store_that_cannot_hold_details_says_so(tmp_path):
    with serve(MemoryProvider(ListModel)) as client, made(client, "alpha") as sock:
        frame = call(sock, "set_details", {"password": SEALED_PASSWORD, "description": "x", "tags": []})
        assert not frame["ok"] and frame["error"]["code"] in {"unavailable", "forbidden"}
