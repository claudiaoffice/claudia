"""The launcher builds the right server command and knows when the web app must be built."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("start", Path(__file__).parent.parent / "scripts" / "start.py")
start = importlib.util.module_from_spec(SPEC)
sys.modules["start"] = start  # dataclasses look their module up
SPEC.loader.exec_module(start)


def test_defaults_run_a_plain_local_server_of_all_apps_with_the_web_app():
    args = start.parse_args([])
    command = start.server_command(args, python="py", built=Path("web/out"))
    assert command[:3] == ["py", "-m", "claudia_server"]
    assert command[command.index("--web") + 1] == "web/out"
    assert command[command.index("--port") + 1] == "8765"
    assert "--no-tls" in command
    assert "--model" not in command and "--apps" not in command, "the server serves every app by default (D430)"
    assert start.page_url(args) == "http://127.0.0.1:8765/"


def test_tls_is_the_servers_own_default_when_asked_for():
    args = start.parse_args(["--tls", "--port", "9000", "--dir", "data"])
    command = start.server_command(args)
    assert "--no-tls" not in command
    assert Path(command[command.index("--dir") + 1]) == Path("data", "documents")
    assert start.page_url(args) == "https://127.0.0.1:9000/"


def test_the_web_app_is_built_when_missing_or_asked_for(tmp_path):
    assert start.needs_build(start.parse_args([]), built=tmp_path)
    (tmp_path / "index.html").write_text("<html></html>")
    assert not start.needs_build(start.parse_args([]), built=tmp_path)
    assert start.needs_build(start.parse_args(["--rebuild"]), built=tmp_path)


def test_waiting_gives_up_when_the_server_stops():
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    assert start.wait_for_port("127.0.0.1", 1, dead, seconds=2) is False


def test_naming_an_app_starts_the_same_server_and_opens_that_apps_page():
    """D433: ``./start.sh composes`` is read as "I want to work on texts"."""
    composes = start.parse_args(["composes", "--port", "9100"])
    assert composes.app == "composes"
    assert start.server_command(composes) == start.server_command(start.parse_args(["--port", "9100"]))
    assert start.page_url(composes) == "http://127.0.0.1:9100/?app=composes"
    assert start.parse_args(["--app", "creates"]).app == "creates"


def test_all_is_the_one_server_and_the_start_page():
    args = start.parse_args(["all", "--port", "9000"])
    assert args.app is None and start.page_url(args) == "http://127.0.0.1:9000/"
    assert start.server_command(args) == start.server_command(start.parse_args(["--port", "9000"]))


def test_shape_folders_are_handed_to_the_server():
    command = start.server_command(start.parse_args(["creates", "--shapes", "a", "--shapes", "b"]))
    given = [command[i + 1] for i, part in enumerate(command) if part == "--shapes"]
    assert given == ["a", "b"]


def test_documents_and_state_live_in_one_folder_per_checkout():
    args = start.parse_args(["--dir", "mine"])
    command = start.server_command(args)
    assert Path(command[command.index("--dir") + 1]) == Path("mine", "documents")
    assert Path(command[command.index("--state-dir") + 1]) == Path("mine", "state")
    default = start.server_command(start.parse_args([]))
    assert Path(default[default.index("--state-dir") + 1]) == start.DATA / "state", "inside the checkout"


def test_folders_of_earlier_layouts_are_named_never_used_or_moved(tmp_path):
    root, checkout = tmp_path / ".claudia", tmp_path
    (root / "composes" / "documents").mkdir(parents=True)  # the three-server layout (D437)
    (checkout / "demo-docs").mkdir()
    (checkout / "demo-docs" / "budget.claudia").write_bytes(b"x")
    (checkout / "docs-computes").mkdir()  # empty: nothing to say
    assert start.old_folders(root, checkout) == [root / "composes", checkout / "demo-docs"]
    assert (checkout / "demo-docs" / "budget.claudia").exists()


def test_the_guide_names_every_app_at_the_one_address_and_what_to_do_there(tmp_path):
    args = start.parse_args(["--port", "9000", "--dir", str(tmp_path)])
    (tmp_path / "creates" / "documents").mkdir(parents=True)
    (tmp_path / "creates" / "documents" / "x").write_text("")
    guide = start.guide(args)
    for app in ("computes", "composes", "creates"):
        assert f"http://127.0.0.1:9000/?app={app}" in guide
    assert "Ctrl+C" in guide and "9001" not in guide
    assert str(tmp_path / "creates") in guide, "an old folder is named so that it can be deleted"


def test_a_server_that_others_can_reach_must_be_encrypted(capsys):
    """Passwords travel in the first frame: plain text is only for this computer (SEC-07)."""
    for host in ("0.0.0.0", "::", "192.168.1.20", "claudia.example.org"):
        with pytest.raises(SystemExit) as stopped:
            start.parse_args(["--host", host])
        assert stopped.value.code == 2, host
        assert "--tls" in capsys.readouterr().err, host


@pytest.mark.parametrize("extra", [["--host", "127.0.0.1"], ["--host", "localhost"], ["--host", "::1"], []])
def test_plain_text_stays_fine_on_this_computer(extra):
    assert start.parse_args(extra).tls is False


def test_an_encrypted_server_may_listen_on_any_address():
    assert start.parse_args(["--host", "0.0.0.0", "--tls"]).host == "0.0.0.0"


def _model(folder: Path, name: str) -> Path:
    (folder / name).mkdir(parents=True)
    (folder / name / "openvino_model.xml").write_text("<net/>")
    return folder / name


def test_the_ai_model_is_handed_to_the_one_server(tmp_path):
    """One model for every app that can use it (computes, creates; D432): the server decides, not the launcher."""
    model = _model(tmp_path, "qwen-ov")
    args = start.parse_args(["composes", "--ai", str(model), "--ai-device", "CPU", "--dir", str(tmp_path)])
    command = start.server_command(args)
    assert command[command.index("--ai") + 1] == str(model)
    assert command[command.index("--ai-device") + 1] == "CPU"
    assert "qwen-ov" in start.guide(args)
    assert "--ai" not in start.server_command(start.parse_args([])), "no model unless asked for"


def test_ai_without_a_folder_takes_the_one_model_in_ai_models(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "MODELS_DIR", tmp_path)
    (tmp_path / "notes").mkdir()  # a folder without a model is not one
    model = _model(tmp_path, "qwen-ov")
    assert start.parse_args(["--ai"]).ai == str(model)
    assert start.parse_args(["all", "--ai"]).ai == str(model)


@pytest.mark.parametrize("models", [[], ["a-ov", "b-ov"]])
def test_ai_without_a_folder_says_what_to_do_when_it_cannot_choose(tmp_path, monkeypatch, capsys, models):
    monkeypatch.setattr(start, "MODELS_DIR", tmp_path)
    for name in models:
        _model(tmp_path, name)
    with pytest.raises(SystemExit):
        start.parse_args(["--ai"])
    err = capsys.readouterr().err
    assert "--ai MODEL_DIR" in err
    assert ("optimum-cli" in err) if not models else ("a-ov, b-ov" in err)


def test_a_device_without_a_model_is_refused(capsys):
    with pytest.raises(SystemExit):
        start.parse_args(["--ai-device", "CPU"])
    assert "--ai" in capsys.readouterr().err


def test_openvino_is_installed_into_the_environment_without_removing_anything(monkeypatch):
    ran = []
    monkeypatch.setattr(start.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(start.subprocess, "run", lambda command, **kw: ran.append((command, kw)))
    start.install_openvino()
    ((command, kw),) = ran
    assert command[:2] == ["/bin/uv", "sync"]
    assert "--inexact" in command and "--locked" in command
    assert command[command.index("--extra") + 1] == "openvino"
    assert kw["cwd"] == start.ROOT


def test_every_server_gets_the_checkouts_fonts_folder():
    command = start.server_command(start.parse_args(["composes", "--dir", "mine"]))
    assert Path(command[command.index("--fonts") + 1]) == Path("mine", "fonts")


def test_every_server_gets_the_checkouts_hyphenation_folder():
    command = start.server_command(start.parse_args(["composes", "--dir", "mine"]))
    assert Path(command[command.index("--hyphenation") + 1]) == Path("mine", "hyphenation")


def test_the_hyphenation_patterns_are_fetched_once_and_a_failure_does_not_stop_the_start(tmp_path, capsys, monkeypatch):
    from claudia_server import hyphenation

    calls = []
    monkeypatch.setattr(
        hyphenation.HyphenationService, "from_folder", classmethod(lambda cls, folder: cls(tuple(calls), {}))
    )

    def fetched(folder):
        calls.append(folder)

    assert start.ensure_hyphenation(tmp_path, fetch=fetched) is True
    assert start.ensure_hyphenation(tmp_path, fetch=fetched) is True
    assert calls == [tmp_path / "hyphenation"], "fetched the first time only"

    def offline(folder):
        raise hyphenation.FetchError("no network")

    assert start.ensure_hyphenation(tmp_path / "other", fetch=offline) is False
    assert "Could not fetch the hyphenation patterns" in capsys.readouterr().out


def test_the_starter_fonts_are_fetched_once_and_a_failure_does_not_stop_the_start(tmp_path, capsys):
    from claudia_fonts import FetchError

    calls = []

    def fetched(folder):
        calls.append(folder)
        (folder / "inter").mkdir(parents=True)
        (folder / "inter" / "collection.json").write_text("{}")

    assert start.ensure_fonts(tmp_path, fetch=fetched) is True
    assert start.ensure_fonts(tmp_path, fetch=fetched) is True
    assert calls == [tmp_path / "fonts"], "fetched the first time only"

    def offline(folder):
        raise FetchError("no network")

    assert start.ensure_fonts(tmp_path / "other", fetch=offline) is False
    assert "Could not fetch the fonts" in capsys.readouterr().out
