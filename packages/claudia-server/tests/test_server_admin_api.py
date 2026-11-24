"""``/api/admin/*``: the settings pages' own API, signed in to separately from any document."""

import contextlib
import itertools
import json
import sys

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from claudia_core.testing import ListModel
from claudia_server.admin import AdminDirectory
from claudia_server.admin_api import AdminContext, AiRuntime
from claudia_server.admin_sessions import AdminSessions
from claudia_server.admin_start import ResetNote, load_reset_note
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.server_settings import ServerSettings
from claudia_server.setup_code import SetupCode, read_code, write_code

PASSWORD = "correct horse battery"
CODE = "K7QM-4TXR-92HB"  # the setup code of the server under test (D1371)
_DOC_IDS = (f"doc-{n}" for n in itertools.count())


def serve(*, exposed=True, ai_enabled=True, admins=None, settings=None, state_dir=None, hub_options=None):
    hub = Hub(MemoryProvider(ListModel), **(hub_options or {}))
    admin = AdminContext(
        admins=admins if admins is not None else AdminDirectory(cost=2**4),
        sessions=AdminSessions(),
        settings=settings if settings is not None else ServerSettings(max_documents=hub.max_documents),
        state_dir=state_dir,
        ai=AiRuntime(models=(ListModel,), enabled=ai_enabled),
        exposed=exposed,
        setup_code=SetupCode.of(CODE),
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
            "setup_code": True,
        }

    app, _, _ = serve(exposed=False, state_dir=tmp_path / "loopback")
    with TestClient(app) as client:
        assert client.get("/api/admin/status").json() == {
            "needs_administrator": False,
            "exposed": False,
            "administrator": None,
            "setup_code": True,
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
def test_setup_needs_the_setup_code_on_every_server(tmp_path):
    """SEC-12, D1370: without the code, or with a wrong one, nobody becomes the first administrator, loopback too."""
    for exposed in (True, False):
        app, _, admin = serve(exposed=exposed, state_dir=tmp_path / str(exposed))
        with TestClient(app) as client:
            for body in (
                {"name": "mallory", "password": PASSWORD},
                {"name": "mallory", "password": PASSWORD, "code": "K7QM-4TXR-92H8"},
                {"name": "mallory", "password": PASSWORD, "code": 42},
            ):
                response = client.post("/api/admin/setup", json=body)
                assert response.status_code == 403
                assert "setup code" in response.json()["detail"]
            assert len(admin.admins) == 0


def test_the_code_counts_as_typed_and_dies_with_the_first_administrator(tmp_path):
    app, _, admin = serve(state_dir=tmp_path)
    write_code(tmp_path, admin.setup_code)
    with TestClient(app) as client:
        body = {"name": "tobi", "password": PASSWORD, "code": " k7qm 4txr 92hb "}
        assert client.post("/api/admin/setup", json=body).status_code == 200
        assert admin.setup_code is None
        assert read_code(tmp_path) is None
        assert client.get("/api/admin/status").json()["setup_code"] is False


def test_a_server_without_a_code_lets_nobody_set_up(tmp_path):
    app, _, admin = serve(state_dir=tmp_path)
    admin.setup_code = None
    with TestClient(app) as client:
        assert client.get("/api/admin/status").json()["setup_code"] is False
        body = {"name": "tobi", "password": PASSWORD, "code": CODE}
        assert client.post("/api/admin/setup", json=body).status_code == 403


def test_no_answer_contains_the_code(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        for path in ("/api/admin/status",):
            assert "K7QM" not in client.get(path).text
        assert "K7QM" not in client.post("/api/admin/setup", json={"name": "a", "password": "b"}).text
        assert "K7QM" not in client.post("/api/admin/setup-code", json={"code": "nope"}).text


def test_a_code_from_a_link_can_be_checked_first(tmp_path):
    app, _, admin = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/admin/setup-code", json={"code": "k7qm-4txr-92hb"}).status_code == 204
        assert client.post("/api/admin/setup-code", json={"code": "K7QM-4TXR-92H8"}).status_code == 403
        assert client.post("/api/admin/setup-code", json={}).status_code == 403
        assert len(admin.admins) == 0


def test_too_many_wrong_codes_make_an_address_wait_and_the_checks_count(tmp_path):
    app, _, admin = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        wrong = {"name": "mallory", "password": PASSWORD, "code": "0000-0000-0000"}
        assert client.post("/api/admin/setup-code", json={"code": wrong["code"]}).status_code == 403
        for _ in range(3):  # three tries are free, as at the sign-in (D1266); the fourth failure makes it wait
            assert client.post("/api/admin/setup", json=wrong).status_code == 403
        waited = client.post("/api/admin/setup", json={**wrong, "code": CODE})  # even the right one waits now
        assert waited.status_code == 429
        assert int(waited.headers["Retry-After"]) >= 1
        assert waited.json()["retry_after"] >= 1
        assert client.post("/api/admin/setup-code", json={"code": CODE}).status_code == 429
        assert len(admin.admins) == 0


def test_someone_faster_gets_409_also_with_the_right_code(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        assert (
            client.post("/api/admin/setup", json={"name": "ben", "password": PASSWORD, "code": CODE}).status_code == 200
        )
        late = client.post("/api/admin/setup", json={"name": "anna", "password": PASSWORD, "code": CODE})
        assert late.status_code == 409
        assert client.post("/api/admin/setup-code", json={"code": CODE}).status_code == 409


# --------------------------------------------------------------------------------------- the reset note (D1375)
def test_the_reset_note_is_for_administrators_until_one_dismisses_it(tmp_path):
    admins = AdminDirectory(cost=2**4)
    admins.add("carla", PASSWORD, added="2026-11-20T14:05:00Z")
    note = ResetNote("2026-11-20T14:03:12Z", ("anna", "ben"))
    (tmp_path / "admin").mkdir()
    (tmp_path / "admin" / "reset.json").write_text(json.dumps(note.to_data()), encoding="utf-8")
    app, _, admin = serve(admins=admins, state_dir=tmp_path)
    admin.reset_note = note
    with TestClient(app) as client:
        assert client.get("/api/admin/reset-note").status_code == 401
        assert "anna" not in client.get("/api/admin/status").text
        token = client.post("/api/admin/login", json={"name": "carla", "password": PASSWORD}).json()["token"]
        signed = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/admin/reset-note", headers=signed).json() == {
            "at": "2026-11-20T14:03:12Z",
            "previous": ["anna", "ben"],
        }
        assert client.delete("/api/admin/reset-note", headers=signed).status_code == 204
        assert client.get("/api/admin/reset-note", headers=signed).json() is None
        assert load_reset_note(tmp_path) is None
        assert client.delete("/api/admin/reset-note", headers=signed).status_code == 204


def test_setup_becomes_the_first_administrator_and_signs_them_in(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE})
        assert response.status_code == 200
        token = response.json()["token"]
        assert response.json()["admin"] == {"name": "tobi", "added": response.json()["admin"]["added"], "you": True}
        assert client.get("/api/admin/status").json()["needs_administrator"] is False
        assert client.get("/api/admin/me", headers={"Authorization": f"Bearer {token}"}).json() == {"name": "tobi"}


def test_setup_is_refused_once_the_server_has_an_administrator(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE})
        response = client.post("/api/admin/setup", json={"name": "anna", "password": PASSWORD, "code": CODE})
        assert response.status_code == 409


def test_setup_rejects_a_short_password(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/admin/setup", json={"name": "tobi", "password": "short", "code": CODE})
        assert response.status_code == 400


def test_login_with_the_wrong_password_is_refused(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE})
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
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()[
            "token"
        ]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.post("/api/admin/logout", headers=headers).status_code == 204
        assert client.get("/api/admin/me", headers=headers).status_code == 401
        assert client.post("/api/admin/logout", headers=headers).status_code == 204  # signing out twice is fine


# ------------------------------------------------------------------------------------------- administrators
def test_an_administrator_can_add_and_remove_another(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()[
            "token"
        ]
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
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()[
            "token"
        ]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.delete("/api/admin/admins/tobi", headers=headers)
        assert response.status_code == 409


def test_removing_an_administrator_signs_them_out_everywhere(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        tobi_token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()[
            "token"
        ]
        headers = {"Authorization": f"Bearer {tobi_token}"}
        client.post("/api/admin/admins", headers=headers, json={"name": "anna", "password": PASSWORD})
        anna_token = client.post("/api/admin/login", json={"name": "anna", "password": PASSWORD}).json()["token"]
        client.delete("/api/admin/admins/anna", headers=headers)
        response = client.get("/api/admin/me", headers={"Authorization": f"Bearer {anna_token}"})
        assert response.status_code == 401


def test_changing_a_password(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()[
            "token"
        ]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/api/admin/admins/tobi/password", headers=headers, json={"password": "another one"})
        assert response.status_code == 204
        assert client.post("/api/admin/login", json={"name": "tobi", "password": PASSWORD}).status_code == 401
        assert client.post("/api/admin/login", json={"name": "tobi", "password": "another one"}).status_code == 200


# ------------------------------------------------------------------------------------------------------ settings
def test_max_documents_takes_effect_on_the_live_hub_and_is_saved(tmp_path):
    app, hub, _ = serve(state_dir=tmp_path, hub_options={"max_documents": 5})
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()[
            "token"
        ]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put("/api/admin/settings/max-documents", headers=headers, json={"max_documents": 20})
        assert response.status_code == 200
        assert response.json()["max_documents"] == 20
        assert response.json()["changed"]["max_documents"]["by"] == "tobi"
    assert hub.max_documents == 20


def test_max_documents_rejects_nonsense(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()[
            "token"
        ]
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
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()[
            "token"
        ]
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
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()[
            "token"
        ]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put("/api/admin/settings/access-secret", headers=headers, json={"access_secret": "short"})
        assert response.status_code == 400


def test_typeset_settings_are_saved_and_diagnosed(tmp_path):
    """A program that cannot be found is refused with a sentence (SEC-16: nothing is kept that was not seen to run);
    with nothing configured the programs are looked up on the PATH, and the answer says whether they are there."""
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        headers = _admin(client)
        missing = client.put("/api/admin/settings/typeset", headers=headers, json={"xelatex": "/no/such/xelatex"})
        assert missing.status_code == 400
        assert "/no/such/xelatex" in missing.json()["detail"]

        response = client.put(
            "/api/admin/settings/typeset", headers=headers, json={"xelatex": None, "pdftocairo": None}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["typeset"] == {"xelatex": None, "pdftocairo": None}
        assert set(body["typeset_diagnosis"]) == {"xelatex", "pdftocairo"}
        assert client.get("/api/admin/settings", headers=headers).json()["typeset"]["xelatex"] is None


def test_ai_settings_are_refused_when_the_assistant_is_disabled(tmp_path):
    app, _, _ = serve(state_dir=tmp_path, ai_enabled=False)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()[
            "token"
        ]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put("/api/admin/settings/ai", headers=headers, json={"model_dir": None})
        assert response.status_code == 400
        assert "disabled" in response.json()["detail"]


def test_ai_settings_without_a_model_dir_use_the_scripted_stand_in(tmp_path):
    """``ListModel`` has no stand-in or model-driven assistant of its own, so turning the AI "off" (``model_dir``
    ``None``) is the one AI change this test can make without a real OpenVINO model to load."""
    app, hub, admin = serve(state_dir=tmp_path, ai_enabled=True)
    with TestClient(app) as client:
        token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()[
            "token"
        ]
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


# SEC-16: the LaTeX programs are run for every formula, so a setting is accepted only when the program says it is one.


def _program(folder, name: str, says: str, *, to_stderr: bool = False):
    """A stand-in program in ``folder`` that prints ``says`` and ends well."""
    import stat

    script = folder / name
    redirect = " >&2" if to_stderr else ""
    script.write_text(f"#!/bin/sh\necho '{says}'{redirect}\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return str(script)


def _admin(client) -> dict:
    token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.skipif(sys.platform == "win32", reason="the stand-in programs are shell scripts")
def test_a_program_that_is_not_xelatex_is_refused_as_xelatex(tmp_path):
    app, _, _ = serve(state_dir=tmp_path / "state")
    other = _program(tmp_path, "true-ish", "hello")
    with TestClient(app) as client:
        headers = _admin(client)
        response = client.put("/api/admin/settings/typeset", headers=headers, json={"xelatex": other})
        assert response.status_code == 400
        assert "XeTeX" in response.json()["detail"]
        assert client.get("/api/admin/settings", headers=headers).json()["typeset"]["xelatex"] is None


@pytest.mark.skipif(sys.platform == "win32", reason="the stand-in programs are shell scripts")
def test_a_program_that_says_it_is_xelatex_and_pdftocairo_is_kept(tmp_path):
    app, _, _ = serve(state_dir=tmp_path / "state")
    xelatex = _program(tmp_path, "xelatex", "XeTeX 3.141592653-2.6-0.999996 (TeX Live 2025)")
    pdftocairo = _program(tmp_path, "pdftocairo", "pdftocairo version 24.02.0", to_stderr=True)
    with TestClient(app) as client:
        headers = _admin(client)
        response = client.put(
            "/api/admin/settings/typeset", headers=headers, json={"xelatex": xelatex, "pdftocairo": pdftocairo}
        )
        assert response.status_code == 200
        assert response.json()["typeset"] == {"xelatex": xelatex, "pdftocairo": pdftocairo}


@pytest.mark.skipif(sys.platform == "win32", reason="the stand-in programs are shell scripts")
def test_a_program_that_is_not_pdftocairo_is_refused_as_pdftocairo(tmp_path):
    app, _, _ = serve(state_dir=tmp_path / "state")
    other = _program(tmp_path, "echo-ish", "XeTeX 3.14")
    with TestClient(app) as client:
        response = client.put("/api/admin/settings/typeset", headers=_admin(client), json={"pdftocairo": other})
        assert response.status_code == 400
        assert "pdftocairo" in response.json()["detail"]
