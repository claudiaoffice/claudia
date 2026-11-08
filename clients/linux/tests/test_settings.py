"""The shell's own persisted settings (E5.7, D31): see settings.py. No GTK import, runs without a display."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claudia_shell_gtk.settings import load_shell_locale, save_shell_locale


def test_nothing_saved_yet_is_none(tmp_path: Path) -> None:
    assert load_shell_locale(tmp_path / "shell.json") is None


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "shell.json"
    save_shell_locale("de", path)
    assert load_shell_locale(path) == "de"


def test_save_creates_the_config_folder_if_it_does_not_exist_yet(tmp_path: Path) -> None:
    path = tmp_path / "not-yet-created" / "shell.json"
    save_shell_locale("de", path)
    assert load_shell_locale(path) == "de"


def test_a_later_save_overwrites_the_earlier_one(tmp_path: Path) -> None:
    path = tmp_path / "shell.json"
    save_shell_locale("de", path)
    save_shell_locale("en", path)
    assert load_shell_locale(path) == "en"


def test_malformed_json_is_treated_as_nothing_saved(tmp_path: Path) -> None:
    path = tmp_path / "shell.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_shell_locale(path) is None


def test_json_that_is_not_an_object_is_treated_as_nothing_saved(tmp_path: Path) -> None:
    path = tmp_path / "shell.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_shell_locale(path) is None


def test_a_missing_or_non_string_locale_key_is_treated_as_nothing_saved(tmp_path: Path) -> None:
    path = tmp_path / "shell.json"
    path.write_text(json.dumps({"other": "thing"}), encoding="utf-8")
    assert load_shell_locale(path) is None
    path.write_text(json.dumps({"locale": 7}), encoding="utf-8")
    assert load_shell_locale(path) is None
    path.write_text(json.dumps({"locale": ""}), encoding="utf-8")
    assert load_shell_locale(path) is None


def test_saving_where_nothing_can_be_written_does_not_raise(tmp_path: Path) -> None:
    """A read-only home or a full disk must never crash the shell over a settings write (settings.py's docstring)."""
    blocked_file = tmp_path / "not-a-folder"
    blocked_file.write_text("", encoding="utf-8")
    save_shell_locale("de", blocked_file / "shell.json")  # blocked_file is a file, not a folder: mkdir must fail
    assert load_shell_locale(blocked_file / "shell.json") is None


def test_the_default_path_is_under_paths_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_shell_locale("de")
    assert (tmp_path / "claudia" / "shell.json").is_file()
    assert load_shell_locale() == "de"
