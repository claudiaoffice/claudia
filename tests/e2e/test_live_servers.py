"""The servers the browser tests start hash passwords at the lowest cost the settings allow (PROC-55's follow-up).

A real server measures how hard to make password hashing so that it takes ``kdf_target_seconds`` on its machine (D1267,
0.75 s by default), and making a document hashes three times. The browser tests make hundreds of documents and test
nothing about that cost, so their servers aim at the lowest target a person could set
(``kdf_policy.MIN_TARGET_SECONDS``): two to three times faster to a recovery key. A test that chose a target of its own
keeps it.
"""

from __future__ import annotations

import json
from pathlib import Path

from live import PASSWORD, _http, server

from claudia_server.hub import DEFAULT_MAX_DOCUMENTS
from claudia_server.kdf_policy import MIN_TARGET_SECONDS
from claudia_server.server_settings import SecuritySettings, ServerSettings, load_settings, save_settings


def _target_the_server_uses(url: str, state: Path) -> float:
    """What the running server's settings page says it aims at, asked as its first administrator would."""
    code = (state / "admin" / "setup-code").read_text().strip()
    body = json.dumps({"name": "tobi", "password": PASSWORD, "code": code}).encode()
    status, answer = _http(f"{url}/api/admin/setup", body, {"content-type": "application/json"})
    assert status == 200, answer
    status, settings = _http(f"{url}/api/admin/settings", headers={"Authorization": f"Bearer {answer['token']}"})
    assert status == 200, settings
    return settings["kdf"]["target_seconds"]


def test_a_test_server_aims_at_the_lowest_cost_the_settings_allow(tmp_path):
    with server(tmp_path) as live:
        assert _target_the_server_uses(live.url, tmp_path / "state") == MIN_TARGET_SECONDS


def test_a_test_that_saved_other_settings_keeps_them_and_still_hashes_quickly(tmp_path):
    save_settings(tmp_path / "state", ServerSettings(max_documents=7))
    with server(tmp_path) as live:
        assert _target_the_server_uses(live.url, tmp_path / "state") == MIN_TARGET_SECONDS
    assert load_settings(tmp_path / "state", default_max_documents=DEFAULT_MAX_DOCUMENTS).max_documents == 7


def test_a_test_that_chose_a_target_of_its_own_keeps_it(tmp_path):
    chosen = SecuritySettings().kdf_target_seconds / 2
    save_settings(tmp_path / "state", ServerSettings(max_documents=7, security=SecuritySettings(chosen)))
    with server(tmp_path) as live:
        assert _target_the_server_uses(live.url, tmp_path / "state") == chosen
