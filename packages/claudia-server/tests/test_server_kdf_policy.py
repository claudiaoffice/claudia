"""The cost of hashing for new documents is measured in the background and applies to new documents (D1267)."""

import threading

import pytest
from starlette.testclient import TestClient

from claudia_core.testing import ListModel
from claudia_document_file import KdfParams, read_manifest
from claudia_server.admin import AdminDirectory
from claudia_server.admin_api import AdminContext, AiRuntime
from claudia_server.admin_sessions import AdminSessions
from claudia_server.app import create_app
from claudia_server.hub import Hub
from claudia_server.kdf_policy import KdfPolicy
from claudia_server.sealed import SealedDocuments
from claudia_server.server_settings import SecuritySettings, ServerSettings, load_settings, save_settings
from claudia_server.setup_code import SetupCode

FLOOR = KdfParams(iterations=3, memory_kib=64 * 1024, lanes=4)
BIG = KdfParams(iterations=4, memory_kib=256 * 1024, lanes=4)
CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
PASSWORD = "correct horse battery"
CODE = "K7QM-4TXR-92HB"  # the setup code of the server under test (D1371)


class Measured:
    """A stand-in for ``calibrate`` that can be held up and counts how it was asked."""

    def __init__(self, result=BIG):
        self.result = result
        self.asked = []
        self.gate = threading.Event()
        self.gate.set()

    def __call__(self, target, **more):
        self.gate.wait(5)
        self.asked.append(target)
        return self.result


def test_until_it_is_measured_the_floor_is_used():
    held = Measured()
    held.gate.clear()
    policy = KdfPolicy(0.75, floor=FLOOR, calibrate=held)
    policy.start()
    assert policy.current() == FLOOR
    assert policy.describe()["measured"] is False
    held.gate.set()
    assert policy.wait(5)
    assert policy.current() == BIG and policy.describe()["measured"] is True


def test_starting_twice_measures_once():
    held = Measured()
    policy = KdfPolicy(0.75, floor=FLOOR, calibrate=held)
    policy.start()
    policy.start()
    assert policy.wait(5)
    assert held.asked == [0.75]


def test_a_new_target_is_measured_again():
    held = Measured()
    policy = KdfPolicy(0.75, floor=FLOOR, calibrate=held)
    policy.start()
    policy.wait(5)
    held.result = FLOOR
    policy.retarget(0.4)
    assert policy.wait(5)
    assert held.asked == [0.75, 0.4] and policy.current() == FLOOR
    assert policy.describe()["target_seconds"] == 0.4


def test_an_old_measuring_does_not_overwrite_a_newer_one():
    held = Measured(result=BIG)
    held.gate.clear()
    policy = KdfPolicy(0.75, floor=FLOOR, calibrate=held)
    policy.start()
    fresh = Measured(result=FLOOR)
    policy._calibrate = fresh  # the next measuring is another one
    policy.retarget(0.3)
    assert policy.wait(5)
    held.gate.set()
    for thread in threading.enumerate():
        if thread.name == "claudia-kdf":
            thread.join(5)
    assert policy.current() == FLOOR


def test_a_failing_measuring_keeps_the_floor():
    def broken(target, **more):
        raise MemoryError

    policy = KdfPolicy(0.75, floor=FLOOR, calibrate=broken)
    policy.start()
    assert policy.wait(5)
    assert policy.current() == FLOOR


@pytest.mark.parametrize("bad", [0, -1, 0.01, 31, float("nan"), float("inf"), "1", True, None])
def test_a_target_outside_what_makes_sense_is_refused(bad):
    with pytest.raises(ValueError, match="seconds"):
        KdfPolicy(0.75, floor=FLOOR).retarget(bad)


def test_new_documents_take_the_cost_as_it_is_when_they_are_made(tmp_path):
    held = Measured(result=CHEAP)
    policy = KdfPolicy(0.75, floor=CHEAP, calibrate=held)
    store = SealedDocuments(tmp_path, ListModel, kdf=policy.current)
    store.add_user("one", "Annabelle", "Correct-Horse-9", "owner")
    assert read_manifest(tmp_path / "docs" / "one.claudia").kdf == CHEAP
    policy._set(KdfParams(iterations=2, memory_kib=128, lanes=1))
    store.add_user("two", "Annabelle", "Correct-Horse-9", "owner")
    assert read_manifest(tmp_path / "docs" / "two.claudia").kdf == KdfParams(iterations=2, memory_kib=128, lanes=1)
    assert read_manifest(tmp_path / "docs" / "one.claudia").kdf == CHEAP, "the first keeps what it was made with"


def test_a_fixed_cost_still_works(tmp_path):
    store = SealedDocuments(tmp_path, ListModel, kdf=CHEAP)
    store.add_user("one", "Annabelle", "Correct-Horse-9", "owner")
    assert read_manifest(tmp_path / "docs" / "one.claudia").kdf == CHEAP


# -- the setting -----------------------------------------------------------------------------------------------------
def test_the_security_setting_round_trips_and_has_a_default(tmp_path):
    assert load_settings(tmp_path, default_max_documents=1).security == SecuritySettings()
    assert SecuritySettings().kdf_target_seconds == 0.75
    settings = ServerSettings(max_documents=1, security=SecuritySettings(kdf_target_seconds=1.5))
    save_settings(tmp_path, settings)
    assert load_settings(tmp_path, default_max_documents=1).security.kdf_target_seconds == 1.5
    assert settings.to_public_dict()["security"] == {"kdf_target_seconds": 1.5}


def test_settings_saved_before_this_existed_still_load(tmp_path):
    save_settings(tmp_path, ServerSettings(max_documents=1))
    path = tmp_path / "admin" / "settings.json"
    import json

    data = json.loads(path.read_text())
    del data["security"]
    path.write_text(json.dumps(data))
    assert load_settings(tmp_path, default_max_documents=1).security == SecuritySettings()


def _serve(tmp_path, policy):
    hub = Hub(__import__("claudia_server.hub", fromlist=["MemoryProvider"]).MemoryProvider(ListModel))
    admin = AdminContext(
        admins=AdminDirectory(cost=2**4),
        sessions=AdminSessions(),
        settings=ServerSettings(max_documents=hub.max_documents),
        state_dir=tmp_path,
        ai=AiRuntime(models=(ListModel,), enabled=True),
        exposed=True,
        kdf=policy,
        setup_code=SetupCode.of(CODE),
    )
    from claudia_server.auth import ScryptDirectory

    return create_app(hub, ScryptDirectory(), admin=admin), admin


def _signed_in(client):
    token = client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD, "code": CODE}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_the_settings_page_shows_what_was_chosen_and_whether_it_is_measured(tmp_path):
    held = Measured()
    policy = KdfPolicy(0.75, floor=FLOOR, calibrate=held)
    policy.start()
    policy.wait(5)
    app, _ = _serve(tmp_path, policy)
    with TestClient(app) as client:
        body = client.get("/api/admin/settings", headers=_signed_in(client)).json()
    assert body["security"] == {"kdf_target_seconds": 0.75}
    assert body["kdf"] == {
        "target_seconds": 0.75,
        "iterations": 4,
        "memory_kib": 256 * 1024,
        "lanes": 4,
        "measured": True,
    }


def test_an_administrator_sets_the_target_and_it_is_measured_again(tmp_path):
    held = Measured()
    policy = KdfPolicy(0.75, floor=FLOOR, calibrate=held)
    app, admin = _serve(tmp_path, policy)
    with TestClient(app) as client:
        headers = _signed_in(client)
        answer = client.put("/api/admin/settings/security", headers=headers, json={"kdf_target_seconds": 1.2})
        assert answer.status_code == 200
        assert answer.json()["security"]["kdf_target_seconds"] == 1.2
        assert policy.wait(5)
    assert held.asked[-1] == 1.2
    assert admin.settings.security.kdf_target_seconds == 1.2
    assert admin.settings.changed["security"].by == "tobi"
    assert load_settings(tmp_path, default_max_documents=1).security.kdf_target_seconds == 1.2


@pytest.mark.parametrize("bad", [0, -2, 100, "fast", None, True])
def test_a_target_that_makes_no_sense_is_refused_and_nothing_changes(tmp_path, bad):
    policy = KdfPolicy(0.75, floor=FLOOR, calibrate=Measured())
    app, admin = _serve(tmp_path, policy)
    with TestClient(app) as client:
        answer = client.put(
            "/api/admin/settings/security", headers=_signed_in(client), json={"kdf_target_seconds": bad}
        )
    assert answer.status_code == 400
    assert admin.settings.security.kdf_target_seconds == 0.75


def test_the_security_setting_needs_an_administrator(tmp_path):
    app, _ = _serve(tmp_path, KdfPolicy(0.75, floor=FLOOR, calibrate=Measured()))
    with TestClient(app) as client:
        assert client.put("/api/admin/settings/security", json={"kdf_target_seconds": 1}).status_code in (401, 403)


def test_a_server_without_a_policy_still_has_the_page(tmp_path):
    hub_app, admin = _serve(tmp_path, None)
    with TestClient(hub_app) as client:
        headers = _signed_in(client)
        body = client.get("/api/admin/settings", headers=headers).json()
        assert body["kdf"] is None
        assert (
            client.put("/api/admin/settings/security", headers=headers, json={"kdf_target_seconds": 1}).status_code
            == 200
        )
