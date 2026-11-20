"""An unencrypted export comes back in as a new document (D1272, E2.9): export from one document, upload the zip,
make a new document of it, and compare."""

import base64

from starlette.testclient import TestClient
from test_server_import import app_hub, hello, hosted, request, upload

from claudia_computes import SetCells, WorkbookModel, parse_input
from claudia_container import write_export
from claudia_server import MemoryProvider, create_app
from claudia_server.suite import Module, Suite


def server():
    from claudia_server import ScryptDirectory

    suite = Suite([Module(app_hub(MemoryProvider(WorkbookModel), WorkbookModel), ScryptDirectory(cost=2**4))])
    return TestClient(create_app(suite))


def exported(client, name="source"):
    with client.websocket_connect(f"/api/computes/docs/{name}/ws") as ws:
        ws.send_json(hello(create=True))
        assert ws.receive_json()["ok"]
        doc = hosted(client, "computes", name).document
        doc.execute(SetCells("s1", ((0, 0, parse_input("99")), (1, 0, parse_input("=A1*2")))), author="ann")
        answer = request(ws, "export_claudia", {})
        assert answer["ok"], answer
        return base64.b64decode(answer["result"]["data"]), doc.model.serialize()


def test_the_zip_is_recognised_and_says_what_it_is():
    with server() as client:
        data, _ = exported(client)
        answer = upload(client, data, name="source.claudia-export.zip").json()
        assert answer["format"] == "claudia-export" and answer["kind"] == "Claudia export"
        assert answer["app"] == "computes" and answer["hosted"]


def test_the_upload_says_who_made_the_export_and_when():
    with server() as client:
        data, _ = exported(client)
        answer = upload(client, data, name="source.claudia-export.zip").json()
        assert answer["made_by"] and answer["made_at"].startswith("20")


def test_an_import_makes_a_new_document_with_the_identical_state():
    with server() as client:
        data, state = exported(client)
        token = upload(client, data, name="source.claudia-export.zip").json()["upload"]
        with client.websocket_connect("/api/computes/docs/copy/ws") as ws:
            ws.send_json(hello(user="newowner", create=True, upload=token))
            welcome = ws.receive_json()
            assert welcome["ok"], welcome
            imported = welcome["result"]["imported"]
            assert imported["format"] == "claudia-export" and imported["kept"] is False
            doc = hosted(client, "computes", "copy").document
            assert [e.command.kind for e in doc.log.path(doc.revision)] == ["core.Import"]
            assert doc.model.serialize() == state
            assert request(ws, "ping", None)["ok"]


def test_the_one_who_imports_is_the_author_of_the_import_and_not_the_exporter():
    with server() as client:
        data, _ = exported(client)
        token = upload(client, data).json()["upload"]
        with client.websocket_connect("/api/computes/docs/copy/ws") as ws:
            ws.send_json(hello(user="newowner", create=True, upload=token))
            assert ws.receive_json()["ok"]
            doc = hosted(client, "computes", "copy").document
            assert {e.author for e in doc.log.path(doc.revision)} == {"newowner"}


def test_an_export_of_another_shape_of_state_is_refused_and_nothing_is_made():
    with server() as client:
        wrong = write_export("computes", 999, {"sheets": []}, exporter="x", exported_at="2026-11-19T10:00:00Z")
        token = upload(client, wrong).json()["upload"]
        with client.websocket_connect("/api/computes/docs/copy/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert not ws.receive_json()["ok"]
        assert not client.app.state.suite.module("computes").hub.exists("copy")


def test_a_damaged_export_is_refused_at_the_upload():
    with server() as client:
        data, _ = exported(client)
        broken = data[: len(data) // 2]
        assert upload(client, broken).status_code == 415


def test_an_export_of_an_app_this_server_does_not_host_says_so():
    with server() as client:
        other = write_export("composes", 1, {}, exporter="x", exported_at="2026-11-19T10:00:00Z")
        answer = upload(client, other).json()
        assert answer["app"] == "composes" and answer["hosted"] is False
