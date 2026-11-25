"""Starting and stopping the local server that the shell hosts (E0.2).

A fake server stands in for ``claudia_server`` so that the tests are fast and need no 3.14 interpreter; the end-to-end
test (``test_e2e.py``) runs the real one.
"""

from __future__ import annotations

import contextlib
import os
import signal
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from claudia_shell_gtk import server
from claudia_shell_gtk.server import LocalServer, ServerStartError


def _free_port() -> int:
    """A port of this computer nobody listens on right now, for the fake servers of these tests."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


SRC = str(Path(server.__file__).resolve().parents[1])

FAKE = textwrap.dedent(
    """
    import http.server, os, subprocess, sys, time

    port, mode = int(sys.argv[1]), sys.argv[2]
    if mode == "crash":
        print("boom: No module named claudia_server", flush=True)
        sys.exit(3)
    if mode == "silent":
        time.sleep(60)
    if mode == "child":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        with open(os.environ["CHILD_PID_FILE"], "w") as out:
            out.write(str(child.pid))

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/api/health" else 404)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, *args):
            pass

    http.server.HTTPServer(("127.0.0.1", port), Handler).serve_forever()
    """
)


@pytest.fixture
def fake(tmp_path: Path):
    script = tmp_path / "fake_server.py"
    script.write_text(FAKE, encoding="utf-8")

    def make(mode: str = "ok", **options: object) -> LocalServer:
        port = _free_port()
        return LocalServer(
            [sys.executable, str(script), str(port), mode],
            url=f"http://127.0.0.1:{port}",
            log=tmp_path / "server.log",
            **options,  # type: ignore[arg-type]
        )

    return make


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:  # a zombie is dead for our purposes
        return Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
    except FileNotFoundError:
        return False


def wait_gone(pid: int, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not alive(pid):
            return True
        time.sleep(0.05)
    return not alive(pid)


def test_start_waits_for_the_health_check_and_returns_the_address(fake) -> None:
    local = fake()
    try:
        assert local.start() == local.url
        assert local.running
    finally:
        local.stop()
    assert not local.running


def test_a_server_that_dies_at_start_is_reported_with_what_it_said(fake) -> None:
    local = fake("crash")
    with pytest.raises(ServerStartError) as failed:
        local.start()
    assert "boom: No module named claudia_server" in str(failed.value)
    assert "exit code 3" in str(failed.value)
    assert not local.running


def test_a_server_that_never_answers_is_killed_after_the_timeout(fake) -> None:
    local = fake("silent", startup_timeout=0.6)
    started = time.monotonic()
    with pytest.raises(ServerStartError) as failed:
        local.start()
    assert time.monotonic() - started < 5
    assert "did not answer" in str(failed.value)
    assert not local.running


def test_stop_ends_the_server_and_everything_it_started(fake, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CHILD_PID_FILE", str(tmp_path / "child.pid"))
    local = fake("child")
    local.start()
    child = int((tmp_path / "child.pid").read_text())
    assert alive(child)
    local.stop()
    assert wait_gone(child), "a process that the server started was left behind"


def test_stop_can_be_called_twice_and_before_start(fake) -> None:
    local = fake()
    local.stop()
    local.start()
    local.stop()
    local.stop()


def test_the_server_cannot_be_started_twice(fake) -> None:
    local = fake()
    local.start()
    try:
        with pytest.raises(RuntimeError):
            local.start()
    finally:
        local.stop()


def test_the_server_dies_when_the_shell_is_killed_without_a_chance_to_clean_up(tmp_path: Path) -> None:
    """The shell crashing (or being killed from the task manager) must not leave a server running."""
    script = tmp_path / "fake_server.py"
    script.write_text(FAKE, encoding="utf-8")
    port = _free_port()
    shell = subprocess.Popen(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                f"""
                import sys, time
                sys.path.insert(0, {SRC!r})
                from claudia_shell_gtk.server import LocalServer
                local = LocalServer([sys.executable, {str(script)!r}, "{port}", "ok"], url="http://127.0.0.1:{port}")
                local.start()
                print("PID", local.pid, flush=True)
                time.sleep(60)
                """
            ),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert shell.stdout is not None
        line = shell.stdout.readline()
        assert line.startswith("PID "), line
        server_pid = int(line.split()[1])
        assert alive(server_pid)
        os.kill(shell.pid, signal.SIGKILL)  # type: ignore[attr-defined] # POSIX only, not on Windows
        shell.wait(timeout=5)
        assert wait_gone(server_pid), "the server outlived the shell"
    finally:
        if shell.poll() is None:
            shell.kill()


def test_a_server_that_outlives_the_shell_survives_its_death(tmp_path: Path) -> None:
    """The shared desktop server (D445) is started with ``outlives_shell``: no death signal, it stops by itself."""
    script = tmp_path / "fake_server.py"
    script.write_text(FAKE, encoding="utf-8")
    port = _free_port()
    shell = subprocess.Popen(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                f"""
                import sys, time
                sys.path.insert(0, {SRC!r})
                from claudia_shell_gtk.server import LocalServer
                local = LocalServer([sys.executable, {str(script)!r}, "{port}", "ok"], url="http://127.0.0.1:{port}",
                                    outlives_shell=True)
                local.start()
                print("PID", local.pid, flush=True)
                time.sleep(60)
                """
            ),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    server_pid = 0
    try:
        assert shell.stdout is not None
        line = shell.stdout.readline()
        assert line.startswith("PID "), line
        server_pid = int(line.split()[1])
        os.kill(shell.pid, signal.SIGKILL)  # type: ignore[attr-defined] # POSIX only, not on Windows
        shell.wait(timeout=5)
        time.sleep(0.3)
        assert alive(server_pid), "the shared server died with the shell"
    finally:
        if shell.poll() is None:
            shell.kill()
        if server_pid:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(server_pid, signal.SIGKILL)  # type: ignore[attr-defined]


def test_a_start_that_ended_by_itself_says_so_and_quotes_only_what_it_wrote(fake, tmp_path: Path) -> None:
    """server.log is shared by every start of the suite's server: an error quotes this start's lines only, and says
    that the process ended by itself (then another window's server may have won, D435)."""
    (tmp_path / "server.log").write_text("an older run said this\n")
    local = fake("crash")
    with pytest.raises(ServerStartError) as failed:
        local.start()
    assert failed.value.exited
    assert "boom" in str(failed.value)
    assert "an older run" not in str(failed.value)


def test_a_start_that_never_answered_did_not_end_by_itself(fake) -> None:
    local = fake("silent", startup_timeout=0.4)
    with pytest.raises(ServerStartError) as failed:
        local.start()
    assert not failed.value.exited


# --------------------------------------------------------------------------------------------- the command line


def test_the_server_command_is_her_private_server_on_loopback_only(tmp_path: Path) -> None:
    """D445: all three apps (no ``--model``), stopping by itself once nobody has used it for a while (D434), and
    proving to be hers with her key (E8.5, D1620)."""
    command = server.server_command(
        "/opt/claudia/python",
        port=8123,
        documents=tmp_path / "docs",
        web=tmp_path / "web",
        state=tmp_path / "state",
        idle_seconds=600,
        owner_key_file=tmp_path / "state" / "owner.key",
    )
    assert command[:3] == ["/opt/claudia/python", "-m", "claudia_server"]
    joined = " ".join(command)
    assert "--model" not in command
    assert "--exit-when-idle 600" in joined
    assert "--host 127.0.0.1" in joined
    assert "--port 8123" in joined
    assert f"--dir {tmp_path / 'docs'}" in joined
    assert f"--web {tmp_path / 'web'}" in joined
    assert f"--state-dir {tmp_path / 'state'}" in joined
    assert f"--owner-key-file {tmp_path / 'state' / 'owner.key'}" in joined
    assert "--no-tls" in command  # plain on the loopback address, as `start.sh` does
    assert "--allow-origin" not in joined  # the page comes from the server itself: same origin


def test_the_server_python_is_found_in_the_repository_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CLAUDIA_SERVER_PYTHON", raising=False)
    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\n")
    python.chmod(0o755)
    assert server.find_server_python(repo=tmp_path) == str(python)


def test_an_explicit_server_python_wins(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDIA_SERVER_PYTHON", "/somewhere/python3.14")
    assert server.find_server_python(repo=tmp_path) == "/somewhere/python3.14"


def test_no_server_python_is_a_clear_error_and_not_a_guess(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CLAUDIA_SERVER_PYTHON", raising=False)
    assert server.find_server_python(repo=tmp_path) is None
