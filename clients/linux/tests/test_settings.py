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


# ------------------------------------------------------------------ the remembered servers and trusted certificates


def test_one_file_holds_the_language_the_servers_and_the_trusted_certificates_without_one_erasing_another(
    tmp_path: Path,
) -> None:
    """The file used to hold only the locale and was rewritten whole; every key must survive every other's save."""
    from claudia_shell_gtk.settings import load_servers, load_trusted, save_servers, save_trusted

    path = tmp_path / "shell.json"
    save_shell_locale("de", path)
    save_servers("computes", [{"origin": "https://a.example.org", "label": "A", "custom": False}], path)
    save_trusted({"https://a.example.org": {"sha256": "ab" * 32, "since": "2026-11-10"}}, path)
    save_shell_locale("en", path)
    assert load_shell_locale(path) == "en"
    assert [e["origin"] for e in load_servers("computes", path)] == ["https://a.example.org"]
    assert load_trusted(path) == {"https://a.example.org": {"sha256": "ab" * 32, "since": "2026-11-10"}}


def test_each_app_has_its_own_server_list(tmp_path: Path) -> None:
    from claudia_shell_gtk.settings import load_servers, save_servers

    path = tmp_path / "shell.json"
    save_servers("computes", [{"origin": "https://sheets.example.org", "label": "S", "custom": False}], path)
    save_servers("creates", [{"origin": "https://slides.example.org", "label": "L", "custom": False}], path)
    assert [e["origin"] for e in load_servers("computes", path)] == ["https://sheets.example.org"]
    assert [e["origin"] for e in load_servers("creates", path)] == ["https://slides.example.org"]
    assert load_servers("composes", path) == []


def test_a_saved_list_is_cleaned_on_the_way_in_and_on_the_way_out(tmp_path: Path) -> None:
    from claudia_shell_gtk.settings import load_servers, save_servers

    path = tmp_path / "shell.json"
    save_servers("computes", [{"origin": "http://192.0.2.7", "label": "bad", "custom": False}], path)
    assert load_servers("computes", path) == []
    path.write_text(json.dumps({"servers": {"computes": [{"origin": "javascript:1", "label": "x", "custom": 0}]}}))
    assert load_servers("computes", path) == []


def test_servers_that_are_not_where_they_should_be_are_nothing(tmp_path: Path) -> None:
    from claudia_shell_gtk.settings import load_servers

    path = tmp_path / "shell.json"
    for content in ({"servers": [1]}, {"servers": "x"}, {"servers": {"computes": "x"}}, {}):
        path.write_text(json.dumps(content), encoding="utf-8")
        assert load_servers("computes", path) == []


def test_only_valid_fingerprints_of_valid_origins_are_trusted(tmp_path: Path) -> None:
    from claudia_shell_gtk.settings import load_trusted

    path = tmp_path / "shell.json"
    good = "ab" * 32
    entry = {"sha256": good, "since": "2026-11-10"}
    path.write_text(
        json.dumps(
            {
                "trusted": {
                    "https://a.example.org": entry,
                    "https://b.example.org": {"sha256": "not a fingerprint", "since": "2026-11-10"},
                    "http://192.0.2.7": entry,  # plain http has no certificate to trust
                    "javascript:1": entry,
                    "https://c.example.org": 5,
                    "https://d.example.org": {"since": "2026-11-10"},
                }
            }
        ),
        encoding="utf-8",
    )
    assert load_trusted(path) == {"https://a.example.org": entry}


def test_the_day_a_certificate_was_trusted_is_optional_and_must_look_like_a_day(tmp_path: Path) -> None:
    from claudia_shell_gtk.settings import load_trusted

    path = tmp_path / "shell.json"
    good = "cd" * 32
    path.write_text(
        json.dumps(
            {
                "trusted": {
                    "https://a.example.org": {"sha256": good},
                    "https://b.example.org": {"sha256": good, "since": "yesterday"},
                }
            }
        ),
        encoding="utf-8",
    )
    assert load_trusted(path) == {
        "https://a.example.org": {"sha256": good, "since": ""},
        "https://b.example.org": {"sha256": good, "since": ""},
    }


def test_a_save_replaces_the_file_whole_or_not_at_all(tmp_path: Path) -> None:
    """Written through a temporary file and renamed, so a crash cannot leave half a settings file behind."""
    path = tmp_path / "shell.json"
    save_shell_locale("de", path)
    assert [p.name for p in tmp_path.iterdir()] == ["shell.json"]
