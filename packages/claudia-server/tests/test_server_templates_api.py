"""Templates over HTTP: the list and a new presentation from a template (E10.4, E10.22), and Server settings ▸ Templates
(D1537, D1538). Administrators only for the settings; check first, then add."""

import pytest
from starlette.testclient import TestClient

from claudia_core import Document, MemoryStore
from claudia_core.testing import ListModel
from claudia_creates import DefineLayout, SlideModel
from claudia_creates.template import TemplateInfo
from claudia_server import Hub, MemoryProvider, create_app, methods_for
from claudia_server.admin import AdminDirectory
from claudia_server.admin_api import AdminContext, AiRuntime
from claudia_server.admin_sessions import AdminSessions
from claudia_server.auth import ScryptDirectory
from claudia_server.server_settings import ServerSettings
from claudia_server.suite import Module, Suite
from claudia_server.template_library import TemplateLibrary, template_file

PASSWORD = "correct horse battery"
TALK = TemplateInfo("Conference talk", "Talks of twenty minutes", "en")


def a_talk_file(info=TALK):
    doc = Document(SlideModel.empty(), store=MemoryStore())
    doc.execute(DefineLayout("title", "Title"), author="ana")
    return template_file(doc.model, info, exporter="anna", exported_at="2026-11-23T10:00:00Z")


@pytest.fixture
def server(tmp_path):
    admins = AdminDirectory(cost=2**4)
    admins.add("anna", PASSWORD, added="2026-11-01T00:00:00Z")
    library = TemplateLibrary(tmp_path / "state" / "templates")
    hub = Hub(MemoryProvider(SlideModel), methods=methods_for(SlideModel))
    suite = Suite([Module(hub, ScryptDirectory(cost=2**4))])
    admin = AdminContext(
        admins=admins,
        sessions=AdminSessions(),
        settings=ServerSettings(max_documents=20),
        state_dir=tmp_path / "state",
        ai=AiRuntime(models=(ListModel,), enabled=False),
        exposed=True,
        templates=library,
    )
    client = TestClient(create_app(suite, admin=admin, templates=library))
    token = client.post("/api/admin/login", json={"name": "anna", "password": PASSWORD}).json()["token"]
    return client, {"authorization": f"Bearer {token}"}, library


# -- the list and a new presentation ----------------------------------------------------------------------------------


def test_the_list_says_the_built_in_template_in_the_language_asked(server):
    client, _, _ = server
    (basic,) = client.get("/api/templates", params={"locale": "en"}).json()["templates"]
    assert (basic["id"], basic["name"], basic["builtin"]) == ("basic", "Basic", True)


def test_a_template_an_administrator_added_is_on_the_list(server):
    client, admin, library = server
    assert client.post("/api/admin/templates", content=a_talk_file(), headers=admin).status_code == 201
    names = [entry["name"] for entry in client.get("/api/templates").json()["templates"]]
    assert names == ["Basic", "Conference talk"]


def test_a_new_presentation_from_a_template_is_made_in_the_usual_way_with_the_upload(server):
    client, admin, _ = server
    client.post("/api/admin/templates", content=a_talk_file(), headers=admin)
    held = client.post("/api/templates/conference-talk/upload", params={"locale": "en"}).json()
    assert (held["format"], held["app"], held["hosted"]) == ("claudia-export", "creates", True)
    with client.websocket_connect("/api/creates/docs/my-talk/ws") as socket:
        socket.send_json(
            {
                "id": 1,
                "method": "hello",
                "params": {"user": "ann", "password": "Correct-Horse-9", "create": True, "upload": held["upload"]},
            }
        )
        assert socket.receive_json()["id"] == 1
    deck = client.app.state.suite.module("creates").hub._documents["my-talk"].document.model
    assert "Title" in [layout.name for layout in deck.layouts]
    assert len(deck.order) == 1 and deck.template.name == "Conference talk"


def test_an_unknown_template_is_not_found(server):
    client, _, _ = server
    assert client.post("/api/templates/nothing/upload").status_code == 404


def test_a_server_with_an_access_secret_lists_templates_for_those_who_know_it(tmp_path):
    library = TemplateLibrary(tmp_path / "templates")
    hub = Hub(MemoryProvider(SlideModel), methods=methods_for(SlideModel))
    secret = "a-long-enough-secret"
    client = TestClient(create_app(hub, ScryptDirectory(cost=2**4), access_secret=secret, templates=library))
    assert client.get("/api/templates").status_code == 401
    assert client.get("/api/templates", headers={"authorization": f"Bearer {secret}"}).status_code == 200


# -- Server settings ▸ Templates --------------------------------------------------------------------------------------


def test_only_an_administrator_sees_or_changes_the_templates(server):
    client, _, _ = server
    assert client.get("/api/admin/templates").status_code == 401
    assert client.post("/api/admin/templates", content=a_talk_file()).status_code == 401
    assert client.delete("/api/admin/templates/conference-talk").status_code == 401


def test_the_page_lists_the_templates_and_says_which_can_be_removed(server):
    client, admin, _ = server
    client.post("/api/admin/templates", content=a_talk_file(), headers=admin)
    page = client.get("/api/admin/templates", headers=admin).json()
    assert page["format"] == 1
    assert [(t["id"], t["removable"]) for t in page["templates"]] == [("basic", False), ("conference-talk", True)]


def test_a_check_says_what_the_file_would_become_and_changes_nothing(server):
    client, admin, library = server
    said = client.post("/api/admin/templates/check", content=a_talk_file(), headers=admin).json()
    assert (said["name"], said["purpose"], said["language"]) == ("Conference talk", "Talks of twenty minutes", "en")
    assert [entry.id for entry in library.entries()] == ["basic"]


@pytest.mark.parametrize("path", ["/api/admin/templates/check", "/api/admin/templates"])
def test_a_file_that_is_no_template_is_refused_with_a_sentence(server, path):
    client, admin, _ = server
    answer = client.post(path, content=b"not a template", headers=admin)
    assert answer.status_code == 400 and answer.json()["detail"] == "this is not a Claudia export"


def test_a_name_that_is_taken_is_refused_and_nothing_is_added(server):
    client, admin, library = server
    client.post("/api/admin/templates", content=a_talk_file(), headers=admin)
    again = client.post("/api/admin/templates", content=a_talk_file(), headers=admin)
    assert again.status_code == 400 and "already" in again.json()["detail"]
    assert len(library.entries()) == 2


def test_removing_a_template_answers_the_page_and_the_built_in_one_stays(server):
    client, admin, _ = server
    client.post("/api/admin/templates", content=a_talk_file(), headers=admin)
    page = client.delete("/api/admin/templates/conference-talk", headers=admin).json()
    assert [t["id"] for t in page["templates"]] == ["basic"]
    assert client.delete("/api/admin/templates/basic", headers=admin).status_code == 409
    assert client.delete("/api/admin/templates/conference-talk", headers=admin).status_code == 404


def test_a_new_presentation_is_not_even_made_when_no_more_uploads_may_wait(server):
    client, _, _ = server
    client.app.state.gateway.uploads._most_per_address = 0
    assert client.post("/api/templates/basic/upload").status_code == 503
