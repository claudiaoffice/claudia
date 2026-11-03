"""Putting a local server together for an app, or saying what is missing (no GTK)."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from claudia_shell_gtk import identity, launch


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("CLAUDIA_SERVER_PYTHON", "CLAUDIA_WEB_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    python = tmp_path / "repo" / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\n")
    python.chmod(python.stat().st_mode | stat.S_IXUSR)
    web = tmp_path / "repo" / "web" / ".output" / "public"
    web.mkdir(parents=True)
    (web / "index.html").write_text("<html></html>")
    return tmp_path / "repo"


def test_a_server_is_prepared_for_the_app_on_a_free_loopback_port(checkout: Path, tmp_path: Path) -> None:
    server = launch.prepare_server(identity.get("composes"), repo=checkout)
    assert server.url.startswith("http://127.0.0.1:")
    assert not server.running  # prepared, not started
    command = server._command  # noqa: SLF001 (what is run is the point of this test)
    assert command[0] == str(checkout / ".venv" / "bin" / "python")
    assert command[command.index("--model") + 1] == "claudia_composes:TextModel"
    assert command[command.index("--web") + 1] == str(checkout / "web" / ".output" / "public")
    assert command[command.index("--dir") + 1] == str(tmp_path / "data" / "claudia" / "composes" / "documents")
    assert server.log_path == tmp_path / "state" / "claudia" / "composes" / "server.log"


def test_the_documents_folder_exists_when_the_server_starts(checkout: Path, tmp_path: Path) -> None:
    launch.prepare_server(identity.get("composes"), repo=checkout)
    assert (tmp_path / "data" / "claudia" / "composes" / "documents").is_dir()


def test_a_missing_server_python_is_explained_with_the_way_to_fix_it(checkout: Path) -> None:
    (checkout / ".venv" / "bin" / "python").unlink()
    with pytest.raises(launch.SetupProblem) as problem:
        launch.prepare_server(identity.get("composes"), repo=checkout)
    assert "CLAUDIA_SERVER_PYTHON" in str(problem.value)
    assert "3.14" in str(problem.value)


def test_a_missing_frontend_is_explained_with_the_way_to_fix_it(checkout: Path) -> None:
    (checkout / "web" / ".output" / "public" / "index.html").unlink()
    with pytest.raises(launch.SetupProblem) as problem:
        launch.prepare_server(identity.get("composes"), repo=checkout)
    assert "CLAUDIA_WEB_DIR" in str(problem.value)


def test_a_wrong_frontend_path_is_reported_not_replaced(checkout: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDIA_WEB_DIR", "/nonexistent/frontend")
    with pytest.raises(launch.SetupProblem) as problem:
        launch.prepare_server(identity.get("composes"), repo=checkout)
    assert "/nonexistent/frontend" in str(problem.value)
