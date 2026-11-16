"""The one local server that the three desktop apps share (D445): which port, whether one is running already, what to
do when two windows start at once, and the presence connection that keeps it from stopping while a window is open.

The twin of ``clients/neutralino/tests/desktop-server.test.ts``. Everything outside the server's own process is faked;
the real health check, the real state file and the real presence socket are covered at the bottom.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import socket
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from claudia_shell_gtk import desktop_server
from claudia_shell_gtk.desktop_server import (
    IDLE_SECONDS,
    SERVER_PORT,
    STATE_FILE,
    DesktopServer,
    Health,
    is_port_free,
    probe_health,
    read_port,
    write_port,
)
from claudia_shell_gtk.server import ServerStartError

OURS = Health("claudia", ("composes", "computes", "creates"), "0.32.0")
NONE = Health("none")


def wait_for(condition: Callable[[], bool], seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


class FakeSocket:
    """A presence connection that the test drops by hand."""

    def __init__(self) -> None:
        self.closed = False
        self._ended = threading.Event()

    def wait_closed(self) -> None:
        self._ended.wait()

    def close(self) -> None:
        self.closed = True
        self._ended.set()

    def drop(self) -> None:
        self._ended.set()


class Harness:
    def __init__(
        self,
        state: Path,
        *,
        answers: list[Health] | None = None,
        port: int = 41233,
        port_free: bool = True,
        version: str | None = "0.32.0",
        start_fails: Exception | None = None,
        app: str = "computes",
    ) -> None:
        self.answers = list(answers or [NONE])
        self.probed: list[str] = []
        self.starts: list[tuple[list[str], str, Path]] = []
        self.sockets: list[FakeSocket] = []
        self.connected: list[str] = []
        self.start_fails = start_fails
        harness = self

        class Process:
            def __init__(self, command: list[str], url: str, log: Path) -> None:
                self.command, self.url, self.log = command, url, log

            def start(self) -> str:
                harness.starts.append((self.command, self.url, self.log))
                if harness.start_fails is not None:
                    raise harness.start_fails
                return self.url

            def stop(self) -> None: ...

        def probe(url: str) -> Health:
            self.probed.append(url)
            return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]

        def connect(url: str) -> FakeSocket:
            self.connected.append(url)
            made = FakeSocket()
            self.sockets.append(made)
            return made

        self.server = DesktopServer(
            app=app,
            python="/repo/.venv/bin/python",
            web=Path("/frontend"),
            documents=Path("/docs"),
            state=state,
            race_wait=0.05,
            probe=probe,
            make_server=Process,
            pick_port=lambda: port,
            port_free=lambda _port: port_free,
            version=lambda: version,
            connect=connect,
            sleep=lambda _seconds: time.sleep(0.001),
        )


@pytest.fixture
def state(tmp_path: Path) -> Path:
    folder = tmp_path / "state"
    folder.mkdir()
    return folder


@pytest.fixture
def harnesses() -> Iterator[list[Harness]]:
    made: list[Harness] = []
    yield made
    for harness in made:
        harness.server.stop()


def make(harnesses: list[Harness], state: Path, **options: object) -> Harness:
    harness = Harness(state, **options)  # type: ignore[arg-type]
    harnesses.append(harness)
    return harness


def test_starts_the_server_on_8765_the_port_of_every_claudia_server(state: Path, harnesses) -> None:
    """D504: ./start.sh, a cloud server and the desktop's own all use 8765."""
    h = make(harnesses, state)
    assert SERVER_PORT == 8765
    assert h.server.start() == "http://127.0.0.1:8765"
    command, _url, log = h.starts[0]
    assert "8765" in command
    assert command[command.index("--exit-when-idle") + 1] == str(IDLE_SECONDS)
    assert "--model" not in command  # all three apps (D445)
    assert json.loads((state / STATE_FILE).read_text()) == {"port": 8765}
    assert log == state / "server.log"


def test_finds_a_server_on_8765_and_starts_nothing_whoever_started_it(state: Path, harnesses) -> None:
    h = make(harnesses, state, answers=[OURS])
    assert h.server.start() == "http://127.0.0.1:8765"
    assert h.starts == []
    assert h.probed == ["http://127.0.0.1:8765"]


def test_goes_back_to_8765_from_a_port_an_earlier_version_picked(state: Path, harnesses) -> None:
    (state / STATE_FILE).write_text(json.dumps({"port": 50123}))
    h = make(harnesses, state)
    assert h.server.start() == "http://127.0.0.1:8765"
    assert h.probed == ["http://127.0.0.1:8765", "http://127.0.0.1:50123"]
    assert json.loads((state / STATE_FILE).read_text()) == {"port": 8765}


def test_still_uses_a_server_on_the_remembered_port_until_it_stops(state: Path, harnesses) -> None:
    (state / STATE_FILE).write_text(json.dumps({"port": 50123}))
    h = make(harnesses, state, answers=[NONE, OURS])
    assert h.server.start() == "http://127.0.0.1:50123"
    assert h.starts == []


def test_refuses_a_running_server_of_another_version_and_says_how_to_get_rid_of_it(state: Path, harnesses) -> None:
    h = make(harnesses, state, answers=[Health("claudia", OURS.apps, "0.31.0")], version="0.32.0")
    with pytest.raises(ServerStartError) as refused:
        h.server.start()
    assert "0.31.0" in str(refused.value)
    assert "0.32.0" in str(refused.value)
    assert "ten minutes" in str(refused.value)


def test_does_not_insist_on_a_version_it_could_not_find_out(state: Path, harnesses) -> None:
    h = make(harnesses, state, answers=[OURS], version=None)
    assert h.server.start() == "http://127.0.0.1:8765"


def test_refuses_a_running_server_that_does_not_serve_this_app(state: Path, harnesses) -> None:
    h = make(harnesses, state, answers=[Health("claudia", ("composes",), "0.32.0")])
    with pytest.raises(ServerStartError, match="does not serve computes"):
        h.server.start()


def test_goes_to_another_port_when_something_else_answers_on_8765(state: Path, harnesses) -> None:
    h = make(harnesses, state, answers=[Health("other")])
    assert h.server.start() == "http://127.0.0.1:41233"
    assert json.loads((state / STATE_FILE).read_text()) == {"port": 41233}


def test_keeps_the_port_it_went_to_while_8765_is_still_taken(state: Path, harnesses) -> None:
    (state / STATE_FILE).write_text(json.dumps({"port": 50123}))
    h = make(harnesses, state, answers=[Health("other"), NONE])
    assert h.server.start() == "http://127.0.0.1:50123"


def test_goes_to_another_port_when_8765_is_taken_by_something_silent(state: Path, harnesses) -> None:
    h = make(harnesses, state, port_free=False)
    assert h.server.start() == "http://127.0.0.1:41233"


def test_treats_an_unreadable_state_file_as_none(state: Path, harnesses) -> None:
    (state / STATE_FILE).write_text("{ not json")
    h = make(harnesses, state)
    assert h.server.start() == "http://127.0.0.1:8765"
    assert json.loads((state / STATE_FILE).read_text()) == {"port": 8765}


# --------------------------------------------------------------------------------------- two windows at once


def test_a_start_that_lost_to_another_one_uses_the_one_that_won(state: Path, harnesses) -> None:
    lost = ServerStartError(
        "the server stopped at start-up (exit code 2)\nanother Claudia server uses /docs", exited=True
    )
    h = make(harnesses, state, answers=[NONE, NONE, OURS], start_fails=lost)
    assert h.server.start() == "http://127.0.0.1:8765"


def test_says_what_the_server_said_when_nobody_else_answers_either(state: Path, harnesses) -> None:
    lost = ServerStartError("the server stopped at start-up (exit code 1)\ntraceback", exited=True)
    h = make(harnesses, state, start_fails=lost)
    with pytest.raises(ServerStartError) as failed:
        h.server.start()
    assert failed.value is lost


def test_does_not_wait_for_another_server_when_its_own_simply_never_answered(state: Path, harnesses) -> None:
    slow = ServerStartError("the server did not answer")
    h = make(harnesses, state, start_fails=slow)
    with pytest.raises(ServerStartError):
        h.server.start()
    assert len(h.probed) == 1  # the one look before starting, none after


def test_the_state_file_is_written_once_the_second_window_keeps_the_first_ones_port(tmp_path: Path) -> None:
    file = tmp_path / STATE_FILE
    assert write_port(file, 41233, exclusive=True)
    assert not write_port(file, 50000, exclusive=True)
    assert read_port(file) == 41233
    assert [p.name for p in tmp_path.iterdir()] == [STATE_FILE]  # whole or not at all, nothing left beside it


# ------------------------------------------------------------------------------------- as the window uses it


def test_spawn_finds_the_server_without_blocking_and_check_ready_says_when(state: Path, harnesses) -> None:
    h = make(harnesses, state)
    h.server.spawn()
    wait_for(h.server.check_ready)
    assert h.server.url == "http://127.0.0.1:8765"


def test_check_ready_raises_what_went_wrong(state: Path, harnesses) -> None:
    h = make(harnesses, state, start_fails=ServerStartError("boom"))
    h.server.spawn()
    with pytest.raises(ServerStartError, match="boom"):
        wait_for(h.server.check_ready)


# ------------------------------------------------------------------------------------------------- presence


def test_keeps_a_presence_connection_and_lets_go_of_it_not_of_the_server(state: Path, harnesses) -> None:
    h = make(harnesses, state)
    h.server.start()
    wait_for(lambda: len(h.sockets) == 1)
    assert h.connected == ["ws://127.0.0.1:8765/api/presence"]
    h.server.stop()
    assert h.sockets[0].closed
    assert len(h.starts) == 1  # closing a window does not stop the server


def test_starts_the_server_again_on_the_same_port_when_it_has_gone(state: Path, harnesses) -> None:
    h = make(harnesses, state, answers=[NONE, NONE, NONE])
    h.server.start()
    wait_for(lambda: len(h.sockets) == 1)
    h.sockets[0].drop()  # the server stopped
    wait_for(lambda: len(h.starts) == 2 and len(h.sockets) == 2)
    assert h.starts[1][1] == h.starts[0][1]


def test_connects_again_without_starting_anything_when_the_server_is_still_there(state: Path, harnesses) -> None:
    h = make(harnesses, state, answers=[NONE, OURS])
    h.server.start()
    wait_for(lambda: len(h.sockets) == 1)
    h.sockets[0].drop()
    wait_for(lambda: len(h.sockets) == 2)
    assert len(h.starts) == 1


# ------------------------------------------------------------------------------------------- the real pieces


def test_the_state_file_reads_nothing_from_a_missing_broken_or_silly_file(tmp_path: Path) -> None:
    file = tmp_path / STATE_FILE
    assert read_port(file) is None
    file.write_text('{"port": 41233}')
    assert read_port(file) == 41233
    for bad in [
        "",
        "x",
        "[]",
        '{"port": "41233"}',
        '{"port": 0}',
        '{"port": 70000}',
        '{"port": 1.5}',
        '{"port": true}',
    ]:
        file.write_text(bad)
        assert read_port(file) is None, bad


def test_the_state_file_is_overwritten_on_request_and_its_folder_made(tmp_path: Path) -> None:
    file = tmp_path / "a" / "b" / STATE_FILE
    assert write_port(file, 41233, exclusive=False)
    assert write_port(file, 50000, exclusive=False)
    assert read_port(file) == 50000


def test_a_port_is_not_free_while_something_listens_on_it() -> None:
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        port = held.getsockname()[1]
        assert not is_port_free(port)
    assert is_port_free(port)


class _Answering:
    """An HTTP server on loopback that answers every GET with ``status`` and ``body``."""

    def __init__(self, status: int, body: str) -> None:
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 (the standard library's name)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body.encode())

            def log_message(self, *_args: object) -> None: ...

        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (
            200,
            '{"ok": true, "apps": ["composes", "creates"], "version": "0.32.0"}',
            OURS.__class__("claudia", ("composes", "creates"), "0.32.0"),
        ),
        (200, '{"ok": true, "apps": ["composes"]}', Health("claudia", ("composes",), None)),
        (200, '{"ok": true}', Health("other")),  # a server from before D444 has no apps
        (200, "<html>", Health("other")),
        (500, '{"ok": true, "apps": []}', Health("other")),
    ],
)
def test_probe_health_knows_a_claudia_server_by_its_answer(status: int, body: str, expected: Health) -> None:
    answering = _Answering(status, body)
    try:
        assert probe_health(answering.url) == expected
    finally:
        answering.close()


def test_probe_health_says_none_when_nobody_answers() -> None:
    answering = _Answering(200, "{}")
    url = answering.url
    answering.close()
    assert probe_health(url) == Health("none")


class _PresenceServer:
    """A WebSocket server that accepts one connection, pings it, and closes it when told to; it records the pong."""

    def __init__(self) -> None:
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.url = f"ws://127.0.0.1:{self.listener.getsockname()[1]}/api/presence"
        self.pong = threading.Event()
        self.path = ""
        self.connection: socket.socket | None = None
        self.accepted = threading.Event()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        connection, _ = self.listener.accept()
        self.connection = connection
        head = b""
        while b"\r\n\r\n" not in head:
            head += connection.recv(1024)
        lines = head.decode().split("\r\n")
        self.path = lines[0].split()[1]
        key = next(line.split(":", 1)[1].strip() for line in lines if line.lower().startswith("sec-websocket-key"))
        accept = base64.b64encode(hashlib.sha1((key + desktop_server._GUID).encode()).digest()).decode()  # noqa: S324
        connection.sendall(
            f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n".encode()
        )
        connection.sendall(bytes([0x89, 4]) + b"ping")  # a ping, unmasked as from a server
        self.accepted.set()
        first = connection.recv(2)
        if first and first[0] & 0x0F == 0xA:
            length = first[1] & 0x7F
            mask = connection.recv(4)
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(connection.recv(length)))
            if payload == b"ping":
                self.pong.set()

    def end(self) -> None:
        assert self.connection is not None
        self.connection.sendall(bytes([0x88, 2]) + (1001).to_bytes(2, "big"))
        self.connection.close()
        self.listener.close()


def _wait_then_set(socket_: desktop_server._WebSocket, done: threading.Event) -> None:
    socket_.wait_closed()
    done.set()


def test_the_presence_socket_answers_pings_and_notices_the_end() -> None:
    server = _PresenceServer()
    socket_ = desktop_server._WebSocket(server.url)
    done = threading.Event()
    threading.Thread(target=_wait_then_set, args=(socket_, done), daemon=True).start()
    assert server.pong.wait(5), "the ping was not answered"
    assert server.path == "/api/presence"
    assert not done.is_set()
    server.end()
    assert done.wait(5)


def test_closing_the_presence_socket_ends_the_wait() -> None:
    server = _PresenceServer()
    socket_ = desktop_server._WebSocket(server.url)
    done = threading.Event()
    threading.Thread(target=_wait_then_set, args=(socket_, done), daemon=True).start()
    server.accepted.wait(5)
    socket_.close()
    assert done.wait(5)
