"""The random id of a document (D533): found by exact match, kept when a file is placed, never twice on a server."""

import io
import json
import re
import uuid
import zipfile
from pathlib import Path

from starlette.testclient import TestClient
from test_server_import import app_hub, hello, upload

from claudia_composes import TextModel
from claudia_computes import WorkbookModel
from claudia_container import KdfParams, read_manifest
from claudia_server import create_app
from claudia_server.sealed import SealedDocuments
from claudia_server.suite import Module, Suite

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
SECRET = "s" * 20


def server(folder: Path, *, models=(WorkbookModel,), **options):
    """A server on ``folder`` with one sealed store per app."""
    modules = []
    for model in models:
        store = SealedDocuments(folder / model.app, model, kdf=CHEAP)
        modules.append(Module(app_hub(store), store))
    return TestClient(create_app(Suite(modules), **options))


def make(client, name, app="computes"):
    """Make a document and return the welcome it was given."""
    with client.websocket_connect(f"/api/{app}/docs/{name}/ws") as ws:
        ws.send_json(hello(create=True))
        frame = ws.receive_json()
        assert frame["ok"]
        return frame["result"]


def file_of(folder: Path, name, app="computes") -> bytes:
    return (folder / app / "docs" / f"{name}.claudia").read_bytes()


def lookup(client, uid, **headers):
    return client.post("/api/docs/lookup", json={"uid": uid}, headers=headers)


def with_manifest(data: bytes, **changes) -> bytes:
    """The file with some fields of its plain manifest changed: what anybody holding the file could do."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(out, "w") as target:
        for info in source.infolist():
            content = source.read(info)
            if info.filename == "manifest.json":
                content = json.dumps({**json.loads(content), **changes}).encode()
            target.writestr(info, content)
    return out.getvalue()


# --- the uid is the document's, and invisible ------------------------------------------------------------------------
def test_a_new_document_gets_a_random_uid_which_the_client_is_told_and_the_list_is_not(tmp_path):
    with server(tmp_path) as client:
        welcome = make(client, "plan")
        parsed = uuid.UUID(welcome["uid"])
        assert (str(parsed), parsed.version) == (welcome["uid"], 4)
        assert read_manifest(tmp_path / "computes" / "docs" / "plan.claudia").uid == welcome["uid"]
        (row,) = client.get("/api/docs").json()["documents"]
        assert "uid" not in row
        assert welcome["uid"] not in json.dumps(client.get("/api/docs").json())


def test_two_documents_never_share_a_uid(tmp_path):
    with server(tmp_path) as client:
        assert make(client, "one")["uid"] != make(client, "two")["uid"]


def test_a_store_in_memory_has_no_uid_to_tell(tmp_path):
    from claudia_server import Hub, MemoryProvider, ScryptDirectory

    with (
        TestClient(create_app(Hub(MemoryProvider(WorkbookModel)), ScryptDirectory(cost=2**4))) as client,
        client.websocket_connect("/api/docs/plan/ws") as ws,
    ):
        ws.send_json(hello(create=True))
        assert ws.receive_json()["result"]["uid"] is None


# --- looking it up ---------------------------------------------------------------------------------------------------
def test_the_exact_uid_finds_the_document_and_says_where_it_is(tmp_path):
    with server(tmp_path) as client:
        uid = make(client, "plan")["uid"]
        found = lookup(client, uid)
        assert found.status_code == 200
        answer = found.json()
        assert (answer["app"], answer["id"]) == ("computes", "plan")
        assert set(answer) == {"app", "id", "modified"}


def test_the_lookup_searches_every_app_of_the_server(tmp_path):
    with server(tmp_path, models=(WorkbookModel, TextModel)) as client:
        make(client, "numbers")
        uid = make(client, "words", app="composes")["uid"]
        assert lookup(client, uid).json()["app"] == "composes"


def test_an_unknown_and_a_malformed_uid_get_the_same_answer(tmp_path):
    with server(tmp_path) as client:
        make(client, "plan")
        unknown = lookup(client, str(uuid.uuid4()))
        for bad in ["plan", "", "0" * 36, str(uuid.uuid4()).upper(), 7, None, ["x"]]:
            refused = lookup(client, bad)
            assert (refused.status_code, refused.json()) == (unknown.status_code, unknown.json())
        assert unknown.status_code == 404


def test_a_part_of_a_uid_finds_nothing(tmp_path):
    with server(tmp_path) as client:
        uid = make(client, "plan")["uid"]
        assert lookup(client, uid[:8]).status_code == 404
        assert lookup(client, uid[:-1]).status_code == 404


def test_the_lookup_needs_the_access_secret_when_the_server_has_one(tmp_path):
    with server(tmp_path, access_secret=SECRET) as client:
        with client.websocket_connect("/api/computes/docs/plan/ws") as ws:
            ws.send_json(hello(create=True, access=SECRET))
            assert ws.receive_json()["ok"]
        uid = read_manifest(tmp_path / "computes" / "docs" / "plan.claudia").uid
        assert lookup(client, uid).status_code == 401
        assert lookup(client, uid, authorization="Bearer wrong" + "x" * 12).status_code == 401
        assert lookup(client, uid, authorization=f"Bearer {SECRET}").status_code == 200


def test_a_server_that_does_not_list_does_not_look_up_either(tmp_path):
    with server(tmp_path, list_documents=False) as client:
        uid = make(client, "plan")["uid"]
        assert lookup(client, uid).status_code in {404, 405}


def test_one_address_cannot_ask_without_end(tmp_path):
    with server(tmp_path) as client:
        throttle = client.app.state.lookup_throttle
        statuses = [lookup(client, str(uuid.uuid4())).status_code for _ in range(throttle.limit + 3)]
        assert statuses[: throttle.limit] == [404] * throttle.limit
        assert statuses[throttle.limit :] == [429] * 3


def test_behind_a_proxy_people_are_asked_for_by_the_address_the_proxy_appended(tmp_path):
    """D1275: with a trusted proxy one person asking without end does not stop the next one (SEC-02)."""
    with server(tmp_path, proxy_hops=1) as client:
        limit = client.app.state.lookup_throttle.limit
        loud = {"x-forwarded-for": "203.0.113.7"}
        statuses = [lookup(client, str(uuid.uuid4()), **loud).status_code for _ in range(limit + 2)]
        assert statuses[limit:] == [429] * 2
        assert lookup(client, str(uuid.uuid4()), **{"x-forwarded-for": "203.0.113.8"}).status_code == 404


def test_without_a_proxy_a_header_written_by_the_client_buys_no_new_address(tmp_path):
    with server(tmp_path) as client:
        limit = client.app.state.lookup_throttle.limit
        statuses = [
            lookup(client, str(uuid.uuid4()), **{"x-forwarded-for": f"203.0.113.{n}"}).status_code
            for n in range(limit + 2)
        ]
        assert statuses[limit:] == [429] * 2


# --- placing ---------------------------------------------------------------------------------------------------------
def test_a_file_placed_on_another_server_keeps_its_uid_and_is_found_there(tmp_path):
    home, away = tmp_path / "home", tmp_path / "away"
    with server(home) as client:
        uid = make(client, "plan")["uid"]
    data = file_of(home, "plan")
    with server(away) as client:
        token = upload(client, data, name="plan.claudia").json()["upload"]
        assert client.post(f"/api/uploads/{token}/place").status_code == 200
        assert read_manifest(away / "computes" / "docs" / "plan.claudia").uid == uid
        assert lookup(client, uid).json()["id"] == "plan"


def test_the_upload_answer_does_not_show_the_uid_or_a_title(tmp_path):
    home = tmp_path / "home"
    with server(home) as client:
        uid = make(client, "plan")["uid"]
    with server(tmp_path / "away") as client:
        answer = upload(client, file_of(home, "plan"), name="plan.claudia").json()
        assert uid not in json.dumps(answer)
        assert "title" not in answer and "uid" not in answer
        assert answer["same_document"] is None


def test_the_same_document_twice_is_refused_and_said_so_in_plain_words(tmp_path):
    home = tmp_path / "home"
    with server(home) as client:
        make(client, "plan")
    data = file_of(home, "plan")
    with server(tmp_path / "away") as client:
        first = upload(client, data, name="plan.claudia").json()
        assert client.post(f"/api/uploads/{first['upload']}/place").status_code == 200
        again = upload(client, data, name="plan.claudia").json()
        assert (again["exists"], again["same_document"]) == (True, "plan")
        refused = client.post(f"/api/uploads/{again['upload']}/place")
        assert refused.status_code == 409
        assert "already" in refused.json()["detail"] and "plan" in refused.json()["detail"]
        assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}", refused.json()["detail"]), "no uid in a message"


def test_a_file_with_the_uid_of_a_document_here_under_another_name_is_refused(tmp_path):
    home = tmp_path / "home"
    with server(home) as client:
        make(client, "plan")
    data = file_of(home, "plan")
    with server(tmp_path / "away") as client:
        token = upload(client, data, name="plan.claudia").json()["upload"]
        assert client.post(f"/api/uploads/{token}/place").status_code == 200
        copy = upload(client, with_manifest(data, name="other"), name="other.claudia").json()
        assert (copy["exists"], copy["same_document"]) == (False, "plan")
        refused = client.post(f"/api/uploads/{copy['upload']}/place")
        assert refused.status_code == 409 and "plan" in refused.json()["detail"]
        assert not (tmp_path / "away" / "computes" / "docs" / "other.claudia").exists()


def test_the_uid_counts_across_all_apps_of_a_server(tmp_path):
    home = tmp_path / "home"
    with server(home) as client:
        make(client, "plan")
    data = file_of(home, "plan")
    with server(tmp_path / "away", models=(WorkbookModel, TextModel)) as client:
        token = upload(client, data, name="plan.claudia").json()["upload"]
        assert client.post(f"/api/uploads/{token}/place").status_code == 200
        twin = upload(client, with_manifest(data, app="composes"), name="plan.claudia").json()
        assert twin["same_document"] == "plan"
        assert client.post(f"/api/uploads/{twin['upload']}/place").status_code == 409


def test_a_file_without_a_sound_uid_is_not_taken_in(tmp_path):
    home = tmp_path / "home"
    with server(home) as client:
        make(client, "plan")
    with server(tmp_path / "away") as client:
        answer = upload(client, with_manifest(file_of(home, "plan"), uid="plan"), name="plan.claudia")
        assert answer.status_code == 415
