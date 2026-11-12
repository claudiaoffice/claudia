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


def test_defaults_run_a_plain_local_server_with_the_web_app():
    args = start.parse_args([])
    command = start.server_command(args, python="py", built=Path("web/out"))
    assert command[:3] == ["py", "-m", "claudia_server"]
    assert command[command.index("--web") + 1] == "web/out"
    assert command[command.index("--port") + 1] == "8765"
    assert "--no-tls" in command
    assert start.page_url(args) == "http://127.0.0.1:8765/"


def test_tls_is_the_servers_own_default_when_asked_for():
    args = start.parse_args(["--tls", "--port", "9000", "--dir", "data"])
    command = start.server_command(args)
    assert "--no-tls" not in command
    assert Path(command[command.index("--dir") + 1]) == Path("data", "computes", "documents")
    assert start.page_url(args) == "https://127.0.0.1:9000/"


def test_a_text_server_serves_the_text_model_with_documents_of_its_own():
    args = start.parse_args(["--app", "composes"])
    command = start.server_command(args)
    assert command[command.index("--model") + 1] == "claudia_composes:TextModel"
    assert Path(command[command.index("--dir") + 1]) == start.DATA / "composes" / "documents", "one app's documents"
    assert "--model" not in start.server_command(start.parse_args([])), "workbooks are the server's default"
    assert start.parse_args(["--app", "composes", "--dir", "mine"]).documents == str(
        Path("mine", "composes", "documents")
    )


def test_the_web_app_is_built_when_missing_or_asked_for(tmp_path):
    assert start.needs_build(start.parse_args([]), built=tmp_path)
    (tmp_path / "index.html").write_text("<html></html>")
    assert not start.needs_build(start.parse_args([]), built=tmp_path)
    assert start.needs_build(start.parse_args(["--rebuild"]), built=tmp_path)


def test_waiting_gives_up_when_the_server_stops():
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    assert start.wait_for_port("127.0.0.1", 1, dead, seconds=2) is False


def test_presentations_run_on_their_own_model_in_their_own_folder():
    command = start.server_command(start.parse_args(["--app", "creates"]))
    assert command[command.index("--model") + 1] == "claudia_creates:SlideModel"
    assert Path(command[command.index("--dir") + 1]).parent.name == "creates", "documents of two apps never mix"
    own = start.server_command(start.parse_args(["--app", "creates", "--dir", "mine"]))
    assert Path(own[own.index("--dir") + 1]) == Path("mine", "creates", "documents")


def test_shape_folders_are_handed_to_the_server():
    command = start.server_command(start.parse_args(["--app", "creates", "--shapes", "a", "--shapes", "b"]))
    given = [command[i + 1] for i, part in enumerate(command) if part == "--shapes"]
    assert given == ["a", "b"]


def test_the_app_can_be_named_without_an_option():
    assert start.parse_args(["composes"]).app == "composes"
    assert start.parse_args(["creates", "--port", "9"]).port == 9
    assert start.parse_args(["--app", "creates"]).app == "creates"
    assert start.parse_args([]).app == "computes"


def test_all_apps_get_a_server_each_on_ports_next_to_each_other():
    args = start.parse_args(["all", "--port", "9000"])
    servers = start.app_servers(args)
    assert [s.app for s in servers] == ["computes", "composes", "creates"]
    assert [s.port for s in servers] == [9000, 9001, 9002]
    assert len({s.dir for s in servers}) == 3, "documents of two apps never mix"
    assert [s.url for s in servers][0] == "http://127.0.0.1:9000/"


def test_one_app_is_one_server_on_the_given_port():
    (server,) = start.app_servers(start.parse_args(["composes", "--port", "9100"]))
    assert (server.app, server.port) == ("composes", 9100)
    command = start.server_command(server.args)
    assert command[command.index("--port") + 1] == "9100"
    assert command[command.index("--model") + 1] == "claudia_composes:TextModel"


def test_a_custom_directory_gets_a_folder_for_each_app():
    servers = start.app_servers(start.parse_args(["all", "--dir", "mine"]))
    assert [Path(s.dir) for s in servers] == [Path("mine", app, "documents") for app in start.APPS]
    assert [Path(s.state) for s in servers] == [Path("mine", app, "state") for app in start.APPS]


def test_dir_means_the_same_for_one_app_and_for_all():
    """It used to be the documents folder itself for one app and the parent of three for ``all`` (QA 2026-11-12)."""
    (alone,) = start.app_servers(start.parse_args(["composes", "--dir", "mine"]))
    together = {s.app: s for s in start.app_servers(start.parse_args(["all", "--dir", "mine"]))}
    assert (alone.dir, alone.state) == (together["composes"].dir, together["composes"].state)


def test_every_server_has_a_state_of_its_own_beside_its_documents():
    """Without ``--state-dir`` all three servers shared one per-user folder (certificate, administrators, settings),
    the same tree the Linux desktop app keeps its documents in."""
    servers = start.app_servers(start.parse_args(["all"]))
    commands = [start.server_command(s.args) for s in servers]
    states = [Path(c[c.index("--state-dir") + 1]) for c in commands]
    assert states == [start.DATA / app / "state" for app in start.APPS]
    assert all(start.DATA in s.parents for s in states), "inside the checkout"


def test_folders_of_an_earlier_version_are_reported_not_moved(tmp_path):
    (tmp_path / "demo-docs").mkdir()
    (tmp_path / "demo-docs" / "budget.claudia").write_bytes(b"x")
    (tmp_path / "docs-computes").mkdir()  # empty: nothing to say
    assert start.legacy_folders("computes", root=tmp_path) == [tmp_path / "demo-docs"]
    assert start.legacy_folders("composes", root=tmp_path) == []
    assert (tmp_path / "demo-docs" / "budget.claudia").exists()


def test_the_guide_names_every_address_and_what_to_do_there():
    guide = start.guide(start.app_servers(start.parse_args(["all", "--port", "9000"])))
    for url in ("http://127.0.0.1:9000/", "http://127.0.0.1:9001/", "http://127.0.0.1:9002/"):
        assert url in guide
    for name in ("computes", "composes", "creates"):
        assert name in guide
    assert "Ctrl+C" in guide
    one = start.guide(start.app_servers(start.parse_args(["creates"])))
    assert "composes" not in one.split("Other apps")[0], "a single app is named alone first"


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


def test_the_ai_model_goes_to_the_app_that_can_use_it(tmp_path):
    """``all --ai``: computes loads the model; composes and creates have no lens yet and keep the stand-in, and a
    server that is handed one refuses to start (``--ai: the AI assistant does not know documents of this kind``)."""
    model = _model(tmp_path, "qwen-ov")
    servers = start.app_servers(start.parse_args(["all", "--ai", str(model), "--ai-device", "CPU"]))
    commands = {s.app: start.server_command(s.args) for s in servers}
    assert commands["computes"][commands["computes"].index("--ai") + 1] == str(model)
    assert commands["computes"][commands["computes"].index("--ai-device") + 1] == "CPU"
    assert "--ai" not in commands["composes"]
    assert "--ai" not in commands["creates"]
    assert "qwen-ov" in start.guide(servers)
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


def test_ai_is_refused_where_no_app_can_use_it(capsys):
    for argv in (["composes", "--ai", "m"], ["creates", "--ai", "m"], ["--ai-device", "CPU"]):
        with pytest.raises(SystemExit):
            start.parse_args(argv)
        assert "--ai" in capsys.readouterr().err, argv


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
