"""The list of documents on a server: ``GET /api/docs`` (supersedes D50's "no list")."""

import asyncio

from starlette.testclient import TestClient

from claudia_core.testing import Insert, ListModel
from claudia_server import Hub, MemoryProvider, ScryptDirectory, create_app
from claudia_server.filestore import FileProvider

PASSWORD = "correct horse battery"


def serve(provider, **options):
    return TestClient(create_app(Hub(provider), ScryptDirectory(cost=2**4), **options))


def test_an_empty_server_lists_nothing():
    with serve(MemoryProvider(ListModel)) as client:
        reply = client.get("/api/docs")
        assert reply.status_code == 200 and reply.json() == {"documents": []}


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
                    ws.send_json(
                        {
                            "id": 2,
                            "method": "apply",
                            "params": {"command": {"k": "list.Insert", "s": 1, "d": {"index": 0, "value": 1}}},
                        }
                    )
                    while ws.receive_json().get("id") != 2:
                        pass
                    listed = client.get("/api/docs").json()["documents"]
                    assert {d["id"]: d["online"] for d in listed} == {"alpha": 0, "beta": 1}
        listed = client.get("/api/docs").json()["documents"]
        assert [d["id"] for d in listed] == ["beta", "alpha"], "most recently changed first"
        assert all(set(d) == {"id", "app", "modified", "online"} for d in listed)
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
