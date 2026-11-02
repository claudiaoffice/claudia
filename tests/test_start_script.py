"""The launcher builds the right server command and knows when the web app must be built."""

import importlib.util
import subprocess
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("start", Path(__file__).parent.parent / "scripts" / "start.py")
start = importlib.util.module_from_spec(SPEC)
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


def test_the_web_app_is_built_when_missing_or_asked_for(tmp_path):
    assert start.needs_build(start.parse_args([]), built=tmp_path)
    (tmp_path / "index.html").write_text("<html></html>")
    assert not start.needs_build(start.parse_args([]), built=tmp_path)
    assert start.needs_build(start.parse_args(["--rebuild"]), built=tmp_path)


def test_waiting_gives_up_when_the_server_stops():
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    assert start.wait_for_port("127.0.0.1", 1, dead, seconds=2) is False
