"""One server, several apps (D430, D431, D432): the suite of modules, its addresses and its shared limits."""

import asyncio
from typing import ClassVar

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from claudia_core.testing import ListModel
from claudia_server import Hub, MemoryProvider, ScryptDirectory, create_app
from claudia_server.hub import HubError
from claudia_server.suite import Module, Suite

PASSWORD = "correct horse battery"


class OtherList(ListModel):
    """A second kind of document, so that a server can host two apps in a test."""

    app: ClassVar[str] = "test-other"


def module(model, **hub_options):
    return Module(Hub(MemoryProvider(model), **hub_options), ScryptDirectory(cost=2**4))


def two_apps(**options):
    return Suite([module(ListModel), module(OtherList)], **options)


def hello(user="ann", password=PASSWORD, create=True, **extra):
    return {"id": 1, "method": "hello", "params": {"user": user, "password": password, "create": create, **extra}}


def make(client, url, **extra):
    with client.websocket_connect(url) as ws:
        ws.send_json(hello(**extra))
        return ws.receive_json()


# ------------------------------------------------------------------------------------------------------ the suite
def test_a_suite_knows_its_apps_in_the_order_given():
    suite = two_apps()
    assert suite.apps == ("test-list", "test-other")
    assert suite.module("test-other").app == "test-other"
    assert suite.module("composes") is None


def test_a_suite_needs_at_least_one_module_and_each_app_once():
    with pytest.raises(ValueError, match="at least one"):
        Suite([])
    with pytest.raises(ValueError, match="twice"):
        Suite([module(ListModel), module(ListModel)])


def test_one_hub_and_its_directory_make_a_suite_of_one():
    hub = Hub(MemoryProvider(ListModel))
    directory = ScryptDirectory(cost=2**4)
    suite = Suite.single(hub, directory)
    assert suite.apps == ("test-list",) and suite.first.hub is hub and suite.first.directory is directory


def test_an_id_is_found_in_the_first_app_that_has_it():
    suite = two_apps()

    async def scenario():
        await suite.module("test-other").hub.open("notes", create=True)
        assert suite.locate("notes").app == "test-other"
        await suite.module("test-list").hub.open("notes", create=True)
        assert suite.locate("notes").app == "test-list", "the order of the apps decides"
        assert suite.locate("nothing") is None

    asyncio.run(scenario())


def test_a_new_document_goes_to_the_app_asked_for_else_the_first():
    suite = two_apps()
    assert suite.for_new(None).app == "test-list"
    assert suite.for_new("test-other").app == "test-other"
    with pytest.raises(HubError) as refused:
        suite.for_new("composes")
    assert refused.value.code == "bad_request"


def test_the_document_cap_counts_every_app_together():
    suite = two_apps(max_documents=2)

    async def scenario():
        await suite.module("test-list").hub.open("a", create=True)
        await suite.module("test-other").hub.open("b", create=True)
        with pytest.raises(HubError) as full:
            await suite.module("test-other").hub.ensure_room()
        assert full.value.code == "unavailable"
        suite.max_documents = 3
        await suite.module("test-list").hub.ensure_room()
        assert all(m.hub.max_documents == 3 for m in suite)

    asyncio.run(scenario())


def test_the_list_holds_the_documents_of_every_app_newest_first():
    suite = two_apps()

    async def scenario():
        await suite.module("test-list").hub.open("a", create=True)
        await asyncio.sleep(0.002)
        await suite.module("test-other").hub.open("b", create=True)
        return suite.listing()

    listed = asyncio.run(scenario())
    assert [(d["id"], d["app"]) for d in listed] == [("b", "test-other"), ("a", "test-list")]


# ----------------------------------------------------------------------------------------------- over the network
def test_the_list_names_every_app_and_the_documents_of_all_of_them():
    with TestClient(create_app(two_apps())) as client:
        assert make(client, "/api/test-other/docs/b/ws")["ok"]
        body = client.get("/api/docs").json()
        assert body["apps"] == ["test-list", "test-other"]
        assert body["app"] is None, "no single app to greet as"
        assert [(d["id"], d["app"]) for d in body["documents"]] == [("b", "test-other")]
        assert client.get("/api/test-other/docs").json() == {"app": "test-other", "documents": body["documents"]}
        assert client.get("/api/test-list/docs").json() == {"app": "test-list", "documents": []}
        assert client.get("/api/composes/docs").status_code == 404


def test_a_server_of_one_app_answers_as_it_always_did():
    hub = Hub(MemoryProvider(ListModel))
    with TestClient(create_app(hub, ScryptDirectory(cost=2**4))) as client:
        assert client.get("/api/docs").json() == {"app": "test-list", "apps": ["test-list"], "documents": []}


def test_the_same_id_can_live_in_two_apps_and_each_is_its_own_document():
    with TestClient(create_app(two_apps())) as client:
        first = make(client, "/api/test-list/docs/notes/ws")
        second = make(client, "/api/test-other/docs/notes/ws", user="ben")
        assert first["ok"] and first["result"]["app"] == "test-list" and first["result"]["created"]
        assert second["ok"] and second["result"]["app"] == "test-other" and second["result"]["created"]
        listed = client.get("/api/docs").json()["documents"]
        assert sorted((d["id"], d["app"]) for d in listed) == [("notes", "test-list"), ("notes", "test-other")]


def test_an_app_the_server_does_not_serve_is_not_found():
    with TestClient(create_app(two_apps())) as client, client.websocket_connect("/api/composes/docs/notes/ws") as ws:
        ws.send_json(hello())
        answer = ws.receive_json()
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert answer["error"]["code"] == "not_found" and closed.value.code == 4404


def test_the_old_address_opens_the_first_app_that_has_the_id():
    with TestClient(create_app(two_apps())) as client:
        assert make(client, "/api/test-other/docs/plan/ws")["ok"]
        again = make(client, "/api/docs/plan/ws", create=False)
        assert again["ok"] and again["result"]["app"] == "test-other"


def test_the_old_address_makes_a_new_document_in_the_app_hello_names_else_in_the_first():
    with TestClient(create_app(two_apps())) as client:
        assert make(client, "/api/docs/one/ws")["result"]["app"] == "test-list"
        assert make(client, "/api/docs/two/ws", app="test-other")["result"]["app"] == "test-other"


def test_the_protocol_is_described_per_app():
    with TestClient(create_app(two_apps())) as client:
        assert client.get("/api/test-other/protocol").status_code == 200
        assert client.get("/api/protocol").json() == client.get("/api/test-list/protocol").json()
        assert client.get("/api/composes/protocol").status_code == 404


# ------------------------------------------------------------------------------------------------------ /api/health
def test_health_names_the_apps_of_the_server_to_anyone():
    """A shell checks what a server runs even where the document list is behind a secret (D444)."""
    with TestClient(create_app(two_apps())) as client:
        body = client.get("/api/health").json()
    assert body == {"ok": True, "apps": ["test-list", "test-other"]}


def test_health_tells_its_version_only_to_this_computer():
    """The desktop apps find a running server and must know whether it is theirs (D445); the version is nobody else's
    business. It is told when the request comes from this computer to this computer's address: a reverse proxy on the
    same machine forwards from the loopback, but with the public host name."""
    from claudia_server import __version__

    def answer(client, base_url):
        app = create_app(two_apps(), allowed_hosts=["office.example"])
        with TestClient(app, client=(client, 50000), base_url=base_url) as c:
            return c.get("/api/health").json()

    assert answer("127.0.0.1", "http://127.0.0.1:8760")["version"] == __version__
    assert answer("::1", "http://localhost:8760")["version"] == __version__
    assert "version" not in answer("192.0.2.7", "http://127.0.0.1:8760")
    assert "version" not in answer("127.0.0.1", "https://office.example")
