"""The servers the browser tests start hash passwords at the lowest cost the settings allow.

A real server measures how hard to make password hashing so that it takes ``kdf_target_seconds`` on its machine (D1267,
0.75 s by default), and making a document hashes three times. The browser tests make hundreds of documents and test
nothing about that cost, so they run at the lowest target a person could set (``kdf_policy.MIN_TARGET_SECONDS``): two to
three times faster to a recovery key, and less time for a race to hide in (PROC-55). A test that saved settings of its
own keeps them.
"""

from __future__ import annotations

from claudia_server.hub import DEFAULT_MAX_DOCUMENTS
from claudia_server.kdf_policy import MIN_TARGET_SECONDS
from claudia_server.server_settings import ServerSettings, load_settings, save_settings
from live import server


def _target(state) -> float:
    return load_settings(state, default_max_documents=DEFAULT_MAX_DOCUMENTS).security.kdf_target_seconds


def test_a_test_server_hashes_at_the_lowest_cost_the_settings_allow(tmp_path):
    with server(tmp_path):
        assert _target(tmp_path / "state") == MIN_TARGET_SECONDS


def test_a_test_that_saved_its_own_settings_keeps_them(tmp_path):
    save_settings(tmp_path / "state", ServerSettings(max_documents=7))
    with server(tmp_path):
        settings = load_settings(tmp_path / "state", default_max_documents=DEFAULT_MAX_DOCUMENTS)
    assert settings.max_documents == 7
    assert settings.security.kdf_target_seconds == 0.75
