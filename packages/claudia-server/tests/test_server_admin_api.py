"""``/api/admin/*``: the settings pages' own API, signed in to separately from any document."""

import contextlib
import itertools
import json

from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from claudia_core.testing import ListModel
from claudia_server.admin import AdminDirectory
from claudia_server.admin_api import AdminContext, AiRuntime
from claudia_server.admin_sessions import AdminSessions
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.server_settings import ServerSettings

PASSWORD = "correct horse battery"
_DOC_IDS = (f"doc-{n}" for n in itertools.count())


def serve(*, exposed=True, ai_enabled=True, admins=None, settings=None, state_dir=None, hub_options=None):
    hub = Hub(MemoryProvider(ListModel), **(hub_options or {}))
    admin = AdminContext(
        admins=admins if admins is not None else AdminDirectory(cost=2**4),
        sessions=AdminSessions(),
        settings=settings if settings is not None else ServerSettings(max_documents=hub.max_documents),
        state_dir=state_dir,
        ai=AiRuntime(model=ListModel, enabled=ai_enabled),
        exposed=exposed,
    )
    app = create_app(hub, ScryptDirectory(), admin=admin)
    return app, hub, admin


def hello(user="ann", password=PASSWORD, create=True, **extra):
    params = {"user": user, "password": password, "create": create, **extra}
    return json.dumps({"id": 1, "method": "hello", "params": params})


# ------------------------------------------------------------------------------------------------------- status
def test_status_says_an_administrator_is_needed_only_when_exposed_and_none_exists(tmp_path):
    app, _, _ = serve(exposed=True, state_dir=tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/admin/status").json() == {
            "needs_administrator": True,
            "exposed": True,
            "administrator": None,
        }

    app, _, _ = serve(exposed=False, state_dir=tmp_path / "loopback")
    with TestClient(app) as client:
        assert client.get("/api/admin/status").json() == {
            "needs_administrator": False,
            "exposed": False,
            "administrator": None,
        }


def test_status_names_the_earliest_added_administrator_once_one_exists(tmp_path):
    admins = AdminDirectory(cost=2**4)
    admins.add("tobi", PASSWORD, added="2026-11-01T00:00:00Z")
    app, _, _ = serve(exposed=True, admins=admins, state_dir=tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/admin/status").json()["administrator"] == "tobi"

    # a second administrator, added later, does not change the hint ...
    admins.add("anna", PASSWORD, added="2026-11-05T00:00:00Z")
    with TestClient(app) as client:
        assert client.get("/api/admin/status").json()["administrator"] == "tobi"

    # ... until the first one is removed, at which point the earliest of those remaining takes over
    admins.remove("tobi")
    with TestClient(app) as client:
        assert client.get("/api/admin/status").json()["administrator"] == "anna"


# -------------------------------------------------------------------------------------------- setup, login, me
def test_setup_becomes_the_first_administrator_and_signs_them_in(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD})
        assert response.status_code == 200
        token = response.json()["token"]
        assert response.json()["admin"] == {"name": "tobi", "added": response.json()["admin"]["added"], "you": True}
        assert client.get("/api/admin/status").json()["needs_administrator"] is False
        assert client.get("/api/admin/me", headers={"Authorization": f"Bearer {token}"}).json() == {"name": "tobi"}


def test_setup_is_refused_once_the_server_has_an_administrator(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD})
        response = client.post("/api/admin/setup", json={"name": "anna", "password": PASSWORD})
        assert response.status_code == 409


def test_setup_rejects_a_short_password(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/admin/setup", json={"name": "tobi", "password": "short"})
        assert response.status_code == 400


def test_login_with_the_wrong_password_is_refused(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD})
        assert client.post("/api/admin/login", json={"name": "tobi", "password": "wrong"}).status_code == 401
        response = client.post("/api/admin/login", json={"name": "tobi", "password": PASSWORD})
        assert response.status_code == 200
        assert "token" in response.json()


def test_every_route_but_status_setup_and_login_needs_a_session(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/admin/me").status_code == 401
        assert client.get("/api/admin/admins").status_code == 401
        assert client.get("/api/admin/settings").status_code == 401
        response = client.get("/api/admin/me")
        assert response.headers["www-authenticate"] == "Bearer"


def test_logout_ends_the_session(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.post("/api/admin/logout", headers=headers).status_code == 204
        assert client.get("/api/admin/me", headers=headers).status_code == 401
        assert client.post("/api/admin/logout", headers=headers).status_code == 204  # signing out twice is fine


# ------------------------------------------------------------------------------------------- administrators
def test_an_administrator_can_add_and_remove_another(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        added = client.post("/api/admin/admins", headers=headers, json={"name": "anna", "password": PASSWORD})
        assert added.status_code == 200 and added.json()["you"] is False
        names = {a["name"] for a in client.get("/api/admin/admins", headers=headers).json()}
        assert names == {"tobi", "anna"}
        assert client.delete("/api/admin/admins/anna", headers=headers).status_code == 204
        names = {a["name"] for a in client.get("/api/admin/admins", headers=headers).json()}
        assert names == {"tobi"}


def test_the_last_administrator_cannot_be_removed_through_the_api(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.delete("/api/admin/admins/tobi", headers=headers)
        assert response.status_code == 409


def test_removing_an_administrator_signs_them_out_everywhere(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        tobi_token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).json()["token"]
        headers = {"Authorization": f"Bearer {tobi_token}"}
        client.post("/api/admin/admins", headers=headers, json={"name": "anna", "password": PASSWORD})
        anna_token = client.post("/api/admin/login", json={"name": "anna", "password": PASSWORD}).json()["token"]
        client.delete("/api/admin/admins/anna", headers=headers)
        response = client.get("/api/admin/me", headers={"Authorization": f"Bearer {anna_token}"})
        assert response.status_code == 401


def test_changing_a_password(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/api/admin/admins/tobi/password", headers=headers, json={"password": "another one"})
        assert response.status_code == 204
        assert client.post("/api/admin/login", json={"name": "tobi", "password": PASSWORD}).status_code == 401
        assert client.post("/api/admin/login", json={"name": "tobi", "password": "another one"}).status_code == 200


# ------------------------------------------------------------------------------------------------------ settings
def test_max_documents_takes_effect_on_the_live_hub_and_is_saved(tmp_path):
    app, hub, _ = serve(state_dir=tmp_path, hub_options={"max_documents": 5})
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put("/api/admin/settings/max-documents", headers=headers, json={"max_documents": 20})
        assert response.status_code == 200
        assert response.json()["max_documents"] == 20
        assert response.json()["changed"]["max_documents"]["by"] == "tobi"
    assert hub.max_documents == 20


def test_max_documents_rejects_nonsense(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        for bad in (0, -1, "many", True):
            assert (
                client.put(
                    "/api/admin/settings/max-documents", headers=headers, json={"max_documents": bad}
                ).status_code
                == 400
            )


def test_the_access_secret_can_be_revealed_set_and_rotated_and_takes_effect_live(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/admin/settings/access-secret", headers=headers).json() == {"access_secret": None}

        assert answer_create(client) == "ok"  # nobody needs a secret yet

        put = client.put("/api/admin/settings/access-secret", headers=headers, json={"access_secret": "a" * 20})
        assert put.status_code == 200 and put.json()["access_secret_set"] is True
        assert client.get("/api/admin/settings/access-secret", headers=headers).json() == {"access_secret": "a" * 20}

        assert answer_create(client) != "ok"  # the secret is now required

        rotated = client.post("/api/admin/settings/access-secret/rotate", headers=headers)
        assert rotated.status_code == 200
        new_secret = rotated.json()["access_secret"]
        assert new_secret != "a" * 20
        assert answer_create(client, access="a" * 20) != "ok"  # the old secret stopped working
        assert answer_create(client, access=new_secret) == "ok"
        assert client.get("/api/admin/me", headers=headers).status_code == 200  # rotating never signs anyone out


def test_the_access_secret_is_rejected_when_too_short(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put("/api/admin/settings/access-secret", headers=headers, json={"access_secret": "short"})
        assert response.status_code == 400


def test_typeset_settings_are_saved_and_diagnosed(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put(
            "/api/admin/settings/typeset",
            headers=headers,
            json={"xelatex": "/no/such/xelatex", "pdftocairo": None},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["typeset"]["xelatex"] == "/no/such/xelatex"
        assert body["typeset_diagnosis"]["xelatex"]["ok"] is False
        assert (
            "install" in body["typeset_diagnosis"]["xelatex"]["detail"].lower()
            or body["typeset_diagnosis"]["xelatex"]["detail"]
        )

        settings_view = client.get("/api/admin/settings", headers=headers).json()
        assert settings_view["typeset"]["xelatex"] == "/no/such/xelatex"


def test_ai_settings_are_refused_when_the_assistant_is_disabled(tmp_path):
    app, _, _ = serve(state_dir=tmp_path, ai_enabled=False)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put("/api/admin/settings/ai", headers=headers, json={"model_dir": None})
        assert response.status_code == 400
        assert "disabled" in response.json()["detail"]


def test_ai_settings_without_a_model_dir_use_the_scripted_stand_in(tmp_path):
    """``ListModel`` has no stand-in or model-driven assistant of its own, so turning the AI "off" (``model_dir``
    ``None``) is the one AI change this test can make without a real OpenVINO model to load."""
    app, hub, admin = serve(state_dir=tmp_path, ai_enabled=True)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put("/api/admin/settings/ai", headers=headers, json={"model_dir": None})
        assert response.status_code == 200
        assert response.json()["ai"]["model_dir"] is None
    assert hub.assistant is None  # ListModel has no stand-in: apply() correctly set it to None
    assert admin.ai.runner is None


def answer_create(client, **extra):
    """``"ok"`` if a brand-new document (its own, never used before) could be made, else the error code."""
    with client.websocket_connect(f"/api/docs/{next(_DOC_IDS)}/ws") as ws:
        ws.send_text(hello(**extra))
        frame = ws.receive_json()
        if frame["ok"]:
            return "ok"
        with contextlib.suppress(WebSocketDisconnect):
            ws.receive_json()
        return frame["error"]["code"]
