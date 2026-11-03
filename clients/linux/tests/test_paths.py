"""Where the shell keeps documents and state, and where it finds the bundled web frontend (D43)."""

from __future__ import annotations

from pathlib import Path

import pytest

from claudia_shell_gtk import paths


def test_documents_live_in_the_xdg_data_folder_of_the_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert paths.documents_dir("composes") == tmp_path / "data" / "claudia" / "composes" / "documents"


def test_state_lives_in_the_xdg_state_folder_of_the_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert paths.state_dir("composes") == tmp_path / "state" / "claudia" / "composes"


def test_without_xdg_variables_the_home_folder_is_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert paths.documents_dir("composes") == tmp_path / ".local" / "share" / "claudia" / "composes" / "documents"
    assert paths.state_dir("composes") == tmp_path / ".local" / "state" / "claudia" / "composes"


def test_an_empty_xdg_variable_counts_as_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The XDG specification says so; a relative path in it is ignored too."""
    monkeypatch.setenv("XDG_DATA_HOME", "")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert paths.documents_dir("composes").is_relative_to(tmp_path / ".local" / "share")
    monkeypatch.setenv("XDG_DATA_HOME", "relative/dir")
    assert paths.documents_dir("composes").is_relative_to(tmp_path / ".local" / "share")


def built(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text("<html></html>")
    return folder


def test_the_frontend_named_in_the_environment_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDIA_WEB_DIR", str(built(tmp_path / "mine")))
    assert paths.find_frontend(repo=tmp_path) == tmp_path / "mine"


def test_a_folder_without_index_html_is_not_a_frontend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "empty").mkdir()
    monkeypatch.setenv("CLAUDIA_WEB_DIR", str(tmp_path / "empty"))
    assert paths.find_frontend(repo=tmp_path) is None


def test_a_development_checkout_is_served_from_its_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDIA_WEB_DIR", raising=False)
    built(tmp_path / "web" / ".output" / "public")
    assert paths.find_frontend(repo=tmp_path) == tmp_path / "web" / ".output" / "public"


def test_nothing_found_is_none_so_that_the_window_can_explain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDIA_WEB_DIR", raising=False)
    assert paths.find_frontend(repo=tmp_path, packaged=tmp_path / "nowhere") is None


def test_a_frontend_shipped_inside_the_package_comes_before_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLAUDIA_WEB_DIR", raising=False)
    built(tmp_path / "web" / ".output" / "public")
    shipped = built(tmp_path / "shipped")
    assert paths.find_frontend(repo=tmp_path, packaged=shipped) == shipped
