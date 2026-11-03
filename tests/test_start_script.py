"""The launcher builds the right server command and knows when the web app must be built."""

import importlib.util
import subprocess
import sys
from pathlib import Path

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
    args = start.parse_args(["--tls", "--port", "9000", "--dir", "docs"])
    command = start.server_command(args)
    assert "--no-tls" not in command
    assert command[command.index("--dir") + 1] == "docs"
    assert start.page_url(args) == "https://127.0.0.1:9000/"


def test_a_text_server_serves_the_text_model_with_documents_of_its_own():
    args = start.parse_args(["--app", "composes"])
    command = start.server_command(args)
    assert command[command.index("--model") + 1] == "claudia_composes:TextModel"
    assert command[command.index("--dir") + 1].endswith("demo-docs-composes"), "one directory holds one app's documents"
    assert "--model" not in start.server_command(start.parse_args([])), "workbooks are the server's default"
    assert start.parse_args(["--app", "composes", "--dir", "mine"]).dir == "mine"


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
    assert Path(command[command.index("--dir") + 1]).name == "demo-docs-creates", "documents of two apps never mix"
    own = start.server_command(start.parse_args(["--app", "creates", "--dir", "mine"]))
    assert own[own.index("--dir") + 1] == "mine"


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
    assert [Path(s.dir).name for s in servers] == ["computes", "composes", "creates"]
    assert all(Path(s.dir).parent == Path("mine") for s in servers)


def test_the_guide_names_every_address_and_what_to_do_there():
    guide = start.guide(start.app_servers(start.parse_args(["all", "--port", "9000"])))
    for url in ("http://127.0.0.1:9000/", "http://127.0.0.1:9001/", "http://127.0.0.1:9002/"):
        assert url in guide
    for name in ("computes", "composes", "creates"):
        assert name in guide
    assert "Ctrl+C" in guide
    one = start.guide(start.app_servers(start.parse_args(["creates"])))
    assert "composes" not in one.split("Other apps")[0], "a single app is named alone first"
