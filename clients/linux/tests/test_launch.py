"""Putting a local server together for an app, or saying what is missing (no GTK)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from claudia_shell_gtk import identity, launch
from claudia_shell_gtk.private_port import private_port
from claudia_shell_gtk.private_server import PrivateServer


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


def test_her_private_server_is_prepared_not_asked_for_yet(checkout: Path, tmp_path: Path) -> None:
    server = launch.prepare_server(identity.get("composes"), repo=checkout)
    assert isinstance(server, PrivateServer)
    assert server.url == ""  # not asked for yet
    assert server._python == str(checkout / ".venv" / "bin" / "python")  # noqa: SLF001 (what is run is the point)
    assert server._web == checkout / "web" / ".output" / "public"  # noqa: SLF001
    assert server.log_path == tmp_path / "state" / "claudia" / "server" / "server.log"


@pytest.mark.parametrize("app", identity.names())
def test_every_app_uses_the_one_folder_of_documents_and_of_state(app: str, checkout: Path, tmp_path: Path) -> None:
    """The three apps share one local server (D445): the same folders, whichever app asks; the app is what the
    server must serve."""
    server = launch.prepare_server(identity.get(app), repo=checkout)
    assert server._app == app  # noqa: SLF001
    assert server._documents == tmp_path / "data" / "claudia" / "documents"  # noqa: SLF001
    assert server.log_path == tmp_path / "state" / "claudia" / "server" / "server.log"


def test_the_folders_exist_once_prepared_and_none_per_app(checkout: Path, tmp_path: Path) -> None:
    launch.prepare_server(identity.get("composes"), repo=checkout)
    assert (tmp_path / "data" / "claudia" / "documents").is_dir()
    assert (tmp_path / "state" / "claudia" / "server").is_dir()
    assert not (tmp_path / "data" / "claudia" / "composes").exists()


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


def test_her_server_is_on_the_port_of_her_account_or_the_one_of_claudia_server_port(
    checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E8.5, D1621: the port of her account; CLAUDIA_SERVER_PORT for a person who needs it for something else."""
    mine = private_port(os.getuid())
    monkeypatch.delenv("CLAUDIA_SERVER_PORT", raising=False)
    assert launch.prepare_server(identity.get("composes"), repo=checkout)._usual == mine  # noqa: SLF001
    monkeypatch.setenv("CLAUDIA_SERVER_PORT", "18765")
    assert launch.prepare_server(identity.get("composes"), repo=checkout)._usual == 18765  # noqa: SLF001
    monkeypatch.setenv("CLAUDIA_SERVER_PORT", "nonsense")
    assert launch.prepare_server(identity.get("composes"), repo=checkout)._usual == mine  # noqa: SLF001
