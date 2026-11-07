"""Persisting the server's own settings and its administrators under its state folder."""

from claudia_server.admin import AdminDirectory
from claudia_server.server_settings import (
    AiSettings,
    ServerSettings,
    TypesetSettings,
    load_admins,
    load_settings,
    save_admins,
    save_settings,
)


def test_fresh_settings_when_nothing_was_ever_saved(tmp_path):
    settings = load_settings(tmp_path, default_max_documents=99)
    assert settings.max_documents == 99
    assert settings.access_secret is None
    assert settings.ai == AiSettings()
    assert settings.typeset == TypesetSettings()
    assert settings.changed == {}


def test_settings_round_trip_through_disk(tmp_path):
    settings = ServerSettings(
        max_documents=5,
        access_secret="a-long-enough-secret",
        ai=AiSettings(model_dir="/models/qwen", device="GPU", max_tokens=256, timeout=60.0),
        typeset=TypesetSettings(xelatex="/usr/bin/xelatex", pdftocairo=None),
    )
    settings.note_changed("max_documents", "tobi")
    save_settings(tmp_path, settings)

    loaded = load_settings(tmp_path, default_max_documents=1)
    assert loaded.max_documents == 5
    assert loaded.access_secret == "a-long-enough-secret"
    assert loaded.ai == settings.ai
    assert loaded.typeset == settings.typeset
    assert loaded.changed["max_documents"].by == "tobi"


def test_the_settings_file_is_private(tmp_path):
    save_settings(tmp_path, ServerSettings(max_documents=1))
    path = tmp_path / "admin" / "settings.json"
    assert path.is_file()
    assert (path.stat().st_mode & 0o777) == 0o600


def test_a_damaged_settings_file_does_not_stop_the_server(tmp_path):
    folder = tmp_path / "admin"
    folder.mkdir()
    (folder / "settings.json").write_text("not json", encoding="utf-8")
    settings = load_settings(tmp_path, default_max_documents=7)
    assert settings.max_documents == 7


def test_public_dict_never_carries_the_access_secret_itself():
    settings = ServerSettings(max_documents=5, access_secret="a-long-enough-secret")
    public = settings.to_public_dict()
    assert public["access_secret_set"] is True
    assert "access_secret" not in public
    assert "a-long-enough-secret" not in repr(public)


def test_admins_round_trip_through_disk(tmp_path):
    admins = AdminDirectory(cost=2**4)
    admins.add("tobi", "correct horse battery", added="2026-01-01T00:00:00.000Z")
    save_admins(tmp_path, admins)

    restored = AdminDirectory()
    load_admins(tmp_path, restored)
    assert restored.verify("tobi", "correct horse battery") is not None


def test_loading_admins_when_none_were_ever_saved_leaves_the_directory_empty(tmp_path):
    directory = AdminDirectory()
    load_admins(tmp_path, directory)
    assert len(directory) == 0


def test_a_damaged_admins_file_leaves_the_directory_empty_rather_than_stopping_the_server(tmp_path):
    folder = tmp_path / "admin"
    folder.mkdir()
    (folder / "admins.json").write_text("not json", encoding="utf-8")
    directory = AdminDirectory()
    load_admins(tmp_path, directory)
    assert len(directory) == 0
