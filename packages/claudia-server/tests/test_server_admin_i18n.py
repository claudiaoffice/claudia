"""The administrator API answers in the language of the page that asks (CODE-92, D31, D322).

The web pages send their App Language as ``Accept-Language``; the server's own refusals are messages (``msg``) and are
said in that language, as a document's refusals are said in the language of its connection. Without the header, or in a
language with no catalog, they stay English.
"""

from starlette.testclient import TestClient
from test_server_admin_api import CODE, PASSWORD, serve

from claudia_core.testing import ListModel
from claudia_server.admin import AdminDirectory
from claudia_server.admin_api import AdminContext, AiRuntime
from claudia_server.admin_sessions import AdminSessions
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.login_throttle import LoginThrottle
from claudia_server.server_settings import ServerSettings
from claudia_server.setup_code import SetupCode

GERMAN = {"Accept-Language": "de"}


def _first_admin(client) -> dict:
    token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_a_wrong_sign_in_is_refused_in_german_for_a_german_page(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        _first_admin(client)
        german = client.post("/api/admin/login", json={"name": "tobi", "password": "nope"}, headers=GERMAN)
        english = client.post("/api/admin/login", json={"name": "tobi", "password": "nope"})
    assert german.status_code == english.status_code == 401
    assert german.json()["detail"] == "Falscher Name oder falsches Passwort"
    assert english.json()["detail"] == "wrong name or password"


def test_a_wrong_setup_code_is_refused_in_german(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        answer = client.post("/api/admin/setup-code", json={"code": "AAAA-BBBB-CCCC"}, headers=GERMAN)
    assert answer.status_code == 403
    assert answer.json()["detail"].startswith("Das ist nicht der Einrichtungscode dieses Servers")


def test_a_refusal_with_a_number_in_it_is_said_in_german_with_the_number(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        headers = {**_first_admin(client), **GERMAN}
        answer = client.post("/api/admin/admins", json={"name": "anna", "password": "short"}, headers=headers)
    assert answer.status_code == 400
    assert answer.json()["detail"].startswith("Das Passwort braucht mindestens ")


def test_too_many_tries_are_said_in_german_and_keep_the_wait(tmp_path):
    hub = Hub(MemoryProvider(ListModel))
    admin = AdminContext(
        admins=AdminDirectory(cost=2**4),
        sessions=AdminSessions(),
        settings=ServerSettings(max_documents=hub.max_documents),
        state_dir=tmp_path,
        ai=AiRuntime(models=(ListModel,), enabled=False),
        exposed=True,
        setup_code=SetupCode.of(CODE),
    )
    throttle = LoginThrottle(free_tries=1, clock=lambda: 0.0)  # the clock stands still: the wait never runs out
    app = create_app(hub, ScryptDirectory(), admin=admin, login_throttle=throttle)
    with TestClient(app) as client:
        _first_admin(client)
        for _ in range(2):
            client.post("/api/admin/login", json={"name": "tobi", "password": "nope"})
        waited = client.post("/api/admin/login", json={"name": "tobi", "password": "nope"}, headers=GERMAN)
    assert waited.status_code == 429
    assert waited.json()["detail"].startswith("Zu viele Versuche")
    assert waited.json()["retry_after"] == int(waited.headers["Retry-After"])


def test_a_language_without_a_catalog_is_answered_in_english(tmp_path):
    app, _, _ = serve(state_dir=tmp_path)
    with TestClient(app) as client:
        _first_admin(client)
        answer = client.post(
            "/api/admin/login", json={"name": "tobi", "password": "nope"}, headers={"Accept-Language": "fi"}
        )
    assert answer.json()["detail"] == "wrong name or password"
