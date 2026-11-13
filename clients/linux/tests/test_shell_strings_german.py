"""The shell's own messages in German (E5.7, D31): every text a person can read in the native window or on the
command line goes through the installed translation, and the catalog the shell ships has it. No GTK import, so this
runs without a display."""

from __future__ import annotations

import pytest

from claudia_shell_gtk import __main__ as main_module
from claudia_shell_gtk import cli, i18n, identity, launch, manifest
from claudia_shell_gtk.i18n import install_translation
from claudia_shell_gtk.server import LocalServer, ServerStartError


@pytest.fixture(autouse=True)
def _german():
    before = i18n._active
    install_translation("de")
    yield
    i18n._active = before


def test_the_command_line_help_is_german(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.parse("computes", ["--help"])
    out = capsys.readouterr().out
    assert "Claudia Computes für den Linux-Desktop" in out
    assert "Weitere Argumente werden an GTK weitergereicht." in out
    assert "--server" in out


def test_a_refused_address_on_the_command_line_is_german(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.parse("computes", ["--server", "http://example.org"])
    assert "Verwenden Sie https://" in capsys.readouterr().err


def test_the_about_links_are_labelled_in_german_when_asked_to() -> None:
    labels = [label for label, _url in manifest.about_links(i18n.translate)]
    assert labels == ["Website", "Problem melden", "Rechtliches"]


def test_the_about_links_stay_english_without_a_translator() -> None:
    assert [label for label, _url in manifest.about_links()] == ["Website", "Report an Issue", "Legal"]


def test_a_missing_python_is_explained_in_german(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launch, "find_server_python", lambda **_: None)
    with pytest.raises(launch.SetupProblem) as problem:
        launch.prepare_server(identity.get("computes"))
    assert "benötigt Python 3.14" in str(problem.value)
    assert "CLAUDIA_SERVER_PYTHON" in str(problem.value)


def test_a_missing_frontend_is_explained_in_german(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launch, "find_server_python", lambda **_: "/usr/bin/python3")
    monkeypatch.setattr(launch, "find_frontend", lambda **_: None)
    monkeypatch.delenv("CLAUDIA_WEB_DIR", raising=False)
    with pytest.raises(launch.SetupProblem) as problem:
        launch.prepare_server(identity.get("computes"))
    assert "Web-Frontend wurde nicht gebaut" in str(problem.value)


def test_a_wrong_frontend_folder_is_named_in_german(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launch, "find_server_python", lambda **_: "/usr/bin/python3")
    monkeypatch.setattr(launch, "find_frontend", lambda **_: None)
    monkeypatch.setenv("CLAUDIA_WEB_DIR", "/nowhere")
    with pytest.raises(launch.SetupProblem) as problem:
        launch.prepare_server(identity.get("computes"))
    assert "CLAUDIA_WEB_DIR ist auf /nowhere gesetzt" in str(problem.value)


def test_a_server_that_died_is_reported_in_german(tmp_path) -> None:
    log = tmp_path / "server.log"
    log.write_text("boom\n", encoding="utf-8")
    local = LocalServer(
        ["python3", "-c", "import sys; print('boom'); sys.exit(3)"],
        url="http://127.0.0.1:9",
        log=log,
        startup_timeout=5,
    )
    with pytest.raises(ServerStartError) as failed:
        local.start()
    assert "beim Start beendet (Exit-Code 3)" in str(failed.value)
    assert "--- Was der Server ausgegeben hat" in str(failed.value)
    assert "boom" in str(failed.value)


def test_the_install_hint_is_german() -> None:
    hint = main_module.install_hint()
    assert hint.startswith("Der Linux-Client von Claudia benötigt GTK 4")
    assert "sudo apt install python3-gi" in hint


def test_the_language_is_installed_before_the_command_line_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--help` and a refused `--server` are the first things a person reads: they must already speak the language."""
    order: list[str] = []

    def resolve_locale() -> str:
        order.append("locale")
        return "de"

    monkeypatch.setattr(main_module, "_resolve_locale", resolve_locale)
    monkeypatch.setattr(main_module, "install_translation", lambda locale: order.append(f"install {locale}"))

    def parse(app, argv):
        order.append("parse")
        raise SystemExit(0)

    monkeypatch.setattr(main_module.cli, "parse", parse)
    with pytest.raises(SystemExit):
        main_module.run("computes", ["--help"])
    assert order == ["locale", "install de", "parse"]
