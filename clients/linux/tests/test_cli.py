"""The command line of every app (E5.8): see cli.py. Parsing only — starting the application is test_e2e.py's job."""

from __future__ import annotations

import pytest

from claudia_shell_gtk import cli, identity
from claudia_shell_gtk._version import __version__


@pytest.mark.parametrize("app", identity.names())
def test_without_arguments_an_app_starts_its_own_local_server(app: str) -> None:
    options = cli.parse(app, [])
    assert options.app == app
    assert options.server is None
    assert not options.debug
    assert options.rest == []


def test_a_server_address_is_taken_as_the_one_origin_it_names() -> None:
    options = cli.parse("computes", ["--server", "Demo.Example.org:8420"])
    assert options.server is not None
    assert options.server.origin == "https://demo.example.org:8420"


def test_the_equals_form_works_too() -> None:
    options = cli.parse("creates", ["--server=https://demo.example.org"])
    assert options.server is not None
    assert options.server.origin == "https://demo.example.org"


def test_plain_http_to_another_computer_is_refused_at_the_command_line(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_:
        cli.parse("computes", ["--server", "http://192.0.2.7:8420"])
    assert exit_.value.code == 2
    assert "https" in capsys.readouterr().err


def test_an_address_that_is_none_is_refused_at_the_command_line(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_:
        cli.parse("computes", ["--server", "ftp://example.org"])
    assert exit_.value.code == 2
    assert "--server" in capsys.readouterr().err


def test_debug_is_recognised_and_everything_else_goes_to_gtk() -> None:
    options = cli.parse("composes", ["--debug", "--gapplication-service", "--name", "x"])
    assert options.debug
    assert options.rest == ["--gapplication-service", "--name", "x"]


@pytest.mark.parametrize("app", identity.names())
def test_the_version_names_the_command_of_the_app(app: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_:
        cli.parse(app, ["--version"])
    assert exit_.value.code == 0
    assert capsys.readouterr().out.strip() == f"claudia-{app} {__version__}"


def test_the_help_says_which_app_it_is_for(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.parse("computes", ["--help"])
    out = capsys.readouterr().out
    assert "Claudia Computes" in out
    assert "--server" in out


def test_an_unknown_app_is_an_error_that_names_the_apps() -> None:
    with pytest.raises(identity.UnknownApp) as unknown:
        cli.parse("slides", [])
    assert "computes" in str(unknown.value)


def test_the_module_form_takes_the_app_as_its_first_argument() -> None:
    assert cli.split_module_arguments(["computes", "--server", "x.example.org"]) == (
        "computes",
        ["--server", "x.example.org"],
    )


@pytest.mark.parametrize("argv", [[], ["--debug"], ["--server", "x.example.org"]])
def test_the_module_form_without_an_app_is_an_error_there_is_no_picker(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_:
        cli.split_module_arguments(argv)
    assert exit_.value.code == 2
    err = capsys.readouterr().err
    assert "composes" in err
    assert "computes" in err
    assert "creates" in err
