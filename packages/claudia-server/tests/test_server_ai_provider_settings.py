"""Server settings ▸ AI: Claude as the AI provider, behind the administrator's page (E7.11, D264, D266).

Anthropic is the fake of ``claudia_ai.testing``; no test reaches the real one.
"""

import json
import logging

import pytest
from starlette.testclient import TestClient
from test_server_admin_api import CODE, PASSWORD

from claudia_ai import FailureReason
from claudia_ai.testing import FakeAnthropic
from claudia_computes import WorkbookModel
from claudia_server.admin import AdminDirectory
from claudia_server.admin_api import AdminContext, AiRuntime
from claudia_server.admin_sessions import AdminSessions
from claudia_server.ai_desk import Failure
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.computes import computes_methods
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.server_settings import AiSettings, Changed, ServerSettings, load_settings, save_settings
from claudia_server.setup_code import SetupCode

KEY = "sk-ant-test-a7Q2"
OTHER_KEY = "sk-ant-test-b4N8"


@pytest.fixture
def anthropic():
    with FakeAnthropic(key=KEY, answer=lambda messages: "ok") as fake:
        fake.keys.add(OTHER_KEY)
        yield fake


def serve(tmp_path, fake, *, operator_key=None):
    hub = Hub(MemoryProvider(WorkbookModel), methods=computes_methods)
    settings = ServerSettings(max_documents=hub.max_documents)
    admin = AdminContext(
        admins=AdminDirectory(cost=2**4),
        sessions=AdminSessions(),
        settings=settings,
        state_dir=tmp_path,
        ai=AiRuntime(models=(WorkbookModel,), enabled=True, anthropic_key=operator_key, anthropic_url=fake.url),
        exposed=True,
        setup_code=SetupCode.of(CODE),
    )
    return create_app(hub, ScryptDirectory(), admin=admin), hub, admin


def signed_in(client):
    token = client.post("/api/admin/setup", json={"name": "anna", "password": PASSWORD, "code": CODE}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def apply_claude(client, headers, *, key=KEY, model="claude-sonnet-5-5", confirm=True):
    claude = {"model": model, **({"key": key} if key else {}), **({"confirm": True} if confirm else {})}
    return client.put("/api/admin/settings/ai", headers=headers, json={"provider": "claude", "claude": claude})


# -- what the page starts with
def test_a_server_that_never_chose_a_provider_answers_with_the_stand_in_and_holds_no_key(tmp_path, anthropic):
    app, _, _ = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        ai = client.get("/api/admin/settings", headers=signed_in(client)).json()["ai"]
    assert ai["provider"] == "stand-in"
    assert ai["claude"] == {
        "model": "claude-sonnet-5-5",
        "key_set": False,
        "key_tail": None,
        "key_from_operator": False,
        "confirmed": None,
    }


def test_settings_saved_before_the_provider_existed_open_as_local_model_or_stand_in(tmp_path):
    old_local = {
        "max_documents": 5,
        "ai": {"model_dir": "/models/qwen", "device": "GPU", "max_tokens": 9, "timeout": 5},
    }
    old_none = {"max_documents": 5, "ai": {"model_dir": None, "device": "GPU", "max_tokens": 512, "timeout": 180.0}}
    assert ServerSettings.load(old_local).ai.provider == "local"
    assert ServerSettings.load(old_none).ai.provider == "stand-in"


def test_the_saved_settings_keep_the_key_and_the_sentence_and_come_back_the_same(tmp_path):
    settings = ServerSettings(max_documents=5)
    settings.ai = AiSettings(provider="claude")
    settings.ai.claude.key = KEY
    settings.ai.claude.confirmed = Changed("anna", "2026-11-22T10:00:00Z")
    save_settings(tmp_path, settings)
    loaded = load_settings(tmp_path, default_max_documents=5)
    assert loaded.ai.provider == "claude" and loaded.ai.claude.key == KEY
    assert loaded.ai.claude.confirmed == Changed("anna", "2026-11-22T10:00:00Z")


# -- applying Claude
def test_claude_is_applied_with_the_right_key_after_one_test_question(tmp_path, anthropic):
    app, hub, admin = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        headers = signed_in(client)
        response = apply_claude(client, headers)
    assert response.status_code == 200
    ai = response.json()["ai"]
    assert ai["provider"] == "claude" and ai["claude"]["model"] == "claude-sonnet-5-5"
    assert ai["claude"]["confirmed"]["by"] == "anna"
    assert len(anthropic.requests) == 1, "one test question, to find a wrong key where the administrator is looking"
    assert admin.settings.ai.provider == "claude"


def test_the_key_is_not_in_the_text_a_log_or_a_failing_test_prints_for_the_settings():
    settings = AiSettings(provider="claude")
    settings.claude.key = KEY
    assert KEY not in repr(settings) + str(settings)


def test_the_key_is_never_returned_only_its_last_four_characters(tmp_path, anthropic):
    app, _, _ = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        headers = signed_in(client)
        put = apply_claude(client, headers)
        got = client.get("/api/admin/settings", headers=headers)
    for response in (put, got):
        assert KEY not in response.text
        claude = response.json()["ai"]["claude"]
        assert claude["key_set"] is True and claude["key_tail"] == "a7Q2" and "key" not in claude


def test_the_key_is_kept_in_the_private_settings_file_and_nowhere_else(tmp_path, anthropic, caplog):
    caplog.set_level(logging.DEBUG)
    app, _, _ = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        apply_claude(client, signed_in(client))
    saved = json.loads((tmp_path / "admin" / "settings.json").read_text())
    assert saved["ai"]["claude"]["key"] == KEY
    assert KEY not in caplog.text


def test_claude_is_not_applied_before_the_administrator_confirmed_that_content_is_sent(tmp_path, anthropic):
    app, _, admin = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        response = apply_claude(client, signed_in(client), confirm=False)
    assert response.status_code == 400
    assert "Document content is sent to Anthropic when someone asks @ai." in response.json()["detail"]
    assert admin.settings.ai.provider == "stand-in" and anthropic.requests == []


def test_the_sentence_is_asked_again_when_switching_to_claude_but_not_when_only_the_key_changes(tmp_path, anthropic):
    app, _, _ = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        headers = signed_in(client)
        apply_claude(client, headers)
        changed_key = apply_claude(client, headers, key=OTHER_KEY, confirm=False)
        assert changed_key.status_code == 200
        client.put("/api/admin/settings/ai", headers=headers, json={"provider": "stand-in"})
        back = apply_claude(client, headers, key=None, confirm=False)
    assert back.status_code == 400 and "Document content is sent to Anthropic" in back.json()["detail"]
    assert anthropic.requests[-1].key == OTHER_KEY


@pytest.mark.parametrize(
    ("fails", "reason", "sentence"),
    [
        ("key_refused", "key_refused", "Anthropic refused the key."),
        ("credit_used_up", "credit_used_up", "The credit balance at Anthropic is used up."),
        ("rate_limited", "rate_limited", "Anthropic's rate limit was reached."),
        ("overloaded", "overloaded", "Anthropic is overloaded at the moment."),
        ("unknown_model", "unknown_model", "Anthropic does not know the model “claude-sonnet-5-5”."),
    ],
)
def test_a_key_or_model_anthropic_refuses_is_refused_here_with_its_reason_and_nothing_changes(
    tmp_path, anthropic, fails, reason, sentence
):
    anthropic.fail(fails)
    app, _, admin = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        response = apply_claude(client, signed_in(client))
    assert response.status_code == 400
    assert response.json()["reason"] == reason and response.json()["detail"] == sentence
    assert admin.settings.ai.provider == "stand-in" and admin.settings.ai.claude.key is None
    assert (
        not (tmp_path / "admin" / "settings.json").exists()
        or "claude" not in json.loads((tmp_path / "admin" / "settings.json").read_text())["ai"]["claude"]["key"]
    )


def test_an_unreachable_anthropic_is_refused_with_its_reason(tmp_path):
    with FakeAnthropic(key=KEY) as gone:
        app, _, admin = serve(tmp_path, gone)
    with TestClient(app) as client:
        response = apply_claude(client, signed_in(client))
    assert response.json()["reason"] == "unreachable"
    assert admin.settings.ai.provider == "stand-in"


def test_any_model_id_may_be_typed(tmp_path, anthropic):
    app, _, _ = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        apply_claude(client, signed_in(client), model="claude-opus-5-5")
    assert anthropic.requests[0].model == "claude-opus-5-5"


# -- the operator's key and removing the key
def test_a_key_the_operator_gave_wins_over_the_saved_one(tmp_path, anthropic):
    app, _, _ = serve(tmp_path, anthropic, operator_key=OTHER_KEY)
    with TestClient(app) as client:
        headers = signed_in(client)
        response = apply_claude(client, headers, key=KEY)
        view = client.get("/api/admin/settings", headers=headers).json()["ai"]["claude"]
    assert response.status_code == 200
    assert {sent.key for sent in anthropic.requests} == {OTHER_KEY}
    assert view["key_from_operator"] is True and view["key_tail"] == "b4N8"


def test_removing_the_key_leaves_no_key_and_keeps_what_the_administrator_confirmed(tmp_path, anthropic):
    app, _, admin = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        headers = signed_in(client)
        apply_claude(client, headers)
        removed = client.put(
            "/api/admin/settings/ai",
            headers=headers,
            json={"provider": "stand-in", "claude": {"remove_key": True}},
        )
    claude = removed.json()["ai"]["claude"]
    assert claude["key_set"] is False and claude["key_tail"] is None and claude["confirmed"]["by"] == "anna"
    assert admin.settings.ai.claude.key is None


def test_claude_stays_chosen_only_with_a_key(tmp_path, anthropic):
    app, _, admin = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        headers = signed_in(client)
        apply_claude(client, headers)
        response = client.put(
            "/api/admin/settings/ai", headers=headers, json={"provider": "claude", "claude": {"remove_key": True}}
        )
    assert response.status_code == 400
    assert admin.settings.ai.claude.key == KEY


# -- the local model's settings are as before
def test_the_local_model_is_chosen_as_before(tmp_path, anthropic):
    app, hub, admin = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        response = client.put("/api/admin/settings/ai", headers=signed_in(client), json={"model_dir": None})
    assert response.status_code == 200
    assert response.json()["ai"]["provider"] == "stand-in" and admin.ai.runner is None


# -- what answers now, and what went wrong with it last
def test_the_page_says_what_answers_now_and_that_nothing_went_wrong(tmp_path, anthropic):
    app, _, _ = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        ai = client.get("/api/admin/settings", headers=signed_in(client)).json()["ai"]
    assert ai["answering"] == {"provider": "stand-in", "label": "Scripted stand-in", "remote": False, "note": ""}
    assert ai["last_error"] is None


def test_after_applying_claude_the_page_says_claude_answers_now_and_that_it_is_remote(tmp_path, anthropic):
    app, _, _ = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        headers = signed_in(client)
        assert apply_claude(client, headers).status_code == 200
        ai = client.get("/api/admin/settings", headers=headers).json()["ai"]
    assert ai["answering"] == {"provider": "claude", "label": "Claude · claude-sonnet-5-5", "remote": True, "note": ""}


def test_the_page_gives_the_reason_of_the_last_failure_in_the_administrators_words(tmp_path, anthropic):
    app, _, admin = serve(tmp_path, anthropic)
    with TestClient(app) as client:
        headers = signed_in(client)
        apply_claude(client, headers, model="claude-x")
        admin.ai.desk.health.failed(
            Failure("claude", FailureReason.UNKNOWN_MODEL, "no such model", "2026-11-22T10:00:00Z")
        )
        ai = client.get("/api/admin/settings", headers=headers).json()["ai"]
    assert ai["last_error"] == {
        "provider": "claude",
        "reason": "unknown_model",
        "sentence": "Anthropic does not know the model “claude-x”.",
        "when": "2026-11-22T10:00:00Z",
    }
