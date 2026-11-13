"""Where a server keeps its certificate and administrators when nobody says (``state.default_state_dir``).

Not covered before (QA 2026-11-12, 46 %), and the question of the round was where things end up on disk: the
environment wins, then each system's own place for per-user data. The Windows case is ``%APPDATA%`` (roaming), while
the Windows shell keeps its documents and the state it passes in ``%LOCALAPPDATA%`` (CODE-15): a default only a bare
``python -m claudia_server`` reaches.
"""

import stat
import sys
from pathlib import Path

import pytest

from claudia_server import state


def test_the_environment_names_the_folder_first(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDIA_STATE_DIR", str(tmp_path / "here"))
    assert state.default_state_dir() == tmp_path / "here"


@pytest.mark.parametrize(
    ("platform", "env", "expected"),
    [
        ("linux", {"XDG_DATA_HOME": "/xdg"}, Path("/xdg/claudia")),
        ("linux", {}, Path("~/.local/share/claudia")),
        ("darwin", {}, Path("~/Library/Application Support/claudia")),
        ("win32", {"APPDATA": "C:/Users/a/AppData/Roaming"}, Path("C:/Users/a/AppData/Roaming/claudia")),
    ],
)
def test_each_system_has_its_own_place(monkeypatch, platform, env, expected):
    monkeypatch.delenv("CLAUDIA_STATE_DIR", raising=False)
    for name in ("XDG_DATA_HOME", "APPDATA"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(state.sys, "platform", platform)
    monkeypatch.setattr(state.Path, "home", classmethod(lambda cls: Path("~")))
    assert state.default_state_dir() == expected


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_the_folder_and_its_secrets_are_the_owners_alone(tmp_path):
    folder = state.private_dir(tmp_path / "a" / "state")
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    secret = folder / "key.pem"
    state.write_private(secret, b"one")
    state.write_private(secret, b"two")  # replaced whole, never appended to
    assert secret.read_bytes() == b"two"
    assert stat.S_IMODE(secret.stat().st_mode) == 0o600
    assert [p.name for p in folder.iterdir()] == ["key.pem"], "no temporary file is left behind"
